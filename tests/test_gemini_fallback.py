"""Testes offline do fallback Groq -> Google Gemini (sem OpenRouter).

Nenhuma chamada real de rede acontece aqui: httpx é interceptado com
MockTransport e as chaves usadas são obviamente falsas.
"""
import json
import httpx
from providers import RoteadorProvedores, ProvedoresIndisponiveis


def test_do_ambiente_monta_groq_e_gemini_na_ordem_correta(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    roteador = RoteadorProvedores.do_ambiente()

    assert [p.nome for p in roteador.provedores] == ["groq", "gemini"]
    groq, gemini = roteador.provedores
    assert groq.base_url == "https://api.groq.com/openai/v1"
    assert gemini.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert gemini.modelo == "gemini-flash-latest"
    assert all(p.nome != "openrouter" for p in roteador.provedores)


def test_do_ambiente_so_com_gemini_quando_groq_vazio(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")

    roteador = RoteadorProvedores.do_ambiente()

    assert [p.nome for p in roteador.provedores] == ["gemini"]


def test_groq_429_cai_para_gemini_compativel_com_openai(monkeypatch):
    historico = [
        {"role": "system", "content": "assistente"},
        {"role": "user", "content": "Quanto custa o Yamaha C40?"},
    ]

    def tratar_groq(req):
        return httpx.Response(429, json={"error": "rate limited"})

    def tratar_gemini(req):
        assert req.url.path == "/v1beta/openai/chat/completions"
        assert req.headers["Authorization"] == "Bearer chave-gemini-fake"
        corpo = json.loads(req.content)
        assert corpo["messages"] == historico
        assert corpo["model"] == "gemini-3.5-flash-lite"
        assert corpo["tools"][0]["function"]["name"] == "buscar_produtos"
        return httpx.Response(200, json={
            "choices": [{"message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "buscar_produtos", "arguments": '{"nome":"Yamaha C40"}'}}],
            }}]
        })

    client_original = httpx.Client
    chamadas = {"n": 0}

    def client_mock(*args, **kwargs):
        chamadas["n"] += 1
        tratador = tratar_groq if chamadas["n"] == 1 else tratar_gemini
        return client_original(*args, transport=httpx.MockTransport(tratador), **kwargs)

    monkeypatch.setattr("providers.httpx.Client", client_mock)
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    roteador = RoteadorProvedores.do_ambiente()
    ferramentas = [{"type": "function", "function": {"name": "buscar_produtos", "parameters": {"type": "object", "properties": {}}}}]
    resultado = roteador.completar(historico, ferramentas)

    assert resultado.provedor == "gemini"
    assert resultado.chamadas[0].nome == "buscar_produtos"
    assert roteador.ultimo_provedor == "gemini"


def test_erro_400_nao_cai_para_gemini(monkeypatch):
    def tratar_groq(req):
        return httpx.Response(400, json={"error": "bad request"})

    client_original = httpx.Client

    def client_mock(*args, **kwargs):
        return client_original(*args, transport=httpx.MockTransport(tratar_groq), **kwargs)

    monkeypatch.setattr("providers.httpx.Client", client_mock)
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")

    roteador = RoteadorProvedores.do_ambiente()
    try:
        roteador.completar([{"role": "user", "content": "Oi"}], [])
        assert False, "deveria ter levantado ProvedoresIndisponiveis"
    except ProvedoresIndisponiveis as exc:
        assert "groq" in str(exc)
        assert "400" in str(exc)
