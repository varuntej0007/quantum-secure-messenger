"""
Onboard LED control for Raspberry Pi 5 (ACT LED).

Confirmed on this hardware (2026-07-10):
  - /sys/class/leds/ACT/brightness exists, mode rw-r--r--, owned root:root
  - Writing requires root (gpio group membership does NOT cover this file
    on Pi 5 by default)
  - Run app.py as:  sudo venv/bin/python3 app.py
    (keeps the venv's installed packages while getting write access)

Never crashes the app if the LED isn't writable -- logs a warning once and
the crypto pipeline keeps working regardless. The LED is a bonus signal,
never a dependency.
"""
import threading
import time

LED_PATH = "/sys/class/leds/ACT/brightness"

_led_available = None


def _check_led():
    global _led_available
    if _led_available is not None:
        return _led_available
    try:
        with open(LED_PATH, "w") as f:
            f.write("0")
        _led_available = True
        print("[pi_led] ACT LED is writable -- physical entropy signal enabled.")
    except Exception as e:
        print(f"[pi_led] LED not writable ({e}). Run with: sudo venv/bin/python3 app.py "
              f"to enable it. Continuing without physical LED.")
        _led_available = False
    return _led_available


def _write(value):
    try:
        with open(LED_PATH, "w") as f:
            f.write(str(value))
    except Exception:
        pass


def _read():
    try:
        with open(LED_PATH) as f:
            return int(f.read().strip())
    except Exception:
        return None


def flash_led(times=2, on_time=0.15, off_time=0.15):
    """Flash the onboard ACT LED. Runs synchronously and returns the raw
    readback sequence (actual values read from the sysfs file after each
    write) -- the same numbers you'd see running it by hand in the
    terminal, now available to show in the UI too."""
    readout = []
    if not _check_led():
        return readout

    for _ in range(times):
        _write(1)
        readout.append(_read())
        time.sleep(on_time)
        _write(0)
        readout.append(_read())
        time.sleep(off_time)

    return readout


# Distinct flash patterns per entropy source -- the LED itself tells the
# truth about where the randomness came from, same principle as the UI.
_PATTERNS = {
    "curby-quantum":   dict(times=3, on_time=0.08, off_time=0.08),  # fast triple
    "curby-classical": dict(times=2, on_time=0.20, off_time=0.20),  # slower double
    "local-fallback":  dict(times=1, on_time=0.60, off_time=0.10),  # single long
}


def flash_led_for_source(source: str):
    flash_led(**_PATTERNS.get(source, dict(times=1, on_time=0.2, off_time=0.2)))


def flash_led_from_entropy(seed_bytes: bytes, source: str = None):
    """Derive the flash pattern directly from the actual session seed bytes,
    so the physical signal reflects genuine randomness instead of a fixed
    label. Falls back to the source-based pattern if no bytes are available.

    byte[0] -> number of blinks (1-5)
    byte[1] -> on-time   (60-310ms)
    byte[2] -> off-time  (60-210ms)

    Returns a dict describing the pattern used, regardless of whether the
    LED write actually succeeded -- so the UI can honestly describe the
    physical event even when the hardware isn't visible.
    """
    if not seed_bytes or len(seed_bytes) < 3:
        pattern = _PATTERNS.get(source, dict(times=1, on_time=0.2, off_time=0.2))
        readout = flash_led(**pattern)
        return {"blinks": pattern["times"], "on_ms": int(pattern["on_time"] * 1000),
                "derived_from_bytes": False, "led_writable": _check_led(),
                "raw_readout": readout}

    n_blinks = 1 + (seed_bytes[0] % 5)
    on_time = 0.06 + (seed_bytes[1] / 255) * 0.25
    off_time = 0.06 + (seed_bytes[2] / 255) * 0.15
    readout = flash_led(times=n_blinks, on_time=on_time, off_time=off_time)
    return {"blinks": n_blinks, "on_ms": int(on_time * 1000),
            "derived_from_bytes": True, "led_writable": _check_led(),
            "raw_readout": readout}
