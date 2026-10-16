"""Provedores de IA suportados, opções de esforço e preços padrão.

Os preços são editáveis no painel (`app_settings.ai_pricing`), que tem prioridade.
Modelo sem preço conhecido fica com custo desconhecido (None), nunca zero.
"""

from decimal import Decimal

PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "efforts": ["low", "medium", "high", "xhigh", "max"],
        "key_url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "efforts": ["none", "minimal", "low", "medium", "high", "xhigh"],
        "key_url": "https://platform.openai.com/api-keys",
    },
    "google": {
        "label": "Google (Gemini)",
        "efforts": ["minimal", "low", "medium", "high"],
        "key_url": "https://aistudio.google.com/apikey",
    },
    "fake": {
        "label": "Simulado (desenvolvimento, sem custo)",
        "efforts": [],
        "key_url": None,
    },
}

TASKS = {
    "transcription": {
        "label": "Transcrição de redações",
        "hint": "Lê a foto da folha. Precisa de um modelo com visão (imagens).",
    },
    "grading": {
        "label": "Correção de redações",
        "hint": "Dá as notas. Trocar o modelo muda as notas: rode a calibração antes.",
    },
    "contest_extraction": {
        "label": "Importação de provas de concurso",
        "hint": "Lê o PDF da prova e do gabarito. Precisa de um modelo com visão.",
    },
}

# US$ por 1M de tokens: entrada, saída, leitura de cache, escrita de cache.
Prices = tuple[Decimal, Decimal, Decimal, Decimal]

DEFAULT_PRICING: dict[str, Prices] = {
    "claude-sonnet-5-5": (Decimal("2"), Decimal("10"), Decimal("0.20"), Decimal("2.50")),
    "claude-opus-5-5": (Decimal("4"), Decimal("20"), Decimal("0.20"), Decimal("5")),
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50"), Decimal("0.01"), Decimal("0.125")),
    "fake": (Decimal(0), Decimal(0), Decimal(0), Decimal(0)),
}


def pricing_table(overrides: dict[str, dict]) -> dict[str, Prices]:
    """Preços padrão + os editados no painel (que têm prioridade)."""
    table = dict(DEFAULT_PRICING)
    for model, p in (overrides or {}).items():
        table[model] = (
            Decimal(str(p.get("input", 0))),
            Decimal(str(p.get("output", 0))),
            Decimal(str(p.get("cache_read", 0))),
            Decimal(str(p.get("cache_write", 0))),
        )
    return table


def find_price(table: dict[str, Prices], model: str) -> Prices | None:
    """Preço exato ou, para IDs com data (`gpt-x-2026-05-01`), o prefixo mais longo."""
    if model in table:
        return table[model]
    matches = [k for k in table if model.startswith(k + "-")]
    return table[max(matches, key=len)] if matches else None


def estimate_cost(
    table: dict[str, Prices], model: str, inp: int, out: int, cache_read: int, cache_write: int
) -> Decimal | None:
    prices = find_price(table, model)
    if prices is None:
        return None
    p_in, p_out, p_read, p_write = prices
    total = inp * p_in + out * p_out + cache_read * p_read + cache_write * p_write
    return (total / Decimal(1_000_000)).quantize(Decimal("0.000001"))
