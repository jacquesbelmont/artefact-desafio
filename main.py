"""Interface CLI simples para demonstração do agente."""
from __future__ import annotations

import argparse
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

from agent import AgenteAtendimento
from history import Historico
from providers import RoteadorProvedores, SemProvedor, ProvedoresIndisponiveis


MAX_MOTIVO_CHARS = 400


def detalhe_http(exc: BaseException | None) -> str:
    """Status e motivo devolvidos pela API (sem a chave), ou '' se a causa não for HTTP.

    A Gemini API às vezes devolve o corpo de erro como uma LISTA com um único
    dict (em vez do dict único do formato OpenAI). Nunca repassamos o texto
    bruto do erro (pode conter trechos da requisição); só uma classificação
    curta e seca do motivo.
    """
    if not isinstance(exc, httpx.HTTPStatusError):
        return ""
    status = exc.response.status_code
    try:
        corpo = exc.response.json()
    except ValueError:
        return f"HTTP {status}: a API não retornou detalhes em JSON"
    if isinstance(corpo, list):
        corpo = corpo[0] if corpo else {}
    if not isinstance(corpo, dict):
        return f"HTTP {status}: formato de erro inesperado"
    erro = corpo.get("error")
    motivo_seguro = "motivo não classificado"
    if isinstance(erro, dict):
        status_erro = erro.get("status")
        if isinstance(status_erro, str) and status_erro:
            motivo_seguro = status_erro
    return f"HTTP {status}: {motivo_seguro}"[:MAX_MOTIVO_CHARS]


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    parser = argparse.ArgumentParser(description="Empório da Música — agente de atendimento")
    parser.add_argument("--sessao", default=None, help="Nome da sessão para retomar histórico")
    args = parser.parse_args()
    sessao = args.sessao or f"demo-{uuid.uuid4().hex[:8]}"
    historico = Historico()
    agente = AgenteAtendimento(RoteadorProvedores.do_ambiente(), historico)
    print("Empório da Música — sua música começa aqui!")
    print(f"Sessão: {sessao} (para retomar: python main.py --sessao {sessao})")
    print("Digite /sair para encerrar.\n")
    while True:
        try:
            mensagem = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo!")
            return
        if mensagem.lower() in ("/sair", "/exit", "/quit"):
            print("Até logo!")
            return
        if not mensagem:
            continue
        try:
            resposta = agente.responder(sessao, mensagem)
        except (SemProvedor, ProvedoresIndisponiveis) as e:
            print(f"Sistema: {e}")
            if detalhe := detalhe_http(e.__cause__):
                print(f"Detalhe: {detalhe}")
            print("Sua mensagem foi registrada; tente novamente depois.")
            continue
        except (ValueError, RuntimeError) as e:
            print(f"Sistema: {e}")
            continue
        print(f"\nAtendente: {resposta.texto}")
        print(f"[API: {resposta.provedor}; ferramentas: {', '.join(resposta.ferramentas_usadas) or 'nenhuma'}]\n")


if __name__ == "__main__":
    main()
