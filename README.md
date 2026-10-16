# Rumo1000

Plataforma de estudos para o ENEM: correção de redações com IA, banco de questões e cronograma. A visão geral está em `CLAUDE.md` e os detalhes em `docs/`.

## Rodando em desenvolvimento

```bash
cp .env.example .env            # ajuste JWT_SECRET; troque as portas se 3000/5432/8000 estiverem ocupadas
docker compose up -d --build    # postgres, backend (:8000), worker e frontend (:3000)
docker compose exec backend alembic upgrade head
```

- App: http://localhost:3000. A API fica em `/api/v1`, repassada ao backend pelo rewrite do Next.
- Docs da API: http://localhost:8000/docs
- E-mails: com `EMAIL_DRIVER=console`, o worker só loga o e-mail (inclusive os links de verificação e de redefinição de senha), então use `docker compose logs -f worker` para ver. Com `EMAIL_DRIVER=resend` + `RESEND_API_KEY`, o envio é real (no modo de teste, use o destinatário `delivered@resend.dev`).

## Dados (fora do git, em `data/`)

```bash
# Questões do ENEM 2009–2023 (texto, imagens e gabarito), do projeto aberto enem.dev
git clone --depth 1 --filter=blob:none --sparse https://github.com/yunger7/enem-api.git data/enem-api
(cd data/enem-api && git sparse-checkout set public && rm -rf .git)
docker compose exec backend python -m scripts.import_questions $(for y in $(seq 2009 2023); do echo --year $y; done)

# Opcional: TRI e habilidade (H1–H30) dos microdados do INEP. Baixe o zip dos microdados
# do ENEM no site do INEP, extraia DADOS/ITENS_PROVA_<ano>.csv para data/inep/ e rode, um ano por vez:
docker compose exec backend python -m scripts.import_questions --year 2023 --microdados data/inep/ITENS_PROVA_2023.csv

# Redações com notas humanas para calibrar a correção (Essay-BR, licença MIT)
git clone --depth 1 https://github.com/rafaelanchieta/essay.git data/essay-br && rm -rf data/essay-br/.git

# Temas oficiais de redação, tópicos e admin de desenvolvimento
docker compose exec backend python -m scripts.seed
```

O importador cruza as duas fontes sozinho: para cada área, escolhe o caderno dos microdados cujo gabarito coincide com o do enem.dev. A área vem da **posição** da questão, porque o campo `discipline` do enem.dev tem erros.

## IA (correção de redações)

- O provedor (Anthropic, OpenAI ou Google), o modelo e o esforço de cada tarefa (transcrição, correção, importação de provas) são escolhidos em **Admin → Inteligência artificial**, sem reiniciar nada.
- As chaves de API também são cadastradas lá. Elas ficam criptografadas no banco com `SETTINGS_ENCRYPTION_KEY`, que precisa estar no `.env`. Gere uma com:
  `docker compose exec backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  Guarde essa chave junto com os backups: sem ela, as chaves salvas no painel não podem ser lidas (basta cadastrá-las de novo).
- Sem nada configurado no painel, vale o `.env`: `AI_DRIVER=fake` (padrão em dev) dá respostas simuladas, sem custo; `AI_DRIVER=anthropic` + `ANTHROPIC_API_KEY` usa a Anthropic.
- Antes de trocar o modelo de correção em produção, rode a calibração com ele: `python -m scripts.eval_grading --n 50 --yes --provider openai --model <id>`.
- Calibração com notas humanas: `docker compose exec -u "$(id -u):$(id -g)" backend python -m scripts.eval_grading --dataset data/essay-br --n 50 --yes`. Gera um relatório em `reports/`.

## Comandos úteis

```bash
docker compose exec backend pytest                    # banco rumo1000_test, transação revertida por teste
docker compose exec backend ruff check .
docker compose exec backend python -m scripts.enqueue system.ping '{}'
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
cd frontend && npm run gen:api                        # regenera lib/api-schema.d.ts (backend no ar)
```

Para adicionar dependências Python, edite `backend/pyproject.toml` e rode `docker compose run --rm --user "$(id -u):$(id -g)" -e UV_CACHE_DIR=/tmp/uv backend uv lock`. Depois faça `docker compose build backend worker`.

## Notas

- **Hospedagem:** VPS própria com Docker Compose e Caddy na frente (HTTPS e mesma origem para front e API). Os únicos serviços externos são o Resend e a Anthropic. O storage é em disco local (volume com backup diário). Guia: `deploy/README.md`.
- **Hot reload:** o backend recarrega sozinho. O **worker não**: depois de mudar código de jobs, rode `docker compose restart worker`. Se uma alteração do frontend não aparecer, rode `docker compose restart frontend`.
- **Dependências novas do frontend:** o `node_modules` do container fica num volume. Depois de `npm install`, recrie o volume com `docker compose rm -sf frontend && docker volume rm rumo1000_frontend_node_modules && docker compose up -d frontend`.
- **Produção:** veja `deploy/README.md`.
