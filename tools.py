"""Ferramentas somente de leitura. O modelo não acessa arquivos diretamente."""
from __future__ import annotations

import csv
import hmac
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from policies import consultar_politicas

DATA = Path(__file__).resolve().parent / "data"
CENTAVOS = Decimal("0.01")


def tabela(nome: str) -> list[dict]:
    permitidos = {"products", "categories", "customers", "orders", "order_items", "promotions"}
    if nome not in permitidos:
        raise ValueError("Tabela não permitida")
    with (DATA / f"{nome}.csv").open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalizar(texto: str) -> str:
    from policies import normalizar as _normalizar
    return _normalizar(str(texto))


def moeda(valor: Decimal) -> str:
    valor = valor.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def promocoes_ativas() -> dict[str, dict]:
    promocoes: dict[str, dict] = {}
    for p in tabela("promotions"):
        if p["is_active"] != "1":
            continue
        produto_id = p["product_id"]
        # Se aparecerem duas promoções para o mesmo produto, não cumulamos.
        if produto_id not in promocoes or Decimal(p["discount_percent"]) > Decimal(promocoes[produto_id]["discount_percent"]):
            promocoes[produto_id] = p
    return promocoes


def buscar_produtos(nome: str = "", categoria: str = "", preco_max: float | None = None) -> dict:
    """Produtos compráveis: active E estoque > 0. Preço final respeita promoção ativa."""
    categorias = {c["category_id"]: c["name"] for c in tabela("categories")}
    promos = promocoes_ativas()
    limite_preco = Decimal(str(preco_max)) if preco_max is not None else None
    if limite_preco is not None and limite_preco < 0:
        raise ValueError("Preço máximo precisa ser positivo")
    encontrados = []
    for p in tabela("products"):
        if p["status"] != "active" or int(p["stock_quantity"]) <= 0:
            continue
        nome_produto = p["name"]
        categoria_produto = categorias.get(p["category_id"], "Não informada")
        if nome and normalizar(nome) not in normalizar(nome_produto):
            continue
        if categoria and normalizar(categoria) not in normalizar(categoria_produto):
            continue
        preco = Decimal(p["price_brl"])
        promo = promos.get(p["product_id"])
        desconto = Decimal(promo["discount_percent"]) if promo else Decimal("0")
        final = (preco * (Decimal("100") - desconto) / Decimal("100")).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        if limite_preco is not None and final > limite_preco:
            continue
        encontrado = {
            "produto_id": int(p["product_id"]),
            "nome": nome_produto,
            "categoria": categoria_produto,
            "descricao": p["description"][:220],
            "preco_tabela": moeda(preco),
            "preco_atual": moeda(final),
            "estoque": int(p["stock_quantity"]),
        }
        if promo:
            encontrado["promocao"] = {"descricao": promo["description"], "desconto_percentual": str(desconto)}
        encontrados.append(encontrado)
    encontrados.sort(key=lambda x: Decimal(x["preco_atual"].removeprefix("R$ ").replace(".", "").replace(",", ".")))
    return {
        "total_encontrados": len(encontrados),
        "produtos": encontrados[:8],
        "aviso": "Preços e estoque vêm dos CSVs de exemplo; confirmação final depende da loja. Promoções sem datas nos dados.",
    }


def status_pedido(order_id: int, email: str) -> dict:
    """Proteção demonstrativa: combina ID do pedido com email cadastrado.

    Isto NÃO substitui autenticação real. Nunca retornar outros dados do cliente.
    """
    try:
        pedido_id = int(order_id)
    except (ValueError, TypeError):
        return {"erro": "ID do pedido inválido"}
    if not isinstance(email, str) or not email.strip():
        return {"erro": "Solicite o e-mail cadastrado antes da consulta."}
    pedidos = [o for o in tabela("orders") if int(o["order_id"]) == pedido_id]
    if not pedidos:
        return {"erro": "Pedido não localizado ou identificação não confirmada."}
    p = pedidos[0]
    clientes = [c for c in tabela("customers") if c["customer_id"] == p["customer_id"]]
    if not clientes or not hmac.compare_digest(clientes[0]["email"].strip().casefold(), email.strip().casefold()):
        return {"erro": "Pedido não localizado ou identificação não confirmada."}
    return {
        "pedido_id": pedido_id,
        "status": p["status"],
        "data_pedido": p["order_date"],
        "valor_registrado": moeda(Decimal(p["total_brl"])),
        "codigo_rastreamento": p["tracking_code"] or None,
        "entrega_prevista_no_registro": p["estimated_delivery"] or None,
        "aviso": "Datas e status são um retrato dos CSVs; não representam consulta ao sistema de transporte em tempo real.",
    }


FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_produtos",
            "description": "Consulta produtos disponíveis no catálogo CSV por nome, categoria e orçamento; calcula desconto de promoção ativa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "categoria": {"type": "string"},
                    "preco_max": {"type": "number", "description": "Valor máximo do produto em reais"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "status_pedido",
            "description": "Consulta pedido quando cliente fornece número do pedido E email de cadastro. Não chamar com email inventado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "email": {"type": "string"},
                },
                "required": ["order_id", "email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_politicas",
            "description": "Consulta o PDF de políticas da loja: horários, endereço, pagamentos, fretes, trocas, garantias, promoções, WhatsApp ou privacidade.",
            "parameters": {
                "type": "object",
                "properties": {"assunto": {"type": "string"}},
                "required": ["assunto"],
                "additionalProperties": False,
            },
        },
    },
]

_FUNCOES = {
    "buscar_produtos": buscar_produtos,
    "status_pedido": status_pedido,
    "consultar_politicas": consultar_politicas,
}


def executar_ferramenta(nome: str, argumentos_json: str) -> str:
    if nome not in _FUNCOES:
        return json.dumps({"erro": "Ferramenta não autorizada."}, ensure_ascii=False)
    try:
        argumentos: Any = json.loads(argumentos_json)
        if not isinstance(argumentos, dict):
            raise ValueError("Argumentos precisam ser objeto JSON")
        resultado = _FUNCOES[nome](**argumentos)
        return json.dumps(resultado, ensure_ascii=False)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return json.dumps({"erro": "Parâmetros inválidos para a ferramenta."}, ensure_ascii=False)
    except Exception:
        # Erros internos não são enviados ao LLM com paths, credenciais ou traceback.
        return json.dumps({"erro": "Não foi possível consultar os dados agora."}, ensure_ascii=False)
