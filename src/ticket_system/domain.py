from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
import unicodedata

from .errors import ValidationError


class Status(str, Enum):
    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Category(str, Enum):
    UNCLASSIFIED = "unclassified"
    ACCOUNT_ACCESS = "account_access"
    SOFTWARE = "software"
    NETWORK = "network"
    HARDWARE = "hardware"
    FACILITIES = "facilities"
    OTHER = "other"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    MODIFIED = "modified"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class CreateTicket:
    title: str
    description: str
    submitter: str
    priority: Priority | str = Priority.P2


@dataclass(frozen=True)
class Ticket:
    id: int
    public_id: str
    title: str
    description: str
    submitter: str
    status: Status
    category: Category
    priority: Priority
    version: int
    fingerprint: str
    created_at: str
    updated_at: str
    seed_key: str | None = None


@dataclass(frozen=True)
class AIRecommendation:
    category: Category
    priority: Priority
    summary: str
    reason: str


@dataclass(frozen=True)
class Suggestion:
    id: int
    ticket_id: int
    model: str
    prompt_version: str
    original_category: Category | None
    original_priority: Priority | None
    summary: str | None
    reason: str | None
    raw_response: str | None
    status: SuggestionStatus
    created_at: str
    final_category: Category | None = None
    final_priority: Priority | None = None
    reviewer: str | None = None
    reviewed_at: str | None = None
    failure_code: str | None = None


ALLOWED_TRANSITIONS = {
    Status.NEW: {Status.TRIAGED},
    Status.TRIAGED: {Status.IN_PROGRESS},
    Status.IN_PROGRESS: {Status.RESOLVED},
    Status.RESOLVED: {Status.IN_PROGRESS, Status.CLOSED},
    Status.CLOSED: set(),
}


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def _validate_length(value: str, field: str, maximum: int) -> None:
    if not value:
        raise ValidationError(f"{field}不能为空")
    if len(value) > maximum:
        raise ValidationError(f"{field}长度必须在 1 到 {maximum} 个字符之间")


def validate_create(data: CreateTicket) -> CreateTicket:
    title = _normalize_text(data.title)
    description = _normalize_text(data.description)
    submitter = _normalize_text(data.submitter)
    _validate_length(title, "标题", 120)
    _validate_length(description, "描述", 4000)
    _validate_length(submitter, "提交人", 80)
    try:
        priority = Priority(data.priority)
    except ValueError as error:
        raise ValidationError("优先级必须是 P0、P1、P2 或 P3") from error
    return CreateTicket(title, description, submitter, priority)


def _fingerprint_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def ticket_fingerprint(data: CreateTicket) -> str:
    payload = [
        _fingerprint_text(data.submitter),
        _fingerprint_text(data.title),
        _fingerprint_text(data.description),
    ]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def ensure_transition(current: Status, target: Status) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValidationError(f"不允许状态从 {current.value} 变更为 {target.value}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
