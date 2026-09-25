"""Server-owned organization registry; no request supplies storage locations."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.engine import make_url

from services.api.config import Settings


class Organization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}$")
    name: str = Field(min_length=1, max_length=100)
    database_url: str
    artifact_dir: Path


class Membership(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=128)
    organization: str
    roles: list[Literal["viewer", "analyst", "admin"]] = Field(min_length=1)


class Credential(Membership):
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{32,256}$", repr=False)


class IdentityProvider(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issuer: str = Field(pattern=r"^https://[^\s]+$")
    audience: str = Field(min_length=1)
    jwks_url: str = Field(pattern=r"^https://[^\s]+$")
    max_lifetime_seconds: int = Field(default=3600, ge=60, le=3600)


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment: Literal["staging", "production"] = "staging"
    organizations: list[Organization] = Field(min_length=1, max_length=100)
    credentials: list[Credential] = Field(default_factory=list, repr=False)
    identity_provider: IdentityProvider | None = None
    memberships: list[Membership] = Field(default_factory=list)
    request_limit: int = Field(default=300, ge=1, le=10000)
    body_limit: int = Field(default=1024 * 1024, ge=1024, le=2 * 1024 * 1024)

    @model_validator(mode="after")
    def boundaries(self):
        ids = [o.id for o in self.organizations]
        if len(set(ids)) != len(ids):
            raise ValueError("Organization IDs must be unique")
        databases = []
        for organization in self.organizations:
            url = make_url(organization.database_url)
            if url.get_backend_name() == "sqlite":
                if url.database in (None, "", ":memory:"):
                    raise ValueError("Each organization needs a persistent database")
                databases.append(("sqlite", str(Path(url.database).resolve()).lower()))
            elif url.get_backend_name() == "postgresql":
                databases.append(
                    ("postgresql", (url.host or "").lower(), url.port or 5432, url.database)
                )
            else:
                raise ValueError("Unsupported organization database")
        if len(set(databases)) != len(databases):
            raise ValueError("Organizations must use separate databases")
        tokens = [hashlib.sha256(c.token.encode()).digest() for c in self.credentials]
        if len(set(tokens)) != len(tokens) or any(
            c.organization not in ids for c in self.credentials
        ):
            raise ValueError("Credentials must be unique and assigned to a known organization")
        members = [(m.organization, m.subject) for m in self.memberships]
        if len(set(members)) != len(members) or any(
            m.organization not in ids for m in self.memberships
        ):
            raise ValueError("Memberships must be unique and assigned to known organizations")
        if self.environment == "production" and (
            self.identity_provider is None or not self.memberships or self.credentials
        ):
            raise ValueError(
                "Production requires identity-provider memberships and forbids static credentials"
            )
        return self

    def settings_for(self, organization):
        return Settings(
            database_url=organization.database_url,
            artifact_dir=organization.artifact_dir,
            environment=self.environment,
            api_token="gateway-only-no-direct-authentication-allowed",
            require_gateway=True,
            organization_id=organization.id,
        )


def load_registry(path):
    return Registry.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
