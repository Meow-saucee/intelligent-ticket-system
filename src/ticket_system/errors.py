class TicketSystemError(Exception):
    exit_code = 3

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class ValidationError(TicketSystemError):
    exit_code = 2


class NotFoundError(TicketSystemError):
    pass


class ConflictError(TicketSystemError):
    pass


class DuplicateTicketError(ConflictError):
    def __init__(self, existing_id: str) -> None:
        self.existing_id = existing_id
        super().__init__(f"检测到 24 小时内的重复工单：{existing_id}")


class AIUnavailableError(TicketSystemError):
    exit_code = 4

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
