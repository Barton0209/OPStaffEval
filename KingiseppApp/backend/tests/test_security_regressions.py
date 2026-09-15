from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from starlette.requests import Request
from sqlalchemy.orm import object_session

from app.models import GroupOfUsers, PasswordSetupCode, Territory, UserTerritoryMapping
from app.rate_limit import _rate_limit_key
from app.security import create_access_token


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_groups_require_authentication(client):
    assert client.get("/api/groups").status_code == 401
    assert client.get("/api/groups/territories").status_code == 401
    assert client.get("/api/groups/photos").status_code == 401


def test_setup_password_cannot_be_used_without_identity_proof(client, seed):
    response = client.post(
        "/api/auth/control/setup-password",
        json={"user_id": seed["master"].id, "code": "000000", "new_password": "Replacement123"},
    )
    assert response.status_code == 403


def test_setup_code_is_single_use_and_revokes_old_token(client, seed):
    target = seed["master"]
    old_headers = _auth(target)
    issued = client.post(f"/api/admin/users/{target.id}/setup-code", headers=_auth(seed["admin_op"]))
    assert issued.status_code == 200
    code = issued.json()["setup_code"]
    assert client.get("/api/field/me", headers=old_headers).status_code == 401

    payload = {"user_id": target.id, "code": code, "new_password": "Replacement123"}
    completed = client.post("/api/auth/control/setup-password", json=payload)
    assert completed.status_code == 200
    assert client.post("/api/auth/control/setup-password", json=payload).status_code == 403


def test_setup_code_rejects_wrong_and_expired_codes(client, seed):
    target = seed["foreman"]
    issued = client.post(f"/api/admin/users/{target.id}/setup-code", headers=_auth(seed["admin_op"]))
    assert issued.status_code == 200
    assert client.post("/api/auth/control/setup-password", json={
        "user_id": target.id, "code": "999999", "new_password": "Replacement123"
    }).status_code == 403
    db = object_session(target)
    setup_code = db.query(PasswordSetupCode).filter_by(user_id=target.id).one()
    assert setup_code.attempts == 1
    setup_code.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/auth/control/setup-password", json={
        "user_id": target.id, "code": issued.json()["setup_code"], "new_password": "Replacement123"
    }).status_code == 403


def test_admin_op_cannot_grant_privileged_role(client, seed):
    response = client.patch(
        f"/api/admin/users/{seed['master'].id}",
        json={"role": "management_op"},
        headers=_auth(seed["admin_op"]),
    )
    assert response.status_code == 403


def test_user_status_is_strictly_validated(client, seed):
    response = client.patch(
        f"/api/admin/users/{seed['master'].id}",
        json={"status": "arbitrary"},
        headers=_auth(seed["admin_op"]),
    )
    assert response.status_code == 422


def test_groups_enforce_territory_scope(client, seed):
    admin = seed["admin_op"]
    db = object_session(admin)
    own = Territory(organization_id=admin.organization_id, code="own", name="Участок А")
    foreign = Territory(organization_id=admin.organization_id, code="foreign", name="Участок Б")
    db.add_all([own, foreign])
    db.flush()
    db.add(UserTerritoryMapping(user_id=admin.id, territory_id=own.id, territory_name=own.name))
    db.add(GroupOfUsers(
        organization_id=admin.organization_id, territory_id=foreign.id,
        territory_name=foreign.name, group_name="foreign", permission="read",
    ))
    db.commit()

    headers = _auth(admin)
    response = client.get("/api/groups", headers=headers)
    assert response.status_code == 200
    assert response.json() == []
    assert client.get("/api/groups?territory=Участок Б", headers=headers).status_code == 403


def test_photo_folder_rejects_traversal(client, seed):
    response = client.get("/api/groups/photos?folder=..", headers=_auth(seed["admin_op"]))
    assert response.status_code == 400


def test_xff_is_ignored_from_untrusted_peer(monkeypatch):
    monkeypatch.setattr("app.rate_limit.get_settings", lambda: SimpleNamespace(trusted_proxies="10.0.0.0/8"))
    scope = {
        "type": "http", "method": "GET", "path": "/", "headers": [(b"x-forwarded-for", b"1.2.3.4")],
        "client": ("192.0.2.10", 1234), "server": ("test", 80), "scheme": "http", "query_string": b"",
    }
    assert _rate_limit_key(Request(scope)) == "192.0.2.10"


def test_xff_is_used_from_trusted_peer(monkeypatch):
    monkeypatch.setattr("app.rate_limit.get_settings", lambda: SimpleNamespace(trusted_proxies="10.0.0.0/8"))
    scope = {
        "type": "http", "method": "GET", "path": "/", "headers": [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")],
        "client": ("10.2.3.4", 1234), "server": ("test", 80), "scheme": "http", "query_string": b"",
    }
    assert _rate_limit_key(Request(scope)) == "1.2.3.4"
