from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStore:
    """Durable Postgres store with an in-memory fallback for local/dev use."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None
        self._lock = threading.RLock()
        self._memory = {
            "runs": {},
            "approvals": {},
            "connectors": {},
            "audit": [],
        }
        if database_url:
            self._connect()

    @property
    def durable(self) -> bool:
        return self._pool is not None

    def _connect(self) -> None:
        try:
            import psycopg2
            from psycopg2 import pool
            self._pool = pool.SimpleConnectionPool(1, 10, self.database_url)
            self._ensure_schema()
        except Exception as exc:
            print(f"[AgentStore] Postgres unavailable; using memory store: {exc}")
            self._pool = None

    def _connection(self):
        if not self._pool:
            return None
        return self._pool.getconn()

    def _release(self, conn) -> None:
        if conn and self._pool:
            self._pool.putconn(conn)

    def _ensure_schema(self) -> None:
        conn = self._connection()
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aria_agent_runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    output_text TEXT,
                    worker_names TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS aria_agent_approvals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    decided_at TIMESTAMPTZ,
                    expires_at TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS aria_agent_connectors (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    connector_type TEXT NOT NULL,
                    base_url TEXT,
                    config_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, name)
                );
                CREATE TABLE IF NOT EXISTS aria_agent_audit (
                    id BIGSERIAL PRIMARY KEY,
                    run_id TEXT,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_agent_approvals_user_idx
                    ON aria_agent_approvals(user_id, status, expires_at);
                CREATE INDEX IF NOT EXISTS aria_agent_runs_user_idx
                    ON aria_agent_runs(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS aria_agent_audit_run_idx
                    ON aria_agent_audit(run_id, created_at DESC);
            """)
            conn.commit()
        finally:
            self._release(conn)

    def create_run(self, user_id: str, input_text: str, workers: list[str]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        row = {
            "id": run_id,
            "user_id": user_id,
            "status": "running",
            "input": input_text,
            "output": None,
            "workers": workers,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        if not self._pool:
            with self._lock:
                self._memory["runs"][run_id] = row
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO aria_agent_runs(id,user_id,status,input_text,worker_names) VALUES(%s,%s,%s,%s,%s)",
                (run_id, user_id, "running", input_text, json.dumps(workers)),
            )
            conn.commit()
        finally:
            self._release(conn)
        return row

    def update_run(self, run_id: str, status: str, output: Any = None) -> None:
        serialized = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
        if not self._pool:
            with self._lock:
                if run_id in self._memory["runs"]:
                    self._memory["runs"][run_id]["status"] = status
                    self._memory["runs"][run_id]["output"] = output
                    self._memory["runs"][run_id]["updated_at"] = now_iso()
            return
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE aria_agent_runs SET status=%s, output_text=%s, updated_at=NOW() WHERE id=%s",
                (status, serialized, run_id),
            )
            conn.commit()
        finally:
            self._release(conn)

    def create_approval(
        self,
        run_id: str,
        user_id: str,
        tool_name: str,
        action: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> dict[str, Any]:
        approval_id = str(uuid.uuid4())
        created = now_iso()
        expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        row = {
            "id": approval_id,
            "run_id": run_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "action": action,
            "payload": payload,
            "status": "pending",
            "created_at": created,
            "expires_at": expires,
        }
        if not self._pool:
            with self._lock:
                self._memory["approvals"][approval_id] = row
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO aria_agent_approvals
                (id,run_id,user_id,tool_name,action,payload_json,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                """,
                (approval_id, run_id, user_id, tool_name, action, json.dumps(payload, default=str), expires),
            )
            conn.commit()
        finally:
            self._release(conn)
        return row

    def get_approval(self, approval_id: str, user_id: str | None = None) -> Optional[dict[str, Any]]:
        if not self._pool:
            row = self._memory["approvals"].get(approval_id)
            if row and (user_id is None or row["user_id"] == user_id):
                return dict(row)
            return None
        conn = self._connection()
        try:
            cur = conn.cursor()
            if user_id:
                cur.execute(
                    "SELECT id,run_id,user_id,tool_name,action,payload_json,status,created_at,expires_at FROM aria_agent_approvals WHERE id=%s AND user_id=%s",
                    (approval_id, user_id),
                )
            else:
                cur.execute(
                    "SELECT id,run_id,user_id,tool_name,action,payload_json,status,created_at,expires_at FROM aria_agent_approvals WHERE id=%s",
                    (approval_id,),
                )
            r = cur.fetchone()
            if not r:
                return None
            return {
                "id": r[0], "run_id": r[1], "user_id": r[2], "tool_name": r[3], "action": r[4],
                "payload": json.loads(r[5]), "status": r[6], "created_at": str(r[7]),
                "expires_at": str(r[8]),
            }
        finally:
            self._release(conn)

    def decide_approval(self, approval_id: str, user_id: str, decision: str) -> Optional[dict[str, Any]]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        row = self.get_approval(approval_id, user_id)
        if not row:
            return None
        if row["status"] != "pending":
            return row
        if datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
            decision = "expired"
        if not self._pool:
            with self._lock:
                self._memory["approvals"][approval_id]["status"] = decision
            row["status"] = decision
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE aria_agent_approvals SET status=%s, decided_at=NOW() WHERE id=%s AND user_id=%s AND status='pending'",
                (decision, approval_id, user_id),
            )
            conn.commit()
        finally:
            self._release(conn)
        row["status"] = decision
        return row

    def list_connectors(self, user_id: str) -> list[dict[str, Any]]:
        if not self._pool:
            return [dict(v) for v in self._memory["connectors"].values() if v["user_id"] == user_id]
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,user_id,name,connector_type,base_url,config_json,created_at,updated_at FROM aria_agent_connectors WHERE user_id=%s ORDER BY name",
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                {"id":r[0],"user_id":r[1],"name":r[2],"connector_type":r[3],"base_url":r[4],
                 "config_json":json.loads(r[5]),"created_at":str(r[6]),"updated_at":str(r[7])}
                for r in rows
            ]
        finally:
            self._release(conn)

    def upsert_connector(self, row: dict[str, Any]) -> dict[str, Any]:
        if not self._pool:
            with self._lock:
                self._memory["connectors"][row["id"]] = dict(row)
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO aria_agent_connectors(id,user_id,name,connector_type,base_url,config_json)
                VALUES(%s,%s,%s,%s,%s,%s)
                ON CONFLICT(user_id,name) DO UPDATE SET
                    connector_type=EXCLUDED.connector_type,
                    base_url=EXCLUDED.base_url,
                    config_json=EXCLUDED.config_json,
                    updated_at=NOW()
                """,
                (
                    row["id"], row["user_id"], row["name"], row["connector_type"], row.get("base_url"),
                    json.dumps(row.get("config_json", {}), default=str)
                ),
            )
            conn.commit()
        finally:
            self._release(conn)
        return row

    def delete_connector(self, connector_id: str, user_id: str) -> bool:
        if not self._pool:
            row = self._memory["connectors"].get(connector_id)
            if row and row["user_id"] == user_id:
                del self._memory["connectors"][connector_id]
                return True
            return False
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM aria_agent_connectors WHERE id=%s AND user_id=%s", (connector_id, user_id))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        finally:
            self._release(conn)

    def audit(self, run_id: str | None, user_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        safe = json.dumps(payload, ensure_ascii=False, default=str)
        if not self._pool:
            with self._lock:
                self._memory["audit"].append({
                    "run_id": run_id, "user_id": user_id, "event_type": event_type,
                    "payload": payload, "created_at": now_iso()
                })
            return
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO aria_agent_audit(run_id,user_id,event_type,payload_json) VALUES(%s,%s,%s,%s)",
                (run_id, user_id, event_type, safe),
            )
            conn.commit()
        finally:
            self._release(conn)
