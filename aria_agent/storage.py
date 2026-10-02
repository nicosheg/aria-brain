from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStore:
    """Durable Postgres state with a safe in-memory fallback for development."""

    def __init__(self, database_url: str = ""):
        self.database_url = database_url
        self._pool = None
        self._lock = threading.RLock()
        self._memory = {"runs": {}, "approvals": {}, "connectors": {}, "memory": {}, "automations": {}, "audit": []}
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
            print(f"[AgentStore] Postgres unavailable; memory fallback active: {exc}")
            self._pool = None

    def _connection(self):
        return self._pool.getconn() if self._pool else None

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
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, status TEXT NOT NULL,
                    input_text TEXT NOT NULL, output_text TEXT,
                    worker_names TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS aria_agent_approvals (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL, action TEXT NOT NULL, payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    decided_at TIMESTAMPTZ, expires_at TIMESTAMPTZ NOT NULL
                );
                CREATE TABLE IF NOT EXISTS aria_agent_connectors (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
                    connector_type TEXT NOT NULL, base_url TEXT, config_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id, name)
                );
                CREATE TABLE IF NOT EXISTS aria_agent_memory (
                    user_id TEXT NOT NULL, key TEXT NOT NULL, content TEXT NOT NULL,
                    importance DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY(user_id, key)
                );
                CREATE TABLE IF NOT EXISTS aria_agent_audit (
                    id BIGSERIAL PRIMARY KEY, run_id TEXT, user_id TEXT, event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS aria_agent_automations (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL,
                    trigger_name TEXT NOT NULL, prompt TEXT NOT NULL, secret_hash TEXT NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(user_id,name)
                );
                CREATE INDEX IF NOT EXISTS aria_agent_automations_user_idx
                  ON aria_agent_automations(user_id, enabled);
                CREATE INDEX IF NOT EXISTS aria_agent_approvals_user_idx
                  ON aria_agent_approvals(user_id,status,expires_at);
                CREATE INDEX IF NOT EXISTS aria_agent_runs_user_idx
                  ON aria_agent_runs(user_id,created_at DESC);
                CREATE INDEX IF NOT EXISTS aria_agent_audit_run_idx
                  ON aria_agent_audit(run_id,created_at DESC);
            """)
            conn.commit()
        finally:
            self._release(conn)

    def create_run(self, user_id: str, input_text: str, workers: list[str]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        row = {"id": run_id, "user_id": user_id, "status": "running", "input": input_text,
               "output": None, "workers": workers, "created_at": now_iso(), "updated_at": now_iso()}
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
                    self._memory["runs"][run_id].update(status=status, output=output, updated_at=now_iso())
            return
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE aria_agent_runs SET status=%s,output_text=%s,updated_at=NOW() WHERE id=%s",
                        (status, serialized, run_id))
            conn.commit()
        finally:
            self._release(conn)

    def create_approval(self, run_id: str, user_id: str, tool_name: str, action: str,
                        payload: dict[str, Any], ttl_seconds: int) -> dict[str, Any]:
        approval_id = str(uuid.uuid4())
        expires = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        row = {"id": approval_id, "run_id": run_id, "user_id": user_id, "tool_name": tool_name,
               "action": action, "payload": payload, "status": "pending",
               "created_at": now_iso(), "expires_at": expires}
        if not self._pool:
            with self._lock:
                self._memory["approvals"][approval_id] = row
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO aria_agent_approvals(id,run_id,user_id,tool_name,action,payload_json,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (approval_id, run_id, user_id, tool_name, action, json.dumps(payload, default=str), expires),
            )
            conn.commit()
        finally:
            self._release(conn)
        return row

    def get_approval(self, approval_id: str, user_id: str | None = None) -> Optional[dict[str, Any]]:
        if not self._pool:
            row = self._memory["approvals"].get(approval_id)
            return dict(row) if row and (user_id is None or row["user_id"] == user_id) else None
        conn = self._connection()
        try:
            cur = conn.cursor()
            query = "SELECT id,run_id,user_id,tool_name,action,payload_json,status,created_at,expires_at FROM aria_agent_approvals WHERE id=%s"
            params: list[Any] = [approval_id]
            if user_id:
                query += " AND user_id=%s"
                params.append(user_id)
            cur.execute(query, params)
            r = cur.fetchone()
            if not r:
                return None
            return {"id": r[0], "run_id": r[1], "user_id": r[2], "tool_name": r[3], "action": r[4],
                    "payload": json.loads(r[5]), "status": r[6], "created_at": str(r[7]), "expires_at": str(r[8])}
        finally:
            self._release(conn)

    def decide_approval(self, approval_id: str, user_id: str, decision: str) -> Optional[dict[str, Any]]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid approval decision")
        row = self.get_approval(approval_id, user_id)
        if not row:
            return None
        if row["status"] != "pending":
            return row
        expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if expires < datetime.now(timezone.utc):
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
                "UPDATE aria_agent_approvals SET status=%s,decided_at=NOW() WHERE id=%s AND user_id=%s AND status='pending'",
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
            return [{"id": r[0], "user_id": r[1], "name": r[2], "connector_type": r[3],
                     "base_url": r[4], "config_json": json.loads(r[5]), "created_at": str(r[6]), "updated_at": str(r[7])}
                    for r in rows]
        finally:
            self._release(conn)

    def upsert_connector(self, row: dict[str, Any]) -> dict[str, Any]:
        if not self._pool:
            with self._lock:
                existing = next((k for k, v in self._memory["connectors"].items()
                                 if v["user_id"] == row["user_id"] and v["name"].lower() == row["name"].lower()), None)
                if existing:
                    row["id"] = existing
                self._memory["connectors"][row["id"]] = dict(row)
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO aria_agent_connectors(id,user_id,name,connector_type,base_url,config_json)
                   VALUES(%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,name) DO UPDATE SET
                     connector_type=EXCLUDED.connector_type, base_url=EXCLUDED.base_url,
                     config_json=EXCLUDED.config_json, updated_at=NOW()
                   RETURNING id""",
                (row["id"], row["user_id"], row["name"], row["connector_type"], row.get("base_url"),
                 json.dumps(row.get("config_json", {}), default=str)),
            )
            actual_id = cur.fetchone()[0]
            conn.commit()
            row["id"] = actual_id
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

    def write_memory(self, user_id: str, key: str, content: str, importance: float = 0.5) -> dict[str, Any]:
        key, content = (key or "").strip(), (content or "").strip()
        if not key or not content:
            raise ValueError("memory key and content are required")
        importance = max(0.0, min(1.0, float(importance)))
        row = {"key": key, "content": content, "importance": importance, "updated_at": now_iso()}
        if not self._pool:
            with self._lock:
                self._memory["memory"][(user_id, key)] = row
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO aria_agent_memory(user_id,key,content,importance)
                   VALUES(%s,%s,%s,%s)
                   ON CONFLICT(user_id,key) DO UPDATE SET
                     content=EXCLUDED.content, importance=EXCLUDED.importance, updated_at=NOW()""",
                (user_id, key, content, importance),
            )
            conn.commit()
        finally:
            self._release(conn)
        return row

    def read_memory(self, user_id: str, key: str = "", limit: int = 20) -> list[dict[str, Any]]:
        if not self._pool:
            items = [v for (uid, _), v in self._memory["memory"].items()
                     if uid == user_id and (not key or key.lower() in v["key"].lower())]
            return items[:limit]
        conn = self._connection()
        try:
            cur = conn.cursor()
            if key:
                cur.execute("SELECT key,content,importance,updated_at FROM aria_agent_memory WHERE user_id=%s AND key ILIKE %s ORDER BY importance DESC,updated_at DESC LIMIT %s",
                            (user_id, f"%{key}%", limit))
            else:
                cur.execute("SELECT key,content,importance,updated_at FROM aria_agent_memory WHERE user_id=%s ORDER BY importance DESC,updated_at DESC LIMIT %s",
                            (user_id, limit))
            return [{"key": r[0], "content": r[1], "importance": r[2], "updated_at": str(r[3])} for r in cur.fetchall()]
        finally:
            self._release(conn)

    def create_automation(self, user_id: str, name: str, trigger_name: str, prompt: str, secret_hash: str) -> dict[str, Any]:
        automation_id = uuid.uuid4().hex
        row = {
            "id": automation_id, "user_id": user_id, "name": name.strip(),
            "trigger_name": trigger_name.strip(), "prompt": prompt.strip(),
            "secret_hash": secret_hash, "enabled": True, "created_at": now_iso(),
        }
        if not self._pool:
            with self._lock:
                existing = next((v for v in self._memory["automations"].values()
                                 if v["user_id"] == user_id and v["name"].lower() == row["name"].lower()), None)
                if existing:
                    row["id"] = existing["id"]
                self._memory["automations"][row["id"]] = row
            return row
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO aria_agent_automations(id,user_id,name,trigger_name,prompt,secret_hash)
                   VALUES(%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(user_id,name) DO UPDATE SET
                     trigger_name=EXCLUDED.trigger_name,prompt=EXCLUDED.prompt,secret_hash=EXCLUDED.secret_hash,
                     enabled=TRUE,updated_at=NOW()
                   RETURNING id""",
                (row["id"], user_id, row["name"], row["trigger_name"], row["prompt"], row["secret_hash"]),
            )
            row["id"] = cur.fetchone()[0]
            conn.commit()
        finally:
            self._release(conn)
        return row

    def get_automation(self, automation_id: str, user_id: str | None = None) -> Optional[dict[str, Any]]:
        if not self._pool:
            row = self._memory["automations"].get(automation_id)
            if row and (user_id is None or row["user_id"] == user_id):
                return dict(row)
            return None
        conn = self._connection()
        try:
            cur = conn.cursor()
            query = "SELECT id,user_id,name,trigger_name,prompt,secret_hash,enabled,created_at,updated_at FROM aria_agent_automations WHERE id=%s"
            params: list[Any] = [automation_id]
            if user_id:
                query += " AND user_id=%s"
                params.append(user_id)
            cur.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id":row[0],"user_id":row[1],"name":row[2],"trigger_name":row[3],
                "prompt":row[4],"secret_hash":row[5],"enabled":row[6],
                "created_at":str(row[7]),"updated_at":str(row[8]),
            }
        finally:
            self._release(conn)

    def list_automations(self, user_id: str) -> list[dict[str, Any]]:
        if not self._pool:
            return [dict(v) for v in self._memory["automations"].values() if v["user_id"] == user_id]
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,user_id,name,trigger_name,prompt,enabled,created_at,updated_at FROM aria_agent_automations WHERE user_id=%s ORDER BY name",
                (user_id,),
            )
            return [
                {"id":r[0],"user_id":r[1],"name":r[2],"trigger_name":r[3],"prompt":r[4],
                 "enabled":r[5],"created_at":str(r[6]),"updated_at":str(r[7])}
                for r in cur.fetchall()
            ]
        finally:
            self._release(conn)

    def set_automation_enabled(self, automation_id: str, user_id: str, enabled: bool) -> bool:
        if not self._pool:
            row = self._memory["automations"].get(automation_id)
            if not row or row["user_id"] != user_id:
                return False
            row["enabled"] = bool(enabled)
            return True
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE aria_agent_automations SET enabled=%s,updated_at=NOW() WHERE id=%s AND user_id=%s",
                (bool(enabled), automation_id, user_id),
            )
            changed = cur.rowcount > 0
            conn.commit()
            return changed
        finally:
            self._release(conn)

    def delete_automation(self, automation_id: str, user_id: str) -> bool:
        if not self._pool:
            row = self._memory["automations"].get(automation_id)
            if row and row["user_id"] == user_id:
                del self._memory["automations"][automation_id]
                return True
            return False
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM aria_agent_automations WHERE id=%s AND user_id=%s", (automation_id, user_id))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        finally:
            self._release(conn)

    def audit(self, run_id: str | None, user_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        if not self._pool:
            with self._lock:
                self._memory["audit"].append({"run_id": run_id, "user_id": user_id, "event_type": event_type,
                                              "payload": payload, "created_at": now_iso()})
            return
        conn = self._connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO aria_agent_audit(run_id,user_id,event_type,payload_json) VALUES(%s,%s,%s,%s)",
                (run_id, user_id, event_type, json.dumps(payload, ensure_ascii=False, default=str)),
            )
            conn.commit()
        finally:
            self._release(conn)
