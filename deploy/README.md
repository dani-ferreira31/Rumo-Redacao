# Deploy na VPS

Tudo roda num único `docker compose` na VPS. Os únicos serviços externos são a API da Anthropic e o Resend.

| Serviço | O que faz |
|---|---|
| `caddy` | HTTPS automático (Let's Encrypt) e proxy reverso. `/api/*` e `/health` vão para o backend; o resto vai para o frontend |
| `postgres` | Banco, sem porta exposta para fora |
| `backend` | API FastAPI. Aplica as migrations ao subir |
| `worker` | Fila de jobs (transcrição, correção, e-mails) e lembretes do cronograma |
| `frontend` | Next.js em modo standalone |
| `backup` | Todo dia às `BACKUP_HOUR`: dump do banco e cópia do storage em `./backups`, guardando `BACKUP_KEEP_DAYS` dias |

## Requisitos

- VPS com Ubuntu 24.04 (ou similar), 2 vCPU e 4 GB de RAM. 2 GB funcionam, mas o build do frontend fica lento.
- Um domínio com registro DNS **A** (e AAAA, se houver IPv6) apontando para o IP da VPS.
- Chave da API da Anthropic e chave do Resend, com o domínio de envio verificado no Resend.

## 1. Preparar o servidor

```bash
# Docker (script oficial)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER      # saia e entre de novo na sessão

# Firewall: só SSH, HTTP e HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

> O Docker publica portas por fora do ufw. Neste compose, só o Caddy publica portas (80/443), o que é o esperado.

## 2. Código e configuração

```bash
git clone <seu-repositorio> rumo1000 && cd rumo1000
cp .env.prod.example .env.prod
nano .env.prod
```

Preencha pelo menos estes campos:
- `DOMAIN`, `APP_URL`, `API_URL`
- `POSTGRES_PASSWORD`, repetindo a mesma senha dentro de `DATABASE_URL`
- `JWT_SECRET` (gere com `openssl rand -hex 32`)
- `SETTINGS_ENCRYPTION_KEY`, que criptografa as chaves de IA salvas pelo painel (veja o README principal para gerar). **Guarde uma cópia fora da VPS**: sem ela, as chaves do painel precisam ser cadastradas de novo
- `RESEND_API_KEY`. As chaves de IA (Anthropic, OpenAI, Google) podem ficar no `.env.prod` ou ser cadastradas depois em Admin → Inteligência artificial
- `EMAIL_FROM`, com o domínio verificado no Resend
- `SEED_ADMIN_EMAIL` e `SEED_ADMIN_PASSWORD`

Depois proteja o arquivo: `chmod 600 .env.prod`.

## 3. Subir

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.prod ps
curl https://SEU-DOMINIO/health           # {"db":"ok","storage":"ok"}
```

Na primeira subida, o Caddy obtém o certificado sozinho (pode levar alguns segundos).

## 4. Dados iniciais

```bash
alias dc='docker compose -f docker-compose.prod.yml --env-file .env.prod'

# Temas oficiais de redação, tópicos e o admin inicial
dc exec backend python -m scripts.seed

# Questões: copie data/enem-api/public para ./data/enem-api/public no servidor
# (ou rode o mesmo git clone esparso do README principal) e importe:
dc exec backend python -m scripts.import_questions $(for y in $(seq 2009 2023); do echo --year $y; done)

# Opcional: completar TRI/habilidade com os microdados do INEP (um ano por vez)
dc exec backend python -m scripts.import_questions --year 2023 --microdados data/inep/ITENS_PROVA_2023.csv
```

Entre com o admin e **troque a senha** pelo fluxo "Esqueci minha senha".

## 5. Atualizar a aplicação

```bash
git pull
dc up -d --build          # o backend aplica as migrations novas ao subir
dc logs -f backend worker # acompanhe
```

## 6. Backups e restauração

Os backups ficam em `./backups`:
- `db-AAAAMMDD-HHMM.dump`: banco, no formato custom do `pg_dump`;
- `storage-AAAAMMDD-HHMM.tar.gz`: fotos das redações e imagens das questões.

**Copie-os para fora da VPS** (outra máquina ou storage externo), por exemplo com `rsync` agendado no seu computador. Um backup que fica só no próprio servidor não protege contra perda da VPS.

Para fazer um backup na hora: `dc exec backup sh /backup.sh now`.

Para restaurar:

```bash
dc stop backend worker

# banco
dc exec -T postgres pg_restore --clean --if-exists -U app -d rumo1000 < backups/db-AAAAMMDD-HHMM.dump

# storage
docker run --rm -v rumo1000_storage:/data/storage -v "$PWD/backups":/b alpine \
  sh -c 'rm -rf /data/storage/* && tar -xzf /b/storage-AAAAMMDD-HHMM.tar.gz -C /data'

dc start backend worker
```

Teste a restauração de vez em quando num ambiente separado.

## 7. Operação

- **Logs:** `dc logs -f backend worker caddy`. Saem em JSON, com `request_id`, `job_id` e `essay_id`.
- **Painel:** Admin → Sistema mostra a saúde dos serviços e a fila (com reprocessar/cancelar); Admin → Módulos e limites liga/desliga partes do app e define o orçamento mensal de IA.
- **Custo de IA:** página Admin → Custos. A cobrança real fica no console de cada provedor; confira os preços em Admin → Inteligência artificial.
- **Calibração:** antes de trocar prompt ou modelo, rode `dc exec backend python -m scripts.eval_grading --dataset data/essay-br --n 50 --yes`. Os relatórios ficam em `./reports`. No compose de produção, monte `./reports:/app/reports` se quiser guardá-los fora do container.
- **Jobs com falha:** `dc exec postgres psql -U app -d rumo1000 -c "select id, queue, attempts, last_error from jobs where status='failed' order by id desc limit 20"`.
