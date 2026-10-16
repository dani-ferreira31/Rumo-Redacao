# 06 — Roadmap de implementação

Implemente **uma fase por vez**, na ordem. Cada fase termina com testes passando e os critérios de aceite atendidos. Faça commits pequenos por tarefa.

> **Como usar com o Claude Code:** peça uma fase de cada vez, por exemplo: "Leia o CLAUDE.md e os docs, depois implemente a Fase 0 do docs/06-roadmap.md". Revise, rode e só então passe para a próxima.

---

## Fase 0: Fundação
- [x] Monorepo com `backend/`, `frontend/`, `docker-compose.yml` (postgres:16, backend, worker, frontend) e `.env.example`.
- [x] Backend FastAPI: config com `pydantic-settings`, sessão async do SQLAlchemy, formato padrão de erros, logging JSON, `GET /health`.
- [x] Alembic configurado. **Migration inicial gerada a partir de `db/schema.sql`** (extensões, enums, configuração `pt_unaccent`, tabelas, índices, triggers e seed).
- [x] Interface `Storage` com `LocalStorage` (dev e produção na VPS): `put`, `get`, `delete`, `delete_prefix`, `signed_url`.
- [x] Fila de jobs: `enqueue()`, worker com `SKIP LOCKED`, retry com backoff, recuperação de jobs presos e registro de handlers por nome.
- [x] Frontend Next.js + Tailwind com layout base (menu: Painel, Redações, Questões, Cronograma) e cliente de API tipado gerado do OpenAPI.
- [x] `pytest` com banco de teste (transação revertida por teste).

**Aceite:** `docker compose up` sobe tudo; `alembic upgrade head` cria as 26 tabelas; um job de teste enfileirado é processado pelo worker; `/health` responde ok.

## Fase 1: Contas e e-mails (Resend)
- [x] Cadastro, login, refresh com rotação, logout, verificação de e-mail, esqueci/redefinir senha (ver `02-arquitetura.md`).
- [x] Cliente Resend + templates Jinja2 + job `email.send` + `email_logs`.
- [x] Rate limit nos endpoints de auth.
- [x] `GET/PATCH/DELETE /me`.
- [x] Telas: cadastro (com data de nascimento e consentimento do responsável se < 18), login, verificar e-mail, esqueci senha, perfil.

**Aceite:** fluxo completo funciona ponta a ponta com o Resend em modo de teste; tokens expirados ou reutilizados são rejeitados; testes cobrem os casos de erro.

## Fase 2: Correção de redações ⭐
- [x] `app/ai/client.py` (wrapper + `ai_usage`), com tool use forçado e validação Pydantic.
- [x] Pré-processamento de imagem (OpenCV), com testes usando imagens de exemplo.
- [x] Transcrição (ETAPA 1) e prompt `transcricao.md`.
- [x] Checagens objetivas (ETAPA 2).
- [x] Prompts `correcao_sistema.md` + `rubrica.md` (montada a partir da Cartilha do INEP) + few-shot.
- [x] Correção dupla, 3ª execução, consolidação e validações (ETAPAS 3 a 5).
- [x] Endpoints de `/essays`.
- [x] Telas: nova redação (upload com dicas de foto e preview), revisão da transcrição (imagem ao lado do texto, marcadores destacados), resultado (notas, abas por competência, desvios, checklist da C5), histórico com gráfico de evolução.
- [x] E-mail "correção pronta".
- [x] `scripts/eval_grading.py` com QWK, ±40, MAE e viés.

**Aceite:** uma foto real vira transcrição revisável e depois resultado completo; redação com 7 linhas é anulada sem chamar a IA; testes da consolidação passam; o eval roda em pelo menos 50 redações e gera relatório.

## Fase 3: Banco de questões

> Implementado com as fontes **enem.dev** (texto, imagens e gabarito de 2009 a 2023) + **microdados do INEP** (TRI e habilidade, opcional), cruzadas automaticamente pelo gabarito. Isso substitui a extração dos PDFs com IA descrita abaixo.
- [x] `scripts/import_questions.py`:
  - lê os **microdados do INEP** (arquivo de itens da prova: código do item, área, posição, gabarito, habilidade, parâmetros TRI, cor/código do caderno) e cria `exams`, `questions` e `exam_questions`;
  - extrai enunciados e alternativas dos **PDFs oficiais das provas**. Sugestão: renderizar as páginas e usar o Claude (visão) para devolver JSON `{numero, enunciado_md, alternativas, imagens: [bbox]}`, recortando as imagens para `question_assets`;
  - marca tudo como `reviewed = false`.
  - (Alternativa a avaliar: APIs/datasets abertos de questões do ENEM, verificando licença e qualidade.)
- [ ] Classificação de disciplina/tópico: sugestão por IA com fila de revisão no admin. (Feito: fila de revisão e classificação manual no admin. Falta: sugestão por IA, que depende da chave.)
- [x] Endpoints de catálogo, listagem com filtros, resposta, favoritos e estatísticas.
- [x] Prática livre (feedback imediato) e lista (feedback ao final).
- [x] Telas: filtros, questão (com imagens, alternativas e feedback), favoritos, estatísticas por área/disciplina.
- [x] Tela admin de revisão de questões.

**Aceite:** pelo menos 3 anos importados; o gabarito nunca aparece antes da resposta (há teste para isso); a busca textual funciona sem acentos; as estatísticas batem com as tentativas.

## Fase 4: Cronograma de estudos
- [x] CRUD de planos e blocos com validação de sobreposição (409), ativação única e duplicação.
- [x] **Grade semanal**: tabela Seg–Dom × faixas de 30 min (`grid_start`–`grid_end`); clicar/arrastar em células vazias cria um bloco; arrastar move; puxar a borda redimensiona; clicar edita (modal com matéria, cor, notas, lembrete). Cor padrão por área. Em mobile: visualização por dia com lista.
- [x] Resumo: horas por semana e por área (gráfico).
- [x] Lembretes: tick do agendador a cada minuto, cálculo no fuso do usuário, deduplicação por `dedupe_key`, link de descadastro.
- [ ] Exportar o cronograma como imagem/PDF para imprimir (opcional nesta fase).

**Aceite:** não é possível criar blocos sobrepostos; blocos encostados (10:00–11:00 e 11:00–12:00) são aceitos; o lembrete chega uma única vez no horário certo para um usuário em `America/Recife` e outro em `America/Manaus` (teste com relógio simulado).

## Fase 5: Painel e acabamento
- [x] `/dashboard`: blocos de hoje, última redação, acerto da semana, sequência de estudo.
- [x] Exclusão de conta com limpeza do storage; páginas de Termos e Privacidade.
- [x] Observabilidade: logs com `essay_id`/`job_id`; painel admin de custo de IA.
- [x] Deploy na **VPS própria**: `docker-compose.prod.yml` com Caddy (HTTPS), Postgres, backend, worker e frontend; backup diário de `pg_dump` + storage; firewall (só 80/443); instruções de deploy e de restauração.

## Fase 6: Painel admin e concursos
- [x] Painel admin redesenhado (visão geral, IA, custos, sistema, módulos e limites, conteúdo), só com números agregados: nenhuma rota `/admin/*` devolve nome, e-mail, redação ou respostas de aluno (há teste que varre as rotas).
- [x] IA multi-provedor (Anthropic, OpenAI, Google) com adaptadores em `app/ai/providers/`; provedor, modelo e esforço escolhidos por tarefa no painel, valendo sem reiniciar.
- [x] Chaves de API cadastradas pelo painel, criptografadas (Fernet, `SETTINGS_ENCRYPTION_KEY`), nunca devolvidas; salvar exige a senha do admin; botão de testar conexão lista os modelos.
- [x] Tabela de preços editável; modelo sem preço aparece como custo desconhecido. Custos por período, tarefa e modelo; última calibração de cada modelo.
- [x] Sistema: saúde (banco, storage, disco, batimento do worker, e-mail, chaves), fila com reprocessar/cancelar (sem payload, e-mails mascarados), log de ações.
- [x] Módulos liga/desliga (redações, ENEM, concursos, cronograma, cadastros, lembretes); limite de redações por aluno/mês; orçamento mensal de IA com aviso em 80% e bloqueio em 100%.
- [x] Concursos: área "Concursos públicos" com disciplinas próprias; importação de PDF da prova + gabarito pela IA (em trechos de 8 páginas), revisão com a página ao lado, recorte de figura, publicação; itens Certo/Errado; aba Concursos no banco de questões com filtros de banca, órgão, cargo, nível, ano e formato.
- [ ] Calibrar a correção com cada provedor/modelo antes de usar em produção (depende das chaves).
- [ ] Testar a importação com provas reais de cada banca (depende da chave de um provedor com leitura de PDF).

**Aceite:** trocar o modelo de uma tarefa no painel muda o próximo job sem reiniciar; a chave nunca aparece em nenhuma resposta; com o módulo desligado, o aluno recebe 503 e o admin continua acessando; uma prova importada só aparece para os alunos depois de publicada e o gabarito Certo/Errado não vaza antes da resposta.

## Depois do MVP
- Simulado completo cronometrado com **nota TRI estimada**.
- **Cronograma gerado por IA** a partir das horas livres e das áreas fracas.
- Registro de estudo e aderência ao cronograma (`study_sessions`).
- Reescrita guiada: o aluno reescreve um parágrafo e recebe feedback só daquele trecho.
- Painel do professor (turmas, correção revisada por humano).
- App mobile.
