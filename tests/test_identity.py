import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from services.identity import IdentityVerifier
from services.organizations import Registry


@pytest.fixture
def identity():
    registry = Registry.model_validate(
        {
            "environment": "production",
            "organizations": [
                {
                    "id": "north",
                    "name": "North",
                    "database_url": "sqlite:///north.db",
                    "artifact_dir": "artifacts/release",
                }
            ],
            "identity_provider": {
                "issuer": "https://issuer.example",
                "audience": "fraudgraph",
                "jwks_url": "https://issuer.example/keys",
            },
            "memberships": [{"subject": "alice", "organization": "north", "roles": ["viewer"]}],
        }
    )
    verifier = IdentityVerifier(registry)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier.client = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
    )
    now = int(time.time())
    claims = {
        "sub": "alice",
        "org": "north",
        "iss": "https://issuer.example",
        "aud": "fraudgraph",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
    }
    return verifier, key, claims


def encode(key, claims):
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "local-test"})


def test_verified_identity_uses_server_roles(identity):
    verifier, key, claims = identity
    claims["roles"] = ["admin"]
    assert verifier.verify(encode(key, claims)) == {
        "subject": "alice",
        "organization": "north",
        "roles": ["viewer"],
    }


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "https://attacker.example"},
        {"aud": "other"},
        {"org": "south"},
        {"sub": "mallory"},
        {"exp": 1},
        {"exp": int(time.time()) + 7200},
        {"nbf": int(time.time()) + 300},
        {"org": ["north"]},
        {"iat": "123"},
    ],
)
def test_invalid_claims_fail_closed(identity, change):
    verifier, key, claims = identity
    claims.update(change)
    assert verifier.verify(encode(key, claims)) is None


def test_signature_algorithm_and_missing_claims(identity):
    verifier, key, claims = identity
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert verifier.verify(encode(other, claims)) is None
    assert verifier.verify(jwt.encode(claims, "", algorithm="none")) is None
    assert verifier.verify(b"invalid") is None
    assert verifier.verify("a" * 8193) is None
    for name in ("exp", "iat", "nbf", "org", "sub"):
        assert verifier.verify(encode(key, {k: v for k, v in claims.items() if k != name})) is None


def test_production_requires_external_identity():
    with pytest.raises(ValueError, match="identity-provider"):
        Registry.model_validate(
            {
                "environment": "production",
                "organizations": [
                    {
                        "id": "north",
                        "name": "North",
                        "database_url": "sqlite:///north.db",
                        "artifact_dir": "artifacts/release",
                    }
                ],
            }
        )
