# 04 — API REST

- Base: `/api/v1`. JSON em `snake_case`. Datas em ISO 8601 UTC.
- Auth: `Authorization: Bearer <access_token>`, exceto nos endpoints marcados como públicos.
- Erros no formato `{"error": {"code": "string_estavel", "message": "texto em pt-BR", "details": {...}}}`.
- Paginação por cursor nas listas: `?limit=20&cursor=...` retorna `{"items": [...], "next_cursor": "..."}`.
- A documentação OpenAPI gerada pelo FastAPI (`/docs`) é a referência viva. O frontend gera os tipos a partir dela.

## Auth (`/auth`)
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/register` | público. `{name, email, password, birth_date}` → cria usuário e enfileira e-mail de verificação |
| POST | `/auth/verify-email` | público. `{token}` |
| POST | `/auth/resend-verification` | reenvia (rate limit) |
| POST | `/auth/login` | público. `{email, password}` → `{access_token}` + cookie refresh |
| POST | `/auth/refresh` | usa o cookie e devolve um novo access (com rotação do refresh) |
| POST | `/auth/logout` | revoga o refresh atual |
| POST | `/auth/forgot-password` | público. `{email}`, responde sempre 204 (não revela se o e-mail existe) |
| POST | `/auth/reset-password` | público. `{token, new_password}` (revoga todos os refresh do usuário) |

## Usuário (`/me`)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/me` | perfil do usuário |
| PATCH | `/me` | `name, timezone, target_exam_year, email_reminders_enabled` |
| DELETE | `/me` | exclui a conta (cascata + limpeza do storage via job) |
| GET | `/me/unsubscribe?token=` | público. Desliga lembretes (link do e-mail) |

## Redações (`/essays`)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/essay-themes` | temas oficiais (`?year=`) |
| POST | `/essays` | `multipart/form-data`: `theme_id` **ou** `custom_theme`, e `images[]` (1–2, JPEG/PNG/HEIC, até 10 MB cada) **ou** `text`. Exige e-mail verificado. Responde 202 com o essay |
| GET | `/essays` | histórico (resumo: tema, status, total, data) |
| GET | `/essays/{id}` | detalhe: status, transcrição, resultado (se `graded`), URLs assinadas das imagens |
| PUT | `/essays/{id}/transcription` | `{text}`: salva a revisão do aluno (só em `awaiting_review`) |
| POST | `/essays/{id}/confirm` | confirma a transcrição e enfileira a correção. Status `grading` |
| POST | `/essays/{id}/retry` | só se `failed`. Reenfileira a etapa que falhou |
| DELETE | `/essays/{id}` | exclui a redação e as imagens |
| GET | `/essays/stats` | evolução: lista de `{date, c1..c5, total}` |

Formato do resultado em `GET /essays/{id}` quando `graded`:
```json
{
  "id": "…", "status": "graded",
  "result": {
    "total": 760, "annulled": false, "zero_reason": null,
    "competencies": [
      {"number": 1, "score": 160, "level_summary": "…", "justification": "…",
       "strengths": ["…"], "improvements": ["…"],
       "excerpts": [{"text": "…", "comment": "…"}]}
    ],
    "c1_deviations": [{"text": "…", "type": "concordancia", "suggestion": "…"}],
    "c5_elements": {"agente": {"present": true, "excerpt": "…"}, "acao": {…}, "meio": {…}, "finalidade": {…}, "detalhamento": {…}},
    "general_comment": "…",
    "next_steps": ["…"]
  }
}
```

## Banco de questões
| Método | Rota | Descrição |
|---|---|---|
| GET | `/catalog/areas` | áreas com disciplinas e tópicos (árvore) |
| GET | `/questions` | filtros: `area`, `subject_id`, `topic_id`, `year`, `difficulty=facil\|media\|dificil`, `skill`, `language`, `status=nao_respondidas\|erradas\|favoritas`, `q` (busca). Lista **sem gabarito** |
| GET | `/questions/{id}` | enunciado, alternativas e imagens (**sem gabarito**) |
| POST | `/questions/{id}/answer` | `{selected_option, time_spent_seconds, practice_session_id?}` → `{is_correct, correct_option, explanation_md}`. Em sessão do modo `lista`/`simulado`, **não** devolve o gabarito |
| PUT / DELETE | `/questions/{id}/bookmark` | favoritar / desfavoritar |
| POST | `/practice-sessions` | `{mode, filters, size, time_limit_seconds?}`: sorteia as questões e devolve a sessão com `question_ids` |
| GET | `/practice-sessions/{id}` | progresso |
| POST | `/practice-sessions/{id}/finish` | encerra e devolve o resultado com gabarito e acerto por área |
| GET | `/questions/stats` | acerto por área, disciplina e tópico + série temporal |

**Regra:** o gabarito nunca vai no payload antes de a resposta ser registrada.

## Cronograma (`/study-plans`)
| Método | Rota | Descrição |
|---|---|---|
| GET | `/study-plans` | lista |
| POST | `/study-plans` | `{name, grid_start?, grid_end?}` |
| GET | `/study-plans/active` | cronograma ativo com todos os blocos (para montar a grade) |
| GET | `/study-plans/{id}` | plano + blocos |
| PATCH | `/study-plans/{id}` | renomear, alterar a faixa da grade |
| POST | `/study-plans/{id}/activate` | torna ativo (desativa os outros na mesma transação) |
| POST | `/study-plans/{id}/duplicate` | copia o plano com os blocos |
| DELETE | `/study-plans/{id}` | |
| POST | `/study-plans/{id}/blocks` | `{weekday, start_time "HH:MM", end_time, area_id?, subject_id?, title?, color?, notes?, reminder_minutes_before?}`. 409 `block_overlap` com o bloco conflitante |
| PATCH | `/study-plans/{id}/blocks/{block_id}` | mesmas validações (usado no arrastar/redimensionar) |
| DELETE | `/study-plans/{id}/blocks/{block_id}` | |
| GET | `/study-plans/{id}/summary` | horas por semana, por área e por dia |

Validações dos blocos: `start_time < end_time`; minutos múltiplos de 5 (a interface usa 30, mas a API aceita encaixes finos); pelo menos um entre `area_id`, `subject_id` e `title`; se vierem `subject_id` e `area_id` juntos, devem ser coerentes.

## Painel
| Método | Rota | Descrição |
|---|---|---|
| GET | `/dashboard` | resumo: próximos blocos de hoje, última redação, acerto da semana, sequência de dias estudando |

## Admin (role `admin`)
| Método | Rota | Descrição |
|---|---|---|
| GET/PATCH | `/admin/questions/{id}` | revisar a questão importada (texto, disciplina, tópicos, `reviewed`) |
| GET | `/admin/questions?reviewed=false` | fila de revisão |
| POST/PATCH | `/admin/essay-themes` | gerenciar temas |
| GET | `/admin/ai-usage` | custo por dia/propósito |
| GET/PUT | `/admin/messages/welcome` | boas-vindas automática por e-mail após a 1ª assinatura aprovada (texto com `{nome}`, liga/desliga, atraso em minutos) |
| POST | `/admin/messages/welcome/test` | envia o texto para o e-mail do próprio admin |
| POST | `/admin/users/{id}/message` | mensagem personalizada por e-mail para uma conta (escolhida em Admin → Usuários); responde só `{"queued": true}` |

## Saúde
`GET /health`: público. `{db: "ok", storage: "ok"}`.
