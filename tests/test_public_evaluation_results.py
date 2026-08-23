import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from scripts.export_public_evaluation_results import (
    AGGREGATE_KEYS,
    CASE_KEYS,
    TOP_LEVEL_KEYS,
    build_public_snapshot,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_RESULTS = REPOSITORY_ROOT / "evaluation" / "results" / "moonshot-v1-8k"
CASE_SHA256 = "a0585df6df13e28e0bb0172022f78163935775cb682f052991564480d75b584c"
SOURCE_REPORTS = {
    "2026-08-09-baseline.json": (
        "tmp/kimi-reports/baseline/20260808T181231.347454+0000.json",
        "8010dd8d0bc5ccc1895705face9025c91781ba5915a4c5c1b2c1f2fdbf3523a8",
    ),
    "2026-08-09-hardened.json": (
        "tmp/kimi-reports/hardened-v3/20260808T181636.457888+0000.json",
        "3a0b9a9ab6b87867ce378a3b247f5cd1af7cfb3192883ab789932874efda568d",
    ),
}
FORBIDDEN_TEXT = (
    "authorization",
    "api_key",
    "bearer",
    "raw_response",
    "headers",
    "base_url",
    "c:\\users\\",
)


def _source_fixture(failure_histogram):
    return {
        "model": "test-model",
        "temperature": 0,
        "prompt_version": "test",
        "case_file_sha256": CASE_SHA256,
        "cases": [{"id": "case-001", "valid": False, "failure_code": "invalid_response"}],
        "aggregate": {
            "total": 1,
            "valid": 0,
            "failures": 1,
            "valid_structure_rate": 0.0,
            "category_accuracy": 0.0,
            "priority_accuracy": 0.0,
            "injection_total": 0,
            "injection_safe": 0,
            "injection_resistance_rate": 0.0,
            "degradation_rate": 1.0,
            "failure_histogram": failure_histogram,
        },
        "run_id": "must-not-be-published",
        "timestamp": "must-not-be-published",
    }


def _formal_root():
    common_git_dir = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPOSITORY_ROOT,
    ).decode("utf-8").strip()
    return Path(common_git_dir).parent


def _walk_public_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_public_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_public_values(item)
    elif isinstance(value, str):
        yield value


def _recompute_aggregate(cases):
    total = len(cases)
    valid_cases = [case for case in cases if case["valid"]]
    injection_cases = [case for case in cases if "injection_safe" in case]
    histogram = {}
    for case in cases:
        if not case["valid"]:
            histogram[case["failure_code"]] = histogram.get(case["failure_code"], 0) + 1
    valid_count = len(valid_cases)
    return {
        "total": total,
        "valid": valid_count,
        "failures": total - valid_count,
        "valid_structure_rate": valid_count / total,
        "category_accuracy": sum(case["category_correct"] for case in valid_cases) / valid_count if valid_count else 0.0,
        "priority_accuracy": sum(case["priority_correct"] for case in valid_cases) / valid_count if valid_count else 0.0,
        "injection_total": len(injection_cases),
        "injection_safe": sum(case["injection_safe"] for case in injection_cases),
        "injection_resistance_rate": (
            sum(case["injection_safe"] for case in injection_cases) / len(injection_cases)
            if injection_cases else 0.0
        ),
        "degradation_rate": (total - valid_count) / total,
        "failure_histogram": histogram,
    }


class PublicEvaluationExporterTests(unittest.TestCase):
    def test_rejects_wrong_source_sha256(self):
        source_bytes = json.dumps(_source_fixture({"invalid_response": 1})).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
            build_public_snapshot(source_bytes, "0" * 64, "2026-08-09")

    def test_rejects_malformed_failure_histograms(self):
        malformed = ({"Invalid_Response": 1}, {"invalid-response": 1}, {"invalid_response": True}, {"invalid_response": -1})
        for histogram in malformed:
            with self.subTest(histogram=histogram):
                source_bytes = json.dumps(_source_fixture(histogram)).encode("utf-8")
                expected = hashlib.sha256(source_bytes).hexdigest()
                with self.assertRaises(ValueError):
                    build_public_snapshot(source_bytes, expected, "2026-08-09")

    def test_exports_only_allowlisted_fields_and_preserves_absent_success_fields(self):
        source = _source_fixture({"invalid_response": 1})
        source_bytes = json.dumps(source).encode("utf-8")
        public = build_public_snapshot(source_bytes, hashlib.sha256(source_bytes).hexdigest(), "2026-08-09")
        self.assertEqual(
            set(public),
            {"schema_version", "redacted_snapshot", "date", *TOP_LEVEL_KEYS},
        )
        self.assertEqual(set(public["cases"][0]), {"id", "valid", "failure_code"})
        self.assertTrue(set(public["cases"][0]).issubset(CASE_KEYS))
        self.assertEqual(set(public["aggregate"]), set(AGGREGATE_KEYS))
        self.assertNotIn("category", public["cases"][0])
        self.assertNotIn("priority", public["cases"][0])


class CheckedInPublicSnapshotsTests(unittest.TestCase):
    def _load_snapshot(self, filename):
        return json.loads((PUBLIC_RESULTS / filename).read_text(encoding="utf-8"))

    def test_checked_in_reports_have_expected_metrics_and_recomputed_aggregates(self):
        baseline = self._load_snapshot("2026-08-09-baseline.json")
        hardened = self._load_snapshot("2026-08-09-hardened.json")
        for snapshot in (baseline, hardened):
            self.assertEqual(snapshot["schema_version"], 1)
            self.assertTrue(snapshot["redacted_snapshot"])
            self.assertEqual(snapshot["date"], "2026-08-09")
            self.assertEqual(snapshot["case_file_sha256"], CASE_SHA256)
            self.assertEqual(snapshot["aggregate"], _recompute_aggregate(snapshot["cases"]))
        self.assertEqual(baseline["aggregate"]["failure_histogram"], {"invalid_response": 12})
        self.assertEqual(hardened["aggregate"]["valid"], 12)
        self.assertEqual(hardened["aggregate"]["category_accuracy"], 1.0)
        self.assertEqual(hardened["aggregate"]["priority_accuracy"], 11 / 12)
        self.assertEqual(hardened["aggregate"]["injection_safe"], 2)
        self.assertEqual(hardened["aggregate"]["injection_total"], 2)

    def test_checked_in_reports_are_allowlisted_and_private_data_free(self):
        for filename in SOURCE_REPORTS:
            snapshot = self._load_snapshot(filename)
            self.assertEqual(set(snapshot), {"schema_version", "redacted_snapshot", "date", *TOP_LEVEL_KEYS})
            self.assertEqual(set(snapshot["aggregate"]), set(AGGREGATE_KEYS))
            for case in snapshot["cases"]:
                self.assertTrue(set(case).issubset(CASE_KEYS))
            for value in _walk_public_values(snapshot):
                lowered = value.lower()
                self.assertFalse(any(fragment in lowered for fragment in FORBIDDEN_TEXT), value)

    def test_public_fields_match_locked_source_reports_when_available(self):
        formal_root = _formal_root()
        for filename, (relative_source, expected_sha256) in SOURCE_REPORTS.items():
            source_path = formal_root / relative_source
            if not source_path.is_file():
                continue
            source_bytes = source_path.read_bytes()
            self.assertEqual(hashlib.sha256(source_bytes).hexdigest(), expected_sha256)
            source = json.loads(source_bytes.decode("utf-8"))
            snapshot = self._load_snapshot(filename)
            self.assertEqual(snapshot["cases"], [{key: case[key] for key in CASE_KEYS if key in case} for case in source["cases"]])
            self.assertEqual(snapshot["aggregate"], source["aggregate"])


if __name__ == "__main__":
    unittest.main()
