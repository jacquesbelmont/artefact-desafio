import httpx
from providers import ProvedorOpenAICompativel


def test_http_adapter_formata_chamada_de_tool(monkeypatch):
    solicitacoes = []
    def tratar(req):
        solicitacoes.append(req)
        assert req.url.path == "/v1/chat/completions"
        assert req.headers["Authorization"] == "Bearer token-so-para-teste"
        assert b'"model":"modelo-de-teste"' in req.content
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_123", "type": "function",
                    "function": {"name": "buscar_produtos", "arguments": '{"nome":"Yamaha"}'}}]}}]
        })

    client_original = httpx.Client
    def client_mock(*args, **kwargs):
        return client_original(*args, transport=httpx.MockTransport(tratar), **kwargs)
    monkeypatch.setattr("providers.httpx.Client", client_mock)

    p = ProvedorOpenAICompativel("teste", "https://api.example.test/v1", "token-so-para-teste", "modelo-de-teste")
    resultado = p.completar([{"role": "user", "content": "Oi"}], [])
    assert len(solicitacoes) == 1
    assert resultado.provedor == "teste"
    assert resultado.chamadas[0].nome == "buscar_produtos"
    assert resultado.chamadas[0].argumentos_json == '{"nome":"Yamaha"}'


def test_http_adapter_preserva_extra_content_opaco_do_tool_call(monkeypatch):
    """Gemini 3.x envia extra_content.google.thought_signature no tool_call;
    o adaptador deve preservá-lo exatamente, sem inspecionar nem logar."""
    def tratar(req):
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_123", "type": "function",
                    "function": {"name": "buscar_produtos", "arguments": '{"nome":"Yamaha"}'},
                    "extra_content": {"google": {"thought_signature": "sig-opaco-xyz"}}}]}}]
        })

    client_original = httpx.Client
    def client_mock(*args, **kwargs):
        return client_original(*args, transport=httpx.MockTransport(tratar), **kwargs)
    monkeypatch.setattr("providers.httpx.Client", client_mock)

    p = ProvedorOpenAICompativel("gemini", "https://api.example.test/v1", "token", "modelo-de-teste")
    resultado = p.completar([{"role": "user", "content": "Oi"}], [])
    assert resultado.chamadas[0].extra_content == {"google": {"thought_signature": "sig-opaco-xyz"}}


def test_http_adapter_ignora_extra_content_nao_dict(monkeypatch):
    def tratar(req):
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_123", "type": "function",
                    "function": {"name": "buscar_produtos", "arguments": "{}"},
                    "extra_content": "nao-e-um-dict"}]}}]
        })

    client_original = httpx.Client
    def client_mock(*args, **kwargs):
        return client_original(*args, transport=httpx.MockTransport(tratar), **kwargs)
    monkeypatch.setattr("providers.httpx.Client", client_mock)

    p = ProvedorOpenAICompativel("gemini", "https://api.example.test/v1", "token", "modelo-de-teste")
    resultado = p.completar([{"role": "user", "content": "Oi"}], [])
    assert resultado.chamadas[0].extra_content is None


def test_http_adapter_sem_extra_content_fica_none(monkeypatch):
    def tratar(req):
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_123", "type": "function",
                    "function": {"name": "buscar_produtos", "arguments": "{}"}}]}}]
        })

    client_original = httpx.Client
    def client_mock(*args, **kwargs):
        return client_original(*args, transport=httpx.MockTransport(tratar), **kwargs)
    monkeypatch.setattr("providers.httpx.Client", client_mock)

    p = ProvedorOpenAICompativel("groq", "https://api.example.test/v1", "token", "modelo-de-teste")
    resultado = p.completar([{"role": "user", "content": "Oi"}], [])
    assert resultado.chamadas[0].extra_content is None
