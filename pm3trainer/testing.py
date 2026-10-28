"""Test doubles shared by the test suite."""
from __future__ import annotations

from typing import Callable, Optional, Union


class FakeSession:
    """Drop-in for Pm3Session: canned responses, records commands in .sent."""

    def __init__(
        self,
        responses: Union[dict[str, str], Callable[[str], str]],
        *,
        fail: Optional[Exception] = None,
    ):
        self._responses = responses
        self._fail = fail
        self.sent: list[str] = []

    def start(self) -> None:
        pass

    def run(self, cmd: str, timeout: float = 20.0) -> str:
        self.sent.append(cmd)
        if self._fail is not None:
            raise self._fail
        if callable(self._responses):
            return self._responses(cmd)
        return self._responses.get(cmd, "")

    def close(self) -> None:
        pass
