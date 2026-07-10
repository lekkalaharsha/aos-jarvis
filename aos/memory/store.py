from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from aos.config.loader import DATA_DIR
from aos.memory.entities import json_dumps
from aos.memory.types import MemoryEntity, MemoryEvent, MemoryStatus, TimelineEntry

MEMORY_DIR = DATA_DIR / "memory"
DEFAULT_MEMORY_DB_PATH = MEMORY_DIR / "memory.db"
SCHEMA_VERSION = "phase4_v1"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_memory_store(db_path: Path = DEFAULT_MEMORY_DB_PATH) -> Path:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_event_id INTEGER NOT NULL UNIQUE,
                action TEXT NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL,
                project_root TEXT,
                path TEXT,
                command TEXT,
                tool TEXT,
                risk_tier TEXT NOT NULL,
                success INTEGER NOT NULL,
                blocked INTEGER NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                path TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                counters_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS timeline_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                related_entities_json TEXT NOT NULL,
                source_event_id INTEGER NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_search USING fts5(
                    source_event_id UNINDEXED,
                    kind,
                    text
                )
                """
            )
            search_mode = "fts5"
        except sqlite3.OperationalError:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_search (
                    source_event_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            search_mode = "plain"
        conn.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('last_indexed_audit_event', '0')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES ('search_mode', ?)",
            (search_mode,),
        )
        conn.commit()
    return db_path


def reset_memory_store(db_path: Path = DEFAULT_MEMORY_DB_PATH) -> Path:
    with _connect(db_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS memory_events;
            DROP TABLE IF EXISTS entities;
            DROP TABLE IF EXISTS timeline_entries;
            DROP TABLE IF EXISTS metadata;
            DROP TABLE IF EXISTS memory_search;
            """
        )
        conn.commit()
    return init_memory_store(db_path)


def set_metadata(key: str, value: str, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> None:
    init_memory_store(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def get_metadata(key: str, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> str | None:
    init_memory_store(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def add_memory_event(event: MemoryEvent, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> int:
    init_memory_store(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO memory_events
            (timestamp, source_event_id, action, category, summary, project_root, path, command, tool, risk_tier, success, blocked, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.timestamp,
                event.source_event_id,
                event.action,
                event.category,
                event.summary,
                event.project_root,
                event.path,
                event.command,
                event.tool,
                event.risk_tier,
                int(event.success),
                int(event.blocked),
                json_dumps(event.metadata),
            ),
        )
        if cursor.rowcount:
            conn.execute(
                "INSERT INTO memory_search(source_event_id, kind, text) VALUES (?, 'event', ?)",
                (event.source_event_id, " ".join(part for part in [event.summary, event.path or "", event.command or ""] if part)),
            )
        conn.commit()
        return int(cursor.lastrowid or 0)


def list_memory_events(
    *,
    db_path: Path = DEFAULT_MEMORY_DB_PATH,
    limit: int | None = None,
    category: str | None = None,
) -> list[MemoryEvent]:
    init_memory_store(db_path)
    query = "SELECT * FROM memory_events"
    params: list[object] = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY source_event_id DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        MemoryEvent(
            event_id=row["id"],
            timestamp=row["timestamp"],
            source_event_id=row["source_event_id"],
            action=row["action"],
            category=row["category"],
            summary=row["summary"],
            project_root=row["project_root"],
            path=row["path"],
            command=row["command"],
            tool=row["tool"],
            risk_tier=row["risk_tier"],
            success=bool(row["success"]),
            blocked=bool(row["blocked"]),
            metadata=json.loads(row["metadata_json"]),
        )
        for row in rows
    ]


def upsert_entity(entity: MemoryEntity, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> None:
    init_memory_store(db_path)
    with _connect(db_path) as conn:
        existing = conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity.entity_id,)).fetchone()
        if existing:
            existing_counters = json.loads(existing["counters_json"])
            for key, value in entity.counters.items():
                existing_counters[key] = int(existing_counters.get(key, 0)) + int(value)
            merged_metadata = json.loads(existing["metadata_json"])
            merged_metadata.update(entity.metadata)
            conn.execute(
                """
                UPDATE entities
                SET last_seen = ?, counters_json = ?, metadata_json = ?, path = COALESCE(?, path)
                WHERE entity_id = ?
                """,
                (
                    max(existing["last_seen"], entity.last_seen),
                    json_dumps(existing_counters),
                    json_dumps(merged_metadata),
                    entity.path,
                    entity.entity_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO entities(entity_id, entity_type, name, path, first_seen, last_seen, counters_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity.entity_id,
                    entity.entity_type,
                    entity.name,
                    entity.path,
                    entity.first_seen,
                    entity.last_seen,
                    json_dumps(entity.counters),
                    json_dumps(entity.metadata),
                ),
            )
        conn.commit()


def list_entities(
    *,
    db_path: Path = DEFAULT_MEMORY_DB_PATH,
    entity_type: str | None = None,
    limit: int | None = None,
) -> list[MemoryEntity]:
    init_memory_store(db_path)
    query = "SELECT * FROM entities"
    params: list[object] = []
    if entity_type:
        query += " WHERE entity_type = ?"
        params.append(entity_type)
    query += " ORDER BY last_seen DESC, name ASC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        MemoryEntity(
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            name=row["name"],
            path=row["path"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            counters=json.loads(row["counters_json"]),
            metadata=json.loads(row["metadata_json"]),
        )
        for row in rows
    ]


def add_timeline_entry(entry: TimelineEntry, *, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> int:
    init_memory_store(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO timeline_entries(timestamp, title, description, category, related_entities_json, source_event_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry.timestamp,
                entry.title,
                entry.description,
                entry.category,
                json.dumps(entry.related_entities, sort_keys=True),
                entry.source_event_id,
            ),
        )
        if cursor.rowcount:
            conn.execute(
                "INSERT INTO memory_search(source_event_id, kind, text) VALUES (?, 'timeline', ?)",
                (entry.source_event_id, " ".join([entry.title, entry.description, entry.category])),
            )
        conn.commit()
        return int(cursor.lastrowid or 0)


def list_timeline(
    *,
    db_path: Path = DEFAULT_MEMORY_DB_PATH,
    limit: int | None = None,
    category: str | None = None,
) -> list[TimelineEntry]:
    init_memory_store(db_path)
    query = "SELECT * FROM timeline_entries"
    params: list[object] = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY source_event_id DESC"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        TimelineEntry(
            timestamp=row["timestamp"],
            title=row["title"],
            description=row["description"],
            category=row["category"],
            related_entities=json.loads(row["related_entities_json"]),
            source_event_id=row["source_event_id"],
        )
        for row in rows
    ]


def search_memory_text(query: str, *, db_path: Path = DEFAULT_MEMORY_DB_PATH, limit: int = 10) -> list[int]:
    init_memory_store(db_path)
    search_mode = get_metadata("search_mode", db_path=db_path) or "plain"
    with _connect(db_path) as conn:
        try:
            if search_mode == "fts5":
                rows = conn.execute(
                    "SELECT source_event_id FROM memory_search WHERE memory_search MATCH ? LIMIT ?",
                    (query, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT source_event_id FROM memory_search WHERE text LIKE ? LIMIT ?",
                    (f"%{query}%", limit),
                ).fetchall()
        except sqlite3.OperationalError:
            if search_mode != "fts5":
                return []
            rows = conn.execute(
                "SELECT source_event_id FROM memory_search WHERE text LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
    return [int(row["source_event_id"]) for row in rows]


def get_memory_status(*, db_path: Path = DEFAULT_MEMORY_DB_PATH) -> MemoryStatus:
    init_memory_store(db_path)
    with _connect(db_path) as conn:
        event_count = int(conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0])
        entity_count = int(conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0])
        timeline_count = int(conn.execute("SELECT COUNT(*) FROM timeline_entries").fetchone()[0])
    return MemoryStatus(
        indexed_event_count=event_count,
        entity_count=entity_count,
        timeline_count=timeline_count,
        last_indexed_audit_event=int(get_metadata("last_indexed_audit_event", db_path=db_path) or 0),
        schema_version=get_metadata("schema_version", db_path=db_path) or SCHEMA_VERSION,
    )
