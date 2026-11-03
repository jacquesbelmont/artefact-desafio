"""Duas APIs com o mesmo contrato HTTP de Chat Completions + fallback.

A implementação usa httpx diretamente em vez de instalar dois SDKs diferentes.
Groq e Google Gemini (via sua camada de compatibilidade OpenAI) expõem
endpoints compatíveis com o formato OpenAI. Veja:
https://ai.google.dev/gemini-api/docs/openai
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


class SemProvedor(RuntimeError):
    pass


class ProvedoresIndisponiveis(RuntimeError):
    pass


@dataclass(frozen=True)
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos_json: str
    extra_content: dict | None = None


@dataclass(frozen=True)
class RespostaModelo:
    texto: str
    chamadas: list[ChamadaFerramenta]
    provedor: str


class ProvedorOpenAICompativel:
    def __init__(self, nome: str, base_url: str, chave: str, modelo: str, timeout: float = 25):
        self.nome = nome
        self.base_url = base_url.rstrip("/")
        self.chave = chave
        self.modelo = modelo
        self.timeout = timeout

    def completar(self, mensagens: list[dict], ferramentas: list[dict]) -> RespostaModelo:
        # Não enviamos código nem arquivos do Mac: somente mensagens e schema das tools.
        with httpx.Client(timeout=self.timeout) as client:
            resposta = client.post(
                self.base_url + "/chat/completions",
                headers={"Authorization": "Bearer " + self.chave},
                json={
                    "model": self.modelo,
                    "temperature": 0.2,
                    "messages": mensagens,
                    "tools": ferramentas,
                    "tool_choice": "auto",
                },
            )
            resposta.raise_for_status()
            corpo = resposta.json()

        msg = corpo["choices"][0]["message"]
        chamadas = [
            ChamadaFerramenta(
                id=c["id"],
                nome=c["function"]["name"],
                argumentos_json=c["function"].get("arguments", "{}"),
                extra_content=c.get("extra_content") if isinstance(c.get("extra_content"), dict) else None,
            ) for c in (msg.get("tool_calls") or [])
        ]
        return RespostaModelo(
            texto=msg.get("content") or "", chamadas=chamadas, provedor=self.nome,
        )


def erro_transitorio(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        codigo = exc.response.status_code
        return codigo in (408, 429) or codigo >= 500
    return False


def _retry_after_seguro(resposta: httpx.Response) -> int | None:
    """Extrai Retry-After em segundos, se presente e numérico. Nunca repassa o header bruto."""
    valor = resposta.headers.get("retry-after")
    if valor is None:
        return None
    try:
        segundos = int(float(valor.strip()))
    except (ValueError, AttributeError):
        return None
    return segundos if segundos >= 0 else None


MAX_TENTATIVAS_ULTIMO_PROVEDOR = 3  # 1 tentativa inicial + 2 retries
ESPERAS_RETRY_S = (1, 2)
MAX_ESPERA_RETRY_AFTER_S = 10  # não insistir quando servidor pede espera longa


def _eh_5xx_retentavel(exc: Exception) -> bool:
    """502/503/504 (ou 5xx genérico) justificam retry local no último provedor.

    429/408 não entram aqui: são rate limit/timeout, tratados só por fallback.
    """
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500


def _diagnostico(provedor_nome: str, exc: Exception) -> str:
    """Mensagem curta e segura: nome do provedor, status HTTP e Retry-After (se houver).

    Nunca inclui headers brutos, corpo da requisição/resposta, URLs, tokens ou e-mails.
    """
    partes = [f"provedor={provedor_nome}", f"tipo={type(exc).__name__}"]
    if isinstance(exc, httpx.HTTPStatusError):
        partes.append(f"status={exc.response.status_code}")
        retry_after = _retry_after_seguro(exc.response)
        if retry_after is not None:
            partes.append(f"retry_after_s={retry_after}")
    return ", ".join(partes)


class RoteadorProvedores:
    def __init__(self, provedores: list[Any]):
        self.provedores = list(provedores)
        self.ultimo_provedor: str | None = None

    @classmethod
    def do_ambiente(cls) -> "RoteadorProvedores":
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
        provedores = []
        if chave := os.getenv("GROQ_API_KEY", "").strip():
            provedores.append(ProvedorOpenAICompativel(
                "groq", "https://api.groq.com/openai/v1", chave,
                os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), timeout,
            ))
        if chave := os.getenv("GEMINI_API_KEY", "").strip():
            provedores.append(ProvedorOpenAICompativel(
                "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", chave,
                os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"), timeout,
            ))
        return cls(provedores)

    def completar(
        self,
        mensagens: list[dict],
        ferramentas: list[dict],
        *,
        provedor_fixo: str | None = None,
    ) -> RespostaModelo:
        if not self.provedores:
            raise SemProvedor("Configure GROQ_API_KEY ou GEMINI_API_KEY no .env para iniciar.")
        provedores = self.provedores
        if provedor_fixo is not None:
            # Rodada de tool-calling já em andamento: sem fallback transparente
            # para outro provedor, pois o traço de tool_calls (e eventual
            # thought_signature) é específico do provedor que o gerou.
            provedores = [p for p in self.provedores if p.nome == provedor_fixo]
            if not provedores:
                raise ProvedoresIndisponiveis(
                    f"Provedor fixo '{provedor_fixo}' não está configurado."
                )
        diagnosticos: list[str] = []
        for indice, provedor in enumerate(provedores):
            eh_ultimo = indice == len(provedores) - 1
            exc_final: Exception | None = None
            tentativas = MAX_TENTATIVAS_ULTIMO_PROVEDOR if eh_ultimo else 1
            for tentativa in range(tentativas):
                try:
                    resposta = provedor.completar(mensagens, ferramentas)
                    self.ultimo_provedor = provedor.nome
                    return resposta
                except Exception as exc:
                    exc_final = exc
                    # Só retenta localmente no último provedor e só para 5xx transitório.
                    pode_retentar = eh_ultimo and _eh_5xx_retentavel(exc) and tentativa < tentativas - 1
                    if not pode_retentar:
                        break
                    espera = ESPERAS_RETRY_S[tentativa]
                    if isinstance(exc, httpx.HTTPStatusError):
                        retry_after = _retry_after_seguro(exc.response)
                        if retry_after is not None:
                            # Retry-After é espera MÍNIMA, não teto. Se o servidor
                            # pedir mais do que nosso orçamento, não repetimos.
                            if retry_after > MAX_ESPERA_RETRY_AFTER_S:
                                break
                            espera = max(espera, retry_after)
                    time.sleep(espera)
            if not erro_transitorio(exc_final):
                # 400/401/403 e problemas locais não são mascarados como rate limit.
                raise ProvedoresIndisponiveis(
                    f"Requisição rejeitada ({_diagnostico(provedor.nome, exc_final)})."
                ) from exc_final
            # Mesmas mensagens, sem mutá-las, vão para o próximo provedor.
            diagnosticos.append(_diagnostico(provedor.nome, exc_final))
        raise ProvedoresIndisponiveis(
            "Todas as APIs configuradas estão indisponíveis ou chegaram ao limite. "
            f"Diagnóstico: [{'; '.join(diagnosticos)}]."
        ) from exc_final
