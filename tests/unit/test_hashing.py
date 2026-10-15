from app.auth.hashing import hash_password, verifier_et_mettre_a_jour, verify_password


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


# Hachage écrit par passlib (bcrypt, coût 12) avant le passage à pwdlib — comptes existants.
MOT_DE_PASSE_ANCIEN = "MotDePasse-Ancien-2024"
HACHAGE_BCRYPT_ANCIEN = "$2b$12$O1.l2kZZqHq.ebGOTGlS.u.gyLRi2oSI63T5vo3KmWbrdKhpksKDW"


def test_new_hashes_are_argon2id_with_owasp_parameters() -> None:
    assert hash_password("correct horse battery staple").startswith("$argon2id$v=19$m=19456,t=2,p=1$")


def test_existing_bcrypt_hash_is_still_verified() -> None:
    assert verify_password(MOT_DE_PASSE_ANCIEN, HACHAGE_BCRYPT_ANCIEN)
    assert not verify_password("wrong password", HACHAGE_BCRYPT_ANCIEN)


def test_bcrypt_hash_is_replaced_by_argon2id_on_successful_verification() -> None:
    valide, nouveau = verifier_et_mettre_a_jour(MOT_DE_PASSE_ANCIEN, HACHAGE_BCRYPT_ANCIEN)

    assert valide
    assert nouveau is not None and nouveau.startswith("$argon2id$")
    assert verify_password(MOT_DE_PASSE_ANCIEN, nouveau)


def test_current_hash_is_not_replaced_and_wrong_password_gives_no_new_hash() -> None:
    actuel = hash_password("correct horse battery staple")

    assert verifier_et_mettre_a_jour("correct horse battery staple", actuel) == (True, None)
    assert verifier_et_mettre_a_jour("wrong password", HACHAGE_BCRYPT_ANCIEN) == (False, None)


def test_password_over_72_bytes_against_bcrypt_hash_is_rejected_without_error() -> None:
    trop_long = "é" * 40  # 80 octets en UTF-8 : bcrypt >= 5 lèverait ValueError

    assert not verify_password(trop_long, HACHAGE_BCRYPT_ANCIEN)
    assert not verify_password(MOT_DE_PASSE_ANCIEN + "x" * 60, HACHAGE_BCRYPT_ANCIEN)
    assert verifier_et_mettre_a_jour(trop_long, HACHAGE_BCRYPT_ANCIEN) == (False, None)


def test_argon2id_hashes_the_whole_password_beyond_72_bytes() -> None:
    prefixe = "a" * 72
    hashed = hash_password(prefixe + "suite-1")

    assert verify_password(prefixe + "suite-1", hashed)
    assert not verify_password(prefixe + "suite-2", hashed)
    assert not verify_password(prefixe, hashed)
