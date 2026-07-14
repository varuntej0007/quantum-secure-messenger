"""
Quantum Secure Messenger -- Flask + SocketIO backend.

Demo architecture (single-process, in-memory -- this is a live technical
demo, not a production multi-tenant service):
  - Bob's ML-KEM-768 identity keypair is generated once at server startup.
  - The browser shows two panels (Alice / Bob) that both talk to this
    same server over SocketIO, so every step of the pipeline can be
    broadcast and animated live for anyone watching.
  - Real crypto happens server-side in Python (pqcrypto + cryptography);
    the browser only displays state, it never fakes anything.
"""
import hashlib
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from pqcrypto.kem.ml_kem_768 import generate_keypair, encrypt as kem_encapsulate, decrypt as kem_decapsulate

from curby_client import get_session_entropy
from crypto_engine import derive_session_key, encrypt_message, decrypt_message
from pi_led import flash_led_from_entropy

app = Flask(__name__)
app.config["SECRET_KEY"] = "quantum-secure-messenger-demo"
socketio = SocketIO(app, cors_allowed_origins="*")

# Bob's identity keypair -- generated once when the server starts
bob_public, bob_secret = generate_keypair()
print(f"[startup] Bob's ML-KEM-768 keypair ready ({len(bob_public)} byte public key)")

# In-memory demo session state (single shared session, reset on request)
state = {"entropy": None, "session_key": None}


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("fetch_entropy")
def handle_fetch_entropy():
    entropy = get_session_entropy()
    state["entropy"] = entropy
    led_info = flash_led_from_entropy(entropy["seed_bytes"], entropy["source"])

    if entropy["source"] == "curby-quantum":
        source_plain = "a quantum physics experiment at CU Boulder (entangled photons)"
    elif entropy["source"] == "curby-classical":
        source_plain = "CURBy's classical backup beacon (their quantum source is offline for an upgrade right now)"
    else:
        source_plain = "this Pi's own secure random number generator (CURBy was unreachable)"

    explain = (
        f"We just asked CURBy for their latest random data. We got it from {source_plain}. "
        f"We mixed it with a fresh random number generated locally, so this session's data is "
        f"unique even if CURBy's number hasn't changed recently. We also ran a quick quality "
        f"check on the raw bytes (see below) to sanity-check the randomness looks healthy."
    )

    emit("entropy_result", {
        "source": entropy["source"],
        "beacon_reachable": entropy["beacon_reachable"],
        "curby_round": entropy["curby_round"],
        "curby_timestamp": entropy["curby_timestamp"],
        "curby_data_hash": entropy["curby_data_hash"],
        "seed_preview": entropy["seed_bytes"].hex()[:32] + "...",
        "note": entropy["note"],
        "health_check": entropy["health_check"],
        "led_info": led_info,
        "explain": explain,
    }, broadcast=True)


@socketio.on("establish_session")
def handle_establish_session():
    if state["entropy"] is None:
        emit("pipeline_error", {"message": "Fetch quantum entropy first."})
        return

    ciphertext, alice_kem_secret = kem_encapsulate(bob_public)
    alice_key = derive_session_key(alice_kem_secret, state["entropy"]["seed_bytes"])

    bob_kem_secret = kem_decapsulate(bob_secret, ciphertext)
    bob_key = derive_session_key(bob_kem_secret, state["entropy"]["seed_bytes"])

    keys_match = alice_key == bob_key
    if keys_match:
        state["session_key"] = alice_key

    emit("session_established", {
        "public_key_bytes": len(bob_public),
        "secret_key_bytes": len(bob_secret),
        "kem_ciphertext_bytes": len(ciphertext),
        "shared_secret_bytes": len(alice_kem_secret),
        "key_fingerprint": hashlib.sha256(alice_key).hexdigest()[:16],
        "keys_match": keys_match,
        "explain": (
            "Bob generated a public 'lock' (1184 bytes) and a private 'key' (2400 bytes) using "
            "ML-KEM-768 -- a lock-and-key system designed to stay secure even against future "
            "quantum computers. Alice used Bob's public lock, combined with the quantum entropy "
            "from step 1, to compute a shared secret password. Bob independently computed the "
            "SAME password using his private key. Neither side ever sent the password itself "
            "over the network -- that's the whole point."
        ),
    }, broadcast=True)


@socketio.on("send_message")
def handle_send_message(data):
    if state["session_key"] is None:
        emit("pipeline_error", {"message": "Establish the secure session first."})
        return

    plaintext = (data or {}).get("message", "").strip()
    if not plaintext:
        emit("pipeline_error", {"message": "Type a message first."})
        return

    packet = encrypt_message(state["session_key"], plaintext)
    emit("message_encrypted", {
        "nonce": packet["nonce"],
        "ciphertext": packet["ciphertext"],
        "explain": (
            "Alice's message was scrambled using AES-256-GCM with the shared secret from step 2. "
            "What you see below is unreadable ciphertext -- this is what would travel over the "
            "network if this were deployed publicly."
        ),
    }, broadcast=True)

    time.sleep(2)

    recovered = decrypt_message(state["session_key"], packet["nonce"], packet["ciphertext"])
    emit("message_decrypted", {
        "message": recovered,
        "verified": recovered == plaintext,
        "explain": (
            "Bob used his half of the shared secret to unscramble the ciphertext and got back "
            "the exact original message. 'Integrity verified: true' means AES-GCM also confirmed "
            "nothing was tampered with in transit."
        ),
    }, broadcast=True)


@socketio.on("reset_session")
def handle_reset():
    state["entropy"] = None
    state["session_key"] = None
    emit("session_reset", {}, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
