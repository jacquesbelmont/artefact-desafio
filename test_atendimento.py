"""Teste de demonstração COM API REAL. Não substitui os testes offline em tests/.

Execute apenas depois de configurar GROQ_API_KEY no .env:
  python test_atendimento.py
Saída poderá ser registrada em exemplos/conversas_reais.md.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

from agent import AgenteAtendimento
from history import Historico
from providers import RoteadorProvedores, SemProvedor, ProvedoresIndisponiveis

CENARIOS = [
    ("Catálogo", "Quais violões disponíveis custam até R$ 1.000?", "buscar_produtos"),
    ("Política", "Comprei online e me arrependi. Posso devolver?", "consultar_politicas"),
    ("Endereço", "Qual é o endereço da loja e o horário de sábado?", "consultar_politicas"),
    ("Fora de escopo", "Qual a melhor receita de bolo de cenoura?", None),
]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    agente = AgenteAtendimento(RoteadorProvedores.do_ambiente(), Historico())
    falhas = 0
    print("# Conversas reais de demonstração (API)\n")
    for nome, pergunta, ferramenta in CENARIOS:
        sessao = "teste-" + uuid.uuid4().hex[:12]
        print(f"## {nome}\n\n**Cliente:** {pergunta}\n")
        try:
            resposta = agente.responder(sessao, pergunta)
        except (SemProvedor, ProvedoresIndisponiveis, RuntimeError) as exc:
            print(f"**Erro:** {exc}\n")
            falhas += 1
            continue
        print(f"**Atendente:** {resposta.texto}\n")
        ok = ferramenta in resposta.ferramentas_usadas if ferramenta else not resposta.ferramentas_usadas
        print(f"*Provedor: {resposta.provedor}; tools: {resposta.ferramentas_usadas}; validacao: {'OK' if ok else 'FALHOU'}*\n")
        if not ok:
            falhas += 1
    print(f"**Resultado dos cenários:** {len(CENARIOS)-falhas}/{len(CENARIOS)} sem falhas identificadas.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
