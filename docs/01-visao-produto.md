# 01 — Visão do produto

## Público
Estudantes do ensino médio e vestibulandos que se preparam para o ENEM. Muitos são menores de idade, o que tem impacto na LGPD (ver final).

## Módulo 1 — Correção de redações

### Fluxo do aluno
1. Escolhe um tema: oficial de anos anteriores (com textos motivadores) ou personalizado (digita o título).
2. Envia 1 foto da folha (até 2 páginas, se necessário). Dicas na tela: boa luz, folha inteira, sem sombra e sem inclinação.
3. O sistema pré-processa a imagem e transcreve com IA (status `transcribing`).
4. O aluno vê **a foto ao lado da transcrição**, linha a linha, e corrige palavras lidas errado. Os trechos marcados como `[ilegível]` aparecem destacados (status `awaiting_review`).
5. O aluno confirma e a correção roda (status `grading`).
6. Resultado (status `graded`). Ele inclui:
   - nota total e nota por competência (C1–C5);
   - para cada competência: nível atingido, justificativa, pontos fortes, o que melhorar e trechos comentados;
   - C1: lista de desvios com trecho, tipo e sugestão;
   - C5: checklist dos 5 elementos da proposta de intervenção (agente, ação, meio/modo, finalidade, detalhamento);
   - comentário geral e próximos passos.
7. O aluno recebe um e-mail quando a correção fica pronta, porque ela pode levar 1 a 2 minutos.

### Outros requisitos
- Histórico de redações com gráfico de evolução por competência.
- Alternativa: o aluno pode **digitar/colar o texto** em vez de enviar foto, pulando os passos 2 a 4.

## Módulo 2 — Banco de questões

- Hierarquia: **Área** (Linguagens, Humanas, Natureza, Matemática) → **Disciplina** (ex.: Física) → **Tópico** (ex.: Eletrodinâmica).
- Filtros: área, disciplina, tópico, ano, dificuldade (parâmetro *b* da TRI), habilidade (H1–H30), língua estrangeira, "não respondidas" e "errei".
- Modos:
  - **Prática livre**: uma questão por vez, com feedback imediato.
  - **Lista/simulado**: N questões com cronômetro e feedback só ao final.
- Registro de cada resposta (alternativa, acerto e tempo).
- Favoritos.
- Estatísticas: % de acerto por área/disciplina/tópico e evolução no tempo.
- Busca textual no enunciado (full-text search em português).

## Módulo 3 — Cronograma de estudos

- **Grade semanal** em formato de tabela: colunas Seg–Dom e linhas de horário em intervalos de 30 min. É configurável (ex.: das 06:00 às 23:30).
- O aluno clica/arrasta para criar um **bloco**: dia, início, fim, matéria (área e/ou disciplina), título opcional, cor, observações e lembrete (X minutos antes, opcional).
- Blocos não podem se sobrepor no mesmo dia. Blocos que cruzam a meia-noite não são suportados (o aluno divide em dois).
- O aluno pode ter vários cronogramas (ex.: "Período de aulas" e "Férias"), mas só **um ativo** por vez.
- Resumo: total de horas por semana e por área (gráfico).
- **Registro de estudo** (fase posterior): marcar um bloco como cumprido e ver a aderência semanal.
- **Lembretes por e-mail** (Resend) antes dos blocos, respeitando o fuso do usuário.
- (Fase extra) **Gerar cronograma com IA**: o aluno informa horas disponíveis e áreas fracas (inferidas do banco de questões) e o Claude sugere uma grade editável.

## Contas e e-mails
- Cadastro com e-mail e senha, verificação de e-mail e recuperação de senha. Todos os e-mails são enviados via Resend.
- E-mails transacionais: verificação, redefinição de senha, correção pronta e lembrete de estudo.
- Preferência para desligar lembretes.

## Escopo do MVP
Inclui: auth completo, correção de redação (foto e texto), banco de questões com importação de pelo menos 3 anos, prática livre, cronograma com grade e lembretes.

Fica para depois: simulados cronometrados completos com nota TRI estimada, geração de cronograma por IA, registro de estudo/aderência, app mobile e painel de professor.

O produto **não tem cotas nem planos** (gratuito/pago): todo usuário com e-mail verificado usa tudo sem limite. Não implemente limites de uso, planos ou cobrança.

## LGPD (não ignorar)
- Redações e dados de estudo são dados pessoais. Pode haver menores de idade, então é preciso coletar data de nascimento e exigir consentimento do responsável para menores de 18.
- Termos de uso e política de privacidade devem informar que o texto e a imagem são enviados a um provedor de IA (Anthropic) para processamento.
- O aluno pode excluir uma redação (apaga imagens do storage) e excluir a conta (apaga tudo em cascata).

## Observação sobre conteúdo das questões
As provas do ENEM são publicadas pelo INEP, mas muitos textos-base dentro das questões são de terceiros. Antes de lançar comercialmente, verifique os aspectos de direitos autorais com quem entende do assunto.
