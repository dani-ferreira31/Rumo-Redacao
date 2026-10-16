# 05 — Correção de redações com IA

Este é o coração do produto. O objetivo é **aproximar a nota da banca do ENEM**, não só gerar um texto bonito. Toda decisão aqui deve poder ser medida (ver "Calibração").

## Visão do pipeline

```
[foto] → pré-processamento (OpenCV)
       → ETAPA 1: transcrição literal (Claude, visão)  ──► aluno revisa e confirma
       → ETAPA 2: checagens objetivas (código)
       → ETAPA 3: correção × 2 independentes (Claude)
       → ETAPA 4: 3ª correção se discrepante
       → ETAPA 5: consolidação → essay_results → e-mail
```

## Integração com a Anthropic (regras gerais)

- SDK oficial `anthropic` (cliente assíncrono `AsyncAnthropic`), sempre via `app/ai/client.py`.
- Modelos via `ANTHROPIC_MODEL_TRANSCRIPTION` e `ANTHROPIC_MODEL_GRADING`. Comece com o mesmo modelo nos dois e teste alternativas na calibração (um modelo mais forte só na correção, por exemplo).
- **Saída estruturada via tool use**: defina uma ferramenta (`registrar_transcricao` / `registrar_correcao`) com JSON Schema e force o uso com `tool_choice={"type": "tool", "name": ...}`. Depois valide com Pydantic. Se a validação falhar, tente 1 vez de novo enviando o erro, e depois falhe o job.
- **Prompt caching**: o prompt de sistema da correção (instruções + rubrica + exemplos) é grande e igual para todas as redações. Marque o último bloco estático com `cache_control: {"type": "ephemeral"}`. A 2ª e a 3ª execução da mesma redação, e as redações seguintes, leem do cache.
- Registre em `ai_usage`: tokens de entrada/saída/cache, latência, `request_id`, custo estimado (tabela de preços em config).
- Timeouts e retries: o SDK já tenta de novo em 429/5xx. Configure `max_retries=3` e `timeout=120s`. Erros persistentes fazem o job falhar e a fila reprocessa com backoff.
- Consulte a documentação atual da Anthropic (visão, tool use, prompt caching) ao implementar. Não confie em parâmetros de memória.

---

## ETAPA 1 — Transcrição

**Entrada:** imagem(ns) pré-processada(s) em base64 + prompt `prompts/transcricao.md`.

**Princípios do prompt** (escreva-o em português):
1. Transcreva **exatamente** o que está escrito, linha por linha da folha, **preservando todos os erros** de ortografia, acentuação, pontuação, concordância e maiúsculas/minúsculas.
2. **Nunca** corrija, complete ou "melhore" o texto. Se o aluno escreveu "concerteza", transcreva "concerteza".
3. Palavra ilegível vira `[ilegível]`. Palavra duvidosa vira `[?palavra]` (melhor palpite).
4. Palavras riscadas pelo aluno são **omitidas**. Inserções acima da linha (com sinal de inserção) entram no ponto indicado.
5. Ignore o cabeçalho impresso, a numeração das linhas e qualquer coisa fora da área de texto.
6. Informe se há título (é opcional no ENEM e não conta como linha de texto).
7. Sinalize se encontrar algo que possa identificar o aluno (nome, assinatura). Isso anula a redação no ENEM.

**Ferramenta `registrar_transcricao`** (schema resumido):
```json
{
  "titulo": "string | null",
  "linhas": ["string"],                 // uma entrada por linha física escrita
  "qtd_ilegiveis": "integer",
  "confianca": "alta | media | baixa",
  "possivel_identificacao": "boolean",
  "folha_em_branco": "boolean",
  "observacoes": "string"
}
```

**Depois da IA:**
- Salve em `essays.transcription_raw`. Junte as linhas em `transcription_text` (rascunho editável), `line_count = len(linhas)` e status `awaiting_review`.
- A interface mostra imagem e texto lado a lado e destaca `[ilegível]` e `[?…]`. **A confirmação é bloqueada enquanto restarem marcadores**: o aluno precisa resolvê-los.
- Se `confianca = baixa`, mostre um aviso sugerindo nova foto.

**Métrica de qualidade da transcrição:** CER (*character error rate*) contra transcrições feitas à mão. Monte um conjunto próprio de 30 a 50 fotos reais, com letras variadas. Meta inicial: CER < 3%.

---

## ETAPA 2 — Checagens objetivas (código, sem IA)

Rodam sobre `transcription_text` confirmado:

| Checagem | Regra | Efeito |
|---|---|---|
| Folha em branco | texto vazio | anula (`folha_em_branco`) e não chama a IA |
| Texto insuficiente | ≤ 7 linhas de texto (sem título) | anula (`texto_insuficiente`) e não chama a IA |
| Cópia dos motivadores | sobreposição de n-gramas (n=8) com `essay_themes.motivating_texts`; linhas copiadas são descontadas da contagem | se o que sobra tiver ≤ 7 linhas, anula (`copia_textos_motivadores`); senão, informa as linhas copiadas à IA |
| Excesso de linhas | > 30 linhas | só aviso (no ENEM o texto além da linha 30 não é considerado) |
| Estatísticas | nº de parágrafos, palavras, média de palavras por frase | contexto para a IA |

Para redações enviadas por foto, a contagem de linhas usa as linhas físicas da transcrição. Para texto digitado, estime ~10 palavras por linha da folha oficial e deixe isso claro na interface.

---

## ETAPA 3 — Correção

### Estrutura das mensagens
- **system** (com cache): `prompts/correcao_sistema.md` (papel e regras) + `prompts/rubrica.md` (grade completa) + exemplos calibrados (*few-shot*).
- **user**: tema, textos motivadores (se houver), resultado das checagens objetivas e a redação com **linhas numeradas** (`[L01] …`), para a IA citar trechos com precisão.

### Papel e regras (`correcao_sistema.md`)
- Você é um corretor experiente da banca do ENEM e segue estritamente a Matriz de Referência e a Cartilha do Participante do INEP.
- Primeiro decida se a redação deve ser **anulada**. Só depois avalie as competências.
- Para cada competência, **compare o texto com a descrição de cada nível** e escolha o nível que melhor descreve o texto como um todo. Não parta de uma nota "média" e ajuste.
- Justifique cada nota citando trechos com o número da linha.
- Seja fiel à régua: nota 200 é possível e deve ser dada quando o texto atende ao nível máximo; textos fracos devem receber notas baixas. (LLMs tendem a puxar tudo para o meio, e este alerta é explícito no prompt.)
- O feedback é para um estudante: tom respeitoso, direto e acionável.

### Grade das competências (`rubrica.md`)

Resumo para orientar a escrita do prompt. **Monte o arquivo final a partir da Cartilha do Participante mais recente do INEP**, que é a fonte oficial e detalha cada nível.

**C1: Domínio da modalidade escrita formal**
| Nota | Descrição resumida |
|---|---|
| 200 | Excelente domínio. Desvios gramaticais e de convenções são raros (no máximo uma falha de estrutura sintática e poucos desvios) |
| 160 | Bom domínio, com poucos desvios |
| 120 | Domínio mediano, com alguns desvios |
| 80 | Domínio insuficiente, com muitos desvios |
| 40 | Domínio precário, com desvios diversificados e frequentes |
| 0 | Desconhecimento da modalidade escrita formal |

**C2: Compreensão da proposta, repertório e tipo textual dissertativo-argumentativo**
| Nota | Descrição resumida |
|---|---|
| 200 | Argumentação consistente, com repertório sociocultural legitimado, pertinente ao tema e **produtivo** (usado a favor do argumento); excelente domínio do tipo textual |
| 160 | Argumentação consistente, repertório legitimado e pertinente; bom domínio do tipo |
| 120 | Argumentação previsível; repertório baseado nos motivadores ou não legitimado; domínio mediano |
| 80 | Cópia de trechos dos motivadores ou domínio insuficiente do tipo (ex.: muitos traços de outros tipos textuais) |
| 40 | **Tangenciamento do tema** ou domínio precário do tipo |
| 0 | Fuga total ao tema / não atende ao tipo, o que **anula a redação** |

**C3: Seleção, relação, organização e interpretação das informações (projeto de texto)**
| Nota | Descrição resumida |
|---|---|
| 200 | Informações relacionadas ao tema, consistentes e organizadas, com projeto de texto estratégico e autoria |
| 160 | Informações organizadas, com indícios de autoria |
| 120 | Informações limitadas aos motivadores, pouco organizadas |
| 80 | Informações desorganizadas ou contraditórias, limitadas aos motivadores |
| 40 | Informações pouco relacionadas ao tema, incoerentes, sem defesa de ponto de vista |
| 0 | Informações não relacionadas ao tema e sem defesa de ponto de vista |

**C4: Mecanismos linguísticos de coesão**
| Nota | Descrição resumida |
|---|---|
| 200 | Articula bem as partes do texto, com repertório diversificado de recursos coesivos inter e intraparágrafos |
| 160 | Articula com poucas inadequações e repertório diversificado |
| 120 | Articulação mediana, com inadequações e repertório pouco diversificado |
| 80 | Articulação insuficiente, com muitas inadequações e repertório limitado |
| 40 | Articulação precária |
| 0 | Não articula as informações |

**C5: Proposta de intervenção (respeitando os direitos humanos)**
A IA identifica os 5 elementos: **agente** (quem), **ação** (o quê), **meio/modo** (como), **finalidade** (para quê/efeito) e **detalhamento** (desdobramento de algum elemento).
| Nota | Descrição resumida |
|---|---|
| 200 | Proposta muito bem elaborada, relacionada ao tema e articulada à discussão, com os 5 elementos válidos |
| 160 | 4 elementos válidos |
| 120 | 3 elementos válidos |
| 80 | 2 elementos válidos |
| 40 | 1 elemento, ou proposta vaga/precária/não articulada à discussão |
| 0 | Ausência de proposta, proposta não relacionada ao tema **ou desrespeito aos direitos humanos** |

**Regras cruzadas a explicitar no prompt:**
- Tangenciamento do tema: C2 = 40, e C3 e C5 limitadas a 40.
- Motivos de anulação (todas as notas zero): fuga total ao tema; não atendimento ao tipo dissertativo-argumentativo; texto com até 7 linhas; impropérios, desenhos ou outras formas propositais de anulação; parte do texto deliberadamente desconectada do tema; identificação do participante; texto predominantemente em língua estrangeira; cópia integral dos motivadores (texto próprio insuficiente).

### Ferramenta `registrar_correcao` (schema)
```json
{
  "anulada": "boolean",
  "motivo_anulacao": "fuga_total_ao_tema | nao_dissertativo_argumentativo | parte_desconectada | copia_textos_motivadores | lingua_estrangeira | identificacao | improperios_ou_anulacao | null",
  "tangenciamento": "boolean",
  "competencias": [
    {
      "numero": "1..5",
      "analise": "string (raciocínio comparando o texto com os níveis, antes de decidir)",
      "nota": "0 | 40 | 80 | 120 | 160 | 200",
      "resumo_nivel": "string",
      "justificativa": "string",
      "pontos_fortes": ["string"],
      "pontos_melhoria": ["string"],
      "trechos": [{"linha": "integer", "trecho": "string", "comentario": "string"}]
    }
  ],
  "desvios_c1": [{"linha": "integer", "trecho": "string", "tipo": "ortografia | acentuacao | pontuacao | concordancia | regencia | crase | sintaxe | vocabulario | outro", "sugestao": "string"}],
  "elementos_c5": {
    "agente":       {"presente": "boolean", "trecho": "string | null"},
    "acao":         {"presente": "boolean", "trecho": "string | null"},
    "meio":         {"presente": "boolean", "trecho": "string | null"},
    "finalidade":   {"presente": "boolean", "trecho": "string | null"},
    "detalhamento": {"presente": "boolean", "trecho": "string | null"}
  },
  "comentario_geral": "string",
  "proximos_passos": ["string (2 a 4 ações concretas para a próxima redação)"]
}
```
O campo `analise` vem **antes** de `nota` de propósito: a IA raciocina primeiro e decide depois, o que melhora a consistência.

**Validações no código, após a resposta** (corrija ou rejeite):
- `anulada = true` → todas as notas viram 0.
- `tangenciamento = true` → C2 = 40, C3 ≤ 40, C5 ≤ 40.
- C5: a nota deve ser coerente com a contagem de elementos presentes (5→200, 4→160, 3→120, 2→80, 1→40). Se divergir, registre o aviso e use a contagem como desempate na consolidação.
- Notas fora de `{0,40,…,200}` → rejeita e tenta novamente.

---

## ETAPA 4 — Múltiplos corretores (simulação da banca)

1. Rode **2 correções independentes** (chamadas separadas, mesma entrada, temperatura padrão), em paralelo com `asyncio.gather`.
2. **Discrepância** (critério do ENEM): diferença no total > 100 **ou** em qualquer competência > 80. Havendo discrepância, rode a 3ª correção.
3. Se apenas uma execução anular a redação, isso também conta como discrepância.

## ETAPA 5 — Consolidação

- Sem discrepância: nota final de cada competência = média das 2 execuções.
- Com 3 execuções: use as **duas mais próximas no total** e tire a média.
- Anulação só se a maioria das execuções anular pelo mesmo motivo.
- **Feedback textual**: use o da execução cujo total ficou mais perto da nota final (uma só voz, sem contradições). Para `desvios_c1`, una os desvios das execuções usadas, removendo duplicados por `(linha, trecho)`.
- Grave `essay_results`, atualize `essays.status = graded`, `graded_at`, e enfileire o e-mail `essay_graded`.

Custo esperado: 2 a 3 chamadas de correção + 1 de transcrição por redação. Com caching, fica tipicamente na casa dos centavos de dólar. Acompanhe em `ai_usage`.

---

## Calibração (o que separa brinquedo de produto)

Script `scripts/eval_grading.py`:

1. **Dataset**: redações já corrigidas por competência. Fontes:
   - corpus acadêmico **Essay-BR** (redações no modelo ENEM com notas por competência; verifique a licença e baixe localmente em `data/essay-br/`);
   - redações nota 1000 divulgadas publicamente;
   - um conjunto próprio corrigido por professores de redação (o mais valioso, por ser o mais parecido com o seu público).
2. **Execução**: roda a ETAPA 2 a 5 em N redações (comece com 200) e salva as predições em CSV.
3. **Métricas por competência e no total**:
   - **QWK** (*Quadratic Weighted Kappa*), métrica padrão em correção automática;
   - **% de acerto exato** e **% dentro de ±40**;
   - **MAE** e **viés médio** (predito − real), que revela se o modelo "achata" as notas;
   - matriz de confusão por nível.
4. **Relatório** em `reports/eval_<data>_<prompt_version>.md`.
5. **Regra de ouro**: toda mudança de prompt ou de modelo passa pelo eval antes de ir para produção, e o `prompt_version` aumenta.

**Metas iniciais (ajuste com dados reais):**
- Total: ≥ 70% das redações dentro de ±80 pontos da nota real.
- Cada competência: ≥ 75% dentro de ±40; QWK ≥ 0.6.

**Ajustes comuns se o eval mostrar problemas:**
- Notas achatadas no meio: inclua no few-shot exemplos de 200 e de 40, e reforce a instrução de usar os extremos.
- C1 generosa demais: confira se a transcrição não está corrigindo erros (compare `transcription_raw` com a imagem).
- C5 inconsistente: confie mais na contagem de elementos do que na nota livre.

## Testes automatizados (sem chamar a API)
- Fixtures com respostas da IA gravadas (JSON) para: redação normal, anulada, tangenciamento e resposta inválida.
- Testes unitários da consolidação (sem discrepância, com 3ª execução, anulação divergente).
- Testes das checagens objetivas (7 vs. 8 linhas, cópia de motivadores).
