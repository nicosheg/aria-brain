import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import settings
from .security import SecretBox, normalize_identity


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStore:
    """Durable PostgreSQL store with a safe local JSON fallback for development."""

    def __init__(self):
        self._lock = threading.RLock()
        self._pool = None
        self._schema_ready = False
        self._box = SecretBox(settings.encryption_key, settings.app_secret)
        self._use_postgres = bool(settings.database_url)
        self._path = Path(settings.data_dir) / "agent_store.json"
        if not self._use_postgres:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._write_local(self._empty_local())

    def _empty_local(self) -> dict[str, Any]:
        return {"memory": [], "connections": [], "runs": [], "jobs": [], "users": [], "feedback": []}

    def _read_local(self) -> dict[str, Any]:
        try:
            return json.loads(self._path.read_text("utf-8"))
        except Exception:
            return self._empty_local()

    def _write_local(self, data: dict[str, Any]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self._path)

    def _postgres_conn(self):
        if not self._use_postgres:
            return None
        if self._pool is None:
            import psycopg2
            from psycopg2 import pool
            self._pool = pool.SimpleConnectionPool(1, 10, settings.database_url)
        conn = self._pool.getconn()
        if not self._schema_ready:
            try:
                self._ensure_schema(conn)
                self._schema_ready = True
            except Exception:
                self._pool.putconn(conn, close=True)
                raise
        return conn

    def _release(self, conn, close: bool = False):
        if self._pool is not None and conn is not None:
            self._pool.putconn(conn, close=close)

    def _ensure_schema(self, conn) -> None:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS aria_memory (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    importance DOUBLE PRECISION NOT NULL DEFAULT 0.5,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_memory_user_created
                    ON aria_memory(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS aria_connections (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    url TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    secret_ciphertext TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_connections_user
                    ON aria_connections(user_id);

                CREATE TABLE IF NOT EXISTS aria_runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_text TEXT,
                    output_text TEXT,
                    state_ciphertext TEXT,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_runs_user_created
                    ON aria_runs(user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS aria_jobs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    run_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    locked_at TIMESTAMPTZ,
                    result JSONB,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_jobs_queue
                    ON aria_jobs(status, run_after);

                CREATE TABLE IF NOT EXISTS aria_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    display_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS aria_feedback (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    score INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        conn.commit()

    def _query(self, sql: str, params=(), fetch="all"):
        conn = self._postgres_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if fetch == "one":
                    result = cur.fetchone()
                elif fetch == "all":
                    result = cur.fetchall()
                else:
                    result = None
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release(conn)

    def ensure_user(self, user_id: str, email: str = "", display_name: str = "") -> None:
        uid = normalize_identity(user_id)
        email = normalize_identity(email)
        if self._use_postgres:
            self._query(
                """INSERT INTO aria_users(user_id,email,display_name)
                   VALUES(%s,%s,%s)
                   ON CONFLICT(user_id) DO UPDATE
                   SET email=COALESCE(NULLIF(EXCLUDED.email,''),aria_users.email),
                       display_name=COALESCE(NULLIF(EXCLUDED.display_name,''),aria_users.display_name),
                       updated_at=NOW()""",
                (uid, email, display_name),
                fetch="none",
            )
            return
        with self._lock:
            data = self._read_local()
            row = next((x for x in data["users"] if x["user_id"] == uid), None)
            if row is None:
                row = {"user_id": uid, "email": email, "display_name": display_name, "created_at": now_iso()}
                data["users"].append(row)
            else:
                if email:
                    row["email"] = email
                if display_name:
                    row["display_name"] = display_name
            row["updated_at"] = now_iso()
            self._write_local(data)

    def add_memory(self, user_id: str, kind: str, content: str, metadata: Optional[dict] = None, importance: float = 0.5) -> str:
        mid = str(uuid.uuid4())
        uid = normalize_identity(user_id)
        if self._use_postgres:
            self._query(
                "INSERT INTO aria_memory(id,user_id,kind,content,metadata,importance) VALUES(%s,%s,%s,%s,%s,%s)",
                (mid, uid, kind, content, json.dumps(metadata or {}), max(0.0, min(1.0, importance))),
                fetch="none",
            )
            return mid
        with self._lock:
            data = self._read_local()
            data["memory"].append({
                "id": mid, "user_id": uid, "kind": kind, "content": content,
                "metadata": metadata or {}, "importance": importance, "created_at": now_iso()
            })
            if len(data["memory"]) > 50000:
                data["memory"] = data["memory"][-50000:]
            self._write_local(data)
        return mid

    def search_memory(self, user_id: str, query: str, limit: int = 12) -> list[dict]:
        uid = normalize_identity(user_id)
        qwords = {x for x in query.lower().replace(",", " ").split() if len(x) > 1}
        if self._use_postgres:
            rows = self._query(
                """SELECT id,kind,content,metadata,importance,created_at
                   FROM aria_memory
                   WHERE user_id=%s
                     AND (content ILIKE %s OR kind ILIKE %s)
                   ORDER BY importance DESC,created_at DESC
                   LIMIT %s""",
                (uid, f"%{query}%", f"%{query}%", limit * 4),
            )
            scored = []
            for row in rows:
                content = row[2] or ""
                overlap = len(qwords & set(content.lower().split()))
                scored.append((overlap + float(row[4]) * 0.25, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [
                {"id": r[0], "kind": r[1], "content": r[2], "metadata": r[3] or {}, "importance": r[4],
                 "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5])}
                for _, r in scored[:limit]
            ]
        with self._lock:
            rows = [x for x in self._read_local()["memory"] if x["user_id"] == uid]
        scored = []
        for row in rows:
            overlap = len(qwords & set(row["content"].lower().split()))
            if overlap:
                scored.append((overlap + row.get("importance", 0.5) * 0.25, row))
        scored.sort(key=lambda x: (x[0], x[1].get("created_at", "")), reverse=True)
        return [x[1] for x in scored[:limit]]

    def recent_memory(self, user_id: str, limit: int = 20) -> list[dict]:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            rows = self._query(
                "SELECT id,kind,content,metadata,importance,created_at FROM aria_memory WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (uid, limit),
            )
            return [
                {"id": r[0], "kind": r[1], "content": r[2], "metadata": r[3] or {}, "importance": r[4],
                 "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5])}
                for r in rows
            ]
        with self._lock:
            rows = [x for x in self._read_local()["memory"] if x["user_id"] == uid]
        return sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    def save_connection(self, user_id: str, name: str, kind: str, url: str, secret: str = "", metadata: Optional[dict] = None, connection_id: str = "") -> dict:
        cid = connection_id or str(uuid.uuid4())
        uid = normalize_identity(user_id)
        cipher = self._box.encrypt(secret) if secret else None
        payload = {"id": cid, "user_id": uid, "name": name, "kind": kind, "url": url, "metadata": metadata or {}}
        if self._use_postgres:
            self._query(
                """INSERT INTO aria_connections(id,user_id,name,kind,url,metadata,secret_ciphertext)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(id) DO UPDATE SET name=EXCLUDED.name,kind=EXCLUDED.kind,url=EXCLUDED.url,
                   metadata=EXCLUDED.metadata,secret_ciphertext=EXCLUDED.secret_ciphertext,updated_at=NOW()""",
                (cid, uid, name, kind, url, json.dumps(metadata or {}), cipher), fetch="none",
            )
        else:
            with self._lock:
                data = self._read_local()
                data["connections"] = [x for x in data["connections"] if x["id"] != cid]
                payload["secret_ciphertext"] = cipher
                payload["created_at"] = now_iso()
                payload["updated_at"] = now_iso()
                data["connections"].append(payload)
                self._write_local(data)
        return {"id": cid, "user_id": uid, "name": name, "kind": kind, "url": url, "metadata": metadata or {}}

    def list_connections(self, user_id: str) -> list[dict]:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            rows = self._query(
                "SELECT id,name,kind,url,metadata,created_at,updated_at FROM aria_connections WHERE user_id=%s ORDER BY created_at DESC",
                (uid,),
            )
            return [{"id":r[0],"name":r[1],"kind":r[2],"url":r[3],"metadata":r[4] or {},"created_at":str(r[5]),"updated_at":str(r[6])} for r in rows]
        with self._lock:
            return [{k:v for k,v in row.items() if k != "secret_ciphertext"} for row in self._read_local()["connections"] if row["user_id"] == uid]

    def get_connection(self, user_id: str, connection_id: str) -> Optional[dict]:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            row = self._query(
                "SELECT id,name,kind,url,metadata,secret_ciphertext FROM aria_connections WHERE id=%s AND user_id=%s",
                (connection_id, uid), fetch="one",
            )
            if not row:
                return None
            return {"id":row[0],"name":row[1],"kind":row[2],"url":row[3],"metadata":row[4] or {},
                    "secret":self._box.decrypt(row[5]) if row[5] else ""}
        with self._lock:
            row = next((x for x in self._read_local()["connections"] if x["id"] == connection_id and x["user_id"] == uid), None)
        if not row:
            return None
        return {**row, "secret":self._box.decrypt(row["secret_ciphertext"]) if row.get("secret_ciphertext") else ""}

    def delete_connection(self, user_id: str, connection_id: str) -> bool:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            self._query("DELETE FROM aria_connections WHERE id=%s AND user_id=%s", (connection_id, uid), fetch="none")
            return True
        with self._lock:
            data = self._read_local()
            before = len(data["connections"])
            data["connections"] = [x for x in data["connections"] if not (x["id"] == connection_id and x["user_id"] == uid)]
            self._write_local(data)
            return len(data["connections"]) < before

    def save_run(self, run_id: str, user_id: str, provider: str, model: str, status: str, input_text: str = "", output_text: str = "", state: str = "", metadata: Optional[dict] = None):
        uid = normalize_identity(user_id)
        cipher = self._box.encrypt(state) if state else None
        meta = metadata or {}
        if self._use_postgres:
            self._query(
                """INSERT INTO aria_runs(id,user_id,provider,model,status,input_text,output_text,state_ciphertext,metadata)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(id) DO UPDATE SET status=EXCLUDED.status,output_text=EXCLUDED.output_text,
                   state_ciphertext=EXCLUDED.state_ciphertext,metadata=EXCLUDED.metadata,updated_at=NOW()""",
                (run_id,uid,provider,model,status,input_text,output_text,cipher,json.dumps(meta)), fetch="none",
            )
        else:
            with self._lock:
                data = self._read_local()
                row = {"id":run_id,"user_id":uid,"provider":provider,"model":model,"status":status,"input_text":input_text,
                       "output_text":output_text,"state_ciphertext":cipher,"metadata":meta,"created_at":now_iso(),"updated_at":now_iso()}
                existing = any(x["id"] == run_id for x in data["runs"])
                data["runs"] = [row if x["id"] == run_id else x for x in data["runs"]] if existing else data["runs"] + [row]
                self._write_local(data)

    def get_run(self, user_id: str, run_id: str) -> Optional[dict]:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            row = self._query(
                "SELECT id,user_id,provider,model,status,input_text,output_text,state_ciphertext,metadata FROM aria_runs WHERE id=%s AND user_id=%s",
                (run_id,uid), fetch="one",
            )
            if not row:
                return None
            return {"id":row[0],"user_id":row[1],"provider":row[2],"model":row[3],"status":row[4],"input_text":row[5],"output_text":row[6],
                    "state":self._box.decrypt(row[7]) if row[7] else "", "metadata":row[8] or {}}
        with self._lock:
            row = next((x for x in self._read_local()["runs"] if x["id"] == run_id and x["user_id"] == uid), None)
        if not row:
            return None
        return {**row, "state":self._box.decrypt(row["state_ciphertext"]) if row.get("state_ciphertext") else ""}

    def enqueue_job(self, user_id: str, kind: str, payload: dict, run_after: Optional[str] = None) -> str:
        jid = str(uuid.uuid4())
        uid = normalize_identity(user_id)
        if self._use_postgres:
            self._query(
                "INSERT INTO aria_jobs(id,user_id,kind,payload,run_after) VALUES(%s,%s,%s,%s,COALESCE(%s::timestamptz,NOW()))",
                (jid,uid,kind,json.dumps(payload),run_after), fetch="none",
            )
            return jid
        with self._lock:
            data=self._read_local()
            data["jobs"].append({"id":jid,"user_id":uid,"kind":kind,"payload":payload,"status":"queued","attempts":0,
                                 "run_after":run_after or now_iso(),"created_at":now_iso(),"updated_at":now_iso(),"result":None,"error":None})
            self._write_local(data)
        return jid

    def claim_job(self) -> Optional[dict]:
        if self._use_postgres:
            conn = self._postgres_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE aria_jobs
                        SET status='running', attempts=attempts+1, locked_at=NOW(), updated_at=NOW()
                        WHERE id = (
                            SELECT id FROM aria_jobs
                            WHERE status='queued' AND run_after <= NOW()
                            ORDER BY created_at ASC
                            FOR UPDATE SKIP LOCKED LIMIT 1
                        )
                        RETURNING id,user_id,kind,payload,attempts
                    """)
                    row=cur.fetchone()
                    conn.commit()
                    if not row:
                        return None
                    return {"id":row[0],"user_id":row[1],"kind":row[2],"payload":row[3],"attempts":row[4]}
            finally:
                self._release(conn)
        with self._lock:
            data=self._read_local()
            for row in sorted(data["jobs"], key=lambda x:x.get("created_at","")):
                if row["status"]=="queued":
                    row["status"]="running"; row["attempts"]+=1; row["updated_at"]=now_iso()
                    self._write_local(data)
                    return dict(row)
        return None

    def complete_job(self, job_id: str, result: Optional[dict]=None, error: str="") -> None:
        status="failed" if error else "completed"
        if self._use_postgres:
            self._query("UPDATE aria_jobs SET status=%s,result=%s,error=%s,updated_at=NOW() WHERE id=%s",
                        (status,json.dumps(result or {}),error or None,job_id), fetch="none")
            return
        with self._lock:
            data=self._read_local()
            for row in data["jobs"]:
                if row["id"]==job_id:
                    row["status"]=status; row["result"]=result; row["error"]=error or None; row["updated_at"]=now_iso()
            self._write_local(data)

    def list_jobs(self, user_id: str, limit: int=50) -> list[dict]:
        uid=normalize_identity(user_id)
        if self._use_postgres:
            rows=self._query("SELECT id,kind,payload,status,attempts,result,error,created_at,updated_at FROM aria_jobs WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",(uid,limit))
            return [{"id":r[0],"kind":r[1],"payload":r[2],"status":r[3],"attempts":r[4],"result":r[5],"error":r[6],"created_at":str(r[7]),"updated_at":str(r[8])} for r in rows]
        with self._lock:
            rows=[x for x in self._read_local()["jobs"] if x["user_id"]==uid]
        return sorted(rows,key=lambda x:x.get("created_at",""),reverse=True)[:limit]

    def add_feedback(self,user_id:str,score:int)->str:
        fid=str(uuid.uuid4()); uid=normalize_identity(user_id)
        if self._use_postgres:
            self._query("INSERT INTO aria_feedback(id,user_id,score) VALUES(%s,%s,%s)",(fid,uid,score),fetch="none")
        else:
            with self._lock:
                data=self._read_local(); data["feedback"].append({"id":fid,"user_id":uid,"score":score,"created_at":now_iso()}); self._write_local(data)
        return fid


store = AgentStore()
