# Deploy na VPS

Tudo roda num `docker compose` na VPS, atrás do **Nginx Proxy Manager** (NPM) que já existe no servidor e do **Cloudflare** (DNS com proxy). Os únicos serviços externos são as APIs de IA e o Resend.

Domínio de produção: `rumo.4bsistemas.com.br`.

```
aluno → Cloudflare (HTTPS) → NPM na VPS (443) → rumo1000-frontend:3000
                                              → rumo1000-backend:8000  (/api/*, /health)
```

| Serviço | O que faz |
|---|---|
| `postgres` | Banco, sem porta exposta para fora |
| `backend` | API FastAPI. Aplica as migrations ao subir |
| `worker` | Fila de jobs (transcrição, correção, e-mails) e lembretes do cronograma |
| `frontend` | Next.js em modo standalone |
| `backup` | Todo dia às `BACKUP_HOUR`: dump do banco e cópia do storage em `./backups`, guardando `BACKUP_KEEP_DAYS` dias |

## Requisitos

- VPS com Ubuntu 24.04 (ou similar), 2 vCPU e 4 GB de RAM. 2 GB funcionam, mas o build do frontend fica lento.
- Nginx Proxy Manager rodando em Docker na VPS (portas 80/443).
- O domínio no Cloudflare.
- Chave da API da Anthropic e chave do Resend, com o domínio de envio verificado no Resend.

## 1. Preparar o servidor

```bash
# Docker (script oficial)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER      # saia e entre de novo na sessão

# O NPM já está na rede Docker "proxy-network" (compartilhada com os outros sistemas).
docker network inspect proxy-network --format '{{range .Containers}}{{.Name}} {{end}}'
```

> Este compose não publica nenhuma porta: backend e frontend entram na rede `proxy-network` (variável `PROXY_NETWORK` no `.env.prod`) como `rumo1000-backend` e `rumo1000-frontend`, nomes únicos para não colidir com os outros sistemas da mesma rede. Postgres e worker ficam só na rede interna do projeto.
>
> A porta 81 (painel do NPM) não deve ficar aberta para a internet: acesse por túnel SSH (`ssh -L 8181:localhost:81 usuario@vps` e abra `http://localhost:8181`) ou restrinja no firewall.

## 2. Código e configuração

O repositório é clonado em `~/rumo1000` (o deploy automático usa esse caminho). Se o repositório for privado, crie uma *deploy key* na VPS:

```bash
ssh-keygen -t ed25519 -C "vps-rumo1000" -f ~/.ssh/github_rumo1000 -N ""
cat ~/.ssh/github_rumo1000.pub
# GitHub → repositório → Settings → Deploy keys → Add deploy key (só leitura), cole a chave
cat >> ~/.ssh/config <<'CFG'
Host github.com
  IdentityFile ~/.ssh/github_rumo1000
  IdentitiesOnly yes
CFG
```

```bash
git clone git@github.com:dani-ferreira31/Rumo-Redacao.git ~/rumo1000 && cd ~/rumo1000
cp .env.prod.example .env.prod
nano .env.prod
```

Preencha pelo menos estes campos:
- `APP_URL` e `API_URL` (`https://rumo.4bsistemas.com.br`)
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
```

Depois configure o Cloudflare e o NPM (seção 3.1) e teste: `curl https://rumo.4bsistemas.com.br/health` deve devolver `{"db":"ok","storage":"ok"}`.

## 3.1 Cloudflare e Nginx Proxy Manager

**Cloudflare**
1. DNS → Add record: tipo `A`, nome `rumo`, IPv4 da VPS, **Proxied** (nuvem laranja).
2. SSL/TLS → Overview: modo **Full (strict)**.
3. SSL/TLS → Origin Server → **Create Certificate**: hostnames `rumo.4bsistemas.com.br` (ou `*.4bsistemas.com.br`), formato PEM, validade 15 anos. Copie o *Origin Certificate* e a *Private Key* (a chave só aparece uma vez).
4. Não use cache de HTML nem Rocket Loader neste host. As regras padrão (que só fazem cache de arquivos estáticos) servem.

**Nginx Proxy Manager**
1. SSL Certificates → Add SSL Certificate → **Custom**: nome `rumo-cloudflare-origin`, cole o certificado e a chave do passo 3.
2. Hosts → Proxy Hosts → Add Proxy Host:
   - **Details**: Domain Names `rumo.4bsistemas.com.br`; Scheme `http`; Forward Hostname `rumo1000-frontend`; Forward Port `3000`; marque *Block Common Exploits*. Deixe *Cache Assets* desmarcado.
   - **SSL**: escolha `rumo-cloudflare-origin`; marque *Force SSL* e *HTTP/2 Support*.
   - **Advanced**: cole o conteúdo de [`nginx-proxy-manager.conf`](nginx-proxy-manager.conf), que manda `/api/*` e `/health` para o backend e libera uploads de até 25 MB.
3. Salve. O status do host deve ficar *Online*.

Alternativa ao certificado de origem: no passo 1 do NPM, use *Let's Encrypt* com **DNS Challenge** do Cloudflare (token de API com permissão `Zone:DNS:Edit`). O desafio HTTP não funciona bem atrás do proxy do Cloudflare.

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

### Deploy automático (GitHub Actions)

`.github/workflows/deploy.yml` roda a cada push na `main` (ou manualmente em Actions → Deploy → Run workflow): entra na VPS por SSH, faz `git reset --hard origin/main` em `~/rumo1000` e sobe com `up -d --build --wait`. O `.env.prod`, `data/` e `backups/` não são versionados e não são tocados.

Configuração (uma vez só):

1. Gere um par de chaves só para o GitHub Actions (no seu computador):
   ```bash
   ssh-keygen -t ed25519 -C "github-actions-rumo1000" -f ~/.ssh/rumo1000_actions -N ""
   ssh-copy-id -i ~/.ssh/rumo1000_actions.pub -p <porta> <usuario>@<ip-da-vps>
   ```
   O usuário precisa estar no grupo `docker` e ser o dono de `~/rumo1000`.
2. GitHub → repositório → Settings → Secrets and variables → Actions → New repository secret:

   | Secret | Valor |
   |---|---|
   | `VPS_HOST` | IP da VPS (não use o domínio: ele passa pelo Cloudflare, que não repassa SSH) |
   | `VPS_USER` | usuário SSH |
   | `VPS_PORT` | porta SSH (ex.: `22`) |
   | `VPS_SSH_KEY` | conteúdo inteiro de `~/.ssh/rumo1000_actions` (a chave **privada**, com as linhas `BEGIN`/`END`) |

3. Faça o primeiro deploy à mão (seções 2 a 4). Os seguintes saem sozinhos a cada push.

### Manual

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

- **Logs:** `dc logs -f backend worker frontend` (o log de acesso HTTP fica no NPM). Saem em JSON, com `request_id`, `job_id` e `essay_id`.
- **Painel:** Admin → Sistema mostra a saúde dos serviços e a fila (com reprocessar/cancelar); Admin → Módulos e limites liga/desliga partes do app e define o orçamento mensal de IA.
- **Custo de IA:** página Admin → Custos. A cobrança real fica no console de cada provedor; confira os preços em Admin → Inteligência artificial.
- **Calibração:** antes de trocar prompt ou modelo, rode `dc exec backend python -m scripts.eval_grading --dataset data/essay-br --n 50 --yes`. Os relatórios ficam em `./reports`. No compose de produção, monte `./reports:/app/reports` se quiser guardá-los fora do container.
- **Jobs com falha:** `dc exec postgres psql -U app -d rumo1000 -c "select id, queue, attempts, last_error from jobs where status='failed' order by id desc limit 20"`.
