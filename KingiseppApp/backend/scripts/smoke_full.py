"""End-to-end smoke against running API."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw
        return e.code, payload


def main() -> int:
    admin_password = os.environ.get("SMOKE_ADMIN_PASSWORD")
    master_tab_no = os.environ.get("SMOKE_MASTER_TAB_NO")
    master_password = os.environ.get("SMOKE_MASTER_PASSWORD")
    if not admin_password:
        raise RuntimeError("SMOKE_ADMIN_PASSWORD must be set")
    code, health = call("GET", "/api/health")
    assert code == 200, health
    print("health:", health)

    code, admin = call("POST", "/api/field/auth/login", body={"tab_no": "ADMIN-OP", "password": admin_password})
    assert code == 200, admin
    at = admin["access_token"]
    code, dash = call("GET", "/api/admin/dashboard", token=at)
    assert code == 200, dash
    print("dashboard:", dash)

    code, rows = call("GET", "/api/registry/rows", token=at)
    assert code == 200, rows
    print("registry rows:", len(rows))

    if not master_tab_no or not master_password:
        print("master smoke skipped: set SMOKE_MASTER_TAB_NO and SMOKE_MASTER_PASSWORD")
        return 0
    code, master = call("POST", "/api/field/auth/login", body={"tab_no": master_tab_no, "password": master_password})
    if code != 200:
        print("master login failed:", code, master)
    else:
        mt = master["access_token"]
        code, items = call("GET", "/api/field/assignments", token=mt)
        assert code == 200, items
        print("master assignments:", len(items))
        if items and not items[0].get("is_urgent") and items[0]["assignment_id"]:
            first = items[0]
            body = {
                "score_quality": 4,
                "score_discipline": 4,
                "score_safety": 4,
                "score_skills": 4,
                "score_versatility": 4,
                "comment": "smoke full",
                "assignment_version": first["assignment_version"],
                "client_mutation_id": "smoke-full-1",
            }
            code, ev = call(
                "POST",
                f"/api/field/assignments/{first['assignment_id']}/evaluation?submit=true",
                token=mt,
                body=body,
            )
            print("submit:", code, ev)
        code, ticket = call(
            "POST",
            "/api/field/tickets",
            token=mt,
            body={"message": "smoke ticket: проверка списка"},
        )
        print("ticket:", code, ticket)

    if rows and rows[0].get("employee_id"):
        code, kv = call(
            "POST",
            "/api/registry/kvyr",
            token=at,
            body={"employee_id": rows[0]["employee_id"], "coeff": 1.05, "comment": "smoke"},
        )
        print("kvyr:", code, kv)

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
