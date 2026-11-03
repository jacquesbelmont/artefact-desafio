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
