import re

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
        self.buffer = ""

    def sendline(self, line):
        self.sent.append(line)

    def read_nonblocking(self, size, timeout=None):
        raise pexpect.TIMEOUT("idle")

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


# The Iceman prompt as it reaches the pty (bracketed-paste on, green "usb").
PROMPT = "\x1b[?2004h[\x1b[1;32musb\x1b[0m] pm3 --> "


class StreamChild:
    """Byte-stream stand-in: replies arrive as text followed by a prompt."""

    def __init__(self, replies, buffer="", incoming=""):
        self.replies = replies
        self.buffer = buffer        # unmatched data left by the previous expect
        self._incoming = incoming   # data the client wrote but not yet read
        self.before = ""
        self.sent = []

    def sendline(self, line):
        self.sent.append(line)
        self._incoming += line + "\r\n" + self.replies[line] + PROMPT

    def read_nonblocking(self, size, timeout=None):
        if not self._incoming:
            raise pexpect.TIMEOUT("idle")
        data, self._incoming = self._incoming, ""
        return data

    def expect(self, pattern, timeout=None):
        self.buffer += self._incoming
        self._incoming = ""
        m = re.search(pattern, self.buffer)
        if m is None:
            raise pexpect.TIMEOUT("no prompt")
        self.before, self.buffer = self.buffer[:m.start()], self.buffer[m.end():]
        return 0

    def close(self, force=True):
        pass


def test_run_matches_real_prompt():
    s = Pm3Session()
    s._child = StreamChild({"lf hid reader": "[+] FC: 1  CN: 2\r\n"})
    assert s.run("lf hid reader") == "[+] FC: 1  CN: 2"


def test_run_discards_redrawn_prompt_so_outputs_stay_in_step():
    # The client redrew its prompt while idle (device message at the prompt):
    # one copy is already buffered, another is still unread on the pty.
    replies = {
        "lf hid clone -w H10301 --fc 215 --cn 31667": "[+] Done!\r\n",
        "lf hid reader": "[+] [H10301  ] HID H10301 26-bit  FC: 215  CN: 31667\r\n",
    }
    child = StreamChild(replies, buffer="\r\n" + PROMPT, incoming="\r\n" + PROMPT)
    s = Pm3Session()
    s._child = child
    assert s.run("lf hid clone -w H10301 --fc 215 --cn 31667") == "[+] Done!"
    assert "CN: 31667" in s.run("lf hid reader")


def test_run_raises_disconnected_on_eof_while_draining():
    class EofChild(StubChild):
        def read_nonblocking(self, size, timeout=None):
            raise pexpect.EOF("gone")

    s = Pm3Session()
    s._child = EofChild()
    with pytest.raises(Pm3Disconnected):
        s.run("hw status")


def test_log_records_commands_and_raw_output(tmp_path):
    log = tmp_path / "pm3.log"
    s = Pm3Session(log_path=str(log))
    s._child = StreamChild({"lf search": "[+] Chipset... T55xx\r\n"}, incoming="stale\r\n")
    s.run("lf search")
    text = log.read_text()
    assert "discarded stale output" in text and "stale" in text
    assert ">>> lf search" in text
    assert "Chipset... T55xx" in text
