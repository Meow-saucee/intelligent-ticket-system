import os
import tempfile
import unittest

from ticket_system.database import connect_database, initialize_database
from ticket_system.domain import Category, CreateTicket, Priority, Status
from ticket_system.errors import ValidationError
from ticket_system.repository import TicketRepository
from ticket_system.service import TicketService


class TicketServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.connection = connect_database(os.path.join(self.tempdir.name, "tickets.db"))
        initialize_database(self.connection)
        self.service = TicketService(TicketRepository(self.connection))

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def test_seed_creates_five_stable_diverse_tickets_once(self):
        self.assertEqual(self.service.seed(), {"created": 5, "existing": 0})

        tickets = self.service.list()
        self.assertEqual(len(tickets), 5)
        self.assertEqual(
            {ticket.seed_key for ticket in tickets},
            {f"sample-{number:03d}" for number in range(1, 6)},
        )
        self.assertGreaterEqual(len({ticket.status for ticket in tickets}), 3)
        self.assertGreaterEqual(len({ticket.category for ticket in tickets}), 4)
        self.assertEqual(
            self.service.list({"category": Category.ACCOUNT_ACCESS})[0].priority,
            Priority.P1,
        )
        self.assertEqual(
            self.service.list({"category": Category.ACCOUNT_ACCESS})[0].status,
            Status.NEW,
        )

    def test_seed_is_idempotent(self):
        self.service.seed()

        self.assertEqual(self.service.seed(), {"created": 0, "existing": 5})
        self.assertEqual(len(self.service.list()), 5)

    def test_create_validates_then_supports_show_history_and_status_change(self):
        created = self.service.create(
            CreateTicket("邮箱无法登录", "密码正确但登录失败", "alice", "P1")
        )

        self.assertEqual(self.service.show(created.public_id), created)
        self.assertEqual(
            [event.event_type for event in self.service.history(created.public_id)],
            ["ticket_created"],
        )

        changed = self.service.change_status(
            created.public_id, "triaged", "operator", expected_version=1
        )
        self.assertEqual(changed.status, Status.TRIAGED)
        self.assertEqual(changed.version, 2)
        self.assertEqual(
            [event.event_type for event in self.service.history(created.public_id)],
            ["ticket_created", "status_changed"],
        )

    def test_create_rejects_empty_title_before_persisting(self):
        with self.assertRaises(ValidationError):
            self.service.create(CreateTicket(" ", "描述", "alice"))

        self.assertEqual(self.service.list(), [])


if __name__ == "__main__":
    unittest.main()
