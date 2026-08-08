import os
import sqlite3
import tempfile
import unittest

from ticket_system.database import connect_database, initialize_database
from ticket_system.domain import CreateTicket, Priority, Status, validate_create
from ticket_system.repository import TicketRepository


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.tempdir.name, "tickets.db")
        self.connection = connect_database(self.database_path)
        initialize_database(self.connection)
        self.repository = TicketRepository(self.connection)

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def _create(self, title, fingerprint, priority=Priority.P2):
        return self.repository.create(
            validate_create(CreateTicket(title, "描述", "alice", priority)),
            "2026-08-08T10:00:00+00:00",
            fingerprint,
        )

    def test_ticket_survives_reopen(self):
        created = self.repository.create(
            validate_create(CreateTicket("VPN 故障", "无法连接", "alice", "P1")),
            "2026-08-08T10:00:00+00:00",
            "fingerprint-1",
        )
        self.connection.close()
        reopened = connect_database(self.database_path)
        initialize_database(reopened)
        found = TicketRepository(reopened).get(created.public_id)
        self.assertEqual(found.title, "VPN 故障")
        self.assertEqual(found.priority, Priority.P1)
        reopened.close()
        self.connection = connect_database(self.database_path)

    def test_list_combines_status_and_priority_filters(self):
        self._create("A", "f1", Priority.P1)
        self._create("B", "f2", Priority.P2)
        results = self.repository.list({"status": Status.NEW, "priority": Priority.P1})
        self.assertEqual([ticket.title for ticket in results], ["A"])

    def test_database_constraints_reject_invalid_status(self):
        self._create("A", "f1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE tickets SET status = 'invalid'")

    def test_database_constraints_reject_unclassified_final_category(self):
        ticket = self._create("A", "f1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO ai_suggestions (
                    ticket_id, model, prompt_version, status, created_at, final_category
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.id,
                    "model",
                    "v1",
                    "pending",
                    "2026-08-08T10:00:00+00:00",
                    "unclassified",
                ),
            )
    def test_schema_tables_and_index_families_exist(self):
        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {"schema_version", "ticket_sequences", "tickets", "ai_suggestions", "audit_events"}
            <= tables
        )
        indexes = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        self.assertTrue(any(name.startswith("idx_tickets_") for name in indexes))
        self.assertTrue(any(name.startswith("idx_ai_suggestions_") for name in indexes))
        self.assertTrue(any(name.startswith("idx_audit_events_") for name in indexes))

    def test_create_assigns_daily_public_id_and_creation_history(self):
        created = self._create("A", "f1")
        self.assertEqual(created.public_id, "TKT-20260808-0001")
        events = self.repository.history(created.public_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "ticket_created")

    def test_find_recent_duplicate_returns_matching_ticket(self):
        created = self._create("A", "f1")
        found = self.repository.find_recent_duplicate("f1", "2026-08-07T10:00:00+00:00")
        self.assertEqual(found.public_id, created.public_id)
        self.assertIsNone(
            self.repository.find_recent_duplicate("f1", "2026-08-08T10:00:01+00:00")
        )

    def test_set_status_updates_version_and_history(self):
        created = self._create("A", "f1")
        updated = self.repository.set_status(
            created.public_id, Status.TRIAGED, "operator", "2026-08-08T11:00:00+00:00"
        )
        self.assertEqual(updated.status, Status.TRIAGED)
        self.assertEqual(updated.version, 2)
        self.assertEqual(
            [event.event_type for event in self.repository.history(created.public_id)],
            ["ticket_created", "status_changed"],
        )


if __name__ == "__main__":
    unittest.main()
