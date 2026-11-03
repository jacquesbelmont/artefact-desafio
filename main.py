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
    """Status e motivo devolvidos pela API (sem a chave), ou '' se a causa não for HTTP."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return ""
    status = exc.response.status_code
    try:
        motivo = exc.response.json().get("error", {}).get("message", "não informado")
    except (ValueError, AttributeError):
        motivo = "a API não retornou detalhes em JSON"
    return f"HTTP {status}: {str(motivo)[:MAX_MOTIVO_CHARS]}"


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
