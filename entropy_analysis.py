"""
Lightweight statistical health checks on fetched entropy bytes.

Not a full NIST SP 800-22 suite (that needs far larger samples than a
single ~64-byte pulse) -- this is the same *category* of first-pass sanity
check a TRNG/QRNG evaluation engineer runs before trusting a source:
bit balance, byte-value distribution (Shannon entropy), and a basic serial
correlation check. Directly relevant groundwork for QRNG/TRNG/error
correction work.

Honesty note: with only ~64 bytes, these numbers are indicative, not
statistically rigorous -- the UI must say so, not present them as a
certified NIST result.
"""
import math
from collections import Counter


def analyze(raw_bytes: bytes) -> dict:
    n_bytes = len(raw_bytes)
    n_bits = n_bytes * 8
    if n_bytes == 0:
        return {"error": "no bytes to analyze"}

    # Bit balance: ratio of 1-bits to total bits. Ideal unbiased source ~0.5
    ones = sum(bin(b).count("1") for b in raw_bytes)
    bit_balance = ones / n_bits

    # Shannon entropy per byte, in bits. Ideal uniform byte source: 8.0
    counts = Counter(raw_bytes)
    shannon_entropy = -sum((c / n_bytes) * math.log2(c / n_bytes) for c in counts.values())

    # Serial correlation between consecutive bytes (rough autocorrelation proxy)
    if n_bytes > 1:
        mean = sum(raw_bytes) / n_bytes
        num = sum((raw_bytes[i] - mean) * (raw_bytes[i + 1] - mean) for i in range(n_bytes - 1))
        den = sum((b - mean) ** 2 for b in raw_bytes)
        serial_correlation = num / den if den else 0.0
    else:
        serial_correlation = 0.0

    return {
        "n_bytes": n_bytes,
        "bit_balance": round(bit_balance, 4),
        "bit_balance_verdict": "within range" if 0.45 <= bit_balance <= 0.55 else "flagged -- small sample",
        "shannon_entropy_bits_per_byte": round(shannon_entropy, 4),
        "entropy_verdict": "within range" if shannon_entropy >= 7.0 else "flagged -- small sample",
        "serial_correlation": round(serial_correlation, 4),
        "sample_size_note": f"n={n_bytes} bytes -- indicative only, not a certified NIST SP 800-22 run",
    }
