from __future__ import annotations

import json

from .domain import AIRecommendation, Category, Priority
from .errors import AIUnavailableError


_FIELDS = {"category", "priority", "summary", "reason"}


def parse_recommendation(text: str) -> AIRecommendation:
    candidate = text.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    elif candidate.startswith("```") or candidate.endswith("```"):
        raise AIUnavailableError("invalid_response", "模型返回格式无效")
    try:
        value = json.loads(candidate)
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise ValueError("schema")
        if not isinstance(value["summary"], str) or not value["summary"].strip() or len(value["summary"]) > 200:
            raise ValueError("summary")
        if not isinstance(value["reason"], str) or not value["reason"].strip() or len(value["reason"]) > 300:
            raise ValueError("reason")
        recommendation = AIRecommendation(
            Category(value["category"]),
            Priority(value["priority"]),
            value["summary"].strip(),
            value["reason"].strip(),
        )
    except Exception as error:
        if isinstance(error, AIUnavailableError):
            raise
        raise AIUnavailableError("invalid_response", "模型返回的分类建议无效") from error
    return recommendation
