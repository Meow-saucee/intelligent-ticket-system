import json
import unittest

from ticket_system.ai_schema import parse_recommendation
from ticket_system.domain import Category, Priority
from ticket_system.errors import AIUnavailableError


class AISchemaTests(unittest.TestCase):
    def test_accepts_object_and_single_json_fence(self):
        payload = {
            "category": "hardware",
            "priority": "P2",
            "summary": "打印机缺墨",
            "reason": "设备耗材问题",
        }
        for text in (json.dumps(payload), f"```json\n{json.dumps(payload)}\n```"):
            result = parse_recommendation(text)
            self.assertEqual((result.category, result.priority), (Category.HARDWARE, Priority.P2))

    def test_rejects_extra_fields_and_invalid_values(self):
        base = {
            "category": "hardware",
            "priority": "P2",
            "summary": "摘要",
            "reason": "理由",
        }
        for field, value in (("extra", "x"), ("category", "unclassified"), ("priority", "P4")):
            payload = dict(base)
            payload[field] = value
            with self.assertRaises(AIUnavailableError):
                parse_recommendation(json.dumps(payload))

    def test_rejects_multiple_objects_and_bad_lengths(self):
        payload = {"category": "other", "priority": "P3", "summary": "", "reason": "理由"}
        with self.assertRaises(AIUnavailableError):
            parse_recommendation(json.dumps(payload))
        valid = {"category": "other", "priority": "P3", "summary": "摘要", "reason": "理由"}
        with self.assertRaises(AIUnavailableError):
            parse_recommendation(json.dumps(valid) + json.dumps(valid))
        valid["reason"] = "x" * 301
        with self.assertRaises(AIUnavailableError):
            parse_recommendation(json.dumps(valid))


if __name__ == "__main__":
    unittest.main()
