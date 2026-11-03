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


def erro_http_com_retry_after(status, retry_after):
    req = httpx.Request("POST", "https://exemplo.test/chat/completions")
    resp = httpx.Response(status, request=req, headers={"retry-after": retry_after})
    return httpx.HTTPStatusError(f"HTTP {status}", request=req, response=resp)


def test_diagnostico_de_erro_400_inclui_provedor_e_status_sem_vazar_segredos():
    principal = ProvedorFalso("groq", erro_http(400))
    with pytest.raises(ProvedoresIndisponiveis) as exc_info:
        RoteadorProvedores([principal]).completar([{"role": "user", "content": "Oi"}], [])
    mensagem = str(exc_info.value)
    assert "groq" in mensagem
    assert "400" in mensagem
    assert "Authorization" not in mensagem
    assert "Bearer" not in mensagem


def test_diagnostico_inclui_retry_after_quando_presente_e_numerico():
    principal = ProvedorFalso("groq", erro_http_com_retry_after(400, "30"))
    with pytest.raises(ProvedoresIndisponiveis) as exc_info:
        RoteadorProvedores([principal]).completar([{"role": "user", "content": "Oi"}], [])
    assert "retry_after_s=30" in str(exc_info.value)


def test_diagnostico_ignora_retry_after_nao_numerico():
    principal = ProvedorFalso("groq", erro_http_com_retry_after(400, "Wed, 21 Oct"))
    with pytest.raises(ProvedoresIndisponiveis) as exc_info:
        RoteadorProvedores([principal]).completar([{"role": "user", "content": "Oi"}], [])
    assert "retry_after_s" not in str(exc_info.value)


def test_groq_429_sem_reserva_mensagem_final_tem_diagnostico_sanitizado():
    principal = ProvedorFalso("groq", erro_http_com_retry_after(429, "12"))
    with pytest.raises(ProvedoresIndisponiveis) as exc_info:
        RoteadorProvedores([principal]).completar([{"role": "user", "content": "Oi"}], [])
    mensagem = str(exc_info.value)
    assert "groq" in mensagem
    assert "HTTPStatusError" in mensagem
    assert "429" in mensagem
    assert "retry_after_s=12" in mensagem
    assert "Authorization" not in mensagem
    assert "Bearer" not in mensagem
    assert "exemplo.test" not in mensagem


def test_ambas_apis_com_falha_transitoria_incluem_diagnostico_de_cada_provedor():
    principal = ProvedorFalso("groq", erro_http_com_retry_after(429, "5"))
    reserva = ProvedorFalso("reserva", erro_http(503))
    with pytest.raises(ProvedoresIndisponiveis) as exc_info:
        RoteadorProvedores([principal, reserva]).completar([{"role": "user", "content": "Oi"}], [])
    mensagem = str(exc_info.value)
    assert "provedor=groq" in mensagem
    assert "status=429" in mensagem
    assert "retry_after_s=5" in mensagem
    assert "provedor=reserva" in mensagem
    assert "status=503" in mensagem
    assert "Authorization" not in mensagem
    assert "Bearer" not in mensagem
