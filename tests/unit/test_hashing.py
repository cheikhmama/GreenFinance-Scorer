from app.auth.hashing import hash_password, verify_password


def test_verify_password_accepts_the_original_password() -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", hashed)


def test_verify_password_rejects_a_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")

    assert not verify_password("wrong password", hashed)


def test_hash_password_never_stores_the_plaintext() -> None:
    password = "correct horse battery staple"

    assert password not in hash_password(password)


def test_hash_password_is_salted_and_therefore_not_deterministic() -> None:
    password = "correct horse battery staple"

    assert hash_password(password) != hash_password(password)
