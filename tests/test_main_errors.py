"""Safe CLI error details for Gemini's list-shaped and OpenAI's dict-shaped errors."""
import httpx

from main import detalhe_http


def _erro_http(status, payload):
    req = httpx.Request("POST", "https://example.test/chat/completions")
    resp = httpx.Response(status, json=payload, request=req)
    return httpx.HTTPStatusError("request rejected", request=req, response=resp)


def test_gemini_lista_json_exibe_apenas_status_seguro():
    erro = _erro_http(400, [{"error": {
        "code": 400, "status": "INVALID_ARGUMENT",
        "message": "missing thought_signature [PRIVATE-SIGNATURE]!",
    }}])
    detalhe = detalhe_http(erro)
    assert detalhe == "HTTP 400: INVALID_ARGUMENT"
    assert "PRIVATE-SIGNATURE" not in detalhe


def test_erro_dict_exibe_status_sem_mensagem_bruta():
    erro = _erro_http(429, {"error": {
        "status": "RESOURCE_EXHAUSTED",
        "message": "Bearer secret-never-display",
    }})
    assert detalhe_http(erro) == "HTTP 429: RESOURCE_EXHAUSTED"


def test_erro_sem_http_nao_tem_detalhe():
    assert detalhe_http(ValueError("sensitive")) == ""
