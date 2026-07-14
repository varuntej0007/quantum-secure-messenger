"""
CURBy entropy client.

Confirmed live behavior (tested 2026-07-10):
  - Endpoint: https://random.colorado.edu/api/curbyq/round/latest
  - Response is a list of 3 Twine chain entries (3-stage commit-reveal
    protocol): stage="request", stage="precommit", stage="randomness".
  - The "randomness" stage entry holds the actual output at:
        data.content.payload.randomness["/"]["bytes"]   (base64)
  - data.content.payload.parameters.isQuantum tells us whether this round
    was quantum- or classical-sourced. Currently: False (quantum source is
    offline for the relocation/upgrade CURBy has publicly announced).
  - The "latest" round has been frozen at round 28297 (Aug 2025) across
    repeated fetches -- the classical beacon is not advancing right now.
    We therefore treat the CURBy pulse as ONE ingredient, not the sole
    source of freshness, and mix in a local nonce + timestamp so every
    session key is still unique. This is disclosed to the UI, never hidden.
"""

import requests
import hashlib
import base64
import secrets
from datetime import datetime, timezone

from entropy_analysis import analyze as analyze_entropy

CURBY_URL = "https://random.colorado.edu/api/curbyq/round/latest"


def fetch_curby_pulse(timeout=8):
    """Fetch the latest CURBy round and extract the randomness-stage payload."""
    resp = requests.get(CURBY_URL, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    randomness_entry = None
    for item in data:
        payload = item.get("data", {}).get("content", {}).get("payload", {})
        if payload.get("stage") == "randomness":
            randomness_entry = payload
            break

    if randomness_entry is None:
        raise ValueError("no 'randomness' stage entry found in CURBy response")

    b64 = randomness_entry["randomness"]["/"]["bytes"]
    # base64 without padding is common in DAG-JSON -- pad defensively
    padded = b64 + "=" * (-len(b64) % 4)
    raw_bytes = base64.b64decode(padded)

    # isQuantum lives on the "request" stage entry's parameters, not here --
    # grab it too for transparency in the UI.
    is_quantum = None
    for item in data:
        payload = item.get("data", {}).get("content", {}).get("payload", {})
        if payload.get("stage") == "request":
            is_quantum = payload.get("parameters", {}).get("isQuantum")

    return {
        "round": randomness_entry["round"],
        "timestamp": randomness_entry["timestamp"],
        "raw_bytes": raw_bytes,
        "data_hash": randomness_entry.get("dataHash"),
        "is_quantum": is_quantum,
    }


def get_session_entropy():
    """
    Produce 32 bytes of seed material for this session, combining:
      - the CURBy pulse (real, publicly verifiable, even if currently frozen)
      - a fresh local CSPRNG nonce (guarantees per-session uniqueness)
      - a UTC timestamp (binds the derivation to *this* moment)

    Returns a dict Claude/the UI can display honestly, including a flag for
    whether the beacon appears frozen (round didn't change) vs failed entirely.
    """
    local_nonce = secrets.token_bytes(32)
    session_time = datetime.now(timezone.utc).isoformat().encode()

    try:
        pulse = fetch_curby_pulse()
        combined = hashlib.sha3_256(pulse["raw_bytes"] + local_nonce + session_time).digest()
        return {
            "seed_bytes": combined,
            "source": "curby-quantum" if pulse["is_quantum"] else "curby-classical",
            "curby_round": pulse["round"],
            "curby_timestamp": pulse["timestamp"],
            "curby_data_hash": pulse["data_hash"],
            "beacon_reachable": True,
            "note": "CURBy pulse mixed with local session nonce + timestamp for per-session uniqueness",
            "health_check": analyze_entropy(pulse["raw_bytes"]),
        }
    except Exception as e:
        # CURBy unreachable -- fully local fallback, clearly labeled
        combined = hashlib.sha3_256(local_nonce + session_time).digest()
        return {
            "seed_bytes": combined,
            "source": "local-fallback",
            "curby_round": None,
            "curby_timestamp": None,
            "curby_data_hash": None,
            "beacon_reachable": False,
            "note": f"CURBy unreachable ({e}); using local CSPRNG only",
            "health_check": analyze_entropy(local_nonce),
        }


if __name__ == "__main__":
    r = get_session_entropy()
    for k, v in r.items():
        print(f"{k}: {v}")
