import json
import os
import tempfile
import unittest
from pathlib import Path

from ticket_system.domain import AIRecommendation, Category, Priority
from ticket_system.evaluation import evaluate_cases, load_cases, write_report
from ticket_system.errors import AIUnavailableError


class _FakeClient:
    model = "fake"
    temperature = 0

    def __init__(self):
        self.calls = 0

    def analyze(self, ticket, prompt_version):
        self.calls += 1
        if self.calls == 11:
            raise AIUnavailableError("provider_error", "provider down")
        if self.calls == 12:
            raise AIUnavailableError("invalid_response", "bad json")
        category = Category.HARDWARE if "打印机" in ticket.description else Category.OTHER
        return AIRecommendation(category, Priority.P2 if category is Category.HARDWARE else Priority.P3, "摘要", "理由"), "raw"


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "cases.json"
        data = []
        for index in range(12):
            data.append({
                "id": f"case-{index:03d}",
                "title": "打印机" if index < 10 else "异常",
                "description": "打印机缺墨" if index < 10 else "其他问题",
                "expected_category": "hardware" if index < 10 else "other",
                "expected_priority": "P2" if index < 10 else "P3",
                **({"injection": {"malicious_category": "account_access", "malicious_priority": "P0"}} if index == 10 else {}),
            })
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_loader_and_metrics_capture_success_failure_and_injection(self):
        cases = load_cases(self.path)
        report = evaluate_cases(cases, _FakeClient(), "hardened")
        self.assertEqual(report.aggregate["total"], 12)
        self.assertEqual(report.aggregate["failures"], 2)
        self.assertEqual(report.aggregate["failure_histogram"], {"provider_error": 1, "invalid_response": 1})
        self.assertEqual(report.aggregate["valid_structure_rate"], 10 / 12)
        self.assertEqual(report.prompt_version, "hardened")

    def test_report_writes_json_atomically(self):
        report = evaluate_cases(load_cases(self.path), _FakeClient(), "baseline")
        output = write_report(report, Path(self.tempdir.name) / "reports")
        self.assertTrue(output.exists())
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("case_file_sha256", payload)
        self.assertEqual(payload["prompt_version"], "baseline")


if __name__ == "__main__":
    unittest.main()
