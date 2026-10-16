import os
import tempfile

# Configuração de teste antes de qualquer import do app (Settings é cacheado).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/rumo1000_test"
)
os.environ["STORAGE_LOCAL_PATH"] = tempfile.mkdtemp(prefix="rumo1000-storage-")
os.environ["EMAIL_DRIVER"] = "console"
os.environ["JWT_SECRET"] = "segredo-de-teste-com-32-bytes-ou-mais"
os.environ["APP_URL"] = "http://app.test"
os.environ["AI_DRIVER"] = "fake"
os.environ["SETTINGS_ENCRYPTION_KEY"] = "kKz8n1oGfRk0d1wKXxS0fJ7mVb5bJ0bqkq3a0H4xR2Q="

from collections.abc import AsyncIterator, Callable  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,  # noqa: E402
)

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _upgrade(sync_conn) -> None:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.attributes["connection"] = sync_conn
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Recria o schema do banco de teste do zero e aplica as migrations."""
    eng = create_async_engine(get_settings().database_url)
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(_upgrade)
    yield eng
    await eng.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Conexão com transação externa revertida ao fim de cada teste."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        yield conn
        await trans.rollback()


@pytest.fixture
def session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    """Fábrica de sessões que fazem commit em SAVEPOINT (nada chega ao banco de verdade)."""

    def factory() -> AsyncSession:
        return AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return factory


@pytest.fixture
async def db(session_factory) -> AsyncIterator[AsyncSession]:
    session = session_factory()
    yield session
    await session.close()


@pytest.fixture
async def client(db: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_session():
        yield db

    app.dependency_overrides[get_session] = _override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """O cache das configurações sobreviveria ao rollback de cada teste."""
    from app.modules.system.settings import clear_cache

    clear_cache()
    yield
    clear_cache()
