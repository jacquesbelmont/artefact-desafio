"""Regressão: Groq emite tool_calls, falha (429) na rodada seguinte, Gemini assume.

Reproduz offline o bug relatado: o roteador tinha fallback transparente DENTRO
de uma mesma rodada de tool-calling. Como Groq e Gemini não compartilham o
mesmo formato de "prova" de raciocínio (o Gemini 3.x exige um thought_signature
opaco de volta na mensagem assistant), repassar o tool_calls gerado pelo Groq
para o Gemini resulta em HTTP 400 real da API.

A correção: uma vez que o modelo começa a pedir ferramentas, o roteador fica
"pinado" naquele provedor (sem fallback automático). Se o provedor pinado falhar
de forma transitória, o AgenteAtendimento descarta o rascunho da rodada (as
ferramentas são só leitura, então não há efeito colateral a desfazer) e
reinicia o turno do zero no próximo provedor configurado -- que então gera seu
próprio tool_calls e sua própria assinatura, sem herdar nada do Groq.

Nenhuma chamada real de rede acontece aqui: httpx é interceptado com
MockTransport.
"""
from __future__ import annotations

import json

import httpx

from agent import AgenteAtendimento
from history import Historico
from providers import ProvedoresIndisponiveis, RoteadorProvedores


def _resposta_tool_call(nome_funcao: str, argumentos: dict, extra_content: dict | None = None) -> httpx.Response:
    tool_call: dict = {
        "id": "call_1",
        "type": "function",
        "function": {"name": nome_funcao, "arguments": json.dumps(argumentos, ensure_ascii=False)},
    }
    if extra_content is not None:
        tool_call["extra_content"] = extra_content
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [tool_call]}}]
    })


def _resposta_texto(texto: str) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": texto}}]
    })


def test_groq_pede_ferramenta_depois_429_gemini_assume_a_rodada_do_zero(tmp_path, monkeypatch):
    chamadas_groq: list[dict] = []
    chamadas_gemini: list[dict] = []
    assinatura_gemini = {"google": {"thought_signature": "sig-opaca-xyz"}}

    def tratar_groq(req: httpx.Request) -> httpx.Response:
        corpo = json.loads(req.content)
        chamadas_groq.append(corpo)
        if len(chamadas_groq) == 1:
            # 1a rodada: Groq pede a ferramenta. Sem extra_content (Groq não usa).
            return _resposta_tool_call("buscar_produtos", {"categoria": "Violões", "preco_max": 1000})
        # 2a rodada (já pinado em "groq"): rate limit.
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    def tratar_gemini(req: httpx.Request) -> httpx.Response:
        corpo = json.loads(req.content)
        chamadas_gemini.append(corpo)
        mensagens = corpo["messages"]
        if len(chamadas_gemini) == 1:
            # O Gemini deve ver o turno reiniciado do zero: nada de tool_calls
            # ou role "tool" vindos da tentativa frustrada com o Groq.
            assert [m["role"] for m in mensagens] == ["system", "user"]
            assert not any("tool_calls" in m for m in mensagens)
            return _resposta_tool_call(
                "buscar_produtos", {"categoria": "Violões", "preco_max": 1000},
                extra_content=assinatura_gemini,
            )
        # 2a rodada do Gemini: a assinatura opaca precisa voltar intacta.
        assistant_msg = next(m for m in reversed(mensagens) if m["role"] == "assistant")
        assert assistant_msg["tool_calls"][0]["extra_content"] == assinatura_gemini
        return _resposta_texto("Achei o Yamaha C40 por R$ 599,90 no catálogo.")

    client_original = httpx.Client

    def client_mock(*args, **kwargs):
        def tratador(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.groq.com":
                return tratar_groq(req)
            return tratar_gemini(req)
        return client_original(*args, transport=httpx.MockTransport(tratador), **kwargs)

    monkeypatch.setattr("providers.httpx.Client", client_mock)
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    roteador = RoteadorProvedores.do_ambiente()
    historico = Historico(tmp_path / "teste.sqlite3")
    agente = AgenteAtendimento(roteador, historico)

    resultado = agente.responder("sessao-failover", "Quero um violão até 1000 reais")

    assert resultado.provedor == "gemini"
    assert resultado.ferramentas_usadas == ["buscar_produtos"]
    assert resultado.texto == "Achei o Yamaha C40 por R$ 599,90 no catálogo."

    # Groq: 1a rodada (sucesso, tool_call) + 2a rodada (429) = 2 chamadas.
    assert len(chamadas_groq) == 2
    # Gemini: 1a rodada (tool_call com assinatura) + 2a rodada (texto final) = 2.
    assert len(chamadas_gemini) == 2

    # Histórico: só a pergunta do usuário (uma vez) e a resposta final.
    mensagens_persistidas = historico.mensagens("sessao-failover")
    assert [m["role"] for m in mensagens_persistidas] == ["user", "assistant"]
    assert mensagens_persistidas[0]["content"] == "Quero um violão até 1000 reais"
    assert mensagens_persistidas[1]["content"] == "Achei o Yamaha C40 por R$ 599,90 no catálogo."


def test_pin_no_groq_com_erro_400_nao_tenta_gemini(monkeypatch, tmp_path):
    """400 é permanente: não deve reiniciar a rodada em outro provedor."""

    def tratar_groq(req: httpx.Request) -> httpx.Response:
        corpo = json.loads(req.content)
        if not any(m["role"] == "tool" for m in corpo["messages"]):
            return _resposta_tool_call("buscar_produtos", {"categoria": "Violões"})
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    chamou_gemini = {"vezes": 0}

    def tratar_gemini(req: httpx.Request) -> httpx.Response:
        chamou_gemini["vezes"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "não deveria chegar aqui"}}]})

    client_original = httpx.Client

    def client_mock(*args, **kwargs):
        def tratador(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.groq.com":
                return tratar_groq(req)
            return tratar_gemini(req)
        return client_original(*args, transport=httpx.MockTransport(tratador), **kwargs)

    monkeypatch.setattr("providers.httpx.Client", client_mock)
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")

    roteador = RoteadorProvedores.do_ambiente()
    historico = Historico(tmp_path / "t.sqlite3")
    agente = AgenteAtendimento(roteador, historico)
    try:
        agente.responder("sessao-400", "Quero um violão")
        assert False, "deveria ter levantado ProvedoresIndisponiveis"
    except ProvedoresIndisponiveis as exc:
        assert "groq" in str(exc)
        assert "400" in str(exc)
    assert chamou_gemini["vezes"] == 0


def test_pin_sem_segundo_provedor_configurado_propaga_erro(tmp_path, monkeypatch):
    """Só Groq configurado: 429 pinado não tem para onde cair, erro deve subir."""

    def tratar_groq(req: httpx.Request) -> httpx.Response:
        corpo = json.loads(req.content)
        if not any(m["role"] == "tool" for m in corpo["messages"]):
            return _resposta_tool_call("buscar_produtos", {"categoria": "Violões"})
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    client_original = httpx.Client

    def client_mock(*args, **kwargs):
        return client_original(*args, transport=httpx.MockTransport(tratar_groq), **kwargs)

    monkeypatch.setattr("providers.httpx.Client", client_mock)
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    roteador = RoteadorProvedores.do_ambiente()
    historico = Historico(tmp_path / "teste.sqlite3")
    agente = AgenteAtendimento(roteador, historico)

    try:
        agente.responder("sessao-sem-reserva", "Quero um violão")
        assert False, "deveria ter levantado ProvedoresIndisponiveis"
    except ProvedoresIndisponiveis as exc:
        assert "groq" in str(exc)
        assert "429" in str(exc)
    # A pergunta do usuário continua registrada para retomada; sem resposta.
    assert [m["role"] for m in historico.mensagens("sessao-sem-reserva")] == ["user"]


def test_groq_429_antes_de_qualquer_tool_call_ainda_cai_para_gemini(monkeypatch, tmp_path):
    """Fallback automático pré-existente (sem tool_calls ainda) continua intacto."""

    def tratar_groq(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    def tratar_gemini(req: httpx.Request) -> httpx.Response:
        return _resposta_texto("Posso ajudar! Qual instrumento você procura?")

    client_original = httpx.Client

    def client_mock(*args, **kwargs):
        def tratador(req: httpx.Request) -> httpx.Response:
            if req.url.host == "api.groq.com":
                return tratar_groq(req)
            return tratar_gemini(req)
        return client_original(*args, transport=httpx.MockTransport(tratador), **kwargs)

    monkeypatch.setattr("providers.httpx.Client", client_mock)
    monkeypatch.setenv("GROQ_API_KEY", "chave-groq-fake")
    monkeypatch.setenv("GEMINI_API_KEY", "chave-gemini-fake")

    roteador = RoteadorProvedores.do_ambiente()
    historico = Historico(tmp_path / "teste.sqlite3")
    agente = AgenteAtendimento(roteador, historico)

    resultado = agente.responder("sessao-fallback-inicial", "Oi")
    assert resultado.provedor == "gemini"
    assert resultado.texto == "Posso ajudar! Qual instrumento você procura?"
