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
