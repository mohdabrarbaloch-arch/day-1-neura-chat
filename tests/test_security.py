"""Tests for password hashing and JWT helpers."""

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_plaintext():
    hashed = hash_password("supersecret123")
    assert hashed != "supersecret123"
    assert hashed.startswith("$2")


def test_hash_is_salted_so_two_hashes_differ():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_verify_rejects_malformed_hash():
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_long_password_is_truncated_not_rejected():
    # bcrypt caps at 72 bytes; a 200-char password must still round-trip.
    long_password = "a" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed) is True


def test_token_round_trip():
    token = create_access_token(42)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"


def test_token_rejects_tampering():
    token = create_access_token(7)
    assert decode_access_token(token + "x") is None


def test_expired_token_is_rejected():
    token = create_access_token(1, expires_minutes=-1)
    assert decode_access_token(token) is None
