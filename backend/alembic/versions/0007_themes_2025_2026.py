"""Temas oficiais da redação do ENEM 2025 e 2026 (dados; idempotente)

O deploy roda `alembic upgrade head`, mas não o seed: a migration garante que os
temas novos cheguem à produção. Não duplica se o seed ou o admin já cadastrou.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THEMES = [
    (2026, "A valorização do Sistema Único de Saúde (SUS) como direito universal"),
    (2025, "Perspectivas acerca do envelhecimento na sociedade brasileira"),
]


def upgrade() -> None:
    for year, title in THEMES:
        op.get_bind().execute(
            sa.text(
                "INSERT INTO essay_themes (title, year, is_official) "
                "SELECT :title, :year, true "
                "WHERE NOT EXISTS (SELECT 1 FROM essay_themes WHERE title = :title)"
            ),
            {"title": title, "year": year},
        )


def downgrade() -> None:
    # Dados: não remove (redações podem apontar para esses temas).
    pass
