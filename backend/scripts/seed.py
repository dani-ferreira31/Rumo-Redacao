"""Dados iniciais idempotentes: temas oficiais de redação, tópicos por disciplina
e um admin de desenvolvimento (se SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD estiverem
definidos).

Uso: python -m scripts.seed
"""

import asyncio
import os
import re
import unicodedata

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.core.enums import UserRole
from app.core.security import hash_password, utcnow
from app.modules.essays.models import EssayTheme
from app.modules.questions.models import Subject, Topic
from app.modules.users.models import User

# Temas da aplicação regular do ENEM (título + ano). Textos motivadores são
# opcionais e podem ser cadastrados depois pelo admin.
OFFICIAL_THEMES = [
    (2026, "A valorização do Sistema Único de Saúde (SUS) como direito universal"),
    (2025, "Perspectivas acerca do envelhecimento na sociedade brasileira"),
    (2024, "Desafios para a valorização da herança africana no Brasil"),
    (
        2023,
        "Desafios para o enfrentamento da invisibilidade do trabalho de cuidado realizado pela "
        "mulher no Brasil",
    ),
    (2022, "Desafios para a valorização de comunidades e povos tradicionais no Brasil"),
    (2021, "Invisibilidade e registro civil: garantia de acesso à cidadania no Brasil"),
    (2020, "O estigma associado às doenças mentais na sociedade brasileira"),
    (2019, "Democratização do acesso ao cinema no Brasil"),
    (2018, "Manipulação do comportamento do usuário pelo controle de dados na internet"),
    (2017, "Desafios para a formação educacional de surdos no Brasil"),
    (2016, "Caminhos para combater a intolerância religiosa no Brasil"),
    (2015, "A persistência da violência contra a mulher na sociedade brasileira"),
]

TOPICS = {
    "matematica": [
        "Razão, proporção e porcentagem",
        "Funções",
        "Função afim",
        "Função quadrática",
        "Exponencial e logaritmo",
        "Progressões",
        "Geometria plana",
        "Geometria espacial",
        "Trigonometria",
        "Estatística",
        "Probabilidade",
        "Análise combinatória",
        "Matemática financeira",
        "Escalas e grandezas",
    ],
    "fisica": [
        "Cinemática",
        "Dinâmica",
        "Energia e trabalho",
        "Hidrostática",
        "Termologia",
        "Óptica",
        "Ondulatória",
        "Eletrodinâmica",
        "Eletromagnetismo",
    ],
    "quimica": [
        "Atomística",
        "Ligações químicas",
        "Funções inorgânicas",
        "Estequiometria",
        "Soluções",
        "Termoquímica",
        "Cinética química",
        "Equilíbrio químico",
        "Eletroquímica",
        "Química orgânica",
        "Química ambiental",
    ],
    "biologia": [
        "Citologia",
        "Genética",
        "Evolução",
        "Ecologia",
        "Fisiologia humana",
        "Botânica",
        "Zoologia",
        "Microbiologia e doenças",
        "Biotecnologia",
    ],
    "historia": [
        "Brasil Colônia",
        "Brasil Império",
        "República Velha",
        "Era Vargas",
        "Ditadura militar",
        "Redemocratização",
        "Antiguidade",
        "Idade Média",
        "Idade Moderna",
        "Revoluções e Idade Contemporânea",
        "Guerras mundiais e Guerra Fria",
    ],
    "geografia": [
        "Cartografia",
        "Geologia e relevo",
        "Clima",
        "Hidrografia",
        "Biomas e vegetação",
        "População",
        "Urbanização",
        "Agropecuária",
        "Industrialização",
        "Globalização",
        "Questões ambientais",
        "Geopolítica",
    ],
    "filosofia": [
        "Filosofia antiga",
        "Filosofia medieval",
        "Filosofia moderna",
        "Ética",
        "Filosofia política",
        "Filosofia contemporânea",
    ],
    "sociologia": [
        "Clássicos da sociologia",
        "Cultura e identidade",
        "Movimentos sociais",
        "Trabalho e sociedade",
        "Cidadania e direitos",
        "Desigualdade social",
    ],
    "portugues": [
        "Interpretação de texto",
        "Gêneros textuais",
        "Variação linguística",
        "Funções da linguagem",
        "Figuras de linguagem",
        "Gramática",
        "Semântica",
    ],
    "literatura": [
        "Escolas literárias",
        "Modernismo",
        "Literatura contemporânea",
        "Análise de poemas",
    ],
    "ingles": ["Interpretação de texto em inglês"],
    "espanhol": ["Interpretação de texto em espanhol"],
    "artes": ["Artes visuais", "Música", "Teatro e dança", "Arte brasileira"],
    "educacao-fisica": ["Esporte e sociedade", "Corpo e saúde"],
    "tic": ["Tecnologias da informação e comunicação"],
    "redacao": [
        "Estrutura dissertativo-argumentativa",
        "Repertório sociocultural",
        "Proposta de intervenção",
    ],
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


async def seed_themes(session) -> int:
    existing = set((await session.execute(select(EssayTheme.year, EssayTheme.title))).all())
    added = 0
    for year, title in OFFICIAL_THEMES:
        if (year, title) not in existing:
            session.add(EssayTheme(title=title, year=year, is_official=True))
            added += 1
    return added


async def seed_topics(session) -> int:
    subjects = {s.slug: s for s in await session.scalars(select(Subject))}
    existing = set((await session.execute(select(Topic.subject_id, Topic.slug))).all())
    added = 0
    for subject_slug, names in TOPICS.items():
        subject = subjects.get(subject_slug)
        if subject is None:
            continue
        for name in names:
            slug = slugify(name)
            if (subject.id, slug) not in existing:
                session.add(Topic(subject_id=subject.id, name=name, slug=slug))
                added += 1
    return added


async def seed_admin(session) -> str | None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if not email or not password:
        return None
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        session.add(
            User(
                name="Admin",
                email=email,
                password_hash=hash_password(password),
                role=UserRole.admin,
                email_verified_at=utcnow(),
            )
        )
        return "criado"
    user.role = UserRole.admin
    return "já existia"


async def main() -> None:
    async with SessionLocal() as session:
        themes = await seed_themes(session)
        topics = await seed_topics(session)
        admin = await seed_admin(session)
        await session.commit()
    await engine.dispose()
    print(
        f"temas adicionados: {themes}; tópicos adicionados: {topics}; "
        f"admin: {admin or 'não configurado'}"
    )


if __name__ == "__main__":
    asyncio.run(main())
