from __future__ import annotations

from pathlib import Path

from aos.memory.store import DEFAULT_MEMORY_DB_PATH, list_entities, list_memory_events, list_timeline
from aos.memory.types import MemoryEvent, MemoryEntity, TimelineEntry


def get_recent_activity(limit: int = 20, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[TimelineEntry]:
    return list_timeline(db_path=db_path, limit=limit)


def get_activity_by_day(day: str, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[TimelineEntry]:
    return [entry for entry in list_timeline(db_path=db_path, limit=None) if entry.timestamp.startswith(day)]


def get_file_activity(path: str, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[MemoryEvent]:
    return [event for event in list_memory_events(db_path=db_path, limit=None, category="file") if event.path == path]


def get_recent_files(limit: int = 20, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[MemoryEntity]:
    return list_entities(db_path=db_path, entity_type="File", limit=limit)


def get_command_history(limit: int = 20, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[MemoryEvent]:
    return [event for event in list_memory_events(db_path=db_path, limit=None, category="command") if event.command][:limit]


def get_blocked_events(limit: int = 20, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[MemoryEvent]:
    return [event for event in list_memory_events(db_path=db_path, limit=None) if event.blocked][:limit]


def get_failed_commands(limit: int = 20, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> list[MemoryEvent]:
    failed: list[MemoryEvent] = []
    for event in list_memory_events(db_path=db_path, limit=None, category="command"):
        return_code = event.metadata.get("return_code")
        if event.blocked or not event.success or return_code not in (None, 0):
            failed.append(event)
    return failed[:limit]
