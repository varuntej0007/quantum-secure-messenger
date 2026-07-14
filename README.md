# Quantum Secure Messenger

A messenger where the AES encryption key is derived from **real quantum-beacon
randomness** combined with a **post-quantum key exchange** — with every step,
including when the quantum source itself is unavailable, shown honestly to
the user instead of faked.

Built for the Light Rider Qualification Contest.

---

## What it does

Alice and Bob want to exchange an encrypted message without ever transmitting
the encryption key itself over the network. This app does that live, using:

1. **CURBy** (`random.colorado.edu`) — a public quantum randomness beacon run
   by CU Boulder / NIST, based on measuring entangled photon pairs at two
   separated detectors.
2. **ML-KEM-768** — a NIST-standardized post-quantum key encapsulation
   mechanism, so the key exchange itself stays secure even against a future
   quantum computer.
3. **AES-256-GCM** — standard authenticated encryption for the actual message.

The quantum entropy isn't just displayed — it's mixed into the final AES key
via HKDF, alongside the ML-KEM shared secret. Even in a hypothetical worst
case where one input were weak, the other still contributes real security.

## Architecture

```
Browser (Alice / Bob panels, live via SocketIO)
        |
        v
Flask + SocketIO server (app.py)
        |
        +--> curby_client.py  --> random.colorado.edu (real API call)
        |        |
        |        v
        |   entropy_analysis.py (bit balance / Shannon entropy / serial correlation)
        |        |
        |        v
        |   pi_led.py (flash pattern derived from the actual random bytes)
        |
        +--> crypto_engine.py
                 +- ML-KEM-768 keypair + encapsulate/decapsulate  (pqcrypto)
                 +- HKDF-SHA3-256(KEM secret + CURBy entropy) -> session key
                 +- AES-256-GCM encrypt/decrypt                  (cryptography)
```

## A real engineering decision, not a workaround

CURBy's live quantum photon source is currently offline for a relocation and
upgrade. We verified this ourselves (not just from documentation) by fetching
the "latest" pulse twice and diffing the response -- it hadn't changed since
August 2025. Rather than either pretending the beacon is live, or blocking
the whole app on it, we designed for this explicitly:

- The CURBy pulse (real, publicly verifiable, even if currently static) is
  mixed with a fresh local nonce and timestamp via SHA3-256, so every session
  still gets unique key material.
- The UI and the physical LED both disclose which mode is active
  (`curby-quantum` / `curby-classical` / `local-fallback`) rather than hiding it.
- The architecture requires no code changes to switch back to live quantum
  randomness the moment CURBy's upgrade finishes.

## The physical signal

The Raspberry Pi's onboard LED flashes whenever entropy is fetched. The
number of blinks and their timing are derived directly from the fetched
random bytes (`byte[0] mod 5 + 1` blinks, timing from `byte[1]`/`byte[2]`) --
a simple but genuine hardware expression of that session's real randomness,
running on the same board doing the cryptography.

## Entropy health check

Before using the fetched bytes, we run a lightweight statistical pass --
bit balance, Shannon entropy (bits/byte), and serial correlation -- the same
*category* of first-pass sanity check a TRNG/QRNG evaluation engineer runs
before trusting a source. With only ~64 bytes per pulse this is indicative,
not a certified NIST SP 800-22 run, and the UI says so explicitly.

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# the onboard LED requires root to write to /sys/class/leds/ACT/brightness
sudo venv/bin/python3 app.py
```

Open `http://192.168.1.2:5000` in a browser. Click through: Fetch Quantum
Entropy -> Establish Secure Session -> type a message -> Send.

## Live demo

**https://payphone-hyperlink-stratus.ngrok-free.dev/**

## Evaluation criteria, addressed directly

| Criteria | How this project addresses it |
|---|---|
| Creativity and originality | Honest handling of a beacon outage rather than hiding it; TRNG/QRNG-style health check; physical LED signal derived from real entropy bytes, not animation |
| Technical implementation | Real ML-KEM-768 + AES-256-GCM + HKDF, end-to-end verified; graceful fallback with no silent failure |
| Effective use of quantum entropy | Entropy is cryptographically load-bearing (feeds the actual AES key derivation), not just displayed |
| UX / interface quality | Live two-panel visualization with plain-English step-by-step explanations, so the pipeline is understandable without reading code |
