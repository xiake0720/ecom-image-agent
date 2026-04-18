"""应用级异常定义。"""

from __future__ import annotations


class AppException(RuntimeError):
    """可映射为统一 JSON 返回的业务异常。"""

    def __init__(self, message: str, *, code: int = 4000, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
