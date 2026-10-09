import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .config import settings
from .security import SecretBox, assert_public_http_url, normalize_identity, redact_secrets


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_legacy_memory_reply(role: str, content: str) -> str:
    """Deduplicate old malformed memory summaries at read time without rewriting history."""
    text = str(content or "")
    if str(role or "").lower() != "assistant":
        return text
    lines = text.splitlines()
    if not lines:
        return text
    heading = lines[0].strip()
    if heading.casefold() not in {
        "here is the most recent durable context i have:",
        "here is the durable context i have:",
    }:
        return text

    facts = []
    seen = set()
    for line in lines[1:]:
        value = line.strip()
        while value and value[0] in {"•", "-", "*"}:
            value = value[1:].strip()
        if not value:
            continue
        key = " ".join(value.casefold().split())
        if key in seen:
            continue
        seen.add(key)
        facts.append(value)
    if not facts:
        return text
    return heading + "\\n" + "\\n".join(f"• {fact}" for fact in facts)


class AgentStore:
    """Durable PostgreSQL store with a safe local JSON fallback for development."""

    def __init__(self):
        self._lock = threading.RLock()
        self._pool = None
        self._schema_ready = False
        self._box = SecretBox(settings.encryption_key, settings.app_secret)
        self._use_postgres = bool(settings.database_url)
        if settings.require_database and not self._use_postgres:
            raise RuntimeError("Supabase/Postgres database is required for this ARIA deployment.")
        self._path = Path(settings.data_dir) / "agent_store.json"
        if not self._use_postgres:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._write_local(self._empty_local())

    def _empty_local(self) -> dict[str, Any]:
        return {"memory": [], "connections": [], "runs": [], "jobs": [], "users": [], "feedback": [], "conversations": [], "messages": []}

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
            self._pool = pool.ThreadedConnectionPool(1, 10, settings.database_url)
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

                CREATE TABLE IF NOT EXISTS aria_conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_conversations_user_updated
                    ON aria_conversations(user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS aria_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES aria_conversations(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS aria_messages_conversation_created
                    ON aria_messages(conversation_id, created_at ASC, id ASC);
                CREATE INDEX IF NOT EXISTS aria_messages_user_created
                    ON aria_messages(user_id, created_at DESC);

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
        """Idempotently store durable facts; conversation turns belong in aria_messages."""
        uid = normalize_identity(user_id)
        safe_kind = str(kind or "fact").strip().lower()[:80] or "fact"
        safe_content = redact_secrets(str(content or "")).strip()
        if not safe_content:
            raise ValueError("Memory content cannot be empty.")
        safe_metadata = metadata or {}
        safe_importance = max(0.0, min(1.0, float(importance)))
        mid = str(uuid.uuid4())

        if self._use_postgres:
            lock_key = json.dumps([uid, safe_kind, " ".join(safe_content.casefold().split())], ensure_ascii=False)
            row = self._query(
                """WITH lock_guard AS MATERIALIZED (
                       SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))
                   ), existing AS MATERIALIZED (
                       SELECT m.id
                       FROM aria_memory AS m CROSS JOIN lock_guard
                       WHERE m.user_id=%s AND m.kind=%s
                         AND lower(regexp_replace(btrim(m.content), '[[:space:]]+', ' ', 'g'))=lower(regexp_replace(btrim(%s), '[[:space:]]+', ' ', 'g'))
                       ORDER BY m.created_at DESC, m.id DESC
                       LIMIT 1
                   ), inserted AS (
                       INSERT INTO aria_memory(id,user_id,kind,content,metadata,importance)
                       SELECT %s,%s,%s,%s,%s::jsonb,%s
                       WHERE NOT EXISTS (SELECT 1 FROM existing)
                       RETURNING id
                   )
                   SELECT id FROM existing
                   UNION ALL
                   SELECT id FROM inserted
                   LIMIT 1""",
                (
                    lock_key, uid, safe_kind, safe_content,
                    mid, uid, safe_kind, safe_content,
                    json.dumps(safe_metadata), safe_importance,
                ),
                fetch="one",
            )
            return row[0] if row else mid

        normalized = " ".join(safe_content.casefold().split())
        with self._lock:
            data = self._read_local()
            existing = next(
                (
                    row for row in reversed(data["memory"])
                    if row.get("user_id") == uid
                    and row.get("kind") == safe_kind
                    and " ".join(str(row.get("content", "")).casefold().split()) == normalized
                ),
                None,
            )
            if existing:
                existing["importance"] = max(float(existing.get("importance", 0.5)), safe_importance)
                existing["metadata"] = {**(existing.get("metadata") or {}), **safe_metadata}
                self._write_local(data)
                return existing["id"]
            data["memory"].append({
                "id": mid, "user_id": uid, "kind": safe_kind, "content": safe_content,
                "metadata": safe_metadata, "importance": safe_importance, "created_at": now_iso()
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
                     AND kind NOT IN ('conversation_user','conversation_assistant')
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
            rows = [
                x for x in self._read_local()["memory"]
                if x["user_id"] == uid and x.get("kind") not in {"conversation_user", "conversation_assistant"}
            ]
        scored = []
        for row in rows:
            overlap = len(qwords & set(row["content"].lower().split()))
            if overlap:
                scored.append((overlap + row.get("importance", 0.5) * 0.25, row))
        scored.sort(key=lambda x: (x[0], x[1].get("created_at", "")), reverse=True)
        return [x[1] for x in scored[:limit]]

    def recent_memory(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return unique durable facts, not the repeated transcript of ordinary chat."""
        uid = normalize_identity(user_id)
        limit = max(1, min(int(limit), 500))
        excluded = {"conversation_user", "conversation_assistant"}
        if self._use_postgres:
            rows = self._query(
                """SELECT id,kind,content,metadata,importance,created_at
                   FROM (
                       SELECT DISTINCT ON (kind, lower(btrim(content)))
                              id,kind,content,metadata,importance,created_at
                       FROM aria_memory
                       WHERE user_id=%s AND kind NOT IN ('conversation_user','conversation_assistant')
                       ORDER BY kind, lower(btrim(content)), importance DESC, created_at DESC, id DESC
                   ) AS unique_memory
                   ORDER BY created_at DESC
                   LIMIT %s""",
                (uid, limit),
            )
            return [
                {"id": r[0], "kind": r[1], "content": r[2], "metadata": r[3] or {}, "importance": r[4],
                 "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5])}
                for r in rows
            ]
        with self._lock:
            rows = [
                x for x in self._read_local()["memory"]
                if x.get("user_id") == uid and x.get("kind") not in excluded
            ]
        unique = {}
        for row in rows:
            key = (row.get("kind", ""), " ".join(str(row.get("content", "")).casefold().split()))
            if not key[1]:
                continue
            previous = unique.get(key)
            if previous is None or (row.get("importance", 0.5), row.get("created_at", "")) > (
                previous.get("importance", 0.5), previous.get("created_at", "")
            ):
                unique[key] = row
        return sorted(unique.values(), key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    def recent_messages(self, user_id: str, limit: int = 50) -> list[dict]:
        """Read chronological conversation messages without treating them as durable facts."""
        uid = normalize_identity(user_id)
        limit = max(1, min(int(limit), 500))
        if self._use_postgres:
            rows = self._query(
                """SELECT id,conversation_id,role,content,created_at
                   FROM aria_messages
                   WHERE user_id=%s
                   ORDER BY created_at DESC, id DESC
                   LIMIT %s""",
                (uid, limit),
            )
            rows = list(reversed(rows))
            return [
                {
                    "id": r[0], "conversation_id": r[1], "role": r[2],
                    "content": normalize_legacy_memory_reply(r[2], r[3]),
                    "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                }
                for r in rows
            ]
        with self._lock:
            rows = [
                dict(x) for x in self._read_local().get("messages", [])
                if x.get("user_id") == uid
            ]
        rows.sort(key=lambda x: (x.get("created_at", ""), x.get("id", "")))
        for row in rows:
            row["content"] = normalize_legacy_memory_reply(row.get("role", ""), row.get("content", ""))
        return rows[-limit:]

    def save_connection(self, user_id: str, name: str, kind: str, url: str, secret: str = "", metadata: Optional[dict] = None, connection_id: str = "") -> dict:
        url = assert_public_http_url(url)
        if len(json.dumps(metadata or {}, ensure_ascii=False)) > 20000:
            raise ValueError("Connection metadata is too large.")
        if len(secret) > 4000:
            raise ValueError("Connection secret is too large.")
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
            rows = self._query(
                "DELETE FROM aria_connections WHERE id=%s AND user_id=%s RETURNING id",
                (connection_id, uid),
            )
            return bool(rows)
        with self._lock:
            data = self._read_local()
            before = len(data["connections"])
            data["connections"] = [x for x in data["connections"] if not (x["id"] == connection_id and x["user_id"] == uid)]
            self._write_local(data)
            return len(data["connections"]) < before

    def claim_run_resume(self, user_id: str, run_id: str) -> bool:
        """Atomically claim a pending approval run so concurrent approval requests cannot resume it twice."""
        uid = normalize_identity(user_id)
        if self._use_postgres:
            rows = self._query(
                """
                UPDATE aria_runs
                SET status='resuming', updated_at=NOW()
                WHERE id=%s AND user_id=%s AND status='awaiting_approval'
                RETURNING id
                """,
                (run_id, uid),
            )
            return bool(rows)

        with self._lock:
            data = self._read_local()
            for row in data["runs"]:
                if row["id"] == run_id and row["user_id"] == uid and row.get("status") == "awaiting_approval":
                    row["status"] = "resuming"
                    row["updated_at"] = now_iso()
                    self._write_local(data)
                    return True
        return False

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

    def create_conversation(self, user_id: str, title: str = "New conversation") -> dict:
        cid = str(uuid.uuid4())
        uid = normalize_identity(user_id)
        safe_title = redact_secrets(str(title or "New conversation").strip())[:120] or "New conversation"
        if self._use_postgres:
            self._query(
                "INSERT INTO aria_conversations(id,user_id,title) VALUES(%s,%s,%s)",
                (cid, uid, safe_title),
                fetch="none",
            )
            return {"id": cid, "user_id": uid, "title": safe_title, "status": "active", "created_at": now_iso(), "updated_at": now_iso()}
        with self._lock:
            data = self._read_local()
            row = {"id": cid, "user_id": uid, "title": safe_title, "status": "active", "created_at": now_iso(), "updated_at": now_iso()}
            data["conversations"].append(row)
            self._write_local(data)
            return dict(row)

    def get_conversation(self, user_id: str, conversation_id: str, include_messages: bool = True) -> Optional[dict]:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            row = self._query(
                "SELECT id,user_id,title,status,created_at,updated_at FROM aria_conversations WHERE id=%s AND user_id=%s AND status='active'",
                (conversation_id, uid),
                fetch="one",
            )
            if not row:
                return None
            result = {
                "id": row[0], "user_id": row[1], "title": row[2], "status": row[3],
                "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                "updated_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
            }
            if include_messages:
                rows = self._query(
                    "SELECT id,role,content,created_at FROM aria_messages WHERE conversation_id=%s AND user_id=%s ORDER BY created_at ASC,id ASC LIMIT 200",
                    (conversation_id, uid),
                )
                result["messages"] = [
                    {
                        "id": r[0], "role": r[1],
                        "content": normalize_legacy_memory_reply(r[1], r[2]),
                        "created_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                    }
                    for r in rows
                ]
            return result

        with self._lock:
            row = next((x for x in self._read_local()["conversations"] if x["id"] == conversation_id and x["user_id"] == uid and x.get("status") == "active"), None)
            if not row:
                return None
            result = dict(row)
            if include_messages:
                result["messages"] = [
                    {
                        **dict(x),
                        "content": normalize_legacy_memory_reply(x.get("role", ""), x.get("content", "")),
                    }
                    for x in self._read_local()["messages"]
                    if x["conversation_id"] == conversation_id and x["user_id"] == uid
                ]
                result["messages"].sort(key=lambda x: (x.get("created_at", ""), x.get("id", "")))
            return result

    def list_conversations(self, user_id: str, limit: int = 50, search: str = "") -> list[dict]:
        uid = normalize_identity(user_id)
        limit = max(1, min(int(limit), 200))
        q = str(search or "").strip().lower()
        if self._use_postgres:
            params = [uid]
            where = "WHERE user_id=%s AND status='active'"
            if q:
                where += " AND (LOWER(title) LIKE %s OR EXISTS (SELECT 1 FROM aria_messages m WHERE m.conversation_id=aria_conversations.id AND m.content ILIKE %s))"
                params.extend([f"%{q}%", f"%{q}%"])
            params.append(limit)
            rows = self._query(
                f"""SELECT id,title,status,created_at,updated_at,
                           (SELECT COUNT(*) FROM aria_messages m WHERE m.conversation_id=aria_conversations.id) AS message_count,
                           COALESCE((SELECT m.content FROM aria_messages m WHERE m.conversation_id=aria_conversations.id ORDER BY m.created_at DESC,m.id DESC LIMIT 1),'') AS preview
                    FROM aria_conversations
                    {where}
                    ORDER BY updated_at DESC
                    LIMIT %s""",
                tuple(params),
            )
            return [
                {
                    "id": r[0], "title": r[1], "status": r[2],
                    "created_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                    "updated_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "message_count": r[5],
                    "preview": normalize_legacy_memory_reply("assistant", r[6] or ""),
                }
                for r in rows
            ]
        with self._lock:
            data = self._read_local()
            rows = [dict(x) for x in data["conversations"] if x["user_id"] == uid and x.get("status") == "active"]
            if q:
                rows = [
                    x for x in rows
                    if q in x.get("title", "").lower()
                    or any(q in m.get("content", "").lower() for m in data["messages"] if m.get("conversation_id") == x["id"])
                ]
            rows.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            out = []
            for x in rows[:limit]:
                msgs = sorted([m for m in data["messages"] if m["conversation_id"] == x["id"]], key=lambda m:(m.get("created_at",""),m.get("id","")))
                last_message = msgs[-1] if msgs else None
                out.append({
                    **x,
                    "message_count": len(msgs),
                    "preview": normalize_legacy_memory_reply(
                        last_message.get("role", "") if last_message else "",
                        last_message.get("content", "") if last_message else "",
                    ),
                })
            return out

    def add_message(self, conversation_id: str, user_id: str, role: str, content: str) -> str:
        mid = str(uuid.uuid4())
        uid = normalize_identity(user_id)
        safe_role = str(role).strip().lower()
        if safe_role not in {"user", "assistant", "system", "tool"}:
            raise ValueError("Unsupported conversation message role.")
        safe_content = redact_secrets(str(content or ""))
        if self._use_postgres:
            self._query(
                "INSERT INTO aria_messages(id,conversation_id,user_id,role,content) SELECT %s,id,%s,%s,%s FROM aria_conversations WHERE id=%s AND user_id=%s AND status='active'",
                (mid, uid, safe_role, safe_content, conversation_id, uid),
                fetch="none",
            )
            self._query(
                "UPDATE aria_conversations SET updated_at=NOW(), title=CASE WHEN title='New conversation' AND %s <> '' THEN LEFT(%s,120) ELSE title END WHERE id=%s AND user_id=%s AND status='active'",
                (safe_content[:120], safe_content[:120], conversation_id, uid),
                fetch="none",
            )
            return mid
        with self._lock:
            data = self._read_local()
            convo = next((x for x in data["conversations"] if x["id"] == conversation_id and x["user_id"] == uid and x.get("status") == "active"), None)
            if not convo:
                raise ValueError("Conversation not found for this user.")
            row = {"id": mid, "conversation_id": conversation_id, "user_id": uid, "role": safe_role, "content": safe_content, "created_at": now_iso()}
            data["messages"].append(row)
            convo["updated_at"] = row["created_at"]
            if convo.get("title") == "New conversation" and safe_content:
                convo["title"] = safe_content[:120]
            self._write_local(data)
            return mid


    def list_runs(self, user_id: str, limit: int = 100) -> list[dict]:
        uid = normalize_identity(user_id)
        limit = max(1, min(int(limit), 200))
        if self._use_postgres:
            rows = self._query(
                """
                SELECT id,provider,model,status,input_text,output_text,created_at,updated_at
                FROM aria_runs
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (uid, limit),
            )
            return [
                {
                    "id": r[0],
                    "provider": r[1],
                    "model": r[2],
                    "status": r[3],
                    "input": r[4] or "",
                    "output": r[5] or "",
                    "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                    "updated_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
                }
                for r in rows
            ]

        with self._lock:
            rows = [x for x in self._read_local()["runs"] if x["user_id"] == uid]
        rows = sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]
        return [
            {
                "id": row["id"],
                "provider": row.get("provider", ""),
                "model": row.get("model", ""),
                "status": row.get("status", ""),
                "input": row.get("input_text", ""),
                "output": row.get("output_text", ""),
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("updated_at", ""),
            }
            for row in rows
        ]

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
        """Atomically claim one due job and recover abandoned leases."""
        if self._use_postgres:
            conn = self._postgres_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE aria_jobs
                        SET status='queued', locked_at=NULL, updated_at=NOW()
                        WHERE status='running'
                          AND locked_at IS NOT NULL
                          AND locked_at < NOW() - (%s * INTERVAL '1 second')
                        """,
                        (settings.job_lease_seconds,),
                    )
                    cur.execute(
                        """
                        UPDATE aria_jobs
                        SET status='running', attempts=attempts+1, locked_at=NOW(), updated_at=NOW()
                        WHERE id = (
                            SELECT id FROM aria_jobs
                            WHERE status='queued' AND run_after <= NOW()
                            ORDER BY created_at ASC
                            FOR UPDATE SKIP LOCKED LIMIT 1
                        )
                        RETURNING id,user_id,kind,payload,attempts
                        """
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if not row:
                        return None
                    return {
                        "id": row[0],
                        "user_id": row[1],
                        "kind": row[2],
                        "payload": row[3],
                        "attempts": row[4],
                    }
            except Exception:
                conn.rollback()
                raise
            finally:
                self._release(conn)

        with self._lock:
            data = self._read_local()
            now = datetime.now(timezone.utc)
            for row in data["jobs"]:
                if row.get("status") == "running":
                    locked_at = row.get("locked_at")
                    if locked_at:
                        try:
                            locked_dt = datetime.fromisoformat(locked_at.replace("Z", "+00:00"))
                            if now - locked_dt > timedelta(seconds=settings.job_lease_seconds):
                                row["status"] = "queued"
                                row["locked_at"] = None
                        except ValueError:
                            row["status"] = "queued"
                            row["locked_at"] = None

            for row in sorted(data["jobs"], key=lambda x: x.get("created_at", "")):
                if row.get("status") != "queued":
                    continue
                run_after = row.get("run_after")
                if run_after:
                    try:
                        due = datetime.fromisoformat(run_after.replace("Z", "+00:00"))
                        if due > now:
                            continue
                    except ValueError:
                        pass
                row["status"] = "running"
                row["attempts"] = int(row.get("attempts", 0)) + 1
                row["locked_at"] = now.isoformat()
                row["updated_at"] = now.isoformat()
                self._write_local(data)
                return dict(row)
        return None

    def complete_job(self, job_id: str, result: Optional[dict] = None, error: str = "") -> None:
        status = "failed" if error else "completed"
        safe_error = redact_secrets(error or "")
        if self._use_postgres:
            self._query(
                "UPDATE aria_jobs SET status=%s,result=%s,error=%s,locked_at=NULL,updated_at=NOW() WHERE id=%s",
                (status, json.dumps(result or {}), safe_error or None, job_id),
                fetch="none",
            )
            return
        with self._lock:
            data = self._read_local()
            for row in data["jobs"]:
                if row["id"] == job_id:
                    row["status"] = status
                    row["result"] = result
                    row["error"] = safe_error or None
                    row["locked_at"] = None
                    row["updated_at"] = now_iso()
            self._write_local(data)

    def retry_job(self, job_id: str, attempts: int, error: str) -> bool:
        """Retry a failed job with exponential backoff, or fail permanently."""
        safe_error = redact_secrets(error or "")
        if attempts >= settings.job_max_attempts:
            self.complete_job(job_id, error=safe_error or "Maximum attempts reached.")
            return False

        delay = min(300, 2 ** max(0, attempts - 1))
        run_after = datetime.now(timezone.utc).timestamp() + delay

        if self._use_postgres:
            self._query(
                """
                UPDATE aria_jobs
                SET status='queued',
                    run_after=to_timestamp(%s),
                    locked_at=NULL,
                    error=%s,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (run_after, safe_error or None, job_id),
                fetch="none",
            )
            return True

        with self._lock:
            data = self._read_local()
            for row in data["jobs"]:
                if row["id"] == job_id:
                    row["status"] = "queued"
                    row["run_after"] = datetime.fromtimestamp(run_after, timezone.utc).isoformat()
                    row["locked_at"] = None
                    row["error"] = safe_error or None
                    row["updated_at"] = now_iso()
                    self._write_local(data)
                    return True
        return False

    def cancel_job(self, user_id: str, job_id: str) -> bool:
        uid = normalize_identity(user_id)
        if self._use_postgres:
            rows = self._query(
                "UPDATE aria_jobs SET status='cancelled',locked_at=NULL,updated_at=NOW() WHERE id=%s AND user_id=%s AND status IN ('queued','running') RETURNING id",
                (job_id, uid),
            )
            return bool(rows)
        with self._lock:
            data = self._read_local()
            for row in data["jobs"]:
                if row["id"] == job_id and row["user_id"] == uid and row.get("status") in {"queued", "running"}:
                    row["status"] = "cancelled"
                    row["locked_at"] = None
                    row["updated_at"] = now_iso()
                    self._write_local(data)
                    return True
        return False

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
