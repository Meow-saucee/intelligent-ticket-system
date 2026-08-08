from __future__ import annotations

from .domain import Category, Priority
from .errors import ConflictError, ValidationError
from .repository import TicketRepository
from .domain import utc_now


class ReviewService:
    def __init__(self, repository: TicketRepository):
        self.repository = repository

    def review(
        self,
        suggestion_id: int,
        action: str,
        reviewer: str,
        category: Category | str | None = None,
        priority: Priority | str | None = None,
    ):
        reviewer = reviewer.strip()
        if not reviewer:
            raise ValidationError("审核人不能为空")
        if action not in {"confirm", "modify", "reject"}:
            raise ValidationError("审核动作必须是 confirm、modify 或 reject")
        if action == "modify" and (category is None or priority is None):
            raise ValidationError("modify 必须同时提供分类和优先级")
        if action == "reject" and (category is not None or priority is not None):
            raise ValidationError("reject 不能提供最终分类或优先级")
        if action == "confirm" and ((category is None) != (priority is None)):
            raise ValidationError("confirm 覆盖值必须同时提供分类和优先级")
        if category is not None:
            try:
                category = Category(category)
            except ValueError as error:
                raise ValidationError("最终分类无效") from error
            if category is Category.UNCLASSIFIED:
                raise ValidationError("最终分类不能是 unclassified")
        if priority is not None:
            try:
                priority = Priority(priority)
            except ValueError as error:
                raise ValidationError("最终优先级无效") from error
        suggestion = self.repository.get_suggestion(suggestion_id)
        if suggestion.status.value != "pending":
            raise ConflictError("AI 建议已经处理，不能重复审核")
        if action == "confirm" and category is None:
            category = suggestion.original_category
            priority = suggestion.original_priority
        if action in {"confirm", "modify"} and (category is None or priority is None):
            raise ValidationError("AI 建议缺少可生效的分类或优先级")
        return self.repository.review_suggestion(
            suggestion_id,
            action=action,
            reviewer=reviewer,
            final_category=category,
            final_priority=priority,
            now=utc_now(),
        )
