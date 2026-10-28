"""Challenge: read the UID that the game wrote to a magic Mifare Classic card."""
from __future__ import annotations

import random
from typing import Optional

from pm3trainer.answers import norm_hex
from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode

WRITE_TEMPLATE = "hf mf csetuid -u {uid}"


class HfMfRead(Challenge):
    name = "HF Mifare Classic read"
    mode = Mode.READ
    required_card = CardKind.MAGIC_MIFARE
    present_prompt = "Place a magic Mifare Classic card on the reader."
    task_prompt = "The card now has a UID. Read it and type the UID."

    def __init__(self, rng: random.Random):
        self._rng = rng
        self._truth: Optional[str] = None
        self.hints = [
            "Mifare Classic is a high-frequency (hf) tag; try a command that auto-detects HF tags.",
            "Run 'hf search' to identify the card, or 'hf mf info' for Mifare Classic details.",
            "hf search / hf mf info -> read the 4-byte (8-hex-digit) value after 'UID'.",
        ]

    @property
    def solution(self) -> str:
        return self._truth if self._truth is not None else ""

    def setup(self, session) -> None:
        self._truth = f"{self._rng.getrandbits(32):08x}"
        session.run(WRITE_TEMPLATE.format(uid=self._truth))

    def check(self, session, player_input: Optional[str]) -> bool:
        if self._truth is None or player_input is None:
            return False
        return norm_hex(player_input) == norm_hex(self._truth)
