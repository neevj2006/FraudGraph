"""Verify access tokens against one operator-configured issuer and membership registry."""

import jwt


class IdentityVerifier:
    def __init__(self, registry):
        self.config = registry.identity_provider
        self.members = {(m.organization, m.subject): m for m in registry.memberships}
        self.client = jwt.PyJWKClient(self.config.jwks_url, timeout=5, lifespan=300)

    def verify(self, token):
        try:
            if len(token) > 8192:
                return None
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                return None
            key = self.client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.config.issuer,
                audience=self.config.audience,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "org"]},
            )
            if any(type(claims[k]) is not int for k in ("exp", "iat", "nbf")):
                return None
            if not 0 < claims["exp"] - claims["iat"] <= self.config.max_lifetime_seconds:
                return None
            if not isinstance(claims["org"], str) or not isinstance(claims["sub"], str):
                return None
            member = self.members.get((claims["org"], claims["sub"]))
            return member.model_dump() if member else None
        except (jwt.PyJWTError, ValueError, TypeError, OSError):
            return None
