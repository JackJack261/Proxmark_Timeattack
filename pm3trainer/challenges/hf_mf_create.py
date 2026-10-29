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

# A Mifare Classic 4-byte UID's first byte is the manufacturer code. Keep it
# fixed to NXP (0x04) so the randomized UID is always a valid, readable Mifare
# card -- a random first byte can clobber this (0x88 is read as a cascade tag).
UID_MANUFACTURER_BYTE = "04"


def random_mifare_uid(rng: random.Random) -> str:
    """A random 4-byte UID (8 hex) with a valid NXP manufacturer first byte."""
    return UID_MANUFACTURER_BYTE + f"{rng.getrandbits(24):06x}"


class HfMfCreate(Challenge):
    name = "HF Mifare Classic create"
    mode = Mode.CREATE
    required_card = CardKind.MAGIC_MIFARE
    present_prompt = "Place a magic Mifare Classic card on the reader."

    def __init__(self, rng: random.Random):
        self.uid = random_mifare_uid(rng)
        self.task_prompt = f"Set the UID of the magic Mifare Classic card to {self.uid}."
        self.hints = [
            "Mifare Classic is a high-frequency (hf) tag; look under 'hf mf' for a UID-changing command.",
            "Only magic (Chinese backdoor) cards accept a UID change; the command is a 'c' (magic) command that takes the UID as an argument.",
            SET_UID_TEMPLATE.format(uid="<UID>"),
        ]
        self.solution = SET_UID_TEMPLATE.format(uid=self.uid)

    def check(self, session, player_input: Optional[str]) -> bool:
        found = parse_mifare_uid(session.run(READ_COMMAND))
        if found is not None and norm_hex(found) == norm_hex(self.uid):
            return True
        self.feedback = (
            f"The card reads as UID {found.upper()}." if found
            else f"No UID could be read from the card ('{READ_COMMAND}')."
        )
        return False
