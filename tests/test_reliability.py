import os
import tempfile
import threading
import unittest

from ticket_system.database import connect_database, initialize_database
from ticket_system.domain import CreateTicket, Status
from ticket_system.errors import ConflictError, DuplicateTicketError, ValidationError
from ticket_system.repository import TicketRepository
from ticket_system.service import TicketService


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tempdir.name, "tickets.db")
        self.connection = connect_database(self.path)
        initialize_database(self.connection)
        self.service = TicketService(TicketRepository(self.connection))

    def tearDown(self):
        self.connection.close()
        self.tempdir.cleanup()

    def test_duplicate_create_is_rejected_with_existing_public_id(self):
        first = self.service.create(CreateTicket(" VPN ", " 无法连接 ", " alice "))
        with self.assertRaises(DuplicateTicketError) as caught:
            self.service.create(CreateTicket("VPN", "无法连接", "alice", "P1"))
        self.assertEqual(caught.exception.existing_id, first.public_id)
        self.assertEqual(len(self.service.list()), 1)

    def test_status_machine_rejects_illegal_jump_and_records_versions(self):
        ticket = self.service.create(CreateTicket("A", "描述", "alice"))
        with self.assertRaises(ValidationError):
            self.service.change_status(ticket.public_id, Status.RESOLVED, "operator", expected_version=1)
        changed = self.service.change_status(ticket.public_id, Status.TRIAGED, "operator", expected_version=1)
        self.assertEqual(changed.version, 2)
        event = self.service.history(ticket.public_id)[-1]
        self.assertEqual(event.payload, {"actor": "operator", "from": "new", "to": "triaged", "old_version": 1, "new_version": 2})

    def test_stale_version_returns_conflict_without_second_update(self):
        ticket = self.service.create(CreateTicket("A", "描述", "alice"))
        self.service.change_status(ticket.public_id, Status.TRIAGED, "one", expected_version=1)
        with self.assertRaises(ConflictError):
            self.service.change_status(ticket.public_id, Status.IN_PROGRESS, "two", expected_version=1)
        self.assertEqual(self.service.show(ticket.public_id).status, Status.TRIAGED)
        self.assertEqual(len(self.service.history(ticket.public_id)), 2)

    def test_concurrent_identical_creates_have_one_winner(self):
        barrier = threading.Barrier(2)
        results = []

        def worker():
            connection = connect_database(self.path)
            initialize_database(connection)
            service = TicketService(TicketRepository(connection))
            barrier.wait()
            try:
                results.append(("ok", service.create(CreateTicket("A", "描述", "alice")).public_id))
            except DuplicateTicketError as error:
                results.append(("duplicate", error.existing_id))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(item[0] for item in results), ["duplicate", "ok"])
        self.assertEqual(len(self.service.list()), 1)


if __name__ == "__main__":
    unittest.main()
