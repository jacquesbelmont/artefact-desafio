"""Avaliações determinísticas e limitadas de fidelidade; não substituem revisão humana."""
from __future__ import annotations

import re
from decimal import Decimal
from policies import normalizar

DINHEIRO = re.compile(r"(?:R\$\s*)?((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})", re.I)
ESTOQUE = re.compile(r"\b(\d+)\s*(?:unidades?|unid\.?|em\s+estoque)\b|\bestoque\s*:\s*(\d+)\b", re.I)
SEM_PRODUTOS = ("nao ha produtos", "nao temos produtos", "nenhum produto disponivel",
                "nao temos violoes", "nao ha violoes", "nenhum violao disponivel")


def _texto_busca(texto: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", normalizar(texto)))


def _preco_bruto(valor: str) -> Decimal:
    return Decimal(valor.replace("R$", "").replace(" ", "").replace(".", "").replace(",", "."))


def avaliar_catalogo(texto: str, produtos: list[dict]) -> tuple[int, list[str]]:
    """Compara preços/estoques explicitamente associados aos produtos citados.

    Somente afirma o que pôde comparar; itens omitidos ou frases ambíguas exigem
    revisão manual. Não transforma ausência de contradição em prova de precisão.
    """
    erros: list[str] = []
    checagens = 0
    if produtos and any(frase in _texto_busca(texto) for frase in SEM_PRODUTOS):
        erros.append("A resposta nega produtos presentes no catálogo.")
    for linha in texto.splitlines():
        normalizada = _texto_busca(linha)
        for produto in produtos:
            palavras = _texto_busca(produto["nome"]).split()
            if len(palavras) < 2:
                continue
            identidade = " ".join(palavras[:2 if any(c.isdigit() for c in palavras[1]) else 3])
            if identidade not in normalizada:
                continue
            valores = [_preco_bruto(x) for x in DINHEIRO.findall(linha)]
            if valores:
                esperado = _preco_bruto(produto["preco_atual"])
                checagens += 1
                if esperado not in valores:
                    erros.append(f"Preço inconsistente para {produto['nome']}: esperado {produto['preco_atual']}.")
            quantidades = [int(a or b) for a, b in ESTOQUE.findall(linha)]
            if not quantidades and "|" in linha:
                match = re.search(r"\|\s*(\d+)\s*\|?\s*$", linha)
                if match:
                    quantidades = [int(match.group(1))]
            if quantidades:
                checagens += 1
                if int(produto["estoque"]) not in quantidades:
                    erros.append(f"Estoque inconsistente para {produto['nome']}: esperado {produto['estoque']}.")
    return checagens, list(dict.fromkeys(erros))


def avaliar_regras(texto: str, assunto: str) -> list[str]:
    """Detecta somente contradições explícitas de regras simples do PDF; não é RAG."""
    t = _texto_busca(texto)
    erros: list[str] = []
    if assunto == "arrependimento":
        # Prazo de 7 dias corridos, página 4 do manual.
        if re.search(r"\b(?:14|15) dias corridos\b", t):
            erros.append("Prazo de arrependimento contradiz os 7 dias corridos do manual.")
    if assunto == "pix_promocao":
        # O PIX de 5% não acumula com desconto promocional, página 6.
        if re.search(r"\b(?:pix.*(?:acumula|cumulativo)|(?:acumula|cumulativo).*pix)\b", t) and not re.search(
            r"\b(?:nao|nunca|sem)\s+(?:se\s+)?(?:acumula|acumular|cumulativo)\b", t
        ):
            erros.append("Resposta sugere acumular PIX com promoção, proibido pelo manual.")
    if assunto == "alteracao_endereco":
        # O manual não autoriza nem proíbe explicitamente mudança após o envio.
        if re.search(r"\b(?:ja alterei|endereco alterado|alteracao confirmada)\b", t):
            erros.append("Agente afirma ter alterado endereço, mas não existe ferramenta para isso.")
        if re.search(r"\b(?:nao e possivel|impossivel|proibido)\s+alterar\s+(?:o\s+)?endereco", t):
            erros.append("O manual não documenta proibição absoluta de mudança de endereço.")
    return erros
