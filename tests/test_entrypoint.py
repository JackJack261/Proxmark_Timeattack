"""Entry point tests. The Pm3Session is always faked: no real client is spawned."""
import pytest

from pm3trainer import __main__ as entry
from pm3trainer.session import Pm3Disconnected


class FakeSession:
    instances = []
    start_error = None

    def __init__(self, port=None):
        self.port = port
        self.started = False
        self.closed = False
        FakeSession.instances.append(self)

    def start(self):
        if FakeSession.start_error is not None:
            raise FakeSession.start_error
        self.started = True

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_session(monkeypatch):
    FakeSession.instances = []
    FakeSession.start_error = None
    monkeypatch.setattr(entry, "Pm3Session", FakeSession)
    return FakeSession


def test_main_reports_clean_exit_when_session_fails_to_start(capsys):
    FakeSession.start_error = Pm3Disconnected("no device")
    code = entry.main([])
    out = capsys.readouterr()
    assert code != 0
    assert "couldn't connect to the Proxmark" in (out.out + out.err)
    assert "Traceback" not in out.out + out.err
    assert FakeSession.instances[0].closed


def test_main_parses_port_arg(monkeypatch):
    def stop(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(entry, "run_game", stop)
    entry.main(["--port", "/dev/ttyACM1"])
    assert FakeSession.instances[0].port == "/dev/ttyACM1"


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(entry, "run_game", interrupt)
    code = entry.main([])
    out = capsys.readouterr()
    assert code != 0
    assert FakeSession.instances[0].closed
    assert "quit" in (out.out + out.err).lower()
    assert "Traceback" not in out.out + out.err


def test_main_handles_eof(monkeypatch, capsys):
    def eof(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(entry, "run_game", eof)
    code = entry.main([])
    out = capsys.readouterr()
    assert code != 0
    assert FakeSession.instances[0].closed
    assert "quit" in (out.out + out.err).lower()
    assert "Traceback" not in out.out + out.err
