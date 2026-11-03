"""Histórico persistente em SQLite, independente de qual API respondeu."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / ".local" / "conversas.sqlite3"


class Historico:
    def __init__(self, caminho: Path = DEFAULT_DB):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS mensagens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sessao TEXT NOT NULL,
                    papel TEXT NOT NULL CHECK (papel IN ('user','assistant')),
                    conteudo TEXT NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_sessao ON mensagens(sessao, id)")

    def _conexao(self):
        return sqlite3.connect(self.caminho)

    def adicionar(self, sessao: str, papel: str, conteudo: str) -> None:
        if papel not in ("user", "assistant"):
            raise ValueError("Papel inválido")
        if not sessao or len(sessao) > 120:
            raise ValueError("Sessão inválida")
        with self._conexao() as con:
            con.execute(
                "INSERT INTO mensagens (sessao,papel,conteudo) VALUES (?,?,?)",
                (sessao, papel, conteudo),
            )

    def mensagens(self, sessao: str, limite: int = 16) -> list[dict[str, str]]:
        with self._conexao() as con:
            linhas = con.execute("""
                SELECT papel, conteudo FROM mensagens
                WHERE sessao = ? ORDER BY id DESC LIMIT ?
            """, (sessao, limite)).fetchall()
        return [{"role": papel, "content": texto} for papel, texto in reversed(linhas)]
