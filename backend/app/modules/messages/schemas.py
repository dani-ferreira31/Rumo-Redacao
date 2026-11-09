from pydantic import BaseModel, Field, field_validator


def _strip(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Não pode ficar em branco.")
    return v


class MessageIn(BaseModel):
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(
        min_length=1, max_length=5000, description="Texto do e-mail. {nome} vira o primeiro nome."
    )

    _s = field_validator("subject", "body")(_strip)


class WelcomeSettings(MessageIn):
    enabled: bool = False
    delay_minutes: int = Field(
        default=5, ge=0, le=1440, description="Espera depois do 'pagamento confirmado'."
    )


class MessageQueued(BaseModel):
    queued: bool = True
