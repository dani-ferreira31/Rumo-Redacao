"""Camada de IA com os SDKs mockados (nenhuma chamada real a nenhum provedor)."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.ai.catalog import DEFAULT_PRICING, estimate_cost, find_price, pricing_table
from app.ai.client import (
    AIClient,
    AIConfigError,
    AIRefusalError,
    AIRequest,
    AIValidationError,
    ImagePart,
    PdfPart,
    TaskConfig,
    TextPart,
    save_usage,
)
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.google import GoogleProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas import GradingOutput
from app.core.enums import AIPurpose
from app.modules.essays.consolidation import validate_grading
from app.modules.system.settings import set_setting
from tests.grading_factory import grading

# ---- Anthropic ----------------------------------------------------------------


def _anthropic_response(output=None, stop_reason="end_turn", model="claude-sonnet-5-5"):
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=500,
        cache_read_input_tokens=3000,
        cache_creation_input_tokens=0,
    )
    resp = SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=output,
        model=model,
        usage=usage,
        content=[SimpleNamespace(type="text", text="{}")],
        stop_details=None,
    )
    resp._request_id = "req_123"
    return resp


class FakeAnthropicSDK:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    async def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _client(provider) -> AIClient:
    return AIClient(factories={provider.name: lambda _key: provider})


def _request(provider="anthropic", model="claude-sonnet-5-5", effort="high", content=None):
    return AIRequest(
        purpose=AIPurpose.grading,
        config=TaskConfig(provider, model, effort, api_key="chave-teste"),
        system=[TextPart("sistema"), TextPart("rubrica", cache=True)],
        content=content or [TextPart("redação")],
        output_type=GradingOutput,
        validate=validate_grading,
    )


async def test_anthropic_sucesso_registra_uso():
    sdk = FakeAnthropicSDK([_anthropic_response(grading())])
    result = await _client(AnthropicProvider(sdk=sdk)).parse(_request())
    assert result.output.competencias[0].nota == 160
    assert result.provider == "anthropic"
    [row] = result.usage
    assert row.provider == "anthropic"
    assert row.input_tokens == 1000 and row.cache_read_tokens == 3000
    assert row.request_id == "req_123"
    call = sdk.calls[0]
    assert call["output_format"] is GradingOutput
    assert call["output_config"] == {"effort": "high"}
    assert call["fallbacks"] == "default"
    assert "tool_choice" not in call  # forçar ferramenta dá 400 no Sonnet 5.5
    assert call["system"][1]["cache_control"] == {"type": "ephemeral"}


async def test_anthropic_traduz_imagem_e_pdf():
    sdk = FakeAnthropicSDK([_anthropic_response(grading())])
    content = [ImagePart(b"jpg"), PdfPart(b"%PDF"), TextPart("leia")]
    await _client(AnthropicProvider(sdk=sdk)).parse(_request(content=content))
    blocks = sdk.calls[0]["messages"][0]["content"]
    assert blocks[0]["type"] == "image" and blocks[0]["source"]["media_type"] == "image/jpeg"
    assert blocks[1]["type"] == "document"
    assert blocks[1]["source"]["media_type"] == "application/pdf"


async def test_validacao_falha_reenvia_com_os_erros():
    bad = grading()
    bad.competencias[4].numero = 1
    sdk = FakeAnthropicSDK([_anthropic_response(bad), _anthropic_response(grading())])
    result = await _client(AnthropicProvider(sdk=sdk)).parse(_request())
    assert len(result.usage) == 2
    retry_messages = sdk.calls[1]["messages"]
    assert [m["role"] for m in retry_messages] == ["user", "assistant", "user"]
    assert "competências 1 a 5" in retry_messages[-1]["content"][0]["text"]


async def test_validacao_falha_duas_vezes_guarda_o_uso():
    bad = grading(anulada=True, motivo=None)
    sdk = FakeAnthropicSDK([_anthropic_response(bad), _anthropic_response(bad)])
    with pytest.raises(AIValidationError) as info:
        await _client(AnthropicProvider(sdk=sdk)).parse(_request())
    assert len(info.value.usage) == 2


async def test_recusa_vira_erro():
    sdk = FakeAnthropicSDK([_anthropic_response(None, stop_reason="refusal")])
    with pytest.raises(AIRefusalError) as info:
        await _client(AnthropicProvider(sdk=sdk)).parse(_request())
    assert len(info.value.usage) == 1


async def test_sem_chave_da_erro_de_configuracao():
    request = _request()
    request.config = TaskConfig("anthropic", "claude-sonnet-5-5", None, api_key="")
    with pytest.raises(AIConfigError, match="chave"):
        await AIClient().parse(request)


# ---- OpenAI -------------------------------------------------------------------


class FakeOpenAISDK:
    def __init__(self, responses):
        self.queue = list(responses)
        self.calls = []
        self.responses = SimpleNamespace(parse=self._parse)

    async def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.queue.pop(0)


def _openai_response(output=None, incomplete=None, refusal=None):
    content = [SimpleNamespace(type="refusal", refusal=refusal)] if refusal else []
    resp = SimpleNamespace(
        output_parsed=output,
        output_text="{}",
        output=[SimpleNamespace(type="message", content=content)],
        incomplete_details=SimpleNamespace(reason=incomplete) if incomplete else None,
        model="gpt-teste-2026-01-01",
        usage=SimpleNamespace(
            input_tokens=5000,
            output_tokens=800,
            input_tokens_details=SimpleNamespace(cached_tokens=4000, cache_write_tokens=0),
        ),
    )
    resp._request_id = "req_oa"
    return resp


async def test_openai_traduz_pedido_e_uso():
    sdk = FakeOpenAISDK([_openai_response(grading())])
    content = [ImagePart(b"jpg"), PdfPart(b"%PDF", "prova.pdf"), TextPart("leia")]
    request = _request("openai", "gpt-teste", "medium", content)
    result = await _client(OpenAIProvider(sdk=sdk)).parse(request)
    call = sdk.calls[0]
    assert call["text_format"] is GradingOutput
    assert call["instructions"] == "sistema\n\nrubrica"
    assert call["reasoning"] == {"effort": "medium"}
    items = call["input"][0]["content"]
    assert items[0]["type"] == "input_image"
    assert items[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert items[1]["type"] == "input_file" and items[1]["filename"] == "prova.pdf"
    assert items[2] == {"type": "input_text", "text": "leia"}
    [row] = result.usage
    # input_tokens da OpenAI inclui o cache: separa os dois
    assert (row.input_tokens, row.cache_read_tokens, row.output_tokens) == (1000, 4000, 800)
    assert row.provider == "openai" and row.model == "gpt-teste-2026-01-01"


async def test_openai_recusa_e_corte():
    sdk = FakeOpenAISDK([_openai_response(refusal="não posso")])
    with pytest.raises(AIRefusalError):
        await _client(OpenAIProvider(sdk=sdk)).parse(_request("openai", "gpt-teste"))


# ---- Google -------------------------------------------------------------------


class FakeGoogleSDK:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _google_response(text, finish="STOP"):
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))],
        prompt_feedback=None,
        model_version="gemini-teste",
        response_id="resp_g",
        usage_metadata=SimpleNamespace(
            prompt_token_count=3000,
            cached_content_token_count=1000,
            candidates_token_count=400,
            thoughts_token_count=600,
        ),
    )


async def test_google_valida_json_e_conta_pensamento_como_saida():
    sdk = FakeGoogleSDK([_google_response(grading().model_dump_json())])
    request = _request("google", "gemini-teste", "low", [ImagePart(b"jpg"), TextPart("leia")])
    result = await _client(GoogleProvider(sdk=sdk)).parse(request)
    config = sdk.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema["title"] == "GradingOutput"
    assert config.system_instruction == "sistema\n\nrubrica"
    assert config.thinking_config.thinking_level.name == "LOW"
    [row] = result.usage
    assert (row.input_tokens, row.cache_read_tokens, row.output_tokens) == (2000, 1000, 1000)


async def test_google_json_invalido_tenta_de_novo():
    sdk = FakeGoogleSDK([_google_response("{"), _google_response(grading().model_dump_json())])
    result = await _client(GoogleProvider(sdk=sdk)).parse(_request("google", "gemini-teste"))
    assert len(result.usage) == 2


async def test_google_bloqueio_de_seguranca_e_recusa():
    sdk = FakeGoogleSDK([_google_response(None, finish="SAFETY")])
    with pytest.raises(AIRefusalError):
        await _client(GoogleProvider(sdk=sdk)).parse(_request("google", "gemini-teste"))


# ---- preços -------------------------------------------------------------------


def test_custo_de_modelo_desconhecido_e_none():
    assert estimate_cost(DEFAULT_PRICING, "modelo-x", 1, 1, 0, 0) is None


def test_preco_por_prefixo_e_sobrescrita_do_painel():
    table = pricing_table({"gpt-teste": {"input": 1, "output": 4, "cache_read": 0.1}})
    assert find_price(table, "gpt-teste-2026-01-01") == find_price(table, "gpt-teste")
    # 1000*1 + 800*4 + 4000*0.1 = 4600 / 1M
    assert estimate_cost(table, "gpt-teste-2026-01-01", 1000, 800, 4000, 0) == Decimal("0.004600")


async def test_save_usage_calcula_custo_com_a_tabela_do_painel(db):
    sdk = FakeAnthropicSDK([_anthropic_response(grading())])
    result = await _client(AnthropicProvider(sdk=sdk)).parse(_request())
    await save_usage(db, result)
    # 1000*2 + 500*10 + 3000*0.2 = 7600 / 1M
    assert result.usage[0].cost_usd == Decimal("0.007600")

    await set_setting(db, "ai_pricing", {"claude-sonnet-5-5": {"input": 1, "output": 1}})
    sdk = FakeAnthropicSDK([_anthropic_response(grading())])
    result = await _client(AnthropicProvider(sdk=sdk)).parse(_request())
    await save_usage(db, result)
    assert result.usage[0].cost_usd == Decimal("0.001500")


async def test_google_espera_e_tenta_de_novo_na_cota_e_na_sobrecarga():
    from google.genai import errors

    quota = errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "quota",
                "details": [{"retryDelay": "49s"}],
            }
        },
    )
    busy = errors.ServerError(
        503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "x"}}
    )
    sdk = FakeGoogleSDK([quota, busy, _google_response(grading().model_dump_json())])
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    result = await _client(GoogleProvider(sdk=sdk, sleep=sleep)).parse(
        _request("google", "gemini-teste")
    )
    assert result.output.competencias[0].nota == 160
    assert waits[0] == 50  # retryDelay do Google + 1 s
    assert len(waits) == 2


async def test_google_erro_de_requisicao_nao_repete():
    from google.genai import errors

    bad = errors.ClientError(400, {"error": {"code": 400, "status": "INVALID", "message": "x"}})
    sdk = FakeGoogleSDK([bad])
    with pytest.raises(errors.ClientError):
        await _client(GoogleProvider(sdk=sdk, sleep=None)).parse(_request("google", "gemini-teste"))
