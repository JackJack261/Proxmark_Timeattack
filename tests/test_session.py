import pexpect
import pytest

from pm3trainer import session as session_mod
from pm3trainer.session import Pm3Disconnected, Pm3Session, Pm3Timeout
from pm3trainer.testing import FakeSession


class StubChild:
    """Stand-in for a pexpect.spawn object; never touches a real client."""

    def __init__(self, before="", raises=None):
        self._before = before
        self._raises = raises
        self.before = ""
        self.sent = []
        self.closed = False

    def sendline(self, line):
        self.sent.append(line)

    def expect(self, pattern, timeout=None):
        if self._raises is not None:
            raise self._raises
        self.before = self._before
        return 0

    def close(self, force=True):
        self.closed = True


def _session_with(monkeypatch, child):
    monkeypatch.setattr(session_mod, "_spawn", lambda cmd: child)
    s = Pm3Session()
    s._child = child  # skip start(): no startup handshake needed for run()
    return s


def test_fake_session_records_sent_and_returns_response():
    fake = FakeSession({"hw status": "ok output"})
    assert fake.run("hw status") == "ok output"
    assert fake.sent == ["hw status"]


def test_fake_session_raises_configured_error():
    fake = FakeSession({}, fail=Pm3Timeout("slow"))
    with pytest.raises(Pm3Timeout):
        fake.run("lf search")
    assert fake.sent == ["lf search"]


def test_run_strips_ansi_from_output(monkeypatch):
    raw = "hw status\r\n\x1b[1;32mhello\x1b[0m world\r\n"
    s = _session_with(monkeypatch, StubChild(before=raw))
    assert s.run("hw status") == "hello world"


def test_run_raises_disconnected_on_eof(monkeypatch):
    s = _session_with(monkeypatch, StubChild(raises=pexpect.EOF("gone")))
    with pytest.raises(Pm3Disconnected):
        s.run("hw status")


def test_run_raises_timeout(monkeypatch):
    s = _session_with(monkeypatch, StubChild(raises=pexpect.TIMEOUT("slow")))
    with pytest.raises(Pm3Timeout):
        s.run("hw status", timeout=0.1)
