"""Tier B: EarthDial-4B-MS + our LoRA adapter writes the prose.

WHAT THIS DOES
    Tier C narrates from templates. Tier B hands the same kernel-computed facts,
    plus any retrieved corpus chunks, to a fine-tuned language model and lets it
    compose the sentence. The numbers are identical either way -- only the
    wording changes.

THE INVARIANT IS UNCHANGED
    The model never measures. It receives facts the kernel already computed and
    rephrases them. Every string it returns goes through validator.py, which
    rejects any numeral the kernel did not produce. That guard was written for
    exactly this tier:

        "the safety net for Tiers A and B, where an LLM writes the prose and
         WILL invent a plausible figure"

    So a model hallucinating "2,400 hectares" cannot reach the user: the
    narration is withheld and the measured value shown instead.

WHICH HALF OF THE MODEL WRITES, AND WHY
    Measured on this machine, same prompt, one loaded model:

        with adapter    -> 'yes'
        without adapter -> 'Otsu thresholding is a technique in image
                            processing that separates the image into two
                            parts, one of which is the background.'

    That is not a bug. Our adapter was trained on 31,781 rows whose targets
    were 100.0% single words -- yes/no and a/b/c/d, zero multi-word answers --
    with loss on the answer only. It emits one classification token and stops,
    exactly as taught. Asking it for prose asks for the capability the
    fine-tune removed.

    So the two jobs are split across the same weights:

        narration and corpus answers  -> adapter DISABLED (base EarthDial)
        yes-no and MCQ classification -> adapter ENABLED (our 60.1% fine-tune)

    peft's disable_adapter() is a context manager, so this costs no extra VRAM
    and no second load.

WHY THE MODEL IS LOADED THIS WAY
    Our adapter was trained with EarthDial's own `wrap_llm_lora`, which targets
    the Phi-3 language half only -- the vision tower was frozen and the training
    was text-only. The adapter file proves it: 256 tensors across decoder layers
    0-31, zero vision tensors. So the adapter attaches to `model.language_model`
    rather than the full InternVLChatModel.

    The full EarthDial model is still what gets loaded, because that is what we
    fine-tuned and what the architecture claim rests on. The vision tower simply
    is not invoked on a text-only prompt.

QUANTISATION IS NOT OPTIONAL, AND 8-BIT NOT 4-BIT
    EarthDial-4B is 4.35B parameters. At bf16 that is 8.70 GB of weights against
    an RTX 4060 Laptop's 8.59 GB -- it does not fit, before activations.

    8-bit is the default rather than 4-bit because 4-bit MEASURABLY FAULTS on
    this card. torch 2.5.1+cu121 ships kernels for sm_50..sm_90 but skips sm_89,
    which is exactly the 4060's capability, so it runs via PTX JIT -- and
    bitsandbytes' NF4 kernels raise `CUDA error: misaligned address` on the
    first forward pass under that path. 8-bit loads and generates cleanly at
    4.26 GB. Measured, both ways, on this machine.

    Set SATQUERY_4BIT=1 to force NF4 anyway (fine on sm_80/sm_86/sm_90 cards,
    ~2.2 GB); SATQUERY_BF16=1 skips quantisation entirely on a big card.

    Accuracy under quantisation was NOT measured during training -- the 60.1%
    figure is bf16 on a datacentre card -- so treat Tier B prose quality as
    unverified until someone checks it.

FAILURE IS NOT AN OPTION AT DEMO TIME
    Every failure path here degrades to Tier C rather than raising: no GPU, no
    torch, missing weights, OOM mid-generation, a malformed adapter. A tier that
    takes the whole product down when a driver is stale is worse than templates.
    `load_error` records why, and /health can report it.
"""

from __future__ import annotations

import os
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Overridable so the demo machine and a GPU box can point elsewhere without
# editing code.
BASE_DIR = pathlib.Path(os.environ.get(
    "SATQUERY_BASE_MODEL", ROOT / "models" / "EarthDial_4B_MS"))
ADAPTER_DIR = pathlib.Path(os.environ.get(
    "SATQUERY_ADAPTER", ROOT / "models" / "lora_adapter"))
EARTHDIAL_SRC = pathlib.Path(os.environ.get(
    "SATQUERY_EARTHDIAL_SRC", ROOT / "models" / "EarthDial" / "src"))

# 8-bit by default: 4-bit NF4 faults on sm_89 (see the module docstring).
LOAD_IN_4BIT = os.environ.get("SATQUERY_4BIT", "0") != "0"
LOAD_IN_8BIT = (os.environ.get("SATQUERY_BF16", "0") == "0"
                and not LOAD_IN_4BIT)

# 72, down from 160. Corpus answers measured 3.79-4.07 s per call, which is
# the slowest thing a user waits on; the answers themselves come back at ~122
# characters, roughly 30 tokens. The cap was never the limit on length -- the
# model stops at <|end|> long before it -- but it does bound the worst case
# when generation rambles, and a token is ~25 ms here.
MAX_NEW_TOKENS = int(os.environ.get("SATQUERY_MAX_NEW_TOKENS", "72"))

# One model per process, loaded on first use rather than at import: importing
# backend.app must not cost 8 GB of VRAM in a process that only serves /health.
_lock = threading.Lock()
_model = None
_tokenizer = None
load_error: str | None = None
gen_error: str | None = None
_load_attempted = False


def available() -> bool:
    """True when generation can be attempted. Does not trigger a load."""
    return BASE_DIR.exists() and ADAPTER_DIR.exists() and load_error is None


def status() -> dict:
    """Reportable state, for /health. Never raises."""
    return {
        "tier_b_loaded": _model is not None,
        "load_attempted": _load_attempted,
        "load_error": load_error,
        "gen_error": gen_error,
        "base_model_present": BASE_DIR.exists(),
        "adapter_present": ADAPTER_DIR.exists(),
        "quantisation": ("4bit" if LOAD_IN_4BIT
                         else "8bit" if LOAD_IN_8BIT else "bf16"),
    }


def _load():
    """Load EarthDial + adapter once. Sets `load_error` instead of raising."""
    global _model, _tokenizer, load_error, _load_attempted
    if _model is not None or load_error is not None:
        return
    _load_attempted = True

    try:
        import sys

        import torch
        from transformers import AutoTokenizer

        # EarthDial's vendored Phi-3 calls Cache.get_usable_length, which
        # transformers renamed to get_seq_length. Their code targets 4.37;
        # this runs on 4.56. Restore the alias rather than pinning
        # transformers back to a version with no wheel for this Python.
        # Call sites: modeling_phi3.py lines 371, 489, 779, 1101.
        from transformers.cache_utils import DynamicCache as _DC
        if not hasattr(_DC, "get_usable_length"):
            _DC.get_usable_length = (
                lambda self, new_seq_length=None, layer_idx=0:
                self.get_seq_length(layer_idx))

        if not BASE_DIR.exists():
            raise FileNotFoundError(f"base model not at {BASE_DIR}")
        if not (ADAPTER_DIR / "adapter_config.json").exists():
            raise FileNotFoundError(f"adapter not at {ADAPTER_DIR}")

        # EarthDial's modeling code is imported directly rather than through
        # trust_remote_code. Its files do absolute imports of their own package
        # and a relative flash-attention import; transformers' remote-code
        # loader flat-copies them into a cache directory where neither resolves.
        if EARTHDIAL_SRC.exists() and str(EARTHDIAL_SRC) not in sys.path:
            sys.path.insert(0, str(EARTHDIAL_SRC))

        from earthdial.model.internvl_chat.configuration_internvl_chat import (
            InternVLChatConfig,
        )
        from earthdial.model.internvl_chat.modeling_internvl_chat import (
            InternVLChatModel,
        )

        tok = AutoTokenizer.from_pretrained(
            str(BASE_DIR), trust_remote_code=True, use_fast=False)

        cfg = InternVLChatConfig.from_pretrained(str(BASE_DIR))
        cfg.vision_config.use_flash_attn = False        # not installed, not needed
        if hasattr(cfg.llm_config, "attn_implementation"):
            cfg.llm_config.attn_implementation = "eager"

        kw = dict(config=cfg, low_cpu_mem_usage=True)
        if LOAD_IN_4BIT or LOAD_IN_8BIT:
            from transformers import BitsAndBytesConfig
            if LOAD_IN_4BIT:
                kw["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )
            else:
                kw["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            kw["device_map"] = {"": 0}

        try:
            m = InternVLChatModel.from_pretrained(
                str(BASE_DIR), dtype=torch.bfloat16, **kw)
        except TypeError:
            # `dtype` is 5.x; older transformers wants `torch_dtype`.
            m = InternVLChatModel.from_pretrained(
                str(BASE_DIR), torch_dtype=torch.bfloat16, **kw)
        m.eval()
        if not (LOAD_IN_4BIT or LOAD_IN_8BIT):
            m = m.cuda()

        # The adapter targets the language half only -- 256 tensors over decoder
        # layers 0-31, no vision tensors -- so it attaches there, not to the
        # wrapper.
        from peft import PeftModel
        m.language_model = PeftModel.from_pretrained(
            m.language_model, str(ADAPTER_DIR), is_trainable=False)
        m.language_model.eval()

        _model, _tokenizer = m, tok
    except Exception as e:                        # noqa: BLE001 - see docstring
        load_error = f"{type(e).__name__}: {e}"
        _model = _tokenizer = None


def _generate(prompt: str, max_new_tokens: int = MAX_NEW_TOKENS) -> str:
    """Greedy decode. Returns "" on any failure so the caller falls back.

    Written by hand because EarthDial vendors Phi3ForCausalLM as a plain
    nn.Module with no GenerationMixin, so there is no .generate() on the
    language model, and the wrapper's own .generate() expects pixel_values we
    deliberately do not pass.
    """
    import torch

    llm = _model.language_model
    eos = _tokenizer.convert_tokens_to_ids("<|end|>")
    if not isinstance(eos, int) or eos < 0:
        eos = _tokenizer.eos_token_id
    pad = _tokenizer.pad_token_id
    if pad is None:
        pad = eos

    ids = _tokenizer(prompt, return_tensors="pt").input_ids
    ids = ids.to(next(llm.parameters()).device)

    out_ids: list[int] = []
    with torch.no_grad():
        step, past = ids, None
        for _ in range(max_new_tokens):
            o = llm(input_ids=step, past_key_values=past, use_cache=True)
            past = o.past_key_values
            nxt = int(o.logits[:, -1, :].argmax(-1))
            if nxt in (eos, pad):
                break
            out_ids.append(nxt)
            step = torch.tensor([[nxt]], device=ids.device)

    return _tokenizer.decode(out_ids, skip_special_tokens=True).strip()


def _safe_generate(prompt: str, max_new_tokens: int = MAX_NEW_TOKENS,
                   use_adapter: bool = False) -> str:
    """Generate, or record why not and return "" so the caller falls back.

    `gen_error` is separate from `load_error`: a model that loaded and then
    faulted mid-generation is a different problem from a model that was never
    installed, and conflating them cost two debugging cycles on a CUDA
    misaligned-address fault that looked exactly like "no weights present".
    """
    global gen_error
    try:
        llm = _model.language_model
        if use_adapter or not hasattr(llm, "disable_adapter"):
            out = _generate(prompt, max_new_tokens)
        else:
            # Prose needs the base weights; the adapter answers in one token.
            with llm.disable_adapter():
                out = _generate(prompt, max_new_tokens)
        gen_error = None
        return out
    except Exception as e:                        # noqa: BLE001
        gen_error = f"{type(e).__name__}: {e}"
        return ""


def _facts_block(facts: dict) -> str:
    """Kernel facts as flat lines. Only what the kernel computed goes in."""
    keep = ("hectares", "pct", "delta_ha", "a_ha", "b_ha", "a_date", "b_date",
            "index", "thr", "px", "label", "sens_low_ha", "sens_high_ha")
    lines = []
    for k in keep:
        if k in facts and facts[k] is not None:
            v = facts[k]
            lines.append(f"- {k}: {v:,.2f}" if isinstance(v, float)
                         else f"- {k}: {v}")
    return "\n".join(lines)


def narrate_measurement(intent: str, facts: dict, scene_label: str,
                        lang: str = "en") -> str:
    """Rewrite kernel facts as prose. "" means the caller should use Tier C.

    The prompt forbids inventing numbers, but that instruction is not the
    safeguard -- validator.py is. This only reduces how often the guard fires.
    """
    _load()
    if _model is None:
        return ""

    block = _facts_block(facts)
    if not block:
        return ""

    # One worked example, then the values. The previous version was only
    # prohibitions and the model stopped composing -- it echoed the intent
    # name back ('Flood_extent'). Demonstrating the target shape works far
    # better on a 4B model than listing what not to do.
    #
    # The rules that remain address the measured failure: given water in the
    # Kosi basin it wrote "The water in the left of the image is in the sea."
    # -- an inland flood called sea, plus a spatial claim from nothing.
    # validator.validate_narration is what actually blocks that; the prompt
    # only makes it rarer.
    example = (
        "Values: hectares: 1,204.50 | pct: 4.20 | label: built-up area\n"
        "Answer: Built-up area covers 1,204.50 hectares, 4.20% of the scene."
    )
    prompt = (
        "<|user|>\n"
        "Turn measured values into one sentence of plain English.\n\n"
        "You have no image. Only the numbers below, counted by a program.\n\n"
        f"{example}\n\n"
        "Rules: use only the numbers given; never say where something sits "
        "in the frame; never name a waterbody or landmark type.\n\n"
        f"Language code: {lang}\n"
        f"Scene: {scene_label}\n"
        f"Values: {block}\n"
        "Answer:"
        "<|end|>\n<|assistant|>\n"
    )
    # Adapter off: this path needs sentences. See the module docstring.
    return _safe_generate(prompt, use_adapter=False)


def answer_from_corpus(query: str, citations: list[dict],
                       lang: str = "en") -> str:
    """Answer a methodology question from retrieved chunks. "" to fall back.

    Retrieval finds the chunks; this composes an answer from them. The previous
    behaviour pasted the top chunk verbatim, which reads as a document dump
    rather than an answer.

    Numbers appearing in a retrieved document are NOT kernel facts, so the
    caller must validate this text against an empty fact set: a formula's
    constants are fine in prose about a method, but a measurement is not.
    """
    _load()
    if _model is None or not citations:
        return ""

    ctx = "\n\n".join(
        # Two chunks at 700 chars, not three at 1200. Prompt length
        # dominates this path: measured 5.52 s at three full chunks
        # against 1.88 s at one, because ~757 tokens of context cost far
        # more than the ~30 tokens the model then writes. Two keeps a
        # corroborating source while landing the answer near 3 s.
        #
        # Cutting MAX_NEW_TOKENS first was the wrong lever: the model
        # stops at <|end|> well before any cap, so the cap never bound.
        f"[{i + 1}] {c.get('title', '')}\n{(c.get('text') or c.get('excerpt') or '')[:700]}"
        for i, c in enumerate(citations[:2])
    )
    prompt = (
        "<|user|>\n"
        "Answer the question using ONLY the reference material below.\n\n"
        "RULES:\n"
        "- If the references do not answer it, say so plainly.\n"
        "- Do not invent numbers, dates, or citations.\n"
        "- Three sentences at most.\n"
        f"- Write in this language code: {lang}\n\n"
        f"References:\n{ctx}\n\n"
        f"Question: {query}\n"
        "<|end|>\n<|assistant|>\n"
    )
    return _safe_generate(prompt, use_adapter=False)


def classify(question: str, options: str = "") -> str:
    """Answer a yes/no or multiple-choice question with the FINE-TUNED model.

    This is what the adapter is for, and the only path that enables it.
    Measured on the BigEarthNet.txt bench split: 60.1% overall, binary
    69.9% against a 50.5% majority baseline, MCQ 48.4% against 26.7%.

    Returns a bare token ("yes", "no", "a".."d"), or "" when unavailable.
    Nothing here reaches a measurement: the kernel owns every number.
    """
    _load()
    if _model is None:
        return ""
    body = question if not options else question + " " + options
    prompt = (
        "<|user|>\n[s2_ms_10] [classify] " + body
        + "<|end|>\n<|assistant|>\n"
    )
    # 8 tokens is generous: every training target was a single word.
    return _safe_generate(prompt, max_new_tokens=8, use_adapter=True)


def _demo() -> None:
    """Runnable check. Passes without a GPU: absence must degrade, not crash."""
    st = status()
    assert set(st) >= {"tier_b_loaded", "load_error", "base_model_present"}, st
    assert isinstance(available(), bool)

    # _facts_block must pass through only kernel-computed keys.
    got = _facts_block({"hectares": 2603.12, "label": "water",
                        "invented": 999, "nothing": None})
    assert "2,603.12" in got and "water" in got, got
    assert "999" not in got, "a non-kernel key leaked into the prompt"
    assert "nothing" not in got, "a None value leaked into the prompt"

    # The degrade path is the claim worth checking: absence must return ""
    # rather than raise. Only assert it when the model genuinely cannot load --
    # `_model` is None here because _demo() never calls _load(), so testing it
    # would load 8 GB of weights and then assert they produced nothing.
    if not (BASE_DIR.exists() and ADAPTER_DIR.exists()):
        assert narrate_measurement("flood_extent", {"hectares": 1.0}, "s") == ""
        assert answer_from_corpus("what is otsu", [{"title": "t", "text": "x"}]) == ""
        assert classify("is there water?") == ""

    print("tier_b: ok")
    print(f"  base model present : {st['base_model_present']}  ({BASE_DIR})")
    print(f"  adapter present    : {st['adapter_present']}  ({ADAPTER_DIR})")
    print(f"  quantisation       : {st['quantisation']}")
    print(f"  load error         : {st['load_error']}")
    print("  prose: adapter disabled | classification: adapter enabled")
    print("  degrades to Tier C when unavailable")


if __name__ == "__main__":
    _demo()
