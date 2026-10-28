# Proxmark3 Time Attack

A terminal game that trains you to drive a Proxmark3. It drops you into a live
`pm3` session and times you through six challenges: read tags and write cards
using real Proxmark3 commands. Use `hint` and `pass` if you get stuck, at a cost
to your time.

## Install

Target platform is Kali Linux with the Proxmark3 client (`pm3`) on your `PATH`.

```
sudo apt install python3-pexpect
pip install pytest        # only needed to run the tests
```

## Cards you need

The write challenges need rewritable cards:

- **LF:** T5577 cards (for the EM410x and HID create challenges)
- **HF Mifare:** magic / gen1a or gen2 Mifare Classic cards
- **HF iClass:** writable iClass cards

## Run

```
python3 pm3trainer.py [--port /dev/ttyACM0]
```

`--port` is optional; without it the `pm3` client picks the device itself.
Your best total time is saved to `scores.json` in the directory you run from.

## The challenges

1. **LF EM410x read** - read an EM410x tag and report its ID.
2. **LF EM410x create** - write a given EM410x ID onto a T5577.
3. **LF HID create** - write a given HID Prox credential onto a T5577.
4. **HF Mifare Classic read** - read a Mifare Classic card and report the requested detail.
5. **HF Mifare Classic create** - write a given UID onto a magic Mifare card.
6. **HF iClass create** - write the given credential onto a writable iClass card.

Your final score is the total time across all challenges, penalties included.

## Hints and passing

Type either at the prompt during a challenge:

- `hint` - shows a hint, adds **30 seconds** to that challenge.
- `pass` - skips the challenge, adds **180 seconds**.

## Tests

```
python -m pytest -q
```

The tests use a fake session; no Proxmark3 is needed.

## Status

The game is complete, but the exact `pm3` command strings and output parsing
are calibrated against real hardware in a later step (Task 15). Command fidelity
is tuned on-device, so expect adjustments when first run against a real Proxmark3.
