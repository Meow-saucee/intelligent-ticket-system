import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


class _UnauthorizedHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(401)
        self.end_headers()

    def log_message(self, *_args):
        return


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Path(self.tempdir.name) / "acceptance.db"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _UnauthorizedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tempdir.cleanup()

    def run_cli(self, *args, env=None):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = "src"
        if env:
            environment.update(env)
        return subprocess.run(
            [sys.executable, "-m", "ticket_system", "--db", str(self.db), *args],
            capture_output=True,
            encoding="utf-8",
            env=environment,
            check=False,
        )

    def test_seven_step_acceptance_flow(self):
        self.assertEqual(self.run_cli("init").returncode, 0)
        self.assertEqual(json.loads(self.run_cli("seed").stdout), {"created": 5, "existing": 0})
        self.assertEqual(json.loads(self.run_cli("seed").stdout), {"created": 0, "existing": 5})
        created = self.run_cli("create", "--title", "验收工单", "--description", "需要处理", "--submitter", "acceptance", "--priority", "P1")
        self.assertEqual(created.returncode, 0, created.stderr)
        ticket = json.loads(created.stdout)
        listed = self.run_cli("list", "--status", "new", "--priority", "P1")
        self.assertEqual(listed.returncode, 0)
        self.assertTrue(any(row["public_id"] == ticket["public_id"] for row in json.loads(listed.stdout)))
        self.assertEqual(self.run_cli("show", ticket["public_id"]).returncode, 0)
        version = ticket["version"]
        for target in ("triaged", "in_progress", "resolved", "closed"):
            changed = self.run_cli("status", ticket["public_id"], target, "--actor", "acceptance", "--version", str(version))
            self.assertEqual(changed.returncode, 0, changed.stderr)
            version = json.loads(changed.stdout)["version"]
        empty = self.run_cli("create", "--title", "", "--description", "x", "--submitter", "a")
        self.assertEqual(empty.returncode, 2)
        invalid_priority = self.run_cli("create", "--title", "invalid", "--description", "x", "--submitter", "a", "--priority", "P4")
        self.assertEqual(invalid_priority.returncode, 2)
        duplicate = self.run_cli("create", "--title", "验收工单", "--description", "需要处理", "--submitter", "acceptance")
        self.assertEqual(duplicate.returncode, 3)
        self.assertIn(ticket["public_id"], duplicate.stderr)
        failed = self.run_cli(
            "analyze", ticket["public_id"],
            env={"AI_API_KEY": "test-key", "AI_MODEL": "test-model", "AI_BASE_URL": f"http://127.0.0.1:{self.server.server_port}/v1"},
        )
        self.assertEqual(failed.returncode, 4, failed.stderr)
        self.assertIn("工单未改变", failed.stderr)
        final_list = self.run_cli("list")
        self.assertEqual(final_list.returncode, 0, final_list.stderr)
        history = json.loads(self.run_cli("show", ticket["public_id"], "--history").stdout)["history"]
        event_types = [event["event_type"] for event in history]
        self.assertIn("ticket_created", event_types)
        self.assertGreaterEqual(event_types.count("status_changed"), 4)
        self.assertIn("ai_analysis_failed", event_types)


if __name__ == "__main__":
    unittest.main()
