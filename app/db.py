import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATABASE_URL

DB_PATH = Path("data/gateway.db")
USE_PG = DATABASE_URL.startswith("postgres")
PK = "BIGSERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"


@contextmanager
def connect():
    if USE_PG:
        import psycopg  # only needed when DATABASE_URL is set
        conn = psycopg.connect(DATABASE_URL)
    else:
        DB_PATH.parent.mkdir(exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run(sql, params=(), fetch=None):
    if USE_PG:
        sql = sql.replace("?", "%s")
    with connect() as conn:
        cur = conn.execute(sql, params)
        if fetch == "one":
            return cur.fetchone()
        if fetch == "all":
            return cur.fetchall()
    return None


def month_start() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-01 00:00:00")


def init_db():
    with connect() as conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS request_logs (
                id {PK},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                customer_id TEXT,
                policy TEXT,
                model TEXT,
                route_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                latency_ms DOUBLE PRECISION,
                cost_usd DOUBLE PRECISION,
                status TEXT
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS customers (
                id {PK},
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                monthly_limit INTEGER,
                active INTEGER DEFAULT 1
            )"""
        )
        if not USE_PG:  # upgrade an older local database in place
            cols = [r[1] for r in conn.execute("PRAGMA table_info(request_logs)")]
            if "customer_id" not in cols:
                conn.execute("ALTER TABLE request_logs ADD COLUMN customer_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_customer_time "
            "ON request_logs (customer_id, created_at)"
        )


def log_request(policy, model, route_reason, input_tokens, output_tokens,
                latency_ms, cost_usd, status, customer_id="owner"):
    run(
        """INSERT INTO request_logs
           (customer_id, policy, model, route_reason, input_tokens,
            output_tokens, latency_ms, cost_usd, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (customer_id, policy, model, route_reason, input_tokens,
         output_tokens, latency_ms, cost_usd, status),
    )


def create_customer(name: str, key_hash: str, monthly_limit: int) -> int:
    row = run(
        "INSERT INTO customers (name, key_hash, monthly_limit) VALUES (?, ?, ?) RETURNING id",
        (name, key_hash, monthly_limit),
        "one",
    )
    return int(row[0])


def find_customer(key_hash: str):
    row = run(
        "SELECT id, name, monthly_limit, active FROM customers WHERE key_hash = ?",
        (key_hash,),
        "one",
    )
    if not row:
        return None
    return {"id": str(row[0]), "name": row[1], "limit": row[2], "active": bool(row[3])}


def set_active(customer_id: int, active: bool) -> None:
    run("UPDATE customers SET active = ? WHERE id = ?", (1 if active else 0, customer_id))


def usage_for(customer_id: str) -> dict:
    row = run(
        """SELECT COUNT(*), COALESCE(SUM(input_tokens), 0),
                  COALESCE(SUM(output_tokens), 0), COALESCE(SUM(cost_usd), 0)
           FROM request_logs
           WHERE customer_id = ? AND created_at >= ?
             AND status IN ('success', 'cache_hit')""",
        (customer_id, month_start()),
        "one",
    )
    return {
        "requests_this_month": int(row[0]),
        "input_tokens": int(row[1]),
        "output_tokens": int(row[2]),
        "cost_usd": float(row[3]),
    }


def usage_all() -> list[dict]:
    names = {
        str(r[0]): (r[1], r[2], bool(r[3]))
        for r in run("SELECT id, name, monthly_limit, active FROM customers", (), "all")
    }
    rows = run(
        """SELECT customer_id, COUNT(*), COALESCE(SUM(input_tokens), 0),
                  COALESCE(SUM(output_tokens), 0), COALESCE(SUM(cost_usd), 0)
           FROM request_logs
           WHERE created_at >= ? AND status IN ('success', 'cache_hit')
           GROUP BY customer_id""",
        (month_start(),),
        "all",
    )
    out = []
    for cid, n, tin, tout, cost in rows:
        name, limit, active = names.get(cid, (cid, None, True))
        out.append({
            "customer_id": cid, "name": name, "monthly_limit": limit, "active": active,
            "requests": int(n), "input_tokens": int(tin),
            "output_tokens": int(tout), "cost_usd": float(cost),
        })
    return out


def count_month(customer_id: str) -> int:
    return usage_for(customer_id)["requests_this_month"]