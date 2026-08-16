"""
Relationship memory — register attached to a person.

"You always use আপনি with Rahul's father." Tie a register, a vocative and a
language to a contact, and the second conversation with them needs no
configuration at all (blueprint 13.2 #6).

Nobody else has this, and not because it is hard. It only becomes *buildable*
once register is a first-class object with a stable representation — which is
precisely what this project makes it. A product that treats politeness as an
emergent property of the translation has nothing to attach to a contact.

Privacy: this data never leaves the device. It is a local SQLite file, there is
no sync, and there is deliberately no export endpoint. Who you are deferential
to is about as sensitive as a contact list gets.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from register import AUTO, coerce_level, level_name, level_slug
from utils.helpers import PROJECT_ROOT

__all__ = ["Relationship", "RelationshipBook", "RELATIONSHIPS_PATH"]

RELATIONSHIPS_PATH = PROJECT_ROOT / "data" / "relationships.sqlite3"


@dataclass
class Relationship:
    """What we remember about speaking to one person."""

    name: str
    language: str = ""
    register: Optional[int] = None
    addressee: Optional[str] = None
    note: str = ""
    uses: int = 0
    updated_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "language": self.language,
            "register": self.register,
            "register_name": level_name(self.register) if self.register is not None else None,
            "register_slug": level_slug(self.register) if self.register is not None else None,
            "addressee": self.addressee,
            "note": self.note,
            "uses": self.uses,
            "updated_at": self.updated_at,
        }


class RelationshipBook:
    """
    Local, on-device store of per-contact register preferences.

    Degrades to a no-op when the database cannot be opened, for the same reason
    the phrasebook does: a cache is an optimisation, not a dependency, and a
    read-only data directory must not take the app down.
    """

    def __init__(self, path: Path = RELATIONSHIPS_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._broken = False

    def _connect(self) -> Optional[sqlite3.Connection]:
        if self._conn is not None:
            return self._conn
        if self._broken:
            return None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relationships (
                    name       TEXT PRIMARY KEY,
                    language   TEXT NOT NULL DEFAULT '',
                    register   INTEGER,
                    addressee  TEXT,
                    note       TEXT NOT NULL DEFAULT '',
                    uses       INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()
            self._conn = conn
            return conn
        except (sqlite3.Error, OSError, ValueError):
            self._broken = True
            return None

    # ------------------------------------------------------------------

    def remember(
        self,
        name: str,
        *,
        language: str = "",
        register=None,
        addressee: Optional[str] = None,
        note: str = "",
    ) -> Optional[Relationship]:
        """
        Record or update what we know about a contact.

        Only supplied fields are overwritten, so setting a vocative later does
        not wipe the register learned earlier.
        """
        key = _normalise_name(name)
        if not key:
            return None

        conn = self._connect()
        if conn is None:
            return None

        level = None
        if register is not None and register != AUTO:
            try:
                level = coerce_level(register)
            except ValueError:
                level = None

        existing = self.recall(key)
        merged = Relationship(
            name=key,
            language=language or (existing.language if existing else ""),
            register=level if level is not None else (existing.register if existing else None),
            addressee=addressee or (existing.addressee if existing else None),
            note=note or (existing.note if existing else ""),
            uses=(existing.uses if existing else 0),
            updated_at=time.time(),
        )

        try:
            with self._lock:
                conn.execute(
                    "INSERT OR REPLACE INTO relationships "
                    "(name, language, register, addressee, note, uses, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (merged.name, merged.language, merged.register, merged.addressee,
                     merged.note, merged.uses, merged.updated_at),
                )
                conn.commit()
        except sqlite3.Error:
            return None
        return merged

    def recall(self, name: str) -> Optional[Relationship]:
        """What we know about a contact, or None."""
        key = _normalise_name(name)
        conn = self._connect()
        if conn is None or not key:
            return None
        try:
            with self._lock:
                row = conn.execute(
                    "SELECT name, language, register, addressee, note, uses, updated_at "
                    "FROM relationships WHERE name = ?",
                    (key,),
                ).fetchone()
        except sqlite3.Error:
            return None
        return _row_to_relationship(row) if row else None

    def use(self, name: str) -> Optional[Relationship]:
        """Recall a contact and count the use, for 'most recent' ordering."""
        found = self.recall(name)
        if found is None:
            return None
        conn = self._connect()
        if conn is not None:
            try:
                with self._lock:
                    conn.execute(
                        "UPDATE relationships SET uses = uses + 1, updated_at = ? "
                        "WHERE name = ?",
                        (time.time(), found.name),
                    )
                    conn.commit()
            except sqlite3.Error:
                pass
            found.uses += 1
        return found

    def forget(self, name: str) -> bool:
        """Delete a contact. There must always be a way to remove this data."""
        key = _normalise_name(name)
        conn = self._connect()
        if conn is None or not key:
            return False
        try:
            with self._lock:
                cursor = conn.execute("DELETE FROM relationships WHERE name = ?", (key,))
                conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def all(self) -> List[Relationship]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            with self._lock:
                rows = conn.execute(
                    "SELECT name, language, register, addressee, note, uses, updated_at "
                    "FROM relationships ORDER BY updated_at DESC"
                ).fetchall()
        except sqlite3.Error:
            return []
        return [_row_to_relationship(row) for row in rows]

    def stats(self) -> Dict[str, int]:
        return {"contacts": len(self.all())}


def _row_to_relationship(row) -> Relationship:
    return Relationship(
        name=row[0],
        language=row[1] or "",
        register=row[2],
        addressee=row[3],
        note=row[4] or "",
        uses=int(row[5] or 0),
        updated_at=float(row[6] or 0.0),
    )


def _normalise_name(name) -> str:
    if not isinstance(name, str):
        return ""
    return " ".join(name.split()).strip().lower()
