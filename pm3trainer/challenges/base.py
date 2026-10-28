"""Challenge base class shared by all time-attack challenges."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pm3trainer.cards import CardKind


class Mode(Enum):
    CREATE = "create"
    READ = "read"


class Challenge:
    """One time-attack challenge.

    CREATE: the game runs the player's typed command first, then calls
    ``check(session, None)``, which reads the card back and compares it to
    the challenge's target.

    READ: the game calls ``setup(session)`` once (writes random ground truth
    to the card), then ``check(session, answer)`` with the player's answer.

    ``hints`` are ordered (first a nudge, last roughly the command with
    placeholders); ``solution`` is shown on pass. The game loop consumes both.

    ``check`` may set ``feedback`` to say what the card actually held; the game
    shows it after a wrong attempt.
    """

    name: str
    mode: Mode
    required_card: CardKind
    present_prompt: str
    task_prompt: str
    hints: list[str]
    solution: str
    feedback: str = ""

    def setup(self, session) -> None:
        """Prepare the card before the player answers. Default: nothing."""

    def check(self, session, player_input: Optional[str]) -> bool:
        raise NotImplementedError
