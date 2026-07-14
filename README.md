# Quantum Secure Messenger

A messenger where the AES encryption key is derived from real quantum-beacon
randomness combined with a post-quantum key exchange, built for the Light
Rider Qualification Contest.

**Demo video:

*(Note: the live demo runs on a Raspberry Pi 5 and depends on a physical
LED and local network access, so it isn't hosted as a permanent public URL.
The video above shows a full, real run of the working system.)*

---

## What algorithms/technologies this uses, and why each one was chosen

### 1. CURBy quantum entropy beacon (`random.colorado.edu`)
A public randomness beacon operated by CU Boulder / NIST, built on measuring
entangled photon pairs at two detectors ~100m apart. The statistical
correlations in the results can be shown, via Bell's theorem, to not have
been predetermined by any classical hidden mechanism -- a categorically
stronger unpredictability guarantee than ordinary hardware noise (a TRNG).

**Why it matters:** every cryptographic key is only as strong as the
randomness that generated it. A predictable random-number source is a
security hole regardless of how strong the encryption algorithm around it
is -- this has caused real historical breaches. Sourcing entropy from a
physically-certified process closes that gap at the root.

**What we found and how we handled it:** CURBy's live quantum source is
currently offline for a relocation/upgrade -- we verified this ourselves
(fetched the same round twice, confirmed the data was identical, unchanged
since August 2025). Rather than hide this or block the whole app on it, we
mix the CURBy pulse (real, even if currently stale) with fresh local
randomness + a timestamp, and disclose which mode is active
(`curby-quantum` / `curby-classical` / `local-fallback`) everywhere in the
UI. The architecture needs zero code changes to pick up live quantum
randomness again once CURBy's upgrade completes.

### 2. Statistical entropy health check (custom, `entropy_analysis.py`)
Before trusting the fetched bytes, we run three basic sanity checks: bit
balance, Shannon entropy (bits/byte), and serial correlation between
consecutive bytes.

**Why it matters:** this is a simplified version of the same category of
check defined formally in **NIST SP 800-90B**, the real standard for
validating physical entropy sources before they're trusted for
cryptographic use. Real validation needs far larger samples (SP 800-90B
requires roughly 1,000,000+ samples and several different min-entropy
estimators) -- our check is disclosed as indicative only, not a certified
result, but demonstrates the right category of thinking.

### 3. ML-KEM-768 (NIST-standardized post-quantum key exchange)
Classical key exchange (e.g. Diffie-Hellman) relies on math problems that a
sufficiently powerful quantum computer could solve quickly via Shor's
algorithm. Data encrypted today with classical-only key exchange could be
harvested now and decrypted later once such hardware exists
("harvest now, decrypt later"). ML-KEM is built on different math
(lattice-based problems) believed hard even for quantum computers, and was
standardized by NIST in 2024.

**Why it matters here:** this keeps the key exchange itself
quantum-resistant, independent of whether the entropy source is quantum.

### 4. HKDF-SHA3-256 (key derivation)
A standardized method (built on HMAC) for combining multiple secret inputs
of different origin -- here, the ML-KEM shared secret and the CURBy
entropy -- into a single, properly-sized, uniformly strong key, without
either input leaking a weakness through to the output.

**Why it matters:** this is what makes the quantum entropy *cryptographically
load-bearing* rather than just displayed on screen -- it's mathematically
mixed into the actual session key, so it materially contributes to the
final security, not just the UI narrative.

### 5. AES-256-GCM (message encryption)
Industry-standard authenticated symmetric encryption. "Authenticated" means
it doesn't just hide the message -- it cryptographically detects if the
ciphertext was tampered with in transit (verified live in the demo).

### 6. Physical LED signal (`pi_led.py`)
The Pi's onboard LED flashes on every entropy fetch, with blink count and
timing computed directly from the fetched random bytes -- a small, genuine
hardware expression of the actual randomness, not a canned animation.

---

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



## Where this could plug into Light Rider's actual work

- **QRNG/TRNG evaluation tooling:** `entropy_analysis.py` is a minimal,
  extensible starting point for a proper entropy health-check pipeline --
  could be extended toward real SP 800-90B-style min-entropy estimators.
- **LiFi:** both LiFi and QRNG fundamentally involve measuring/manipulating
  photons; a LiFi link could plausibly serve as a physical transport layer
  for distributing beacon-style randomness between devices, or as another
  physical entropy source to evaluate with the same tooling.
- **Error correction / privacy amplification:** the HKDF mixing step here
  is a toy version of "conditioning" a raw entropy source into
  higher-quality output -- the same conceptual step (usually more
  rigorous, e.g. Toeplitz-hashing extractors) sits between a raw QRNG/TRNG
  and its usable output in a production system.
- **Cloud platform integration:** the entropy-fetch + health-check +
  key-derivation pipeline here is stateless and could be exposed as an
  internal API/service other Light Rider systems call for
  quantum-enhanced key material, rather than being messenger-specific.

---

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo venv/bin/python3 app.py   # sudo needed for the onboard LED write
```

Open `http://<device-ip>:5000`. Click through: Fetch Quantum Entropy ->
Establish Secure Session -> type a message -> Send.

---





