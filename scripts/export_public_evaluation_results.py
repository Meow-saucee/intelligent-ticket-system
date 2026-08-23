"""Export a redacted, reproducible public evaluation snapshot."""

import argparse
import hashlib
import json
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


def _validate_failure_histogram(histogram):
    if not isinstance(histogram, dict):
        raise ValueError("failure_histogram must be a dictionary")
    for code, count in histogram.items():
        if not isinstance(code, str) or not _FAILURE_CODE.fullmatch(code):
            raise ValueError("failure_histogram keys must be lowercase underscore error codes")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("failure_histogram values must be non-negative integers")


def build_public_snapshot(source_bytes: bytes, expected_sha256: str, date: str) -> dict:
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual.lower() != expected_sha256.lower():
        raise ValueError(f"source SHA-256 mismatch: {actual}")
    source = json.loads(source_bytes.decode("utf-8"))
    _validate_failure_histogram(source["aggregate"]["failure_histogram"])
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
