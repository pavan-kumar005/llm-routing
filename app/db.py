import sqlite3
from pathlib import Path

DB_PATH = Path("data/gateway.db")


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                policy TEXT,
                model TEXT,
                route_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                latency_ms REAL,
                cost_usd REAL,
                status TEXT
            )
            """
        )


def log_request(policy, model, route_reason, input_tokens,
                output_tokens, latency_ms, cost_usd, status):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO request_logs
            (policy, model, route_reason, input_tokens, output_tokens,
             latency_ms, cost_usd, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (policy, model, route_reason, input_tokens,
             output_tokens, latency_ms, cost_usd, status),
        )