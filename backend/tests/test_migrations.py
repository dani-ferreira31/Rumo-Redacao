from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.models import metadata


async def test_cria_todas_as_tabelas_dos_models(db):
    rows = await db.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
        )
    )
    # 26 do schema inicial + as das migrations seguintes
    assert {r[0] for r in rows} == set(metadata.tables)


async def test_seed_areas_e_disciplinas(db):
    # 4 áreas do ENEM + Concursos públicos (migration 0003), com 16 disciplinas cada lado
    assert await db.scalar(text("SELECT count(*) FROM knowledge_areas")) == 5
    assert await db.scalar(text("SELECT count(*) FROM subjects WHERE area_id < 5")) == 16
    assert await db.scalar(text("SELECT count(*) FROM subjects WHERE area_id = 5")) == 16


async def test_busca_textual_ignora_acentos(db):
    matched = await db.scalar(
        text(
            "SELECT to_tsvector('pt_unaccent', 'funções quadráticas') "
            "@@ websearch_to_tsquery('pt_unaccent', 'funcoes quadraticas')"
        )
    )
    assert matched is True


async def test_models_em_sincronia_com_o_banco(connection):
    def _diff(sync_conn):
        ctx = MigrationContext.configure(sync_conn, opts={"compare_type": True})
        return compare_metadata(ctx, metadata)

    diff = await connection.run_sync(_diff)
    assert diff == [], f"models divergem do banco: {diff}"
