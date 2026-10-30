from __future__ import annotations

import json
from pathlib import Path

from aos.memory.entities import entity_id_for, redact_command, redact_path, redact_text
from aos.memory.store import (
    DEFAULT_MEMORY_DB_PATH,
    add_memory_event,
    add_timeline_entry,
    get_memory_status,
    init_memory_store,
    reset_memory_store,
    set_metadata,
    upsert_entity,
)
from aos.memory.types import MemoryEntity, MemoryEvent, MemoryStatus, TimelineEntry
from aos.safety.audit import DEFAULT_AUDIT_PATH, append_event, list_events


def _parse_payload(payload_json: str) -> dict:
    try:
        return json.loads(payload_json)
    except json.JSONDecodeError:
        return {}


def _derive_category(event_type: str) -> str:
    if event_type.startswith("fs.") or event_type.startswith("snapshot."):
        return "file"
    if event_type.startswith("run."):
        return "command"
    if event_type.startswith("agent."):
        return "agent"
    if event_type.startswith("memory."):
        return "memory"
    return "audit"


def _derive_summary(event, payload: dict) -> str:
    if event.event_type in {"fs.read", "fs.list", "fs.search"}:
        target = redact_path(payload.get("path") or event.resource)
        return f"{event.event_type} {target}"
    if event.event_type in {"fs.write.apply", "fs.edit.apply", "snapshot.restore"}:
        return f"{event.event_type} {redact_path(payload.get('path') or event.resource)}"
    if event.event_type == "fs.blocked":
        return f"fs.blocked {redact_path(payload.get('path') or event.resource)}"
    if event.event_type == "run.apply":
        return f"ran {redact_command(payload.get('command_original') or payload.get('command') or event.action)}"
    if event.event_type in {"run.blocked", "run.timeout"}:
        return f"{event.event_type} {redact_command(payload.get('command_original') or payload.get('command')) or event.resource}"
    if event.event_type.startswith("agent."):
        return redact_text(payload.get("user_message") or payload.get("reason") or event.action) or event.action
    return redact_text(payload.get("reason") or event.action) or event.action


def _derive_memory_event(event) -> tuple[MemoryEvent, list[MemoryEntity], TimelineEntry] | None:
    if event.event_type.startswith("memory."):
        return None
    payload = _parse_payload(event.payload_json)
    category = _derive_category(event.event_type)
    summary = _derive_summary(event, payload)
    success = event.status == "ALLOW" and not bool(payload.get("timed_out", False))
    blocked = event.status == "DENY" or bool(payload.get("blocked", False))
    path = redact_path(payload.get("path") or (event.resource if category == "file" else None))
    command = redact_command(payload.get("command_original") or payload.get("command"))
    project_root = redact_path(payload.get("cwd") or payload.get("project_root") or event.resource if category in {"command", "agent"} else None)
    tool = payload.get("action") if category in {"command", "file"} else event.event_type
    memory_event = MemoryEvent(
        event_id=None,
        timestamp=event.timestamp,
        source_event_id=event.id,
        action=event.action,
        category=category,
        summary=summary,
        project_root=project_root,
        path=path,
        command=command,
        tool=tool,
        risk_tier=event.risk_tier,
        success=success,
        blocked=blocked,
        metadata={
            "event_type": event.event_type,
            "actor": event.actor,
            "status": event.status,
            "return_code": payload.get("return_code"),
        },
    )

    entities: list[MemoryEntity] = []
    related_entities: list[str] = []
    if project_root and project_root != "[REDACTED_PATH]":
        project_name = Path(project_root).name or project_root
        project_entity = MemoryEntity(
            entity_id=entity_id_for("Project", project_name, project_root),
            entity_type="Project",
            name=project_name,
            path=project_root,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            counters={"seen": 1, "success": int(success), "blocked": int(blocked)},
            metadata={},
        )
        entities.append(project_entity)
        related_entities.append(project_entity.entity_id)
    if path and path != "[REDACTED_PATH]":
        file_entity = MemoryEntity(
            entity_id=entity_id_for("File", Path(path).name, path),
            entity_type="File",
            name=Path(path).name,
            path=path,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            counters={"seen": 1, "success": int(success), "blocked": int(blocked)},
            metadata={"category": category},
        )
        entities.append(file_entity)
        related_entities.append(file_entity.entity_id)
    if command:
        command_entity = MemoryEntity(
            entity_id=entity_id_for("Command", command),
            entity_type="Command",
            name=command,
            path=None,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            counters={"seen": 1, "success": int(success), "blocked": int(blocked)},
            metadata={},
        )
        entities.append(command_entity)
        related_entities.append(command_entity.entity_id)
    if event.event_type.startswith("agent.") and payload.get("user_message"):
        task_name = redact_text(payload["user_message"]) or "agent request"
        task_entity = MemoryEntity(
            entity_id=entity_id_for("Task", task_name),
            entity_type="Task",
            name=task_name,
            path=None,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            counters={"seen": 1, "success": int(success), "blocked": int(blocked)},
            metadata={},
        )
        entities.append(task_entity)
        related_entities.append(task_entity.entity_id)
    if blocked or not success:
        error_name = redact_text(payload.get("error") or summary) or "error"
        error_entity = MemoryEntity(
            entity_id=entity_id_for("Error", error_name),
            entity_type="Error",
            name=error_name,
            path=None,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
            counters={"seen": 1, "success": 0, "blocked": int(blocked)},
            metadata={},
        )
        entities.append(error_entity)
        related_entities.append(error_entity.entity_id)

    timeline = TimelineEntry(
        timestamp=event.timestamp,
        title=event.event_type,
        description=summary,
        category=category,
        related_entities=related_entities,
        source_event_id=event.id,
    )
    return memory_event, entities, timeline


def _index_events(events, *, memory_db_path: Path) -> int:
    indexed = 0
    for event in events:
        derived = _derive_memory_event(event)
        if derived is None:
            continue
        memory_event, entities, timeline = derived
        add_memory_event(memory_event, db_path=memory_db_path)
        for entity in entities:
            upsert_entity(entity, db_path=memory_db_path)
        add_timeline_entry(timeline, db_path=memory_db_path)
        indexed += 1
    return indexed


def rebuild_memory_from_audit(
    *,
    audit_path: Path = DEFAULT_AUDIT_PATH,
    memory_db_path: Path = DEFAULT_MEMORY_DB_PATH,
) -> MemoryStatus:
    reset_memory_store(memory_db_path)
    audit_events = list_events(audit_path)
    indexed_count = _index_events(audit_events, memory_db_path=memory_db_path)
    audit_event = append_event(
        audit_path,
        actor="memory",
        event_type="memory.rebuild",
        action="memory.rebuild",
        resource=str(memory_db_path),
        risk_tier="T0",
        status="ALLOW",
        payload={"indexed_count": indexed_count, "success": True},
    )
    set_metadata("last_indexed_audit_event", str(audit_event.id), db_path=memory_db_path)
    return get_memory_status(db_path=memory_db_path)


def index_new_audit_events(
    *,
    audit_path: Path = DEFAULT_AUDIT_PATH,
    memory_db_path: Path = DEFAULT_MEMORY_DB_PATH,
) -> MemoryStatus:
    init_memory_store(memory_db_path)
    last_indexed = get_memory_status(db_path=memory_db_path).last_indexed_audit_event
    audit_events = [event for event in list_events(audit_path) if event.id > last_indexed]
    indexed_count = _index_events(audit_events, memory_db_path=memory_db_path)
    audit_event = append_event(
        audit_path,
        actor="memory",
        event_type="memory.index",
        action="memory.index",
        resource=str(memory_db_path),
        risk_tier="T0",
        status="ALLOW",
        payload={"indexed_count": indexed_count, "success": True},
    )
    set_metadata("last_indexed_audit_event", str(audit_event.id), db_path=memory_db_path)
    return get_memory_status(db_path=memory_db_path)
