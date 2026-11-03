"""Teste de demonstração COM API REAL. Não substitui os testes offline em tests/.

Execute apenas depois de configurar GROQ_API_KEY no .env:
  python test_atendimento.py
  python test_atendimento.py --only Catálogo
  python test_atendimento.py --delay 2
Saída poderá ser registrada em exemplos/conversas_reais.md.
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

from agent import AgenteAtendimento
from history import Historico
from providers import RoteadorProvedores, SemProvedor, ProvedoresIndisponiveis
from tools import buscar_produtos

CENARIOS = [
    ("Catálogo", "Quais violões disponíveis custam até R$ 1.000?", "buscar_produtos"),
    ("Política", "Comprei online e me arrependi. Posso devolver?", "consultar_politicas"),
    ("Endereço", "Qual é o endereço da loja e o horário de sábado?", "consultar_politicas"),
    ("Fora de escopo", "Qual a melhor receita de bolo de cenoura?", None),
]

FRASES_NEGACAO_CATALOGO = (
    "nao ha", "não há", "nao temos", "não temos", "nao encontrei", "não encontrei",
    "nao disponivel", "não disponível", "nenhum produto", "sem produtos",
)


def resposta_nega_catalogo_confirmado(texto: str, ferramentas_usadas: list[str]) -> bool:
    """Checagem automática e honesta: se buscar_produtos confirmou produtos disponíveis
    (categoria Violões, preço <= 1000 nos dados de exemplo), o texto final não pode
    dizer que não há nenhum disponível. Isto NÃO prova que a resposta é correta em
    geral — só rejeita esta contradição específica e verificável offline.
    """
    if "buscar_produtos" not in ferramentas_usadas:
        return False
    tem_violao_barato = bool(buscar_produtos(categoria="Violões", preco_max=1000)["produtos"])
    if not tem_violao_barato:
        return False
    texto_normalizado = texto.lower()
    return any(frase in texto_normalizado for frase in FRASES_NEGACAO_CATALOGO)


def analisar_argumentos(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", dest="only", default=None, help="Nome exato de um cenário (ex.: Catálogo)")
    parser.add_argument("--delay", dest="delay", type=float, default=0.0, help="Segundos de espera entre cenários (>= 0)")
    args = parser.parse_args(argv)
    if args.delay < 0:
        parser.error("--delay precisa ser um número não-negativo")
    return args


def main(argv: list[str] | None = None) -> int:
    args = analisar_argumentos(sys.argv[1:] if argv is None else argv)
    cenarios = CENARIOS
    if args.only is not None:
        cenarios = [c for c in CENARIOS if c[0] == args.only]
        if not cenarios:
            nomes = ", ".join(n for n, _, _ in CENARIOS)
            print(f"Cenário '{args.only}' não encontrado. Disponíveis: {nomes}")
            return 1

    load_dotenv(Path(__file__).resolve().parent / ".env")
    agente = AgenteAtendimento(RoteadorProvedores.do_ambiente(), Historico())
    falhas = 0
    print("# Conversas reais de demonstração (API)\n")
    for indice, (nome, pergunta, ferramenta) in enumerate(cenarios):
        if indice > 0 and args.delay > 0:
            time.sleep(args.delay)
        sessao = "teste-" + uuid.uuid4().hex[:12]
        print(f"## {nome}\n\n**Cliente:** {pergunta}\n")
        try:
            resposta = agente.responder(sessao, pergunta)
        except (SemProvedor, ProvedoresIndisponiveis, RuntimeError) as exc:
            print(f"**Erro:** {exc}\n")
            falhas += 1
            continue
        print(f"**Atendente:** {resposta.texto}\n")
        # Invocar a ferramenta certa não é prova de que o texto final é factualmente
        # correto (o modelo ainda pode contradizer o resultado); por isso a checagem
        # de contradição abaixo é um complemento, não um substituto desta validação.
        ok = ferramenta in resposta.ferramentas_usadas if ferramenta else not resposta.ferramentas_usadas
        contradiz = resposta_nega_catalogo_confirmado(resposta.texto, resposta.ferramentas_usadas)
        if contradiz:
            ok = False
        print(f"*Provedor: {resposta.provedor}; tools: {resposta.ferramentas_usadas}; validacao: {'OK' if ok else 'FALHOU'}*\n")
        if contradiz:
            print("**Inconsistência:** resposta nega catálogo que a ferramenta confirmou disponível.\n")
        if not ok:
            falhas += 1
    print(f"**Resultado dos cenários:** {len(cenarios)-falhas}/{len(cenarios)} sem falhas identificadas.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
