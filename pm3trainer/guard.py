"""Safety guard: block destructive Proxmark3 commands before they reach the device."""

import shlex
from dataclasses import dataclass
from typing import Optional


@dataclass
class CardState:
    """What the game knows about the card on the reader.

    password_set: True if the card is known to have a password, False if known
    to have none, None if unknown.
    """

    password_set: Optional[bool]


@dataclass
class GuardResult:
    allowed: bool
    reason: str


_PASSWORD_FLAGS = ("-p", "--pwd")


def _tokenize(cmd: str) -> list:
    try:
        return shlex.split(cmd)
    except ValueError:
        return cmd.split()


def _is_t55xx_read(tokens: list) -> bool:
    lowered = [t.lower() for t in tokens]
    return lowered[:3] == ["lf", "t55xx", "read"]


def _has_password_flag(tokens: list) -> bool:
    for token in tokens[3:]:
        if token in _PASSWORD_FLAGS:
            return True
        if token.startswith("--pwd="):
            return True
    return False


def check(cmd: str, card: CardState) -> GuardResult:
    """Decide whether `cmd` may be sent to the Proxmark3.

    Rule: `lf t55xx read` with a password flag (-p / --pwd) is blocked unless the
    card is known to have a password. Default-deny when the state is unknown.
    """
    tokens = _tokenize(cmd)
    if _is_t55xx_read(tokens) and _has_password_flag(tokens) and card.password_set is not True:
        return GuardResult(
            allowed=False,
            reason=(
                "Blocked: a T55xx password read (-p/--pwd) on a card that is not "
                "known to have a password set risks corrupting the tag's "
                "configuration. Confirm the card has a password first."
            ),
        )
    return GuardResult(allowed=True, reason="")
