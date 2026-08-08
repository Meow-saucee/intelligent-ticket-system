import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class TicketCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "tickets.db"

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *arguments):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = "src"
        return subprocess.run(
            [sys.executable, "-m", "ticket_system", "--db", str(self.database_path), *arguments],
            capture_output=True,
            encoding="utf-8",
            env=environment,
            check=False,
        )

    def test_create_list_and_show(self):
        created = self.run_cli(
            "create", "--title", "邮箱无法登录", "--description", "密码正确但登录失败",
            "--submitter", "alice", "--priority", "P1",
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        payload = json.loads(created.stdout)
        self.assertRegex(payload["public_id"], r"^TKT-\d{8}-\d{4}$")

        listed = self.run_cli("list", "--status", "new", "--priority", "P1")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(len(json.loads(listed.stdout)), 1)

        shown = self.run_cli("show", payload["public_id"])
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["submitter"], "alice")

    def test_empty_title_returns_validation_exit_code(self):
        result = self.run_cli(
            "create", "--title", "", "--description", "描述", "--submitter", "alice"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("标题不能为空", result.stderr)

    def test_unknown_ticket_returns_not_found_exit_code(self):
        result = self.run_cli("show", "TKT-20260808-9999")

        self.assertEqual(result.returncode, 3)
        self.assertIn("工单不存在", result.stderr)

    def test_second_process_reads_first_process_record(self):
        created = self.run_cli(
            "create", "--title", "VPN 故障", "--description", "无法连接", "--submitter", "alice"
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        public_id = json.loads(created.stdout)["public_id"]

        shown = self.run_cli("show", public_id)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["title"], "VPN 故障")

    def test_status_requires_version_and_rejects_stale_version(self):
        created = self.run_cli("create", "--title", "VPN", "--description", "无法连接", "--submitter", "alice")
        public_id = json.loads(created.stdout)["public_id"]
        changed = self.run_cli("status", public_id, "triaged", "--actor", "operator", "--version", "1")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        stale = self.run_cli("status", public_id, "in_progress", "--actor", "operator", "--version", "1")
        self.assertEqual(stale.returncode, 3)
        self.assertIn("版本冲突", stale.stderr)

    def test_cli_duplicate_invalid_priority_and_illegal_transition(self):
        first = self.run_cli("create", "--title", "VPN", "--description", "无法连接", "--submitter", "alice")
        public_id = json.loads(first.stdout)["public_id"]
        duplicate = self.run_cli("create", "--title", "VPN", "--description", "无法连接", "--submitter", "alice", "--priority", "P1")
        self.assertEqual(duplicate.returncode, 3)
        self.assertIn(public_id, duplicate.stderr)
        invalid = self.run_cli("create", "--title", "Other", "--description", "描述", "--submitter", "alice", "--priority", "P4")
        self.assertEqual(invalid.returncode, 2)
        illegal = self.run_cli("status", public_id, "resolved", "--actor", "operator", "--version", "1")
        self.assertEqual(illegal.returncode, 2)

    def test_show_history_wraps_ticket_and_audit_events(self):
        created = self.run_cli("create", "--title", "VPN", "--description", "无法连接", "--submitter", "alice")
        public_id = json.loads(created.stdout)["public_id"]
        self.run_cli("status", public_id, "triaged", "--actor", "operator", "--version", "1")
        shown = self.run_cli("show", public_id, "--history")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        payload = json.loads(shown.stdout)
        self.assertEqual(payload["ticket"]["public_id"], public_id)
        self.assertEqual([event["event_type"] for event in payload["history"]], ["ticket_created", "status_changed"])


if __name__ == "__main__":
    unittest.main()
