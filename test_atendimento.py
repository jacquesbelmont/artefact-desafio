"""Teste de atendimento: simula uma conversa com o agente e testa a API da Groq.

Uso:
    export GROQ_API_KEY=gsk_...   (ou coloque em agent/.env)
    python3 test_atendimento.py
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from groq import Groq

MODEL = "llama-3.3-70b-versatile"
MAX_TURNS = 5
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SYSTEM_PROMPT = (
    "Você é o atendente virtual da Empório da Música, loja de instrumentos musicais "
    "em Campo Grande/MS. Tom simpático, direto e em português do Brasil. "
    "Use as ferramentas para preço, estoque e status de pedido; nunca invente dados. "
    "Se a pergunta fugir do escopo da loja, recuse com educação."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_produtos",
            "description": "Busca produtos ativos por nome, categoria e/ou preço máximo (BRL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Trecho do nome do produto"},
                    "categoria": {
                        "type": "string",
                        "description": "Categoria, ex.: Violões, Guitarras, Baixos, Ukuleles",
                    },
                    "preco_max": {"type": "number", "description": "Preço máximo em BRL"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "status_pedido",
            "description": "Consulta status, rastreio e previsão de entrega de um pedido pelo id.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "integer"}},
                "required": ["order_id"],
            },
        },
    },
]


def load_table(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / f"desafio_tecnico_ai_eng - {name}.csv")


CATEGORIES = load_table("categories").rename(columns={"name": "category"})
PRODUCTS = load_table("products").merge(
    CATEGORIES[["category_id", "category"]], on="category_id", how="left"
)
ORDERS = load_table("orders")


def buscar_produtos(nome: str = "", categoria: str = "", preco_max: float = None) -> list:
    df = PRODUCTS[PRODUCTS["status"] == "active"]
    if nome:
        df = df[df["name"].str.contains(nome, case=False, na=False)]
    if categoria:
        df = df[df["category"].str.contains(categoria, case=False, na=False)]
    if preco_max is not None:
        df = df[df["price_brl"] <= preco_max]
    cols = ["product_id", "name", "category", "price_brl", "stock_quantity"]
    return df[cols].head(10).to_dict("records")


def status_pedido(order_id: int) -> dict:
    row = ORDERS[ORDERS["order_id"] == order_id]
    if row.empty:
        return {"erro": "Pedido não encontrado"}
    cols = ["order_id", "status", "tracking_code", "estimated_delivery"]
    return json.loads(row[cols].iloc[0].to_json())


TOOL_FUNCS = {"buscar_produtos": buscar_produtos, "status_pedido": status_pedido}


def run_tool(name: str, args: dict) -> str:
    try:
        return json.dumps(TOOL_FUNCS[name](**args), ensure_ascii=False)
    except Exception as exc:  # erro devolvido ao modelo, não engolido
        return json.dumps({"erro": f"{type(exc).__name__}: {exc}"})


def answer(client: Groq, history: list) -> tuple:
    """Roda o loop de tool calling e devolve (texto, ferramentas_usadas, novo_histórico)."""
    messages = list(history)
    used = []
    for _ in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tools=TOOLS,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            return msg.content or "", used, messages
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in msg.tool_calls
                ],
            }
        )
        for call in msg.tool_calls:
            used.append(call.function.name)
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": run_tool(call.function.name, args),
                }
            )
    raise RuntimeError("Limite de turnos de ferramenta excedido")


# (mensagem do cliente, ferramenta esperada ou None)
SCENARIO = [
    ("Oi, bom dia! Quais violões vocês têm até R$ 1000?", "buscar_produtos"),
    ("E qual o status do pedido 2?", "status_pedido"),
    ("Qual a melhor receita de bolo de cenoura?", None),
]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    if not os.getenv("GROQ_API_KEY"):
        print("ERRO: defina GROQ_API_KEY (ambiente ou agent/.env).")
        return 1

    client = Groq()
    history, failures = [], 0
    for user_msg, expected_tool in SCENARIO:
        print(f"\nCliente: {user_msg}")
        history.append({"role": "user", "content": user_msg})
        text, used, history = answer(client, history)
        print(f"Agente:  {text}\n  [ferramentas: {used or 'nenhuma'}]")

        ok = (expected_tool in used) if expected_tool else not used
        print(f"  -> {'OK' if ok else 'FALHOU'} (esperado: {expected_tool or 'nenhuma'})")
        failures += 0 if ok else 1

    print(f"\n{len(SCENARIO) - failures}/{len(SCENARIO)} cenários passaram.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
