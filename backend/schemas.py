"""Pydantic contracts shared by every layer. Spec section 11.

These are the wire format. If a field is here, the frontend may rely on it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Verdict = Literal["ANSWER", "DEGRADE", "ABSTAIN"]
Tier = Literal["A", "B", "C"]


class ToolResult(BaseModel):
    """Return type of every kernel tool, without exception.

    `provenance` must contain enough to recompute `value` from the source raster
    with no other information. That is what makes the ledger real rather than
    decorative.
    """
    ok: bool
    value: float | int | dict | None = None
    unit: str | None = None
    mask_handle: str | None = None
    caveats: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)


class FeasibilityVerdict(BaseModel):
    verdict: Verdict
    intent: str
    prior: float                      # 0..1, feeds the confidence product
    required_bands: list[str] = Field(default_factory=list)
    present_bands: list[str] = Field(default_factory=list)
    missing_bands: list[str] = Field(default_factory=list)
    using_proxy: bool = False
    cloud_fraction: float = 0.0
    reason: str = ""                  # shown verbatim on an ABSTAIN card
    recommendation: str = ""          # "use Sentinel-1 SAR", etc.


class PlanStep(BaseModel):
    id: str                           # "s1", "s2", ... referenced as $s1.field
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolPlan(BaseModel):
    intent: str
    steps: list[PlanStep]
    rationale: str = ""


class EvidenceRecord(BaseModel):
    """One row of the ledger. One per tool execution."""
    step_id: str
    tool: str
    params: dict = Field(default_factory=dict)
    ok: bool = True
    value: Any = None
    unit: str | None = None
    arithmetic: str | None = None     # the human-readable computation
    reproduce: str | None = None      # recipe to recompute from source
    caveats: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    upstream: list[str] = Field(default_factory=list)   # step ids feeding this
    duration_ms: float = 0.0


class Confidence(BaseModel):
    """Product of measurable components. Never a vibe."""
    score: float
    band: Literal["High", "Medium", "Low"]
    components: dict[str, float]
    explanation: str = ""


class SceneRef(BaseModel):
    id: str
    label: str
    sensor: str
    acquired: str
    place: str
    bands: list[str]
    width: int
    height: int
    crs: str
    pixel_area_m2: float
    bounds_wgs84: list[float]
    preview_false: str | None = None
    preview_natural: str | None = None
    synthetic: bool = False
    pair: str | None = None
    description: str = ""
    ground_truth: dict = Field(default_factory=dict)


class AnswerPayload(BaseModel):
    """What the frontend renders."""
    query: str
    intent: str
    verdict: Verdict
    narration: str
    headline: dict | None = None       # {"value": 2603.17, "unit": "hectares", ...}
    scene_ids: list[str] = Field(default_factory=list)
    feasibility: FeasibilityVerdict | None = None
    confidence: Confidence | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    layers: dict[str, str] = Field(default_factory=dict)   # name -> mask handle
    tier: Tier = "C"
    plan: ToolPlan | None = None
    corroboration: dict | None = None
    # Language the question was asked in, and the narration written in. The UI
    # shows the label so a user can see the system understood which language
    # they used, rather than guessing from the reply.
    language: str = "en"
    language_label: str = "English"
    # Retrieved method references (Phase 2, BM25 over a local corpus). Citations
    # only -- retrieval never contributes a measured value.
    citations: list[dict] = Field(default_factory=list)
    # The deterministic kernel facts used to construct the answer and validate numerals.
    facts: dict = Field(default_factory=dict)
    duration_ms: float = 0.0


class QueryRequest(BaseModel):
    query: str
    scene_id: str
    scene_id_b: str | None = None      # second epoch for change detection
    session_id: str | None = None


class TranslateRequest(BaseModel):
    target_lang: str = "en"
    target_language: str | None = None
    intent: str = ""
    verdict: str = "OK"
    scene_label: str = ""
    scene_id: str | None = None
    facts: dict = Field(default_factory=dict)
    confidence: Confidence | None = None
    citations: list[dict] = Field(default_factory=list)
    original_narration: str = ""
    turn_id: str | None = None

