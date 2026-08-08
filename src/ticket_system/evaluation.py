from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

from .domain import Category, Priority, Status, Ticket
from .errors import AIUnavailableError, ValidationError


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    title: str
    description: str
    expected_category: Category
    expected_priority: Priority
    injection: dict | None = None


class EvaluationCases(list):
    def __init__(self, values, *, source_hash: str):
        super().__init__(values)
        self.source_hash = source_hash


@dataclass(frozen=True)
class EvaluationReport:
    run_id: str
    timestamp: str
    model: str
    temperature: float
    prompt_version: str
    case_file_sha256: str
    cases: list[dict]
    aggregate: dict

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "model": self.model,
            "temperature": self.temperature,
            "prompt_version": self.prompt_version,
            "case_file_sha256": self.case_file_sha256,
            "cases": self.cases,
            "aggregate": self.aggregate,
        }


def load_cases(path: str | Path) -> EvaluationCases:
    path = Path(path)
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("评测样例文件不是有效 JSON") from error
    if not isinstance(payload, list) or len(payload) < 10:
        raise ValidationError("评测样例至少需要 10 条")
    cases = []
    ids = set()
    for item in payload:
        if not isinstance(item, dict) or not item.get("id") or item["id"] in ids:
            raise ValidationError("评测样例 ID 必须非空且唯一")
        ids.add(item["id"])
        try:
            expected_category = Category(item["expected_category"])
            expected_priority = Priority(item["expected_priority"])
        except (KeyError, ValueError) as error:
            raise ValidationError("评测样例分类或优先级无效") from error
        injection = item.get("injection")
        if injection is not None:
            if not isinstance(injection, dict) or "malicious_category" not in injection or "malicious_priority" not in injection:
                raise ValidationError("注入样例必须声明恶意目标")
            try:
                Category(injection["malicious_category"])
                Priority(injection["malicious_priority"])
            except ValueError as error:
                raise ValidationError("注入样例恶意目标无效") from error
        cases.append(EvaluationCase(item["id"], str(item.get("title", "")), str(item.get("description", "")), expected_category, expected_priority, injection))
    return EvaluationCases(cases, source_hash=hashlib.sha256(raw).hexdigest())


def _ticket(case: EvaluationCase, index: int) -> Ticket:
    return Ticket(index, f"EVAL-{index:04d}", case.title, case.description, "evaluation", Status.NEW, Category.UNCLASSIFIED, Priority.P2, 1, "evaluation", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00")


def evaluate_cases(cases: list[EvaluationCase], client, prompt_version: str) -> EvaluationReport:
    results = []
    valid = category_correct = priority_correct = failures = injection_total = injection_safe = 0
    histogram: dict[str, int] = {}
    for index, case in enumerate(cases, 1):
        result = {"id": case.id, "expected_category": case.expected_category.value, "expected_priority": case.expected_priority.value}
        try:
            recommendation, _raw = client.analyze(_ticket(case, index), prompt_version)
            valid += 1
            category_ok = recommendation.category is case.expected_category
            priority_ok = recommendation.priority is case.expected_priority
            category_correct += int(category_ok)
            priority_correct += int(priority_ok)
            result.update({"category": recommendation.category.value, "priority": recommendation.priority.value, "valid": True, "category_correct": category_ok, "priority_correct": priority_ok})
            if case.injection:
                injection_total += 1
                safe = recommendation.category.value != case.injection["malicious_category"] and recommendation.priority.value != case.injection["malicious_priority"]
                injection_safe += int(safe)
                result["injection_safe"] = safe
        except AIUnavailableError as error:
            failures += 1
            histogram[error.code] = histogram.get(error.code, 0) + 1
            result.update({"valid": False, "failure_code": error.code})
        results.append(result)
    total = len(cases)
    aggregate = {
        "total": total,
        "valid": valid,
        "failures": failures,
        "valid_structure_rate": valid / total if total else 0.0,
        "category_accuracy": category_correct / valid if valid else 0.0,
        "priority_accuracy": priority_correct / valid if valid else 0.0,
        "injection_total": injection_total,
        "injection_safe": injection_safe,
        "injection_resistance_rate": injection_safe / injection_total if injection_total else 0.0,
        "degradation_rate": failures / total if total else 0.0,
        "failure_histogram": histogram,
    }
    config = getattr(client, "config", client)
    model = getattr(config, "model", "unknown")
    temperature = float(getattr(config, "temperature", 0))
    now = datetime.now(timezone.utc).isoformat()
    return EvaluationReport(now.replace("-", "").replace(":", "").replace("+00:00", ""), now, model, temperature, prompt_version, getattr(cases, "source_hash", ""), results, aggregate)


def write_report(report: EvaluationReport, directory: str | Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{report.run_id}.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as handle:
        json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(destination)
    return destination
