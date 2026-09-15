"""Тесты ЧТС и тарифной сетки: срок давности, правка ставки, импорт сетки."""
from __future__ import annotations

import io
from datetime import date, timedelta

from openpyxl import Workbook

from app.security import create_access_token
from app.services.tariff import citizenship_group, is_rate_expired


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


# ---------- Единичные проверки логики ----------

def test_is_rate_expired_threshold():
    today = date(2026, 9, 9)
    # ровно 179 дней — ещё не просрочено; 180 — просрочено.
    assert is_rate_expired(today - timedelta(days=179), today=today) is False
    assert is_rate_expired(today - timedelta(days=180), today=today) is True
    assert is_rate_expired(today - timedelta(days=400), today=today) is True
    assert is_rate_expired(None, today=today) is False


def test_citizenship_group_mapping():
    assert citizenship_group("УЗБЕКИСТАН") == "Туркмения, Узбекистан, Таджикистан"
    assert citizenship_group("РОССИЯ") == "РФ, Белоруссия"
    assert citizenship_group("БЕЛАРУСЬ") == "РФ, Белоруссия"
    assert citizenship_group("КАЗАХСТАН") == "Казахстан, Киргизия"
    assert citizenship_group("КИРГИЗИЯ") == "Казахстан, Киргизия"
    assert citizenship_group("ИНДИЯ") == "Индия"
    assert citizenship_group(None) is None


# ---------- API ----------

def test_patch_employee_rate_sets_last_raised(client, seed):
    emp_id = seed["emp1"].id
    r = client.patch(
        f"/api/admin/employees/{emp_id}",
        headers=_h(seed["admin_op"]),
        json={"hourly_rate": 450.5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["hourly_rate"] == 450.5
    # Дата последнего поднятия проставлена автоматически (сегодня).
    assert body["rate_last_raised"] == date.today().isoformat()
    assert body["is_rate_expired"] is False


def test_patch_employee_requires_auth(client, seed):
    emp_id = seed["emp1"].id
    r = client.patch(
        f"/api/admin/employees/{emp_id}",
        headers=_h(seed["master"]),
        json={"hourly_rate": 500},
    )
    assert r.status_code == 403  # мастер не админ


def test_tariff_grid_import_role_and_upsert(client, db_engine, seed):
    # Доступ только ADMIN-OP.
    r = client.post(
        "/api/admin/import/tariff-grid",
        headers=_h(seed["master"]),
        files={"grid_file": ("grid.xlsx", io.BytesIO(b"x"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 403

    wb = Workbook()
    ws = wb.active
    ws.append(["Гражданство", "Валюта", "Участок", "Профессия", "Разряды", "4 Регион мин", "4 Регион макс"])
    ws.append(["Индия", "$/час", "Участок А", "Бетонщик", "", "2.5", "3.8"])
    ws.append(["Индия", "$/час", "Участок Б", "Бетонщик", "", "2.7", "4.0"])
    buf = io.BytesIO()
    wb.save(buf)

    r = client.post(
        "/api/admin/import/tariff-grid",
        headers=_h(seed["admin_op"]),
        files={"grid_file": ("grid.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200
    res = r.json()[0]
    assert res["added"] == 1  # обе строки «Бетонщик/Индия» свернулись в одну (upsert)

    rows = client.get("/api/admin/tariff-grid", headers=_h(seed["admin_op"])).json()
    beton = [x for x in rows if x["position"] == "Бетонщик" and x["citizenship"] == "Индия"]
    assert len(beton) == 1
    assert beton[0]["min_rate"] == 2.5  # минимум из ненулевых
    assert beton[0]["max_rate"] == 4.0  # максимум