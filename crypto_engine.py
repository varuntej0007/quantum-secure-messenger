"""
Full Quantum Secure Messenger crypto pipeline.

Flow:
  1. Bob generates an ML-KEM-768 keypair, publishes public_key.
  2. Alice fetches CURBy entropy (quantum/classical pulse + local nonce mix).
  3. Alice encapsulates against Bob's public_key -> (ciphertext, kem_secret).
  4. Both sides derive the SAME AES key via:
         session_key = HKDF-SHA3-256( kem_secret || curby_entropy )
     -- this means the quantum entropy is cryptographically mixed into
     every session key, not just displayed as a number on screen.
  5. Alice encrypts her message with AES-256-GCM under session_key.
  6. Bob decapsulates the ciphertext -> same kem_secret, re-derives the
     same session_key using the CURBy entropy Alice sent alongside the
     ciphertext, and decrypts.
"""
import os
import hashlib
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pqcrypto.kem.ml_kem_768 import generate_keypair, encrypt as kem_encapsulate, decrypt as kem_decapsulate

from curby_client import get_session_entropy


def derive_session_key(kem_shared_secret: bytes, curby_seed: bytes) -> bytes:
    """Combine the KEM shared secret with quantum-derived entropy via HKDF-SHA3-256."""
    hkdf = HKDF(
        algorithm=hashes.SHA3_256(),
        length=32,
        salt=None,
        info=b"quantum-secure-messenger-session-key",
    )
    return hkdf.derive(kem_shared_secret + curby_seed)


def encrypt_message(session_key: bytes, plaintext: str) -> dict:
    aesgcm = AESGCM(session_key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return {"nonce": nonce.hex(), "ciphertext": ct.hex()}


def decrypt_message(session_key: bytes, nonce_hex: str, ciphertext_hex: str) -> str:
    aesgcm = AESGCM(session_key)
    nonce = bytes.fromhex(nonce_hex)
    ct = bytes.fromhex(ciphertext_hex)
    return aesgcm.decrypt(nonce, ct, None).decode()


def full_demo():
    print("=== Bob: generate ML-KEM-768 keypair ===")
    bob_public, bob_secret = generate_keypair()
    print("public_key:", len(bob_public), "bytes")

    print("\n=== Alice: fetch CURBy entropy ===")
    entropy = get_session_entropy()
    print("source:", entropy["source"], "| beacon_reachable:", entropy["beacon_reachable"])

    print("\n=== Alice: encapsulate against Bob's public key ===")
    ciphertext, alice_kem_secret = kem_encapsulate(bob_public)
    alice_session_key = derive_session_key(alice_kem_secret, entropy["seed_bytes"])
    print("session_key (Alice):", alice_session_key.hex())

    print("\n=== Alice: encrypt message ===")
    message = "Hello Bob, this message is protected by quantum entropy + ML-KEM-768."
    packet = encrypt_message(alice_session_key, message)
    print("nonce:", packet["nonce"])
    print("ciphertext:", packet["ciphertext"][:60], "...")

    print("\n=== Bob: decapsulate ciphertext ===")
    bob_kem_secret = kem_decapsulate(bob_secret, ciphertext)
    # Bob needs the SAME curby seed bytes Alice used -- in the real app,
    # Alice sends entropy["seed_bytes"] alongside the KEM ciphertext
    # (both are safe to transmit; neither reveals the AES key alone).
    bob_session_key = derive_session_key(bob_kem_secret, entropy["seed_bytes"])
    print("session_key (Bob):  ", bob_session_key.hex())
    print("KEYS MATCH:", alice_session_key == bob_session_key)

    print("\n=== Bob: decrypt message ===")
    recovered = decrypt_message(bob_session_key, packet["nonce"], packet["ciphertext"])
    print("recovered:", recovered)
    print("MESSAGE MATCH:", recovered == message)


if __name__ == "__main__":
    full_demo()
