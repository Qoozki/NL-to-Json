"""Runtime configuration. Credentials come from the environment only."""
import os
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    auth_token: str = field(repr=False)   # repr=False: never leaks into logs/tracebacks
    tenant_id: str

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        env = os.environ if env is None else env
        missing = [n for n in ("API_AUTH_TOKEN", "TENANT_ID") if not env.get(n, "").strip()]
        if missing:
            raise ConfigError("Missing required environment variable(s): " + ", ".join(missing))
        return cls(auth_token=env["API_AUTH_TOKEN"].strip(), tenant_id=env["TENANT_ID"].strip())

    def request_headers(self) -> Dict[str, str]:
        """Headers for the *outgoing* product-API call. Never put these in an HTTP response."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "X-Tenant-ID": self.tenant_id,
            "Content-Type": "application/json",
        }
