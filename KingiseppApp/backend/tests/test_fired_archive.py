"""Тесты идемпотентного архива уволенных в import_base_v2 (В4)."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy.orm import sessionmaker

from app.models import Assignment, Employee, Evaluation, FiredEmployee
from app.services.imports import import_base_v2


def _make_base_xlsx(path: Path, rows: list[list]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Табельный", "ФИО", "C", "D", "Организация", "Подразделение", "Должность",
               "Разряд", "Состояние", "J", "Дата приема", "Дата увольнения",
               "Гражданство", "Территория"])
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


FIRED_ROW = ["E-1", "Иванов Иван", "", "", "ОП", "Отдел", "Бетонщик", "4",
             "Уволен", "", "2026-01-10", "2026-06-01", "РФ", "ОП Кингисепп"]


def _import(db, path, org):
    return import_base_v2(db, path, org, actor_id=None)


def test_fired_archive_is_idempotent(client, db_engine, seed, tmp_path):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    xlsx = _make_base_xlsx(tmp_path / "base.xlsx", [FIRED_ROW])

    res1 = _import(db, xlsx, seed["org"])
    assert res1.errors == []

    fe_count = db.query(FiredEmployee).filter(FiredEmployee.tab_no == "E-1").count()
    assert fe_count == 1

    emp = db.get(Employee, seed["emp1"].id)
    assert emp.state == "Уволен"

    # Назначение открытого периода снято с оценивания, но не удалено.
    asg = db.get(Assignment, seed["asg1"].id)
    assert asg is not None
    assert asg.evaluate is False

    # Историческая оценка сохранена.
    ev = db.query(Evaluation).filter(Evaluation.assignment_id == seed["asg1"].id).first()
    assert ev is not None

    # Повторный импорт того же файла — без дублей.
    res2 = _import(db, xlsx, seed["org"])
    assert res2.errors == []
    fe_count2 = db.query(FiredEmployee).filter(FiredEmployee.tab_no == "E-1").count()
    assert fe_count2 == 1
    db.close()


def test_fired_archive_restores_on_rehire(client, db_engine, seed, tmp_path):
    """Сотрудник без даты увольнения обновляется штатно (архив не трогаем)."""
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    fired = _make_base_xlsx(tmp_path / "fired.xlsx", [FIRED_ROW])
    _import(db, fired, seed["org"])

    active_row = FIRED_ROW.copy()
    active_row[8] = "Работает"   # I — состояние
    active_row[11] = ""          # L — дата увольнения пуста
    rehired = _make_base_xlsx(tmp_path / "rehired.xlsx", [active_row])
    _import(db, rehired, seed["org"])

    emp = db.get(Employee, seed["emp1"].id)
    assert emp.state == "Работает"
    # Запись архива при этом сохраняется (история не теряется).
    assert db.query(FiredEmployee).filter(FiredEmployee.tab_no == "E-1").count() == 1
    db.close()
