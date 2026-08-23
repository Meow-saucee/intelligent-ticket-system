import copy
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import export_public_evaluation_results as exporter


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPORTER_SCRIPT = REPOSITORY_ROOT / "scripts" / "export_public_evaluation_results.py"
PUBLIC_RESULTS = REPOSITORY_ROOT / "evaluation" / "results" / "moonshot-v1-8k"
CASE_SHA256 = "a0585df6df13e28e0bb0172022f78163935775cb682f052991564480d75b584c"
EXPECTED_TOP = {
    "model",
    "temperature",
    "prompt_version",
    "case_file_sha256",
    "cases",
    "aggregate",
}
EXPECTED_CASE = {
    "id",
    "expected_category",
    "expected_priority",
    "category",
    "priority",
    "valid",
    "category_correct",
    "priority_correct",
    "injection_safe",
    "failure_code",
}
EXPECTED_AGGREGATE = {
    "total",
    "valid",
    "failures",
    "valid_structure_rate",
    "category_accuracy",
    "priority_accuracy",
    "injection_total",
    "injection_safe",
    "injection_resistance_rate",
    "degradation_rate",
    "failure_histogram",
}
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
)
WINDOWS_USER_DIRECTORY = re.compile(r"[a-z]:[\\/]+users(?:[\\/]+|$)", re.IGNORECASE)
ERROR_CODE = re.compile(r"^[a-z]+(?:_[a-z]+)*$")


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


def _complete_source_fixture():
    source = _source_fixture({})
    source["cases"] = [{
        "id": "case-001",
        "expected_category": "hardware",
        "expected_priority": "P2",
        "category": "hardware",
        "priority": "P2",
        "valid": True,
        "category_correct": True,
        "priority_correct": True,
        "injection_safe": True,
        "failure_code": "invalid_response",
    }]
    source["aggregate"].update({
        "valid": 1,
        "failures": 0,
        "valid_structure_rate": 1.0,
        "category_accuracy": 1.0,
        "priority_accuracy": 1.0,
        "injection_total": 1,
        "injection_safe": 1,
        "injection_resistance_rate": 1.0,
        "degradation_rate": 0.0,
    })
    return source


def _source_bytes(source):
    return json.dumps(source, ensure_ascii=False).encode("utf-8")


def _assert_private_data_free(test_case, value):
    for item in _walk_public_values(value):
        lowered = item.lower()
        test_case.assertFalse(any(fragment in lowered for fragment in FORBIDDEN_TEXT), item)
        test_case.assertIsNone(WINDOWS_USER_DIRECTORY.search(item), item)


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
    def _build(self, source, date="2026-08-09"):
        source_bytes = _source_bytes(source)
        return exporter.build_public_snapshot(
            source_bytes, hashlib.sha256(source_bytes).hexdigest(), date
        )

    def test_exporter_allowlist_constants_match_independent_contract(self):
        self.assertEqual(set(exporter.TOP_LEVEL_KEYS), EXPECTED_TOP)
        self.assertEqual(set(exporter.CASE_KEYS), EXPECTED_CASE)
        self.assertEqual(set(exporter.AGGREGATE_KEYS), EXPECTED_AGGREGATE)

    def test_rejects_wrong_source_sha256(self):
        source_bytes = json.dumps(_source_fixture({"invalid_response": 1})).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
            exporter.build_public_snapshot(source_bytes, "0" * 64, "2026-08-09")

    def test_rejects_malformed_failure_histograms(self):
        malformed = ({"Invalid_Response": 1}, {"invalid-response": 1}, {"invalid_response": True}, {"invalid_response": -1})
        for histogram in malformed:
            with self.subTest(histogram=histogram):
                source_bytes = json.dumps(_source_fixture(histogram)).encode("utf-8")
                expected = hashlib.sha256(source_bytes).hexdigest()
                with self.assertRaises(ValueError):
                    exporter.build_public_snapshot(source_bytes, expected, "2026-08-09")

    def test_rejects_non_scalar_and_wrong_type_public_fields(self):
        invalid_fields = (
            (("model",), ""),
            (("model",), {"authorization": "secret"}),
            (("temperature",), True),
            (("temperature",), "zero"),
            (("prompt_version",), ""),
            (("case_file_sha256",), "f" * 63),
            (("cases", 0, "id"), ""),
            (("cases", 0, "expected_category"), ["hardware"]),
            (("cases", 0, "expected_priority"), {"headers": "secret"}),
            (("cases", 0, "category"), ["raw_response"]),
            (("cases", 0, "priority"), 2),
            (("cases", 0, "valid"), 1),
            (("cases", 0, "category_correct"), "true"),
            (("cases", 0, "priority_correct"), 0),
            (("cases", 0, "injection_safe"), []),
            (("cases", 0, "failure_code"), "Invalid-Response"),
            (("aggregate", "total"), True),
            (("aggregate", "valid"), -1),
            (("aggregate", "failures"), "zero"),
            (("aggregate", "valid_structure_rate"), True),
            (("aggregate", "category_accuracy"), -0.1),
            (("aggregate", "priority_accuracy"), 1.1),
            (("aggregate", "injection_total"), False),
            (("aggregate", "injection_safe"), -1),
            (("aggregate", "injection_resistance_rate"), "one"),
            (("aggregate", "degradation_rate"), 2.0),
        )
        for path, invalid_value in invalid_fields:
            with self.subTest(path=path, invalid_value=invalid_value):
                source = _complete_source_fixture()
                target = source
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = invalid_value
                with self.assertRaises(ValueError):
                    self._build(source)
        with self.assertRaises(ValueError):
            self._build(_complete_source_fixture(), date="2026-8-9")

    def test_rejects_forbidden_values_and_nested_private_fields_at_export_boundary(self):
        private_values = (
            (("model",), "uses authorization header"),
            (("model",), "D://Users////alice"),
            (("cases", 0, "category"), "Bearer token"),
            (("cases", 0, "priority"), "raw_response"),
            (("cases", 0, "expected_category"), "base_url"),
            (("model",), {"headers": ["secret"]}),
            (("cases", 0, "category"), [{"api_key": "secret"}]),
        )
        for path, private_value in private_values:
            with self.subTest(path=path, private_value=private_value):
                source = _complete_source_fixture()
                target = source
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = private_value
                with self.assertRaises(ValueError):
                    self._build(source)

    def test_exports_only_allowlisted_fields_and_preserves_absent_success_fields(self):
        source = _source_fixture({"invalid_response": 1})
        public = self._build(source)
        self.assertEqual(
            set(public),
            {"schema_version", "redacted_snapshot", "date", *EXPECTED_TOP},
        )
        self.assertEqual(set(public["cases"][0]), {"id", "valid", "failure_code"})
        self.assertTrue(set(public["cases"][0]).issubset(EXPECTED_CASE))
        self.assertEqual(set(public["aggregate"]), EXPECTED_AGGREGATE)
        self.assertNotIn("category", public["cases"][0])
        self.assertNotIn("priority", public["cases"][0])


class PublicEvaluationCliTests(unittest.TestCase):
    def test_cli_writes_utf8_indented_snapshot_and_preserves_old_target_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = _complete_source_fixture()
            source["model"] = "模型"
            source_path = directory / "source.json"
            source_bytes = _source_bytes(source)
            source_path.write_bytes(source_bytes)
            output_path = directory / "public.json"
            output_path.write_text("old target\n", encoding="utf-8")
            command = [
                sys.executable, str(EXPORTER_SCRIPT), "--source", str(source_path),
                "--output", str(output_path), "--expected-sha256",
                hashlib.sha256(source_bytes).hexdigest(), "--date", "2026-08-09",
            ]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            written = output_path.read_bytes()
            self.assertIn("模型".encode("utf-8"), written)
            self.assertNotIn(b"\\u6a21", written)
            self.assertTrue(written.endswith(b"\n"))
            self.assertIn(b'\n  "schema_version": 1,\n', written)
            self.assertNotIn(b"old target", written)

            prior = output_path.read_bytes()
            bad_sha_command = [*command]
            bad_sha_command[bad_sha_command.index("--expected-sha256") + 1] = "0" * 64
            self.assertNotEqual(subprocess.run(bad_sha_command, capture_output=True).returncode, 0)
            self.assertEqual(output_path.read_bytes(), prior)

            invalid = _complete_source_fixture()
            invalid["model"] = {"authorization": "secret"}
            invalid_bytes = _source_bytes(invalid)
            source_path.write_bytes(invalid_bytes)
            invalid_command = [*command]
            invalid_command[invalid_command.index("--expected-sha256") + 1] = hashlib.sha256(invalid_bytes).hexdigest()
            self.assertNotEqual(subprocess.run(invalid_command, capture_output=True).returncode, 0)
            self.assertEqual(output_path.read_bytes(), prior)
            self.assertEqual(list(directory.glob(f".{output_path.name}.*.tmp")), [])


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
            self.assertEqual(set(snapshot), {"schema_version", "redacted_snapshot", "date", *EXPECTED_TOP})
            self.assertEqual(set(snapshot["aggregate"]), EXPECTED_AGGREGATE)
            for case in snapshot["cases"]:
                self.assertTrue(set(case).issubset(EXPECTED_CASE))
            _assert_private_data_free(self, snapshot)

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
            self.assertEqual(snapshot["cases"], [{key: case[key] for key in EXPECTED_CASE if key in case} for case in source["cases"]])
            self.assertEqual(snapshot["aggregate"], source["aggregate"])


if __name__ == "__main__":
    unittest.main()
