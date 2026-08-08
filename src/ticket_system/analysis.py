from __future__ import annotations

from .ai_client import OpenAICompatibleClient
from .domain import utc_now
from .errors import AIUnavailableError
from .repository import TicketRepository


class AnalysisService:
    def __init__(self, repository: TicketRepository, client: OpenAICompatibleClient):
        self.repository = repository
        self.client = client

    def analyze(self, public_id: str, prompt_version: str = "hardened"):
        ticket = self.repository.get(public_id)
        now = utc_now()
        try:
            recommendation, raw_response = self.client.analyze(ticket, prompt_version)
        except AIUnavailableError as error:
            self.repository.save_ai_suggestion(
                ticket,
                model=getattr(getattr(self.client, "config", None), "model", "unknown"),
                prompt_version=prompt_version,
                now=now,
                status="failed",
                failure_code=error.code,
            )
            raise
        return self.repository.save_ai_suggestion(
            ticket,
            model=getattr(getattr(self.client, "config", None), "model", "unknown"),
            prompt_version=prompt_version,
            now=now,
            status="pending",
            recommendation=recommendation,
            raw_response=raw_response,
        )
