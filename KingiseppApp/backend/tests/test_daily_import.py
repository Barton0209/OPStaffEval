"""Тесты упрощённого ежедневного импорта (Табельный/ФИО/Должность/Участок/Прораб)."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy.orm import sessionmaker

from app.models import Assignment, Employee
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def _make_xlsx(rows: list[list]):
    wb = Workbook()
    ws = wb.active
    ws.append(["Табельный номер", "ФИО", "Должность", "Участок", "Прораб"])
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_daily_assignees_import_updates_and_creates(client, db_engine, seed):
    # Новый сотрудник, которого ещё нет в закреплениях.
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    emp3 = Employee(
        organization_id=seed["org"].id,
        tab_no="E-3",
        fio="Старый ФИО",
        position_1c="",
        territory="Участок А",
    )
    db.add(emp3)
    db.commit()
    emp3_id = emp3.id
    db.close()

    xlsx = _make_xlsx(
        [
            ["E-1", "Иванов Иван Петрович", "Бетонщик 4 разряда", "Участок А", "M-1001"],
            ["E-2", "Петров Пётр", "Арматурщик", "Участок Б", "F-1002"],
            ["E-3", "Сидоров Сидр", "Сварщик", "Участок А", "M-1001"],
        ]
    )

    r = client.post(
        "/api/admin/import/daily-assignees",
        headers=_h(seed["admin_op"]),
        files={"daily_file": ("daily.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["errors"] == []
    assert body["added"] == 1  # E-3 получил новое закрепление
    assert body["updated"] >= 2  # E-1, E-2 обновлены

    # E-1: обновлено ФИО/должность и назначен прораб M-1001 (уже был мастером — осталось).
    db2 = Session()
    emp1 = db2.get(Employee, seed["emp1"].id)
    assert emp1.fio == "Иванов Иван Петрович"
    assert emp1.position_1c == "Бетонщик 4 разряда"
    asg1 = (
        db2.query(Assignment)
        .filter(Assignment.period_id == seed["period"].id, Assignment.employee_id == seed["emp1"].id)
        .first()
    )
    assert asg1 is not None
    assert asg1.evaluate is True

    # E-3: создано закрепление с primary = мастер M-1001.
    asg3 = (
        db2.query(Assignment)
        .filter(Assignment.period_id == seed["period"].id, Assignment.employee_id == emp3_id)
        .first()
    )
    assert asg3 is not None
    assert asg3.primary_user_id == seed["master"].id
    db2.close()


def test_daily_assignees_import_unknown_employee(client, db_engine, seed):
    xlsx = _make_xlsx([["E-999", "Неизвестный", "Должность", "Участок А", "M-1001"]])
    r = client.post(
        "/api/admin/import/daily-assignees",
        headers=_h(seed["admin_op"]),
        files={"daily_file": ("daily.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["skipped"] == 1
    assert any("не найден" in e for e in body["errors"])


def test_daily_assignees_rbac(client, seed):
    """Мастер не может вызывать админ-импорт."""
    xlsx = _make_xlsx([["E-1", "Иванов Иван", "", "Участок А", "M-1001"]])
    r = client.post(
        "/api/admin/import/daily-assignees",
        headers=_h(seed["master"]),
        files={"daily_file": ("daily.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 403