from agent import AgenteAtendimento
from history import Historico
from providers import ChamadaFerramenta, RespostaModelo


class RoteadorFalso:
    def __init__(self):
        self.recebidas = []

    def completar(self, mensagens, ferramentas):
        self.recebidas.append(mensagens)
        if any(m["role"] == "tool" for m in mensagens):
            return RespostaModelo("Achei opções no catálogo.", [], "mock")
        return RespostaModelo("", [ChamadaFerramenta("call_1", "buscar_produtos", '{"categoria":"Violões","preco_max":1000}')], "mock")


def test_agente_executa_ferramenta_e_salva_historico(tmp_path):
    db = Historico(tmp_path / "teste.sqlite3")
    llm = RoteadorFalso()
    agente = AgenteAtendimento(llm, db)
    r = agente.responder("sessao1", "Violões até 1000")
    assert r.texto == "Achei opções no catálogo."
    assert r.ferramentas_usadas == ["buscar_produtos"]
    assert len(llm.recebidas) == 2
    assert any(m["role"] == "tool" and "produtos" in m["content"] for m in llm.recebidas[1])
    assert [m["role"] for m in db.mensagens("sessao1")] == ["user", "assistant"]


class RoteadorFalsoComAssinatura:
    """Simula Gemini 3.x: a 1a rodada devolve tool_calls com extra_content opaco.

    A 2a rodada só responde com sucesso se o extra_content voltar inalterado
    na mensagem assistant reconstruída -- reproduzindo a exigência real do
    thought_signature do Gemini 3.x (senão o provedor devolveria HTTP 400).
    """

    def __init__(self):
        self.recebidas = []

    def completar(self, mensagens, ferramentas):
        self.recebidas.append(mensagens)
        if any(m["role"] == "tool" for m in mensagens):
            assistant_msg = next(m for m in reversed(mensagens) if m["role"] == "assistant")
            chamada = assistant_msg["tool_calls"][0]
            if chamada.get("extra_content") != {"google": {"thought_signature": "sig-opaco-abc"}}:
                raise RuntimeError("thought_signature ausente ou alterado: simula HTTP 400 do Gemini")
            return RespostaModelo("Achei opções no catálogo.", [], "mock-gemini")
        return RespostaModelo(
            "",
            [ChamadaFerramenta(
                "call_1", "buscar_produtos", '{"categoria":"Violões","preco_max":1000}',
                extra_content={"google": {"thought_signature": "sig-opaco-abc"}},
            )],
            "mock-gemini",
        )


def test_agente_repassa_extra_content_opaco_entre_rodadas(tmp_path):
    db = Historico(tmp_path / "teste.sqlite3")
    llm = RoteadorFalsoComAssinatura()
    agente = AgenteAtendimento(llm, db)
    r = agente.responder("sessao3", "Violões até 1000")
    assert r.texto == "Achei opções no catálogo."
    assert r.provedor == "mock-gemini"
    segunda_rodada = llm.recebidas[1]
    assistant_msg = next(m for m in segunda_rodada if m["role"] == "assistant")
    assert assistant_msg["tool_calls"][0]["extra_content"] == {
        "google": {"thought_signature": "sig-opaco-abc"}
    }


class RoteadorFalsoVariosToolCalls:
    """Duas chamadas de ferramenta em paralelo, cada uma com extra_content próprio."""

    def __init__(self):
        self.recebidas = []

    def completar(self, mensagens, ferramentas):
        self.recebidas.append(mensagens)
        if any(m["role"] == "tool" for m in mensagens):
            return RespostaModelo("Pronto.", [], "mock-gemini")
        return RespostaModelo(
            "",
            [
                ChamadaFerramenta("call_1", "buscar_produtos", '{"categoria":"Violões"}',
                    extra_content={"google": {"thought_signature": "sig-1"}}),
                ChamadaFerramenta("call_2", "buscar_produtos", '{"categoria":"Teclados"}',
                    extra_content={"google": {"thought_signature": "sig-2"}}),
            ],
            "mock-gemini",
        )


def test_agente_repassa_extra_content_em_chamadas_paralelas(tmp_path):
    db = Historico(tmp_path / "teste.sqlite3")
    llm = RoteadorFalsoVariosToolCalls()
    agente = AgenteAtendimento(llm, db)
    agente.responder("sessao4", "Violões e teclados até 1000")
    segunda_rodada = llm.recebidas[1]
    assistant_msg = next(m for m in segunda_rodada if m["role"] == "assistant")
    assinaturas = [c["extra_content"]["google"]["thought_signature"] for c in assistant_msg["tool_calls"]]
    assert assinaturas == ["sig-1", "sig-2"]


def test_agente_nao_adiciona_extra_content_quando_ausente_groq(tmp_path):
    db = Historico(tmp_path / "teste.sqlite3")
    llm = RoteadorFalso()
    agente = AgenteAtendimento(llm, db)
    agente.responder("sessao5", "Violões até 1000")
    segunda_rodada = llm.recebidas[1]
    assistant_msg = next(m for m in segunda_rodada if m["role"] == "assistant")
    assert "extra_content" not in assistant_msg["tool_calls"][0]


def test_pergunta_e_salva_mesmo_se_api_falhar(tmp_path):
    class Falha:
        def completar(self, mensagens, ferramentas):
            raise RuntimeError("API indisponível")
    db = Historico(tmp_path / "teste.sqlite3")
    agente = AgenteAtendimento(Falha(), db)
    import pytest
    with pytest.raises(RuntimeError):
        agente.responder("sessao2", "Oi!")
    assert db.mensagens("sessao2") == [{"role": "user", "content": "Oi!"}]
