from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN = 8
PASSWORD_MAX = 128


def _check_password(v: str) -> str:
    if len(v) < PASSWORD_MIN:
        raise ValueError(f"A senha precisa ter pelo menos {PASSWORD_MIN} caracteres.")
    if len(v) > PASSWORD_MAX:
        raise ValueError(f"A senha pode ter no máximo {PASSWORD_MAX} caracteres.")
    if v.strip() == "":
        raise ValueError("A senha não pode ser só espaços.")
    return v


class RegisterIn(BaseModel):
    invite_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Código do link de convite. Sem convite, a conta precisa de assinatura.",
    )
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str
    birth_date: date
    guardian_consent: bool = False

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Informe seu nome.")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _check_password(v)

    @field_validator("birth_date")
    @classmethod
    def _birth_date(cls, v: date) -> date:
        today = date.today()
        if v >= today:
            raise ValueError("Data de nascimento inválida.")
        if today.year - v.year > 120:
            raise ValueError("Data de nascimento inválida.")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class EmailIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _check_password(v)
