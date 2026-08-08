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


if __name__ == "__main__":
    unittest.main()
