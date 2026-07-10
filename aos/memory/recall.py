from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from aos.memory.entities import redact_text
from aos.memory.store import DEFAULT_MEMORY_DB_PATH, list_memory_events, list_timeline, search_memory_text
from aos.memory.timeline import (
    get_activity_by_day,
    get_blocked_events,
    get_command_history,
    get_failed_commands,
    get_recent_activity,
)
from aos.memory.types import RecallResult
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event

SUPPORTED_RECALLS = (
    "what did I work on recently",
    "what did I edit today",
    "what files changed",
    "what commands did I run",
    "what failed recently",
    "show blocked actions",
    "show project timeline",
)

CHANGED_FILE_ACTIONS = {"fs.write.apply", "fs.edit.apply", "snapshot.restore"}


def _summarize_entries(entries) -> str:
    if not entries:
        return "No matching memory entries were found."
    return "\n".join(f"{entry.timestamp} {entry.title}: {entry.description}" for entry in entries[:10])


def recall(query: str, limit: int = 10, *, db_path: Path = DEFAULT_MEMORY_DB_PATH, audit_path: Path = DEFAULT_AUDIT_PATH) -> RecallResult:
    lowered = query.strip().lower()
    entries = []
    entities = []
    if "work on recently" in lowered or "recent activity" in lowered:
        entries = get_recent_activity(limit=limit, db_path=db_path)
        summary = _summarize_entries(entries)
    elif "edit today" in lowered or "edited today" in lowered:
        today = datetime.now(timezone.utc).date().isoformat()
        entries = [
            entry
            for entry in get_activity_by_day(today, db_path=db_path)
            if entry.category == "file" and entry.title in CHANGED_FILE_ACTIONS
        ][:limit]
        summary = _summarize_entries(entries)
    elif "files changed" in lowered:
        changed_events = [
            event for event in list_memory_events(db_path=db_path, limit=None, category="file") if event.action in CHANGED_FILE_ACTIONS and event.path
        ]
        seen_paths: set[str] = set()
        changed_paths: list[tuple[str, str]] = []
        for event in changed_events:
            if event.path in seen_paths:
                continue
            seen_paths.add(event.path)
            changed_paths.append((event.path, event.timestamp))
            if len(changed_paths) >= limit:
                break
        summary = "\n".join(f"{Path(path).name} last changed {timestamp}" for path, timestamp in changed_paths) or "No changed files were recorded."
    elif "commands did i run" in lowered or "command history" in lowered:
        command_events = get_command_history(limit=limit, db_path=db_path)
        summary = "\n".join(f"{event.timestamp} {event.command}" for event in command_events) or "No commands were recorded."
    elif "failed recently" in lowered:
        failed = get_failed_commands(limit=limit, db_path=db_path)
        summary = ("Failed activity:\n" + "\n".join(f"{event.timestamp} {event.summary}" for event in failed)) if failed else "No recent failures were recorded."
    elif "blocked actions" in lowered:
        blocked = get_blocked_events(limit=limit, db_path=db_path)
        summary = ("Blocked activity:\n" + "\n".join(f"{event.timestamp} {event.summary}" for event in blocked)) if blocked else "No blocked actions were recorded."
    elif "project timeline" in lowered or lowered == "timeline":
        entries = list_timeline(db_path=db_path, limit=limit)
        summary = _summarize_entries(entries)
    else:
        ids = search_memory_text(redact_text(query) or query, db_path=db_path, limit=limit)
        if ids:
            entries = [entry for entry in list_timeline(db_path=db_path, limit=None) if entry.source_event_id in ids][:limit]
            summary = _summarize_entries(entries)
        else:
            summary = "Supported recall queries: " + ", ".join(SUPPORTED_RECALLS)
    result = RecallResult(
        query=query,
        matched_entries=entries,
        matched_entities=entities,
        summary=summary,
        source_info={
            "matched_entry_ids": [entry.source_event_id for entry in entries],
            "matched_entity_ids": [entity.entity_id for entity in entities],
        },
    )
    append_event(
        audit_path,
        actor="memory",
        event_type="memory.recall",
        action="memory.recall",
        resource=str(db_path),
        risk_tier="T0",
        status="ALLOW",
        payload={
            "query": redact_text(query),
            "result_count": len(entries) + len(entities),
            "success": True,
        },
    )
    return result
