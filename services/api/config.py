from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FRAUDGRAPH_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./artifacts/fraudgraph.db"
    artifact_dir: Path = Path("artifacts/release")
    api_token: str = "local-demo-token-change-me"
    environment: str = "local"
    analyst_tokens: dict[str, str] = {}
    require_gateway: bool = False
    organization_id: str = "local"
    max_pending_jobs: int = Field(default=20, ge=1, le=100)
    max_owner_pending_jobs: int = Field(default=5, ge=1, le=20)
    max_retained_jobs: int = Field(default=1000, ge=1, le=10000)
    max_job_payload_bytes: int = Field(default=64 * 1024 * 1024, ge=1024, le=256 * 1024 * 1024)

    def validate_deployment(self):
        if self.environment != "local" and (
            self.api_token == "local-demo-token-change-me" or len(self.api_token) < 32
        ):
            raise ValueError("Set a random API token of at least 32 characters outside local mode")
