from __future__ import annotations

from .domain import Category, CreateTicket, Priority, Status, ticket_fingerprint, utc_now, validate_create
from .errors import ValidationError
from .repository import AuditEvent, TicketRepository
from .seed import SAMPLE_TICKETS


class TicketService:
    def __init__(self, repository: TicketRepository):
        self.repository = repository

    def create(self, data: CreateTicket, *, seed_key: str | None = None):
        validated = validate_create(data)
        return self.repository.create(
            validated,
            utc_now(),
            ticket_fingerprint(validated),
            seed_key,
        )

    def list(self, filters: dict | None = None):
        return self.repository.list(self._normalize_filters(filters))

    def show(self, public_id: str):
        return self.repository.get(public_id)

    def change_status(self, public_id: str, target: Status | str, actor: str):
        actor = actor.strip()
        if not actor:
            raise ValidationError("操作人不能为空")
        try:
            target_status = Status(target)
        except ValueError as error:
            raise ValidationError("状态无效") from error
        return self.repository.set_status(public_id, target_status, actor, utc_now())

    def seed(self) -> dict[str, int]:
        created = 0
        existing = 0
        for sample in SAMPLE_TICKETS:
            row = self.repository.connection.execute(
                "SELECT public_id FROM tickets WHERE seed_key = ?", (sample.key,)
            ).fetchone()
            if row is not None:
                existing += 1
                continue

            ticket = self.create(
                CreateTicket(
                    sample.title,
                    sample.description,
                    sample.submitter,
                    sample.priority,
                ),
                seed_key=sample.key,
            )
            self.repository.connection.execute(
                "UPDATE tickets SET category = ? WHERE id = ?",
                (sample.category.value, ticket.id),
            )
            for next_status in _status_path(sample.status):
                self.change_status(ticket.public_id, next_status, "seed")
            created += 1
        return {"created": created, "existing": existing}

    def history(self, public_id: str) -> list[AuditEvent]:
        return self.repository.history(public_id)

    @staticmethod
    def _normalize_filters(filters: dict | None) -> dict:
        if not filters:
            return {}
        normalized = dict(filters)
        for name, enum_type, message in (
            ("status", Status, "状态无效"),
            ("category", Category, "分类无效"),
            ("priority", Priority, "优先级必须是 P0、P1、P2 或 P3"),
        ):
            if name not in normalized:
                continue
            try:
                normalized[name] = enum_type(normalized[name])
            except ValueError as error:
                raise ValidationError(message) from error
        return normalized


def _status_path(target: Status) -> tuple[Status, ...]:
    paths = {
        Status.NEW: (),
        Status.TRIAGED: (Status.TRIAGED,),
        Status.IN_PROGRESS: (Status.TRIAGED, Status.IN_PROGRESS),
        Status.RESOLVED: (Status.TRIAGED, Status.IN_PROGRESS, Status.RESOLVED),
        Status.CLOSED: (Status.TRIAGED, Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED),
    }
    return paths[target]
