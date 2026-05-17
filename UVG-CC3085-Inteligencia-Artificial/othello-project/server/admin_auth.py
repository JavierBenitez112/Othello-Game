from __future__ import annotations

import os
import secrets
from secrets import compare_digest

from fastapi import HTTPException
from starlette import status


class AdminAuthManager:
    def __init__(self) -> None:
        self.username = os.getenv("ADMIN_USERNAME", "admin")
        self.password = os.getenv("ADMIN_PASSWORD", "admin123")
        self._tokens: set[str] = set()

    def login(self, username: str, password: str) -> str:
        if not compare_digest(username, self.username) or not compare_digest(password, self.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

        token = secrets.token_urlsafe(32)
        self._tokens.add(token)
        return token

    def validate_http_token(self, authorization_header: str | None) -> str:
        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin token")

        token = authorization_header.removeprefix("Bearer ").strip()
        if token not in self._tokens:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
        return token

    def validate_ws_token(self, token: str | None) -> bool:
        return bool(token and token in self._tokens)

    def default_credentials(self) -> dict[str, str]:
        return {"username": self.username, "password": self.password}
