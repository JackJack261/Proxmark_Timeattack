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
python3 pm3trainer.py [--port /dev/ttyACM0] [--log pm3.log]
```

`--port` is optional; without it the `pm3` client picks the device itself.
`--log FILE` appends every command the game sends and the client's raw output
to `FILE`, which helps when a check doesn't behave as expected.
Your best total time is saved to `scores.json` in the directory you run from.

## The challenges

1. **LF HID Prox create** - write a given HID Prox credential (facility code + card number) onto a T5577.
2. **LF EM410x create** - write a given EM410x ID onto a T5577.
3. **HF Mifare Classic create** - write a given UID onto a magic Mifare card.
4. **HF iClass create** - write the given credential onto a writable iClass card.
5. **LF EM410x read** - the game writes an EM410x ID to a T5577; read it and report the ID.
6. **HF Mifare UID read** - the game sets a UID on a magic Mifare card; read it and report the UID.

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
