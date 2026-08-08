import os
import tempfile
import unittest

from ticket_system.analysis import AnalysisService
from ticket_system.database import connect_database, initialize_database
from ticket_system.domain import CreateTicket, SuggestionStatus
from ticket_system.errors import AIUnavailableError
from ticket_system.repository import TicketRepository
from ticket_system.service import TicketService


class _GoodClient:
    def analyze(self, ticket, prompt_version):
        from ticket_system.domain import AIRecommendation, Category, Priority
        return AIRecommendation(Category.HARDWARE, Priority.P2, "摘要", "理由"), "raw-model"


class _BadClient:
    def analyze(self, ticket, prompt_version):
        raise AIUnavailableError("provider_error", "模型暂不可用")


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.connection = connect_database(os.path.join(self.tempdir.name, "tickets.db"))
        initialize_database(self.connection)
        self.repository = TicketRepository(self.connection)
        self.ticket = TicketService(self.repository).create(CreateTicket("打印机", "缺墨", "alice"))

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def test_success_saves_pending_without_mutating_ticket(self):
        suggestion = AnalysisService(self.repository, _GoodClient()).analyze(self.ticket.public_id, "hardened")
        self.assertEqual(suggestion.status, SuggestionStatus.PENDING)
        current = self.repository.get(self.ticket.public_id)
        self.assertEqual((current.category.value, current.priority.value, current.status.value), ("unclassified", "P2", "new"))

    def test_failure_saves_failed_suggestion_and_reraises(self):
        with self.assertRaises(AIUnavailableError):
            AnalysisService(self.repository, _BadClient()).analyze(self.ticket.public_id, "baseline")
        row = self.connection.execute("SELECT status, failure_code FROM ai_suggestions").fetchone()
        self.assertEqual((row["status"], row["failure_code"]), ("failed", "provider_error"))


if __name__ == "__main__":
    unittest.main()
