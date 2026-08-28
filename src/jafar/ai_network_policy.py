from dataclasses import dataclass
from enum import StrEnum


class AIMode(StrEnum):
    SYNTHETIC_ONLY = "synthetic_only"
    LOCAL_LIVE_TEST = "local_live_test"
    PRODUCTION = "production"


class DataClassification(StrEnum):
    SYNTHETIC = "synthetic"
    PRIVATE_CLIENT = "private_client"
    PUBLIC = "public"


@dataclass(frozen=True)
class AINetworkPolicy:
    mode: AIMode = AIMode.SYNTHETIC_ONLY
    allow_live_network: bool = False

    def authorize(self, *, provider_enabled: bool, credential: str | None, data: DataClassification) -> None:
        if not provider_enabled or not self.allow_live_network or self.mode == AIMode.SYNTHETIC_ONLY:
            raise PermissionError("live AI network is disabled")
        if data == DataClassification.PRIVATE_CLIENT:
            raise PermissionError("private client data is not allowed for live smoke")
        if not credential:
            raise PermissionError("provider credential is missing")
