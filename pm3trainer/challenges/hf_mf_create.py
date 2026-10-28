"""Challenge: set the UID of a magic Mifare Classic card to a given value."""
from __future__ import annotations

import random
from typing import Optional

from pm3trainer.answers import norm_hex
from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.parsers import parse_mifare_uid

READ_COMMAND = "hf mf info"
SET_UID_TEMPLATE = "hf mf csetuid -u {uid}"


class HfMfCreate(Challenge):
    name = "HF Mifare Classic create"
    mode = Mode.CREATE
    required_card = CardKind.MAGIC_MIFARE
    present_prompt = "Place a magic Mifare Classic card on the reader."

    def __init__(self, rng: random.Random):
        self.uid = f"{rng.getrandbits(32):08x}"
        self.task_prompt = f"Set the UID of the magic Mifare Classic card to {self.uid}."
        self.hints = [
            "Mifare Classic is a high-frequency (hf) tag; look under 'hf mf' for a UID-changing command.",
            "Only magic (Chinese backdoor) cards accept a UID change; the command is a 'c' (magic) command that takes the UID as an argument.",
            SET_UID_TEMPLATE.format(uid="<UID>"),
        ]
        self.solution = SET_UID_TEMPLATE.format(uid=self.uid)

    def check(self, session, player_input: Optional[str]) -> bool:
        found = parse_mifare_uid(session.run(READ_COMMAND))
        return found is not None and norm_hex(found) == norm_hex(self.uid)
