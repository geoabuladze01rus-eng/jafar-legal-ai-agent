from enum import StrEnum


class LicenseState(StrEnum):
    UNLICENSED = "unlicensed"
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    REVOKED = "revoked"


def license_can_authorize_matter_access(_: LicenseState) -> bool:
    """Licensing is deliberately not an authorization boundary."""

    return False
