import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ticket_system.ai_client import AIConfig, OpenAICompatibleClient
from ticket_system.domain import CreateTicket, Ticket
from ticket_system.errors import AIUnavailableError
from ticket_system.prompts import build_messages


def _ticket() -> Ticket:
    from ticket_system.domain import Category, Priority, Status

    return Ticket(1, "TKT-20260809-0001", "打印机", "打印机缺墨", "alice", Status.NEW,
                  Category.UNCLASSIFIED, Priority.P2, 1, "fp", "2026-08-09T00:00:00+00:00",
                  "2026-08-09T00:00:00+00:00")


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"
    seen = {}

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.__class__.seen = {"path": self.path, "auth": self.headers.get("Authorization"), "body": body}
        if self.mode == "401":
            self.send_response(401)
            self.end_headers()
            return
        if self.mode == "429":
            self.send_response(429)
            self.end_headers()
            return
        if self.mode == "500":
            self.send_response(500)
            self.end_headers()
            return
        payload = {"choices": [{"message": {"content": json.dumps({"category": "hardware", "priority": "P2", "summary": "摘要", "reason": "理由"})}}], "model": "demo"}
        raw = json.dumps(payload).encode()
        if self.mode == "large":
            raw = b"x" * 65537
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


class AIClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def config(self):
        return AIConfig(api_key="secret-key", model="demo-model", base_url=self.url, timeout=3)

    def test_posts_openai_compatible_request_and_extracts_content(self):
        _Handler.mode = "ok"
        recommendation, model = OpenAICompatibleClient(self.config()).analyze(_ticket(), "hardened")
        self.assertIn('"category": "hardware"', model)
        self.assertEqual(recommendation.category.value, "hardware")
        self.assertEqual(_Handler.seen["path"], "/v1/chat/completions")
        self.assertEqual(_Handler.seen["auth"], "Bearer secret-key")
        body = json.loads(_Handler.seen["body"])
        self.assertEqual(body["temperature"], 0)

    def test_hardened_prompt_isolates_untrusted_description_as_user_data(self):
        ticket = _ticket()
        messages = build_messages(ticket, "hardened")
        self.assertIn("不可信数据", messages[0]["content"])
        self.assertNotIn(ticket.description, messages[0]["content"])
        self.assertIn(ticket.description, messages[1]["content"])

    def test_maps_provider_failures_without_leaking_secret(self):
        for mode, code in (("401", "auth_failed"), ("429", "rate_limited"), ("500", "provider_error"), ("large", "response_too_large")):
            _Handler.mode = mode
            with self.assertRaises(AIUnavailableError) as caught:
                OpenAICompatibleClient(self.config()).analyze(_ticket(), "baseline")
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn("secret-key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
