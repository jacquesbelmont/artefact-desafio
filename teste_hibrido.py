"""Quinto cenário real: pedido + PDF de entregas, em dois turnos.

Usa exclusivamente dados FICTÍCIOS dos CSVs. Nunca publica e-mail de teste.
Exemplo: python teste_hibrido.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv
from agent import AgenteAtendimento
from history import Historico
from providers import RoteadorProvedores, SemProvedor, ProvedoresIndisponiveis
from tools import tabela, status_pedido
from avaliacao import avaliar_regras

PEDIDO_DEMO = 8  # pedido de exemplo marcado como 'shipped' nos CSVs
PERGUNTA_1 = ("Meu pedido 8 já foi enviado? Ainda posso mudar o endereço de entrega?")
PERGUNTA_2 = ("O e-mail cadastrado é {email}. Verifique meu pedido e consulte "
              "as políticas de entrega. A mudança do endereço está garantida?")


def _email_ficticio_pedido() -> str:
    pedido = next(p for p in tabela("orders") if int(p["order_id"]) == PEDIDO_DEMO)
    cliente = next(c for c in tabela("customers") if c["customer_id"] == pedido["customer_id"])
    return cliente["email"]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    email = _email_ficticio_pedido()
    esperado = status_pedido(PEDIDO_DEMO, email)
    agente = AgenteAtendimento(RoteadorProvedores.do_ambiente(), Historico())
    sessao = "hibrido-" + uuid.uuid4().hex[:12]
    falhas = []
    ferramentas = []
    print("# Fifth real conversation — order status + delivery policy\n")
    print("**Customer:** " + PERGUNTA_1 + "\n", flush=True)
    try:
        resposta1 = agente.responder(sessao, PERGUNTA_1)
        ferramentas += resposta1.ferramentas_usadas
        texto1 = resposta1.texto.replace(email, "[e-mail fictício omitido]")
        print("**Agent:** " + texto1 + "\n", flush=True)
        print(f"*Provider: {resposta1.provedor}; tools: {resposta1.ferramentas_usadas}*\n", flush=True)
        # Chamar status_pedido sem e-mail não expõe dados: a ferramenta bloqueia
        # a consulta e retorna apenas um erro de verificação. O que importa é
        # não revelar status/rastreamento antes da autenticação demonstrativa.
        if esperado.get("codigo_rastreamento") and esperado["codigo_rastreamento"] in texto1:
            falhas.append("Código de rastreamento revelado antes da verificação do e-mail.")
        if "email" not in _normalizar_simples(texto1).replace("-", ""):
            falhas.append("Agente não pediu o e-mail necessário para validar o pedido.")
        print("**Customer:** Meu e-mail cadastrado é [e-mail fictício do CSV omitido]. "
              "Pode verificar o pedido e a política de entrega?\n", flush=True)
        resposta2 = agente.responder(sessao, PERGUNTA_2.format(email=email))
        ferramentas += resposta2.ferramentas_usadas
        texto2 = resposta2.texto.replace(email, "[e-mail fictício omitido]")
        print("**Agent:** " + texto2 + "\n", flush=True)
        print(f"*Provider: {resposta2.provedor}; tools: {resposta2.ferramentas_usadas}*\n", flush=True)
        for ferramenta in ("status_pedido", "consultar_politicas"):
            if ferramenta not in ferramentas:
                falhas.append("Ferramenta obrigatória não usada: " + ferramenta)
        falhas.extend(avaliar_regras(texto1 + "\n" + texto2, "alteracao_endereco"))
        # Status verificado pelo CSV de demonstração: shipped, nunca conclusão de alteração.
        if not any(x in _normalizar_simples(texto2) for x in ("enviado", "despachado", "transporte", "a caminho")):
            falhas.append("A resposta não contextualizou o pedido enviado.")
    except (SemProvedor, ProvedoresIndisponiveis, RuntimeError, ValueError) as exc:
        falhas.append("Falha na API/agente: " + str(exc)[:220])
    print("**Result:** " + ("PASS" if not falhas else "FAIL") + "\n")
    for erro in falhas:
        print("- " + erro)
    print("\n*This checks tool usage and selected factual claims, not full semantic accuracy.*")
    return 1 if falhas else 0


def _normalizar_simples(texto: str) -> str:
    from policies import normalizar
    return normalizar(texto)


if __name__ == "__main__":
    sys.exit(main())
