"""Challenge: read the EM410x ID that the game wrote to a T5577."""
from __future__ import annotations

import random
from typing import Optional

from pm3trainer.answers import norm_hex
from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.challenges.lf_em_create import CLONE_TEMPLATE


class LfEmRead(Challenge):
    name = "LF EM410x read"
    mode = Mode.READ
    required_card = CardKind.T5577
    present_prompt = "Place a blank T5577 on the reader."
    task_prompt = "The card now holds an EM410x ID. Read it and type the ID."

    def __init__(self, rng: random.Random):
        self._rng = rng
        self._truth: Optional[str] = None
        self.hints = [
            "EM410x is a low-frequency (lf) tag; try a command that auto-detects LF tags.",
            "Run 'lf search' and look for the line reporting the EM 410x ID.",
            "lf search -> read the 10-hex-digit value after 'EM 410x ID'.",
        ]

    @property
    def solution(self) -> str:
        return self._truth if self._truth is not None else ""

    def setup(self, session) -> None:
        self._truth = f"{self._rng.getrandbits(40):010x}"
        session.run(CLONE_TEMPLATE.format(id=self._truth))

    def check(self, session, player_input: Optional[str]) -> bool:
        if self._truth is None or player_input is None:
            return False
        return norm_hex(player_input) == norm_hex(self._truth)
