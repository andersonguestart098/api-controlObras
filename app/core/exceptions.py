from typing import Any


class SankhyaAuthenticationError(RuntimeError):
    pass


class SankhyaRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_data: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class SankhyaQueryResponseError(RuntimeError):
    pass
