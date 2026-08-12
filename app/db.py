"""Camada de persistência (SQLite).

Valores monetários são SEMPRE inteiros em centavos. Nenhum float toca o banco.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from .config import DB_PATH

CATEGORIAS_GASTO = [
    "alimentacao",
    "mercado",
    "transporte",
    "moradia",
    "saude",
    "educacao",
    "lazer",
    "compras",
    "servicos",
    "assinaturas",
    "outros",
]

CATEGORIAS_RECEITA = [
    "salario",
    "freelance",
    "vendas",
    "rendimentos",
    "outros",
]

# Rótulos bonitos para exibição.
ROTULOS = {
    "alimentacao": "Alimentação",
    "mercado": "Mercado",
    "transporte": "Transporte",
    "moradia": "Moradia",
    "saude": "Saúde",
    "educacao": "Educação",
    "lazer": "Lazer",
    "compras": "Compras",
    "servicos": "Serviços",
    "assinaturas": "Assinaturas",
    "salario": "Salário",
    "freelance": "Freelance",
    "vendas": "Vendas",
    "rendimentos": "Rendimentos",
    "outros": "Outros",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY,
    telefone    TEXT    NOT NULL UNIQUE,
    nome        TEXT,
    criado_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS lancamentos (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuarios(id),
    tipo           TEXT    NOT NULL CHECK (tipo IN ('gasto', 'receita')),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    categoria      TEXT    NOT NULL,
    descricao      TEXT    NOT NULL,
    ocorrido_em    TEXT    NOT NULL,
    criado_em      TEXT    NOT NULL,
    mensagem_bruta TEXT
);

CREATE INDEX IF NOT EXISTS idx_lanc_usuario_data
    ON lancamentos (usuario_id, ocorrido_em);

-- O WhatsApp reentrega webhooks quando não recebe 200 a tempo. Sem esta
-- tabela, uma reentrega lançaria o mesmo gasto duas vezes.
CREATE TABLE IF NOT EXISTS mensagens_processadas (
    id           TEXT PRIMARY KEY,
    processado_em TEXT NOT NULL
);
"""


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with conectar() as conn:
        conn.executescript(SCHEMA)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Usuários
# --------------------------------------------------------------------------

def obter_ou_criar_usuario(telefone: str, nome: Optional[str] = None) -> int:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT id FROM usuarios WHERE telefone = ?", (telefone,)
        ).fetchone()
        if linha:
            if nome:
                conn.execute(
                    "UPDATE usuarios SET nome = ? WHERE id = ? AND nome IS NULL",
                    (nome, linha["id"]),
                )
            return linha["id"]

        cur = conn.execute(
            "INSERT INTO usuarios (telefone, nome, criado_em) VALUES (?, ?, ?)",
            (telefone, nome, _agora()),
        )
        return cur.lastrowid


# --------------------------------------------------------------------------
# Lançamentos
# --------------------------------------------------------------------------

def inserir_lancamento(
    usuario_id: int,
    tipo: str,
    valor_centavos: int,
    categoria: str,
    descricao: str,
    ocorrido_em: str,
    mensagem_bruta: str = "",
) -> int:
    with conectar() as conn:
        cur = conn.execute(
            """INSERT INTO lancamentos
               (usuario_id, tipo, valor_centavos, categoria, descricao,
                ocorrido_em, criado_em, mensagem_bruta)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                usuario_id,
                tipo,
                valor_centavos,
                categoria,
                descricao,
                ocorrido_em,
                _agora(),
                mensagem_bruta,
            ),
        )
        return cur.lastrowid


def total_por_categoria(
    usuario_id: int, tipo: str, inicio: str, fim: str
) -> list[sqlite3.Row]:
    """Soma agrupada por categoria no intervalo [inicio, fim] (datas inclusive)."""
    with conectar() as conn:
        return conn.execute(
            """SELECT categoria, SUM(valor_centavos) AS total, COUNT(*) AS qtd
               FROM lancamentos
               WHERE usuario_id = ? AND tipo = ?
                 AND ocorrido_em BETWEEN ? AND ?
               GROUP BY categoria
               ORDER BY total DESC""",
            (usuario_id, tipo, inicio, fim),
        ).fetchall()


def total_periodo(
    usuario_id: int,
    tipo: str,
    inicio: str,
    fim: str,
    categoria: Optional[str] = None,
) -> int:
    sql = """SELECT COALESCE(SUM(valor_centavos), 0) AS total
             FROM lancamentos
             WHERE usuario_id = ? AND tipo = ?
               AND ocorrido_em BETWEEN ? AND ?"""
    params: list = [usuario_id, tipo, inicio, fim]
    if categoria:
        sql += " AND categoria = ?"
        params.append(categoria)

    with conectar() as conn:
        return conn.execute(sql, params).fetchone()["total"]


def listar_recentes(usuario_id: int, limite: int = 10) -> list[sqlite3.Row]:
    with conectar() as conn:
        return conn.execute(
            """SELECT id, tipo, valor_centavos, categoria, descricao, ocorrido_em
               FROM lancamentos
               WHERE usuario_id = ?
               ORDER BY id DESC
               LIMIT ?""",
            (usuario_id, limite),
        ).fetchall()


def apagar_ultimo(usuario_id: int) -> Optional[sqlite3.Row]:
    """Apaga o lançamento mais recente do usuário e devolve o que foi apagado."""
    with conectar() as conn:
        linha = conn.execute(
            """SELECT id, tipo, valor_centavos, categoria, descricao
               FROM lancamentos WHERE usuario_id = ?
               ORDER BY id DESC LIMIT 1""",
            (usuario_id,),
        ).fetchone()
        if linha is None:
            return None
        conn.execute("DELETE FROM lancamentos WHERE id = ?", (linha["id"],))
        return linha


# --------------------------------------------------------------------------
# Idempotência de webhooks
# --------------------------------------------------------------------------

def marcar_processada(message_id: str) -> bool:
    """Devolve True se a mensagem é nova; False se já foi processada antes."""
    with conectar() as conn:
        try:
            conn.execute(
                "INSERT INTO mensagens_processadas (id, processado_em) VALUES (?, ?)",
                (message_id, _agora()),
            )
            return True
        except sqlite3.IntegrityError:
            return False
