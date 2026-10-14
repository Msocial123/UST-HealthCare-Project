from app.core.passwords import hash_password, needs_rehash, verify_password

PASSWORD = "Synthetic-Passw0rd-123"


def test_hash_is_argon2id_and_not_plaintext() -> None:
    hashed = hash_password(PASSWORD)
    assert hashed != PASSWORD
    assert PASSWORD not in hashed
    assert hashed.startswith("$argon2id$")
    assert not needs_rehash(hashed)


def test_hashes_are_salted() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_verify_password() -> None:
    hashed = hash_password(PASSWORD)
    assert verify_password(hashed, PASSWORD)
    assert not verify_password(hashed, PASSWORD + "x")


def test_verify_password_with_corrupt_hash_returns_false() -> None:
    assert not verify_password("not-a-valid-hash", PASSWORD)
