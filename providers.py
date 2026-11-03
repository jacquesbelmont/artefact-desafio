"""Duas APIs com o mesmo contrato HTTP de Chat Completions + fallback.

A implementação usa httpx diretamente em vez de instalar dois SDKs diferentes.
Groq e OpenRouter expõem endpoints compatíveis com o formato OpenAI.
"""
from __future__ import annotations

import os
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
        if chave := os.getenv("OPENROUTER_API_KEY", "").strip():
            provedores.append(ProvedorOpenAICompativel(
                "openrouter", "https://openrouter.ai/api/v1", chave,
                os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"), timeout,
            ))
        return cls(provedores)

    def completar(self, mensagens: list[dict], ferramentas: list[dict]) -> RespostaModelo:
        if not self.provedores:
            raise SemProvedor("Configure GROQ_API_KEY ou OPENROUTER_API_KEY no .env para iniciar.")
        for provedor in self.provedores:
            try:
                resposta = provedor.completar(mensagens, ferramentas)
                self.ultimo_provedor = provedor.nome
                return resposta
            except Exception as exc:
                if not erro_transitorio(exc):
                    # 400/401/403 e problemas locais não são mascarados como rate limit.
                    raise ProvedoresIndisponiveis(
                        f"Requisição rejeitada por {provedor.nome} ({type(exc).__name__})."
                    ) from exc
                # Mesmas mensagens, sem mutá-las, vão para o próximo provedor.
        raise ProvedoresIndisponiveis(
            "Todas as APIs configuradas estão indisponíveis ou chegaram ao limite."
        )
