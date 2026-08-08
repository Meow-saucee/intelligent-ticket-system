import unittest

from ticket_system.domain import (
    AIRecommendation,
    Category,
    CreateTicket,
    Priority,
    Status,
    ensure_transition,
    ticket_fingerprint,
    validate_create,
)
from ticket_system.errors import ValidationError


class DomainTests(unittest.TestCase):
    def test_validate_create_trims_and_defaults_priority(self):
        result = validate_create(CreateTicket("  VPN  ", "  无法连接  ", "  alice  "))
        self.assertEqual((result.title, result.description, result.submitter), ("VPN", "无法连接", "alice"))
        self.assertEqual(result.priority, Priority.P2)

    def test_empty_title_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "标题不能为空"):
            validate_create(CreateTicket("   ", "描述", "alice"))

    def test_illegal_priority_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "优先级"):
            validate_create(CreateTicket("标题", "描述", "alice", "P4"))

    def test_fingerprint_normalizes_case_and_whitespace(self):
        first = CreateTicket(" VPN  Down ", "Cannot   connect", "Alice")
        second = CreateTicket("vpn down", "cannot connect", "alice")
        self.assertEqual(ticket_fingerprint(first), ticket_fingerprint(second))

    def test_allowed_and_forbidden_transitions(self):
        ensure_transition(Status.NEW, Status.TRIAGED)
        ensure_transition(Status.RESOLVED, Status.IN_PROGRESS)
        with self.assertRaisesRegex(ValidationError, "不允许"):
            ensure_transition(Status.NEW, Status.RESOLVED)

    def test_category_and_priority_values_are_closed(self):
        self.assertEqual(Category.HARDWARE.value, "hardware")
        self.assertEqual([item.value for item in Priority], ["P0", "P1", "P2", "P3"])

    def test_ai_recommendation_rejects_unclassified_category(self):
        with self.assertRaisesRegex(ValidationError, "unclassified"):
            AIRecommendation(Category.UNCLASSIFIED, Priority.P2, "摘要", "原因")


if __name__ == "__main__":
    unittest.main()
