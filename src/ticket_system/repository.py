from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import sqlite3

from .database import immediate_transaction
from .domain import Category, CreateTicket, Priority, Status, Ticket, ensure_transition
from .errors import DuplicateTicketError, ConflictError, NotFoundError


@dataclass(frozen=True)
class AuditEvent:
    id: int
    ticket_id: int
    event_type: str
    actor: str | None
    payload: dict
    created_at: str


def _value(value):
    return value.value if isinstance(value, Enum) else value


def _ticket(row: sqlite3.Row) -> Ticket:
    return Ticket(
        id=row["id"],
        public_id=row["public_id"],
        title=row["title"],
        description=row["description"],
        submitter=row["submitter"],
        status=Status(row["status"]),
        category=Category(row["category"]),
        priority=Priority(row["priority"]),
        version=row["version"],
        fingerprint=row["fingerprint"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        seed_key=row["seed_key"],
    )


class TicketRepository:
    _filter_columns = {
        "status": "status",
        "category": "category",
        "priority": "priority",
        "submitter": "submitter",
        "fingerprint": "fingerprint",
    }

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create(
        self,
        data: CreateTicket,
        now: str,
        fingerprint: str,
        seed_key: str | None = None,
        duplicate_cutoff: str | None = None,
    ) -> Ticket:
        day = now[:10].replace("-", "")
        with immediate_transaction(self.connection):
            if duplicate_cutoff is not None:
                duplicate = self.find_recent_duplicate(fingerprint, duplicate_cutoff)
                if duplicate is not None:
                    raise DuplicateTicketError(duplicate.public_id)
            sequence = self.connection.execute(
                """
                INSERT INTO ticket_sequences(day, value) VALUES (?, 1)
                ON CONFLICT(day) DO UPDATE SET value = value + 1
                RETURNING value
                """,
                (day,),
            ).fetchone()[0]
            public_id = f"TKT-{day}-{sequence:04d}"
            cursor = self.connection.execute(
                """
                INSERT INTO tickets(
                    public_id, title, description, submitter, status, category,
                    priority, version, fingerprint, created_at, updated_at, seed_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    public_id,
                    data.title,
                    data.description,
                    data.submitter,
                    Status.NEW.value,
                    Category.UNCLASSIFIED.value,
                    _value(data.priority),
                    1,
                    fingerprint,
                    now,
                    now,
                    seed_key,
                ),
            )
            ticket_id = cursor.lastrowid
            self.connection.execute(
                "INSERT INTO audit_events(ticket_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (ticket_id, "ticket_created", "{}", now),
            )
            return _ticket(self.connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())

    def get(self, public_id: str) -> Ticket:
        row = self.connection.execute(
            "SELECT * FROM tickets WHERE public_id = ?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"工单不存在：{public_id}")
        return _ticket(row)

    def list(self, filters: dict | None = None) -> list[Ticket]:
        filters = filters or {}
        clauses = []
        parameters = []
        for key, value in filters.items():
            column = self._filter_columns.get(key)
            if column is None:
                raise ValueError(f"不支持的筛选字段：{key}")
            clauses.append(f"{column} = ?")
            parameters.append(_value(value))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(
            f"SELECT * FROM tickets{where} ORDER BY created_at DESC, id DESC", parameters
        ).fetchall()
        return [_ticket(row) for row in rows]

    def find_recent_duplicate(self, fingerprint: str, cutoff: str) -> Ticket | None:
        row = self.connection.execute(
            "SELECT * FROM tickets WHERE fingerprint = ? AND created_at >= ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (fingerprint, cutoff),
        ).fetchone()
        return None if row is None else _ticket(row)

    def update_status_if_version(
        self,
        public_id: str,
        target: Status,
        actor: str,
        expected_version: int,
        now: str,
    ) -> Ticket:
        with immediate_transaction(self.connection):
            current = self.get(public_id)
            target = Status(_value(target))
            ensure_transition(current.status, target)
            new_version = expected_version + 1
            updated = self.connection.execute(
                "UPDATE tickets SET status = ?, version = version + 1, updated_at = ? WHERE id = ? AND version = ?",
                (target.value, now, current.id, expected_version),
            )
            if updated.rowcount != 1:
                raise ConflictError("工单版本冲突，请刷新后重试")
            payload = json.dumps(
                {
                    "actor": actor,
                    "from": current.status.value,
                    "to": target.value,
                    "old_version": expected_version,
                    "new_version": new_version,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            self.connection.execute(
                "INSERT INTO audit_events(ticket_id, event_type, actor, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (current.id, "status_changed", actor, payload, now),
            )
            return self.get(public_id)

    def history(self, public_id: str) -> list[AuditEvent]:
        ticket = self.get(public_id)
        rows = self.connection.execute(
            "SELECT * FROM audit_events WHERE ticket_id = ? ORDER BY created_at ASC, id ASC",
            (ticket.id,),
        ).fetchall()
        return [
            AuditEvent(
                id=row["id"],
                ticket_id=row["ticket_id"],
                event_type=row["event_type"],
                actor=row["actor"],
                payload=json.loads(row["payload"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
