from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    time: float = Field(ge=0)
    amount: float = Field(ge=0, le=1e12)
    account: str | None = Field(default=None, max_length=256)
    card: str | None = Field(default=None, max_length=256)
    device: str | None = Field(default=None, max_length=256)
    address: str | None = Field(default=None, max_length=256)
    merchant: str | None = Field(default=None, max_length=256)


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Event] = Field(min_length=1, max_length=500)


class CaseChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["investigating", "escalated", "dismissed", "confirmed"] = "investigating"
    note: str = Field(min_length=1, max_length=4000)


class AlertScore(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    score: float = Field(ge=0, le=1)
    baseline_score: float = Field(ge=0, le=1)
    graph_score: float = Field(ge=0, le=1)
    model_version: str
    cutoff: float
    confidence: str
    amount: float
    time: float
    model: str
    dataset: str
    status: str
    entity_types: list[str]


class NoteRecord(BaseModel):
    text: str
    actor: str
    time: str


class QueueSummary(BaseModel):
    open: int
    high_risk: int
    flagged_value: float


class AlertQueue(BaseModel):
    schema_version: str
    total: int
    items: list[AlertScore]
    summary: QueueSummary


class CaseRecord(BaseModel):
    id: str
    alert_id: str
    owner: str
    status: str
    notes: list[NoteRecord]
    updated: str
    revision: int


class AlertDetail(AlertScore):
    case: CaseRecord | None
    notice: str


class EvidenceNode(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    type: Literal["transaction", "account", "card", "device", "address", "merchant"]
    label: str
    focal: bool


class EvidenceEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    time: float
    provenance: str
    rule: str


class EvidenceGraph(BaseModel):
    schema_version: str
    cutoff: float
    nodes: list[EvidenceNode]
    edges: list[EvidenceEdge]
    patterns: list[str]
    truncated: bool
    historical_transactions: int
    attribution: str


class CaseList(BaseModel):
    items: list[CaseRecord]
