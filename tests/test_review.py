import os
import tempfile
import unittest

from ticket_system.database import connect_database, initialize_database
from ticket_system.domain import AIRecommendation, Category, CreateTicket, Priority, SuggestionStatus
from ticket_system.errors import ConflictError, ValidationError
from ticket_system.repository import TicketRepository
from ticket_system.review import ReviewService
from ticket_system.service import TicketService


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.connection = connect_database(os.path.join(self.tempdir.name, "tickets.db"))
        initialize_database(self.connection)
        self.repository = TicketRepository(self.connection)
        self.ticket = TicketService(self.repository).create(CreateTicket("打印机", "缺墨", "alice"))
        self.review = ReviewService(self.repository)

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def suggestion(self, *, status="pending"):
        return self.repository.save_ai_suggestion(
            self.ticket,
            model="demo",
            prompt_version="hardened",
            now="2026-08-09T01:00:00+00:00",
            status=status,
            recommendation=AIRecommendation(Category.HARDWARE, Priority.P2, "摘要", "理由") if status == "pending" else None,
            raw_response="raw" if status == "pending" else None,
            failure_code="provider_error" if status == "failed" else None,
        )

    def test_confirm_applies_original_recommendation_and_triages(self):
        suggestion = self.suggestion()
        reviewed, ticket = self.review.review(suggestion.id, "confirm", "bob")
        self.assertEqual(reviewed.status, SuggestionStatus.CONFIRMED)
        self.assertEqual((ticket.category, ticket.priority, ticket.status.value), (Category.HARDWARE, Priority.P2, "triaged"))

    def test_modify_preserves_original_and_changes_final(self):
        suggestion = self.suggestion()
        reviewed, ticket = self.review.review(suggestion.id, "modify", "bob", Category.FACILITIES, Priority.P3)
        self.assertEqual(reviewed.status, SuggestionStatus.MODIFIED)
        self.assertEqual((reviewed.original_category, reviewed.final_category), (Category.HARDWARE, Category.FACILITIES))
        self.assertEqual((ticket.category, ticket.priority), (Category.FACILITIES, Priority.P3))

    def test_reject_leaves_ticket_unclassified(self):
        suggestion = self.suggestion()
        reviewed, ticket = self.review.review(suggestion.id, "reject", "bob")
        self.assertEqual(reviewed.status, SuggestionStatus.REJECTED)
        self.assertEqual(ticket.category.value, "unclassified")

    def test_invalid_and_repeated_reviews_are_rejected(self):
        suggestion = self.suggestion()
        with self.assertRaises(ValidationError):
            self.review.review(suggestion.id, "confirm", "")
        with self.assertRaises(ValidationError):
            self.review.review(suggestion.id, "modify", "bob", Category.FACILITIES)
        self.review.review(suggestion.id, "confirm", "bob")
        with self.assertRaises(ConflictError):
            self.review.review(suggestion.id, "confirm", "carol")
        self.assertEqual(len(self.repository.history(self.ticket.public_id)), 3)

    def test_failed_suggestion_cannot_be_reviewed(self):
        failed = self.suggestion(status="failed")
        with self.assertRaises(ConflictError):
            self.review.review(failed.id, "confirm", "bob")


if __name__ == "__main__":
    unittest.main()
