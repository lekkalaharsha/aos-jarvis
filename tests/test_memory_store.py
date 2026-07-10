from aos.memory.store import (
    add_memory_event,
    add_timeline_entry,
    get_memory_status,
    init_memory_store,
    list_entities,
    list_memory_events,
    list_timeline,
    upsert_entity,
)
from aos.memory.types import MemoryEntity, MemoryEvent, TimelineEntry


def test_memory_store_initializes(tmp_path):
    db_path = tmp_path / "memory.db"
    init_memory_store(db_path)
    status = get_memory_status(db_path=db_path)

    assert status.indexed_event_count == 0
    assert status.entity_count == 0
    assert status.timeline_count == 0


def test_add_and_list_memory_events(tmp_path):
    db_path = tmp_path / "memory.db"
    add_memory_event(
        MemoryEvent(None, "2026-01-01T00:00:00+00:00", 1, "fs.read", "file", "read file", str(tmp_path), "README.md", None, "fs.read", "T0", True, False, {}),
        db_path=db_path,
    )

    events = list_memory_events(db_path=db_path)
    assert len(events) == 1
    assert events[0].summary == "read file"


def test_upsert_and_list_entities(tmp_path):
    db_path = tmp_path / "memory.db"
    upsert_entity(
        MemoryEntity("File:README.md", "File", "README.md", "README.md", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", {"seen": 1}, {}),
        db_path=db_path,
    )
    upsert_entity(
        MemoryEntity("File:README.md", "File", "README.md", "README.md", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00", {"seen": 1}, {}),
        db_path=db_path,
    )

    entities = list_entities(db_path=db_path, entity_type="File")
    assert len(entities) == 1
    assert entities[0].counters["seen"] == 2


def test_add_and_list_timeline_entries(tmp_path):
    db_path = tmp_path / "memory.db"
    add_timeline_entry(
        TimelineEntry("2026-01-01T00:00:00+00:00", "fs.read", "read file", "file", ["File:README.md"], 1),
        db_path=db_path,
    )

    entries = list_timeline(db_path=db_path)
    assert len(entries) == 1
    assert entries[0].title == "fs.read"


def test_status_reports_counts(tmp_path):
    db_path = tmp_path / "memory.db"
    add_memory_event(
        MemoryEvent(None, "2026-01-01T00:00:00+00:00", 1, "fs.read", "file", "read file", str(tmp_path), "README.md", None, "fs.read", "T0", True, False, {}),
        db_path=db_path,
    )
    upsert_entity(
        MemoryEntity("File:README.md", "File", "README.md", "README.md", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", {"seen": 1}, {}),
        db_path=db_path,
    )
    add_timeline_entry(
        TimelineEntry("2026-01-01T00:00:00+00:00", "fs.read", "read file", "file", ["File:README.md"], 1),
        db_path=db_path,
    )

    status = get_memory_status(db_path=db_path)
    assert status.indexed_event_count == 1
    assert status.entity_count == 1
    assert status.timeline_count == 1

