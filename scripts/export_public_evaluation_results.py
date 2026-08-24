"""Export a redacted, reproducible public evaluation snapshot."""

import argparse
import hashlib
import json
import math
import re
import tempfile
from pathlib import Path


TOP_LEVEL_KEYS = (
    "model",
    "temperature",
    "prompt_version",
    "case_file_sha256",
    "cases",
    "aggregate",
)
CASE_KEYS = (
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
)
AGGREGATE_KEYS = (
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
)
_FAILURE_CODE = re.compile(r"^[a-z]+(?:_[a-z]+)*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_WINDOWS_USER_DIRECTORY = re.compile(r"[a-z]:[\\/]+users(?:[\\/]+|$)", re.IGNORECASE)
_FORBIDDEN_TEXT = (
    "authorization",
    "api_key",
    "bearer",
    "raw_response",
    "headers",
    "base_url",
)
_CASE_STRING_KEYS = (
    "id",
    "expected_category",
    "expected_priority",
    "category",
    "priority",
    "failure_code",
)
_CASE_BOOL_KEYS = (
    "valid",
    "category_correct",
    "priority_correct",
    "injection_safe",
)
_COUNT_KEYS = (
    "total",
    "valid",
    "failures",
    "injection_total",
    "injection_safe",
)
_RATE_KEYS = (
    "valid_structure_rate",
    "category_accuracy",
    "priority_accuracy",
    "injection_resistance_rate",
    "degradation_rate",
)


def _validate_failure_histogram(histogram):
    if not isinstance(histogram, dict):
        raise ValueError("failure_histogram must be a dictionary")
    for code, count in histogram.items():
        if not isinstance(code, str) or not _FAILURE_CODE.fullmatch(code):
            raise ValueError("failure_histogram keys must be lowercase underscore error codes")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("failure_histogram values must be non-negative integers")


def _validate_nonempty_string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _validate_number(value, name, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite non-boolean number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}")


def _validate_private_data_free(value):
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_private_data_free(key)
            _validate_private_data_free(item)
    elif isinstance(value, list):
        for item in value:
            _validate_private_data_free(item)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(fragment in lowered for fragment in _FORBIDDEN_TEXT):
            raise ValueError("public snapshot contains forbidden private data")
        if _WINDOWS_USER_DIRECTORY.search(value):
            raise ValueError("public snapshot contains a Windows user-directory path")


def _required(mapping, key, context):
    if key not in mapping:
        raise ValueError(f"{context} is missing required field: {key}")
    return mapping[key]


def validate_public_snapshot(public: dict) -> None:
    _validate_nonempty_string(public["model"], "model")
    _validate_number(public["temperature"], "temperature")
    _validate_nonempty_string(public["prompt_version"], "prompt_version")
    if not isinstance(public["case_file_sha256"], str) or not _SHA256.fullmatch(public["case_file_sha256"]):
        raise ValueError("case_file_sha256 must be a 64-character hexadecimal string")
    if not isinstance(public["date"], str) or not _DATE.fullmatch(public["date"]):
        raise ValueError("date must use YYYY-MM-DD format")
    if not isinstance(public["cases"], list):
        raise ValueError("cases must be a list")
    for case in public["cases"]:
        if not isinstance(case, dict):
            raise ValueError("each case must be a dictionary")
        for key in _CASE_STRING_KEYS:
            if key in case:
                _validate_nonempty_string(case[key], key)
        if "failure_code" in case and not _FAILURE_CODE.fullmatch(case["failure_code"]):
            raise ValueError("failure_code must be a lowercase underscore error code")
        for key in _CASE_BOOL_KEYS:
            if key in case and type(case[key]) is not bool:
                raise ValueError(f"{key} must be a boolean")
    aggregate = public["aggregate"]
    for key in _COUNT_KEYS:
        _validate_number(aggregate[key], key, minimum=0)
        if not isinstance(aggregate[key], int) or isinstance(aggregate[key], bool):
            raise ValueError(f"{key} must be a non-negative integer")
    for key in _RATE_KEYS:
        _validate_number(aggregate[key], key, minimum=0, maximum=1)
    _validate_failure_histogram(aggregate["failure_histogram"])
    _validate_private_data_free(public)


def build_public_snapshot(source_bytes: bytes, expected_sha256: str, date: str) -> dict:
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual.lower() != expected_sha256.lower():
        raise ValueError(f"source SHA-256 mismatch: {actual}")
    source = json.loads(source_bytes.decode("utf-8"))
    if not isinstance(source, dict):
        raise ValueError("source report must be a dictionary")
    for key in TOP_LEVEL_KEYS:
        _required(source, key, "source report")
    if not isinstance(source["cases"], list):
        raise ValueError("source cases must be a list")
    if not isinstance(source["aggregate"], dict):
        raise ValueError("source aggregate must be a dictionary")
    for key in AGGREGATE_KEYS:
        _required(source["aggregate"], key, "source aggregate")
    for case in source["cases"]:
        if not isinstance(case, dict):
            raise ValueError("source cases must contain dictionaries")
    public = {
        "schema_version": 1,
        "redacted_snapshot": True,
        "date": date,
        **{
            key: source[key]
            for key in TOP_LEVEL_KEYS
            if key not in {"cases", "aggregate"}
        },
        "cases": [
            {key: case[key] for key in CASE_KEYS if key in case}
            for case in source["cases"]
        ],
        "aggregate": {
            key: source["aggregate"][key]
            for key in AGGREGATE_KEYS
        },
    }
    validate_public_snapshot(public)
    return public


def _write_json_atomically(output: Path, public: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
            newline="\n",
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(public, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
        temporary_path.replace(output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--date", required=True)
    arguments = parser.parse_args()
    public = build_public_snapshot(
        arguments.source.read_bytes(), arguments.expected_sha256, arguments.date
    )
    _write_json_atomically(arguments.output, public)


if __name__ == "__main__":
    main()
