from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryEvent:
    event_id: int | None
    timestamp: str
    source_event_id: int
    action: str
    category: str
    summary: str
    project_root: str | None
    path: str | None
    command: str | None
    tool: str | None
    risk_tier: str
    success: bool
    blocked: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryEntity:
    entity_id: str
    entity_type: str
    name: str
    path: str | None
    first_seen: str
    last_seen: str
    counters: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TimelineEntry:
    timestamp: str
    title: str
    description: str
    category: str
    related_entities: list[str]
    source_event_id: int


@dataclass(frozen=True)
class RecallResult:
    query: str
    matched_entries: list[TimelineEntry]
    matched_entities: list[MemoryEntity]
    summary: str
    source_info: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryStatus:
    indexed_event_count: int
    entity_count: int
    timeline_count: int
    last_indexed_audit_event: int
    schema_version: str

