"""Schémas Pydantic — 2FA TOTP."""

from pydantic import BaseModel, Field


class TotpSetupOut(BaseModel):
    secret: str
    provisioning_uri: str


class TotpEnableIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpEnableOut(BaseModel):
    enabled: bool
    backup_codes: list[str]


class TotpDisableIn(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class TotpStatusOut(BaseModel):
    enabled: bool


class TotpVerifyIn(BaseModel):
    """Vérification lors du login (challenge 2FA)."""

    mfa_token: str
    code: str = Field(min_length=6, max_length=64)
