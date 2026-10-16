-- =====================================================================
-- Rumo1000 — schema de referência (PostgreSQL 16)
-- A fonte da verdade em código são os models SQLAlchemy + Alembic.
-- Este arquivo deve ser mantido em sincronia como documentação.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- e-mail case-insensitive
CREATE EXTENSION IF NOT EXISTS unaccent;   -- busca sem acentos

-- Configuração de busca textual: português + remoção de acentos
-- ("funções quadráticas" encontra "função quadrática")
CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = portuguese);
ALTER TEXT SEARCH CONFIGURATION pt_unaccent
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;

-- ---------------------------------------------------------------------
-- Função utilitária: updated_at automático
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- Tipos enumerados
-- ---------------------------------------------------------------------
CREATE TYPE user_role           AS ENUM ('student', 'admin');
CREATE TYPE email_token_purpose AS ENUM ('verify_email', 'reset_password');
CREATE TYPE essay_status        AS ENUM ('uploaded', 'transcribing', 'awaiting_review',
                                         'grading', 'graded', 'failed');
CREATE TYPE essay_input_type    AS ENUM ('photo', 'text');
CREATE TYPE essay_zero_reason   AS ENUM (
  'folha_em_branco',
  'texto_insuficiente',             -- até 7 linhas
  'fuga_total_ao_tema',
  'nao_dissertativo_argumentativo',
  'parte_desconectada',
  'copia_textos_motivadores',
  'lingua_estrangeira',
  'identificacao',
  'improperios_ou_anulacao',
  'ilegivel'
);
CREATE TYPE exam_application    AS ENUM ('regular', 'reaplicacao', 'digital', 'ppl');
CREATE TYPE foreign_language    AS ENUM ('ingles', 'espanhol');
CREATE TYPE practice_mode       AS ENUM ('livre', 'lista', 'simulado');
CREATE TYPE ai_purpose          AS ENUM ('transcription', 'grading', 'planner', 'other');
CREATE TYPE job_status          AS ENUM ('pending', 'running', 'done', 'failed');

-- =====================================================================
-- USUÁRIOS E AUTENTICAÇÃO
-- =====================================================================
CREATE TABLE users (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                     text        NOT NULL,
  email                    citext      NOT NULL UNIQUE,
  password_hash            text        NOT NULL,
  role                     user_role   NOT NULL DEFAULT 'student',
  email_verified_at        timestamptz,
  birth_date               date,                       -- LGPD: identificar menores
  guardian_consent_at      timestamptz,                -- consentimento do responsável (< 18)
  timezone                 text        NOT NULL DEFAULT 'America/Sao_Paulo',
  target_exam_year         smallint,
  email_reminders_enabled  boolean     NOT NULL DEFAULT true,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE email_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose     email_token_purpose NOT NULL,
  token_hash  text NOT NULL UNIQUE,
  expires_at  timestamptz NOT NULL,
  used_at     timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_email_tokens_user ON email_tokens (user_id, purpose);

CREATE TABLE refresh_tokens (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   text NOT NULL UNIQUE,
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz,
  replaced_by  uuid REFERENCES refresh_tokens(id),
  user_agent   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);

-- =====================================================================
-- CATÁLOGO: ÁREAS, DISCIPLINAS, TÓPICOS (compartilhado por questões e cronograma)
-- =====================================================================
CREATE TABLE knowledge_areas (
  id    smallint PRIMARY KEY,
  code  char(2)  NOT NULL UNIQUE,     -- LC, CH, CN, MT
  name  text     NOT NULL
);

CREATE TABLE subjects (
  id       serial PRIMARY KEY,
  area_id  smallint NOT NULL REFERENCES knowledge_areas(id),
  name     text NOT NULL,
  slug     text NOT NULL UNIQUE
);
CREATE INDEX idx_subjects_area ON subjects (area_id);

CREATE TABLE topics (
  id          serial PRIMARY KEY,
  subject_id  int  NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  parent_id   int  REFERENCES topics(id) ON DELETE CASCADE,  -- subtópicos
  name        text NOT NULL,
  slug        text NOT NULL,
  UNIQUE (subject_id, slug)
);

-- =====================================================================
-- REDAÇÕES
-- =====================================================================
CREATE TABLE essay_themes (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title             text     NOT NULL,
  year              smallint,                  -- ano do ENEM, se oficial
  is_official       boolean  NOT NULL DEFAULT false,
  motivating_texts  text,                      -- markdown com os textos motivadores
  created_by        uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE essays (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  theme_id            uuid REFERENCES essay_themes(id) ON DELETE SET NULL,
  custom_theme        text,
  input_type          essay_input_type NOT NULL,
  status              essay_status     NOT NULL DEFAULT 'uploaded',
  transcription_raw   jsonb,     -- saída da IA: {linhas:[], confianca, observacoes, ...}
  transcription_text  text,      -- texto final confirmado pelo aluno
  line_count          smallint,
  error_message       text,
  confirmed_at        timestamptz,   -- aluno confirmou a transcrição
  graded_at           timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT essay_has_theme CHECK (theme_id IS NOT NULL OR custom_theme IS NOT NULL)
);
CREATE INDEX idx_essays_user ON essays (user_id, created_at DESC);
CREATE INDEX idx_essays_status ON essays (status) WHERE status IN ('transcribing', 'grading');
CREATE TRIGGER trg_essays_updated BEFORE UPDATE ON essays
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE essay_images (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  essay_id              uuid NOT NULL REFERENCES essays(id) ON DELETE CASCADE,
  page                  smallint NOT NULL DEFAULT 1 CHECK (page BETWEEN 1 AND 2),
  original_storage_key  text NOT NULL,
  storage_key           text,                 -- imagem pré-processada
  mime_type             text NOT NULL,
  width                 int,
  height                int,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (essay_id, page)
);

-- Cada execução independente de correção (simula um corretor)
CREATE TABLE essay_grading_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  essay_id        uuid NOT NULL REFERENCES essays(id) ON DELETE CASCADE,
  run_number      smallint NOT NULL CHECK (run_number BETWEEN 1 AND 5),
  model           text NOT NULL,
  prompt_version  text NOT NULL,
  c1  smallint NOT NULL CHECK (c1 IN (0, 40, 80, 120, 160, 200)),
  c2  smallint NOT NULL CHECK (c2 IN (0, 40, 80, 120, 160, 200)),
  c3  smallint NOT NULL CHECK (c3 IN (0, 40, 80, 120, 160, 200)),
  c4  smallint NOT NULL CHECK (c4 IN (0, 40, 80, 120, 160, 200)),
  c5  smallint NOT NULL CHECK (c5 IN (0, 40, 80, 120, 160, 200)),
  total           smallint GENERATED ALWAYS AS (c1 + c2 + c3 + c4 + c5) STORED,
  annulled        boolean NOT NULL DEFAULT false,
  zero_reason     essay_zero_reason,
  feedback        jsonb NOT NULL,             -- saída estruturada completa da IA
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (essay_id, run_number),
  CONSTRAINT annulled_means_zero CHECK (NOT annulled OR (c1 + c2 + c3 + c4 + c5) = 0),
  CONSTRAINT annulled_has_reason CHECK (annulled = (zero_reason IS NOT NULL))
);

-- Resultado consolidado mostrado ao aluno (1 por redação)
CREATE TABLE essay_results (
  essay_id          uuid PRIMARY KEY REFERENCES essays(id) ON DELETE CASCADE,
  c1  smallint NOT NULL CHECK (c1 BETWEEN 0 AND 200),
  c2  smallint NOT NULL CHECK (c2 BETWEEN 0 AND 200),
  c3  smallint NOT NULL CHECK (c3 BETWEEN 0 AND 200),
  c4  smallint NOT NULL CHECK (c4 BETWEEN 0 AND 200),
  c5  smallint NOT NULL CHECK (c5 BETWEEN 0 AND 200),
  total             smallint GENERATED ALWAYS AS (c1 + c2 + c3 + c4 + c5) STORED,
  annulled          boolean NOT NULL DEFAULT false,
  zero_reason       essay_zero_reason,
  runs_used         smallint NOT NULL,          -- 2 ou 3
  needed_third_run  boolean  NOT NULL DEFAULT false,
  feedback          jsonb    NOT NULL,          -- feedback consolidado
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- BANCO DE QUESTÕES
-- =====================================================================
CREATE TABLE exams (
  id             serial PRIMARY KEY,
  year           smallint NOT NULL,
  application    exam_application NOT NULL DEFAULT 'regular',
  day            smallint NOT NULL CHECK (day IN (1, 2)),
  booklet_color  text NOT NULL,            -- azul, amarelo, branco, rosa, cinza...
  booklet_code   int,                      -- CO_PROVA dos microdados INEP
  UNIQUE (year, application, day, booklet_color)
);

-- Uma questão é armazenada uma única vez (identificada pelo item INEP);
-- ela aparece em vários cadernos com numeração diferente (exam_questions).
CREATE TABLE questions (
  id                serial PRIMARY KEY,
  inep_item_code    int UNIQUE,              -- CO_ITEM
  year              smallint NOT NULL,
  area_id           smallint NOT NULL REFERENCES knowledge_areas(id),
  subject_id        int REFERENCES subjects(id),
  foreign_language  foreign_language,        -- só para LC (inglês/espanhol)
  skill_code        smallint CHECK (skill_code BETWEEN 1 AND 30),   -- H1..H30
  statement_md      text NOT NULL,           -- enunciado em markdown (imagens via question_assets)
  correct_option    char(1) CHECK (correct_option IN ('A','B','C','D','E')),
  is_annulled       boolean NOT NULL DEFAULT false,
  irt_a             numeric(8,5),            -- discriminação
  irt_b             numeric(8,5),            -- dificuldade
  irt_c             numeric(8,5),            -- acerto ao acaso
  explanation_md    text,                    -- resolução comentada
  source            text NOT NULL DEFAULT 'inep',
  reviewed          boolean NOT NULL DEFAULT false,  -- conferida por humano após importação
  search_vector     tsvector GENERATED ALWAYS AS (to_tsvector('pt_unaccent', statement_md)) STORED,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT answer_or_annulled CHECK (is_annulled OR correct_option IS NOT NULL)
);
CREATE INDEX idx_questions_area_subject ON questions (area_id, subject_id);
CREATE INDEX idx_questions_year ON questions (year);
CREATE INDEX idx_questions_irt_b ON questions (irt_b);
CREATE INDEX idx_questions_search ON questions USING gin (search_vector);
CREATE TRIGGER trg_questions_updated BEFORE UPDATE ON questions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE exam_questions (
  exam_id      int NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
  question_id  int NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  position     smallint NOT NULL,            -- número da questão no caderno
  PRIMARY KEY (exam_id, question_id),
  UNIQUE (exam_id, position)
);

CREATE TABLE question_options (
  question_id  int     NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  letter       char(1) NOT NULL CHECK (letter IN ('A','B','C','D','E')),
  text_md      text    NOT NULL,
  PRIMARY KEY (question_id, letter)
);

CREATE TABLE question_assets (
  id           serial PRIMARY KEY,
  question_id  int  NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  storage_key  text NOT NULL,
  alt_text     text,
  position     smallint NOT NULL DEFAULT 1
);

CREATE TABLE question_topics (
  question_id  int NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  topic_id     int NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  PRIMARY KEY (question_id, topic_id)
);
CREATE INDEX idx_question_topics_topic ON question_topics (topic_id);

CREATE TABLE practice_sessions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mode         practice_mode NOT NULL DEFAULT 'livre',
  filters      jsonb NOT NULL DEFAULT '{}'::jsonb,
  question_ids int[],                       -- ordem fixa para lista/simulado
  time_limit_seconds int,
  started_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz
);
CREATE INDEX idx_practice_sessions_user ON practice_sessions (user_id, started_at DESC);

CREATE TABLE question_attempts (
  id                   bigserial PRIMARY KEY,
  user_id              uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  question_id          int  NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  practice_session_id  uuid REFERENCES practice_sessions(id) ON DELETE SET NULL,
  selected_option      char(1) CHECK (selected_option IN ('A','B','C','D','E')),
  is_correct           boolean NOT NULL,
  time_spent_seconds   int CHECK (time_spent_seconds >= 0),
  answered_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_attempts_user_time ON question_attempts (user_id, answered_at DESC);
CREATE INDEX idx_attempts_user_question ON question_attempts (user_id, question_id);

CREATE TABLE question_bookmarks (
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  question_id  int  NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, question_id)
);

-- =====================================================================
-- CRONOGRAMA DE ESTUDOS
-- =====================================================================
CREATE TABLE study_plans (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        text NOT NULL,
  is_active   boolean NOT NULL DEFAULT false,
  grid_start  time NOT NULL DEFAULT '06:00',   -- faixa exibida na tabela
  grid_end    time NOT NULL DEFAULT '23:30',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (grid_end > grid_start)
);
-- no máximo 1 cronograma ativo por usuário
CREATE UNIQUE INDEX uq_study_plans_active ON study_plans (user_id) WHERE is_active;
CREATE TRIGGER trg_study_plans_updated BEFORE UPDATE ON study_plans
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- weekday: ISO 8601 → 1 = segunda ... 7 = domingo
-- Sobreposição de blocos no mesmo dia é validada no service (StudyBlockOverlapError).
CREATE TABLE study_blocks (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id                  uuid NOT NULL REFERENCES study_plans(id) ON DELETE CASCADE,
  weekday                  smallint NOT NULL CHECK (weekday BETWEEN 1 AND 7),
  start_time               time NOT NULL,
  end_time                 time NOT NULL,
  area_id                  smallint REFERENCES knowledge_areas(id),
  subject_id               int REFERENCES subjects(id),
  title                    text,                 -- ex.: "Revisão de Funções", "Redação"
  color                    text,                 -- hex; default derivado da área
  notes                    text,
  reminder_minutes_before  smallint CHECK (reminder_minutes_before BETWEEN 0 AND 1440),
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  CHECK (end_time > start_time),
  CHECK (area_id IS NOT NULL OR subject_id IS NOT NULL OR title IS NOT NULL)
);
CREATE INDEX idx_study_blocks_plan_day ON study_blocks (plan_id, weekday, start_time);
CREATE INDEX idx_study_blocks_reminder ON study_blocks (weekday, start_time)
  WHERE reminder_minutes_before IS NOT NULL;
CREATE TRIGGER trg_study_blocks_updated BEFORE UPDATE ON study_blocks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Registro do que foi efetivamente estudado (fase posterior)
CREATE TABLE study_sessions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  block_id          uuid REFERENCES study_blocks(id) ON DELETE SET NULL,
  subject_id        int REFERENCES subjects(id),
  started_at        timestamptz NOT NULL,
  duration_minutes  smallint NOT NULL CHECK (duration_minutes > 0),
  notes             text,
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_study_sessions_user ON study_sessions (user_id, started_at DESC);

-- =====================================================================
-- INFRA: USO DE IA, E-MAILS, FILA DE JOBS
-- =====================================================================
CREATE TABLE ai_usage (
  id                  bigserial PRIMARY KEY,
  user_id             uuid REFERENCES users(id) ON DELETE SET NULL,
  essay_id            uuid REFERENCES essays(id) ON DELETE SET NULL,
  purpose             ai_purpose NOT NULL,
  model               text NOT NULL,
  input_tokens        int NOT NULL DEFAULT 0,
  output_tokens       int NOT NULL DEFAULT 0,
  cache_read_tokens   int NOT NULL DEFAULT 0,
  cache_write_tokens  int NOT NULL DEFAULT 0,
  cost_usd            numeric(10,6),
  latency_ms          int,
  request_id          text,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_ai_usage_user_time ON ai_usage (user_id, created_at DESC);

CREATE TABLE email_logs (
  id          bigserial PRIMARY KEY,
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  type        text NOT NULL,           -- verify_email, reset_password, essay_graded, study_reminder
  to_email    citext NOT NULL,
  resend_id   text,
  status      text NOT NULL DEFAULT 'queued',   -- queued, sent, failed
  error       text,
  dedupe_key  text UNIQUE,             -- ex.: reminder:{block_id}:{2026-10-14}
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id            bigserial PRIMARY KEY,
  queue         text NOT NULL,
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  status        job_status NOT NULL DEFAULT 'pending',
  attempts      smallint NOT NULL DEFAULT 0,
  max_attempts  smallint NOT NULL DEFAULT 5,
  run_after     timestamptz NOT NULL DEFAULT now(),
  locked_at     timestamptz,
  last_error    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_pending ON jobs (run_after) WHERE status = 'pending';
CREATE INDEX idx_jobs_running ON jobs (locked_at) WHERE status = 'running';
CREATE TRIGGER trg_jobs_updated BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- SEED MÍNIMO
-- =====================================================================
INSERT INTO knowledge_areas (id, code, name) VALUES
  (1, 'LC', 'Linguagens, Códigos e suas Tecnologias'),
  (2, 'CH', 'Ciências Humanas e suas Tecnologias'),
  (3, 'CN', 'Ciências da Natureza e suas Tecnologias'),
  (4, 'MT', 'Matemática e suas Tecnologias');

INSERT INTO subjects (area_id, name, slug) VALUES
  (1, 'Língua Portuguesa', 'portugues'),
  (1, 'Literatura', 'literatura'),
  (1, 'Inglês', 'ingles'),
  (1, 'Espanhol', 'espanhol'),
  (1, 'Artes', 'artes'),
  (1, 'Educação Física', 'educacao-fisica'),
  (1, 'Tecnologias da Informação e Comunicação', 'tic'),
  (1, 'Redação', 'redacao'),
  (2, 'História', 'historia'),
  (2, 'Geografia', 'geografia'),
  (2, 'Filosofia', 'filosofia'),
  (2, 'Sociologia', 'sociologia'),
  (3, 'Física', 'fisica'),
  (3, 'Química', 'quimica'),
  (3, 'Biologia', 'biologia'),
  (4, 'Matemática', 'matematica');
