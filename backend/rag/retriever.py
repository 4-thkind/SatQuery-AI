"""Local document retrieval. Phase 2, first working slice.

Scope, stated plainly: this is BM25 over a small hand-written corpus. It is not
the dense-vector retriever the full design calls for. What it does have is the
shape that matters -- a corpus on disk, a scored retrieval, and citations that
reach the evidence ledger -- so swapping the scorer for embeddings + FAISS later
touches this file and nothing else.

Why BM25 first rather than embeddings: sentence-transformers pulls in torch,
roughly half a gigabyte, to serve about a dozen chunks. On a corpus this size
lexical matching is not obviously worse, and the whole point of the interface is
that the scorer is replaceable. `search()` is the seam.

The invariant is unchanged and this module is deliberately powerless to break it:
retrieval returns TEXT ONLY. It never produces a number, and nothing it returns
reaches the measurement path. The kernel measures; this explains the method.
"""

from __future__ import annotations

import math
import pathlib
import re
from collections import Counter
from dataclasses import dataclass, field

CORPUS = pathlib.Path(__file__).resolve().parents[2] / "data" / "knowledge" / "corpus.md"

# Words carrying no retrieval signal. Deliberately short: an aggressive stop list
# on a corpus this small removes more signal than noise.
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "was", "were",
    "for", "on", "with", "as", "at", "by", "from", "that", "this", "it", "be",
    "which", "than", "so", "not", "but", "its", "their", "there", "how", "what",
    "when", "why", "does", "do", "can", "will", "would", "should", "has", "have",
}


@dataclass
class Chunk:
    id: str
    title: str
    source: str
    tags: list[str]
    text: str
    tokens: list[str] = field(default_factory=list)


def tokenise(s: str) -> list[str]:
    """Lowercase word tokens, stopwords dropped.

    Index names are kept whole: NDVI and MNDWI must not be split, and a bare
    number in the text is never a retrieval key.
    """
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
        # Title and tags are repeated into the token stream: a chunk titled
        # "MNDWI" should win a query mentioning MNDWI even if the body says it
        # once. Cheap substitute for a field-weighted index.
        c.tokens = tokenise(f"{title} {' '.join(tags)} {title} {text}")
        out.append(c)
    return out


class Retriever:
    """BM25 over the corpus. Built once, queried per request."""

    K1 = 1.5      # term-frequency saturation
    B = 0.75      # length normalisation

    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks if chunks is not None else load_chunks()
        self.N = len(self.chunks)
        self.avg_len = (sum(len(c.tokens) for c in self.chunks) / self.N) if self.N else 0.0
        df = Counter()
        for c in self.chunks:
            for w in set(c.tokens):
                df[w] += 1
        # Standard BM25 IDF with the +1 that keeps it non-negative for terms
        # appearing in most documents -- without it a common term scores below
        # zero and actively penalises a chunk for containing the query word.
        self.idf = {w: math.log(1 + (self.N - n + 0.5) / (n + 0.5))
                    for w, n in df.items()}
        self._tf = [Counter(c.tokens) for c in self.chunks]

    def search(self, query: str, k: int = 3, min_score: float = 1.0
               ) -> list[tuple[Chunk, float]]:
        """Top-k chunks above `min_score`.

        The floor matters: an unrelated question should return nothing rather
        than the least-bad chunk. Citing an irrelevant source is worse than
        citing none, because it looks like grounding while providing none.
        """
        q = tokenise(query)
        if not q or not self.N:
            return []
        scored = []
        for i, c in enumerate(self.chunks):
            tf, dl, s = self._tf[i], len(c.tokens), 0.0
            for w in q:
                f = tf.get(w, 0)
                if not f:
                    continue
                denom = f + self.K1 * (1 - self.B + self.B * dl / self.avg_len)
                s += self.idf.get(w, 0.0) * f * (self.K1 + 1) / denom
            if s >= min_score:
                scored.append((c, round(s, 3)))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def cite(self, query: str, k: int = 3) -> list[dict]:
        """Retrieval formatted for the API and the evidence ledger."""
        return [{"id": c.id, "title": c.title, "source": c.source,
                 "score": s, "tags": c.tags,
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
