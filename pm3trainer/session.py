"""Persistent Proxmark3 client session driven over a pty via pexpect."""
from __future__ import annotations

import re
from typing import Optional

import pexpect

from pm3trainer.parsers import strip_ansi


class Pm3Timeout(Exception):
    """The client did not return to its prompt in time."""


class Pm3Disconnected(Exception):
    """The client process exited or the device went away."""


# The client prompt, tolerating ANSI colour codes around the "usb" token.
_ANSI = r"(?:\x1b\[[0-9;]*m)*"
PROMPT_RE = rf"\[{_ANSI}usb{_ANSI}\] pm3 -->"

_STARTUP_TIMEOUT = 30.0
# How long to wait for more stale output while draining before a command.
_DRAIN_TIMEOUT = 0.1


def _spawn(cmd: list[str]):
    """Spawn the client. Module-level so tests can substitute a stub.

    pexpect.spawn is POSIX-only; this is only called on the real target.
    """
    return pexpect.spawn(cmd[0], cmd[1:], encoding="utf-8", codec_errors="replace")


class Pm3Session:
    def __init__(self, port: Optional[str] = None, log_path: Optional[str] = None):
        self.port = port
        self.log_path = log_path
        self._child = None

    def start(self) -> None:
        cmd = ["pm3"] + ([self.port] if self.port else [])
        self._child = _spawn(cmd)
        self._expect_prompt(_STARTUP_TIMEOUT)

    def run(self, cmd: str, timeout: float = 20.0) -> str:
        if self._child is None:
            raise Pm3Disconnected("session not started")
        stale = self._drain()
        if stale.strip():
            self._log(f"--- discarded stale output ---\n{stale!r}\n")
        self._child.sendline(cmd)
        self._expect_prompt(timeout)
        self._log(f">>> {cmd}\n{self._child.before!r}\n")
        return self._clean(self._child.before, cmd)

    def close(self) -> None:
        if self._child is not None:
            try:
                self._child.close(force=True)
            finally:
                self._child = None

    def _drain(self) -> str:
        """Discard output that arrived after the last prompt.

        The client can redraw its prompt when the device prints while it is
        idle at the prompt. Left in the buffer, that extra prompt would end the
        next command's read early and shift every later output by one command.
        """
        stale = [self._child.buffer]
        self._child.buffer = ""
        while True:
            try:
                stale.append(self._child.read_nonblocking(65536, timeout=_DRAIN_TIMEOUT))
            except pexpect.TIMEOUT:
                return "".join(stale)
            except pexpect.EOF as e:
                raise Pm3Disconnected("pm3 client exited") from e

    def _log(self, text: str) -> None:
        if self.log_path is None:
            return
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            pass

    def _expect_prompt(self, timeout: float) -> None:
        try:
            self._child.expect(PROMPT_RE, timeout=timeout)
        except pexpect.EOF as e:
            raise Pm3Disconnected("pm3 client exited") from e
        except pexpect.TIMEOUT as e:
            raise Pm3Timeout(f"no prompt within {timeout}s") from e

    @staticmethod
    def _clean(raw: str, cmd: str) -> str:
        lines = strip_ansi(raw).replace("\r\n", "\n").replace("\r", "\n").split("\n")
        # The pty echoes the sent command back first; drop it.
        if lines and lines[0].strip().endswith(cmd.strip()):
            lines = lines[1:]
        return "\n".join(lines).strip()
