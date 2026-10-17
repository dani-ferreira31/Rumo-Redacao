from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/rumo1000"
    test_database_url: str = "postgresql+asyncpg://app:app@localhost:5432/rumo1000_test"

    jwt_secret: str = "troque-isto"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    cookie_secure: bool = False
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # IA: provedor padrão quando o painel admin ainda não configurou a tarefa.
    # "fake" devolve respostas de exemplo (dev sem chave) e só aparece no painel nesse modo.
    ai_driver: Literal["fake", "anthropic"] = "fake"
    # Chaves de reserva: as cadastradas no painel (criptografadas no banco) têm prioridade.
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    # Chave Fernet que criptografa as chaves de API salvas pelo painel.
    settings_encryption_key: str = ""
    anthropic_model_transcription: str = "claude-sonnet-5-5"
    anthropic_model_grading: str = "claude-sonnet-5-5"
    anthropic_effort_transcription: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    anthropic_effort_grading: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    # Reexecuta no servidor, em outro modelo, pedidos recusados pelos classificadores.
    anthropic_refusal_fallback: bool = True
    ai_timeout_seconds: float = 180.0
    ai_max_retries: int = 3

    # Redações
    essay_max_image_bytes: int = 10 * 1024 * 1024
    essay_image_max_long_edge: int = 2576

    email_driver: Literal["console", "resend"] = "console"
    resend_api_key: str = ""
    email_from: str = "Rumo1000 <nao-responda@seudominio.com.br>"

    # Mercado Pago (assinatura e doações). Sem token, o pagamento fica indisponível.
    mercadopago_access_token: str = ""
    # Chave secreta das notificações (webhook): Suas integrações → Webhooks.
    mercadopago_webhook_secret: str = ""

    storage_driver: Literal["local"] = "local"
    storage_local_path: str = "./storage"

    worker_poll_interval: float = 1.0
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
