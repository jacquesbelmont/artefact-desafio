from dataclasses import dataclass
import httpx
import pytest
from providers import RoteadorProvedores, RespostaModelo, ProvedoresIndisponiveis


@dataclass
class ProvedorFalso:
    nome: str
    resposta_ou_erro: object

    def __post_init__(self):
        self.recebidas = []

    def completar(self, mensagens, ferramentas):
        self.recebidas.append((list(mensagens), list(ferramentas)))
        if isinstance(self.resposta_ou_erro, Exception):
            raise self.resposta_ou_erro
        return self.resposta_ou_erro


def erro_http(status):
    req = httpx.Request("POST", "https://exemplo.test/chat/completions")
    resp = httpx.Response(status, request=req)
    return httpx.HTTPStatusError(f"HTTP {status}", request=req, response=resp)


def test_fallback_429_repassa_mesmo_historico():
    historico = [
        {"role": "system", "content": "assistente"},
        {"role": "user", "content": "Quanto custa?"},
        {"role": "assistant", "content": "De qual produto?"},
        {"role": "user", "content": "Yamaha C40"},
    ]
    principal = ProvedorFalso("groq", erro_http(429))
    reserva = ProvedorFalso("reserva", RespostaModelo("Vou consultar.", [], "reserva"))
    roteador = RoteadorProvedores([principal, reserva])
    resultado = roteador.completar(historico, [])
    assert resultado.provedor == "reserva"
    assert reserva.recebidas[0][0] == historico
    assert principal.recebidas[0][0] == historico
    assert roteador.ultimo_provedor == "reserva"


def test_erro_400_nao_dispara_fallback():
    principal = ProvedorFalso("groq", erro_http(400))
    reserva = ProvedorFalso("reserva", RespostaModelo("Não deveria chamar", [], "reserva"))
    with pytest.raises(ProvedoresIndisponiveis):
        RoteadorProvedores([principal, reserva]).completar([{"role": "user", "content": "Oi"}], [])
    assert not reserva.recebidas


def test_todas_as_apis_falham():
    prim = ProvedorFalso("groq", erro_http(429))
    res = ProvedorFalso("reserva", erro_http(503))
    with pytest.raises(ProvedoresIndisponiveis):
        RoteadorProvedores([prim, res]).completar([{"role": "user", "content": "Oi"}], [])
