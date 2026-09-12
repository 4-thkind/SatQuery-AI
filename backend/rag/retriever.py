"""Local document retrieval using dense-vector embeddings and FAISS.

Scope: Dense semantic search using sentence-transformers (all-MiniLM-L6-v2)
and FAISS (IndexFlatIP with normalized vectors for cosine similarity) over
the local satellite knowledge corpus.

The public API (search, cite, Chunk dataclass) remains unchanged from the
initial BM25 implementation so that downstream consumers (pipeline, ledger,
FastAPI app) continue to work seamlessly.

The invariant is unchanged and this module is deliberately powerless to break it:
retrieval returns TEXT ONLY. It never produces a number, and nothing it returns
reaches the measurement path. The kernel measures; this explains the method.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
import numpy as np

CORPUS = pathlib.Path(__file__).resolve().parents[2] / "data" / "knowledge" / "corpus.md"


@dataclass
class Chunk:
    id: str
    title: str
    source: str
    tags: list[str]
    text: str
    tokens: list[str] = field(default_factory=list)


STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are",
    "for", "on", "with", "by", "as", "at", "from", "that", "this",
    "it", "be", "was", "were", "how", "what", "why", "does", "do",
}


def tokenise(s: str) -> list[str]:
    """Lowercase word tokens, stop words dropped. Used by the BM25
    fallback; the dense path does not need it."""
    return [w for w in re.findall(r"[a-z0-9]+", s.lower())
            if w not in STOP and len(w) > 1]


def load_chunks(path: pathlib.Path = CORPUS) -> list[Chunk]:
    """Parse the corpus into chunks, split on '## ' headings."""
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    out: list[Chunk] = []
    for block in raw.split("\n## ")[1:]:
        lines = block.strip().split("\n")
        title = lines[0].strip()
        source, tags, body = "", [], []
        for ln in lines[1:]:
            if ln.startswith("source:"):
                source = ln[len("source:"):].strip()
            elif ln.startswith("tags:"):
                tags = [t.strip() for t in ln[len("tags:"):].split(",") if t.strip()]
            else:
                body.append(ln)
        text = "\n".join(body).strip()
        if not text:
            continue
        cid = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
        c = Chunk(id=cid, title=title, source=source, tags=tags, text=text)
        out.append(c)
    return out


class Retriever:
    """Dense semantic retrieval over the corpus using FAISS and sentence-transformers."""

    MODEL_NAME = "all-MiniLM-L6-v2"
    DEFAULT_MIN_SCORE = 0.30  # Cosine similarity threshold for relevance

    def __init__(self, chunks: list[Chunk] | None = None,
                 model_name: str = MODEL_NAME):
        self.chunks = chunks if chunks is not None else load_chunks()
        self.N = len(self.chunks)
        self.model = None
        self.index = None
        self.backend = "bm25"
        # Set when a dense build was attempted and failed; None when dense
        # succeeded or was never possible. Surfaced at /api/v1/health.
        self.fallback_reason: str | None = None

        # Dense retrieval when the stack is installed, BM25 when it is
        # not. Tier C is documented as needing no model weights and no
        # downloads, so the embedding model must not be an import-time
        # requirement of the entire backend: without this fallback,
        # backend.pipeline, backend.ledger and backend.app all fail to
        # import on a machine that only wants templates.
        faiss = None
        SentenceTransformer = None
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
        except ImportError:
            faiss = None

        if faiss is not None and SentenceTransformer is not None and self.N:
            try:
                self.model = SentenceTransformer(model_name)
                corpus_texts = [
                    f"{c.title}\nTags: {', '.join(c.tags)}\n\n{c.text}"
                    for c in self.chunks
                ]
                embeddings = self.model.encode(
                    corpus_texts,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ).astype(np.float32)
                self.index = faiss.IndexFlatIP(embeddings.shape[1])
                self.index.add(embeddings)
                self.backend = "dense"
            except Exception as e:                # noqa: BLE001
                # A cold cache with no network, or a corrupt download, must
                # not take the app down: BM25 still answers.
                #
                # But record WHY. Swallowing this silently meant the badge read
                # "bm25" while every dependency was present and importable,
                # and diagnosing it from outside the process was impossible --
                # several cycles went into theories about interpreters and
                # caches when the answer was one exception away.
                self.model = None
                self.index = None
                self.backend = "bm25"
                self.fallback_reason = f"{type(e).__name__}: {e}"

        if self.backend == "bm25":
            self._build_bm25()

    def _build_bm25(self) -> None:
        """Classic BM25 over the same chunks. No weights, no network."""
        import collections
        import math

        for c in self.chunks:
            c.tokens = tokenise(c.title + " " + " ".join(c.tags)
                                + " " + c.text)
        df = collections.Counter()
        for c in self.chunks:
            for w in set(c.tokens):
                df[w] += 1
        self._avgdl = sum(len(c.tokens) for c in self.chunks) / max(self.N, 1)
        self._idf = {w: math.log(1 + (self.N - d + 0.5) / (d + 0.5))
                     for w, d in df.items()}

    def _search_bm25(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        import collections

        q = tokenise(query)
        if not q:
            return []
        k1, b = 1.5, 0.75
        scored: list[tuple[Chunk, float]] = []
        for c in self.chunks:
            tf = collections.Counter(c.tokens)
            dl = len(c.tokens) or 1
            head = set(tokenise(c.title + " " + " ".join(c.tags)))
            s = 0.0
            for w in q:
                f = tf.get(w, 0)
                if not f:
                    continue
                s += (self._idf.get(w, 0.0) * f * (k1 + 1)
                      / (f + k1 * (1 - b + b * dl / self._avgdl)))
                # A term in the title or tags is what the chunk is ABOUT; the
                # same term buried in prose is a passing mention. Without this
                # the longest chunk that name-drops a term outranks the chunk
                # dedicated to it.
                if w in head:
                    s += 2.0 * self._idf.get(w, 0.0)
            if s > 0:
                scored.append((c, round(s, 3)))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def search(self, query: str, k: int = 3, min_score: float = DEFAULT_MIN_SCORE
               ) -> list[tuple[Chunk, float]]:
        """Top-k chunks above `min_score` using cosine similarity.

        The floor matters: an unrelated question should return nothing rather
        than the least-bad chunk. Citing an irrelevant source is worse than
        citing none, because it looks like grounding while providing none.
        """
        if not query.strip() or not self.N:
            return []
        if self.index is None:
            return [(c, s) for c, s in self._search_bm25(query, k)
                    if s >= 1.0]

        q_emb = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

        k_search = min(k, self.N)
        scores, indices = self.index.search(q_emb, k_search)

        scored: list[tuple[Chunk, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            s = float(score)
            if idx != -1 and s >= min_score:
                scored.append((self.chunks[idx], round(s, 3)))

        return scored

    def cite(self, query: str, k: int = 3) -> list[dict]:
        """Retrieval formatted for the API and the evidence ledger."""
        return [{"id": c.id, "title": c.title, "source": c.source,
                 "score": s, "tags": c.tags,
                 "text": c.text,
                 "excerpt": c.text.split("\n\n")[0][:320]}
                for c, s in self.search(query, k)]


_singleton: Retriever | None = None


def get() -> Retriever:
    """Process-wide retriever. The corpus is small and immutable at runtime."""
    global _singleton
    if _singleton is None:
        _singleton = Retriever()
    return _singleton


def _demo() -> None:
    r = get()
    assert r.N >= 10, f"corpus too small: {r.N} chunks"

    # A question about an index must retrieve that index, not a neighbour.
    top = r.search("what does MNDWI mean")[0][0]
    assert "MNDWI" in top.title, top.title

    top = r.search("why do you need SWIR2 for burn severity")[0][0]
    assert "NBR" in top.title or "Burn" in top.title, top.title

    top = r.search("why can't optical sensors see through clouds")[0][0]
    assert "Cloud" in top.title or "SAR" in top.title, top.title

    # An unrelated question must retrieve NOTHING. Returning the least-bad chunk
    # would look like grounding while supplying none.
    assert r.search("what is the capital of France") == []

    # Every chunk must carry a citation, or a retrieved claim is unattributable.
    for c in r.chunks:
        assert c.source, f"chunk {c.id!r} has no source"

    # Retrieval must never be a route for numbers into an answer. Chunks contain
    # figures as prose; the contract is that nothing here reaches the kernel.
    cites = r.cite("how is flood area measured")
    assert cites and all("excerpt" in x and "source" in x for x in cites)

    print(f"retriever: ok  {r.N} chunks, "
          f"top for 'MNDWI' = {r.search('MNDWI')[0][0].title!r}")


if __name__ == "__main__":
    _demo()
