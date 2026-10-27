"""Synthetic SQLite adapter. Not FG application behavior or a production driver.

Auth, request dedupe, issue CAS and outbox intent share ONE SQLite transaction.
The fake provider has durable idempotency by intent key; removing that assumption
requires a different retry/reconciliation policy, not another catch/retry loop.
"""

import hashlib
import json
import sqlite3

from capcov.behaviors.registry import require


class Backend:
    def __init__(self, filename):
        self.db = sqlite3.connect(filename, isolation_level=None)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS issue(tenant TEXT, id TEXT, status TEXT,
                version INTEGER, identifier TEXT, PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS permission(tenant TEXT, principal TEXT,
                PRIMARY KEY(tenant,principal));
            CREATE TABLE IF NOT EXISTS request(tenant TEXT, principal TEXT, id TEXT,
                payload TEXT, PRIMARY KEY(tenant,principal,id));
            CREATE TABLE IF NOT EXISTS outbox(tenant TEXT, id TEXT, issue TEXT, state TEXT,
                PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS provider(tenant TEXT, id TEXT, payload TEXT,
                PRIMARY KEY(tenant,id));
        """)
        self.lose_commit = False
        self.lose_delivery = False

    def seed(self):
        self.db.execute("INSERT INTO issue VALUES ('tenant-a','i1','draft',0,'N/A')")
        self.db.execute("INSERT INTO permission VALUES ('tenant-a','alice')")

    def close(self):
        self.db.close()

    def effect(self, step):
        args = step["input"]
        operation = step["operation"]
        if operation == "load-issue":
            row = self.db.execute("SELECT version,status,identifier FROM issue WHERE tenant=? AND id=?",
                                  (args["tenant"], args["issue"])).fetchone()
            if row is None:
                return "absent", {}
            # The toy representation contract classifies N/A and generated ISSUE IDs.
            if row[2] != "N/A" and not row[2].startswith("ISSUE-"):
                return "ambiguous", {}
            return "found", {"issue.version": str(row[0]), "issue.status": row[1]}
        if operation == "authorize":
            row = self.db.execute("SELECT 1 FROM permission WHERE tenant=? AND principal=?",
                                  (args["tenant"], args["principal"])).fetchone()
            return ("allowed" if row else "denied"), {}
        if operation == "publish":
            return self.publish(args)
        if operation == "load-intent":
            row = self.db.execute("SELECT issue,state FROM outbox WHERE tenant=? AND id=?",
                                  (args["tenant"], args["intent"])).fetchone()
            if row is None:
                return "absent", {}
            if row[1] == "sent":
                return "complete", {}
            return "pending", {"intent.issue": row[0]}
        if operation == "notify":
            # Simulated external provider; this is NOT atomic with local settlement.
            row = self.db.execute("SELECT payload FROM provider WHERE tenant=? AND id=?",
                                  (args["tenant"], args["intent"])).fetchone()
            if row and row[0] != args["issue"]:
                return "failed", {}
            self.db.execute("INSERT OR IGNORE INTO provider VALUES (?,?,?)",
                            (args["tenant"], args["intent"], args["issue"]))
            if self.lose_delivery:
                self.lose_delivery = False
                return "unknown", {}
            return "ok", {}
        if operation == "settle":
            # In a real adapter this follows a verified provider acknowledgement.
            changed = self.db.execute("UPDATE outbox SET state='sent' WHERE tenant=? AND id=?",
                                      (args["tenant"], args["intent"])).rowcount
            return ("ok" if changed else "missing"), {}
        raise ValueError("unsupported effect: " + operation)

    def publish(self, args):
        tenant, principal, request = args["tenant"], args["principal"], args["request"]
        # Payload identity includes the expected version; no normalization.
        payload = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            permitted = self.db.execute("SELECT 1 FROM permission WHERE tenant=? AND principal=?",
                                        (tenant, principal)).fetchone()
            if not permitted:
                self.db.execute("ROLLBACK")
                return "denied", {}
            previous = self.db.execute("SELECT payload FROM request WHERE tenant=? AND principal=? AND id=?",
                                       (tenant, principal, request)).fetchone()
            if previous:
                self.db.execute("ROLLBACK")
                return ("ok" if previous[0] == payload else "conflict"), {}
            require(args["version"].isdigit(), "invalid expected version")
            changed = self.db.execute("""UPDATE issue SET status='published',version=version+1,identifier=?
                WHERE tenant=? AND id=? AND status='draft' AND version=?""",
                ("ISSUE-" + args["issue"], tenant, args["issue"], int(args["version"]))).rowcount
            if not changed:
                self.db.execute("ROLLBACK")
                return "conflict", {}
            # Intent identity includes principal and request, not request alone.
            intent = hashlib.sha256(json.dumps([principal, request]).encode()).hexdigest()
            self.db.execute("INSERT INTO request VALUES (?,?,?,?)", (tenant, principal, request, payload))
            self.db.execute("INSERT INTO outbox VALUES (?,?,?,'pending')", (tenant, intent, args["issue"]))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        if self.lose_commit:
            self.lose_commit = False
            return "unknown", {}
        return "ok", {}


def drive(session, backend, *, budget=32):
    for _ in range(budget):
        step = session.advance()
        if step["kind"] in {"Done", "Failed"}:
            return step["input"]
        outcome, values = backend.effect(step)
        session.resume({k: step[k] for k in ("workflow", "sequence", "program_sha256")} |
                       {"outcome": outcome, "values": values})
    raise ValueError("workflow step budget exhausted; progress is not established")
