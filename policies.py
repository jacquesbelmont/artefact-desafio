"""Consulta simples às páginas relevantes do PDF de políticas (sem RAG vetorial)."""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path
from pypdf import PdfReader

PDF_PATH = Path(__file__).resolve().parent / "data" / "politicas_da_loja.pdf"

# Os números são páginas físicas do PDF (1 a 8), conferidas no documento.
TOPICOS: dict[str, tuple[tuple[str, ...], tuple[int, ...]]] = {
    "loja": (("endereco", "localizacao", "telefone", "contato", "loja", "cnpj"), (2, 6)),
    "horario": (("horario", "aberto", "abre", "fecha", "funcionamento", "sábado", "sabado", "feriado"), (2, 6)),
    "pagamento": (("pagamento", "pix", "cartao", "boleto", "parcela", "parcelamento"), (3, 6)),
    "trocas": (("troca", "devolucao", "devolver", "arrependimento", "defeito", "reembolso"), (4, 7)),
    "entrega": (("frete", "entrega", "transportadora", "correios", "jadlog", "rastreio", "rastreamento", "prazo"), (4, 5)),
    "promocoes": (("promocao", "desconto", "oferta", "black friday", "liquidacao"), (6, 3)),
    "atendimento": (("atendimento", "whatsapp", "reclamacao", "fora de escopo"), (6, 7)),
    "garantia": (("garantia", "fabricante", "cobertura", "avaria"), (7, 4)),
    "privacidade": (("privacidade", "dados pessoais", "lgpd", "exclusao"), (7, 8)),
}


def normalizar(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(c)
    )


@lru_cache(maxsize=1)
def paginas_pdf() -> list[str]:
    leitor = PdfReader(str(PDF_PATH))
    return [pagina.extract_text() or "" for pagina in leitor.pages]


def consultar_politicas(assunto: str) -> dict:
    if not isinstance(assunto, str) or not assunto.strip():
        return {"erro": "Informe o assunto da política a consultar."}
    pedido = normalizar(assunto.strip())
    combinacoes = []
    for nome, (palavras, paginas) in TOPICOS.items():
        if normalizar(nome) in pedido or any(normalizar(p) in pedido for p in palavras):
            combinacoes.append((nome, paginas))
    if not combinacoes:
        return {"erro": "Assunto não identificado no índice.", "assuntos_disponiveis": list(TOPICOS)}
    numeros = list(dict.fromkeys(n for _nome, paginas in combinacoes[:2] for n in paginas))
    textos = paginas_pdf()
    # Limite de até 3 páginas. Não truncamos páginas selecionadas, para não
    # omitir exceções importantes das regras dentro de uma página.
    numeros = numeros[:3]
    return {
        "assunto": assunto,
        "fonte": "Manual de Políticas e Procedimentos, versão 2.1 (junho/2025)",
        "paginas": [{"pagina": n, "texto": textos[n - 1]} for n in numeros],
        "observacao": "Manual pode conter ambiguidades; casos duvidosos devem ir à equipe humana.",
    }
