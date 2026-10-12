from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 400,
        retry_after_seconds: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    payload = {"detail": exc.message, "code": exc.code}
    if exc.retry_after_seconds is not None:
        payload["retry_after_seconds"] = exc.retry_after_seconds
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
    )
