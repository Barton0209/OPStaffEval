"""API для выгрузок: полный Excel сотрудников, пакет PDF анкет."""

import io
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Assignment,
    Employee,
    Evaluation,
    EvaluationPeriod,
    EvaluationStatus,
    Organization,
    User,
    UserRole,
)
from app.services.imports import ensure_org_by_id, nf

router = APIRouter(prefix="/api/employees", tags=["employees_export"])
settings = get_settings()

ALLOWED_EXPORT_ROLES = {
    UserRole.management_op,
    UserRole.admin,
    UserRole.admin_op,
    UserRole.cok_okit,
}


def _avg(ev) -> float | None:
    scores = [ev.score_quality, ev.score_discipline, ev.score_safety,
              ev.score_skills, ev.score_versatility]
    valid = [s for s in scores if s is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


# ==================== Полный Excel сотрудников ====================


@router.get("/export.xlsx")
def export_all_employees(
    position: str | None = None,
    territory: str | None = None,
    department: str | None = None,
    user: User = Depends(require_roles(*ALLOWED_EXPORT_ROLES)),
    db: Session = Depends(get_db),
):
    """Полная выгрузка всех сотрудников по разрешённой области."""
    org, _ = ensure_org_by_id(db, user.organization_id)

    query = (
        db.query(Employee)
        .filter(Employee.organization_id == org.id)
    )

    if position:
        query = query.filter(Employee.position_1c.ilike(f"%{position}%"))
    if territory:
        query = query.filter(Employee.territory.ilike(f"%{territory}%"))
    if department:
        query = query.filter(Employee.department_1c.ilike(f"%{department}%"))

    employees = query.order_by(Employee.fio).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Все сотрудники"

    headers = [
        "Табельный", "ФИО", "Организация", "Подразделение", "Должность",
        "Разряд", "Территория", "Гражданство", "Дата приёма",
        "Состояние", "Испытательный срок", "ЧТС", "Дата повышения ЧТС",
    ]
    ws.append(headers)

    today = date.today()
    for emp in employees:
        probation_active = False
        if emp.probation_end_date and emp.probation_end_date >= today:
            probation_active = True

        ws.append([
            emp.tab_no,
            emp.fio,
            emp.territory or "",
            emp.department_1c or "",
            emp.position_1c or "",
            emp.category or "",
            emp.territory or "",
            emp.citizenship or "",
            emp.hire_date.isoformat() if emp.hire_date else "",
            emp.state or "",
            "Да" if probation_active else "Нет",
            emp.hourly_rate or "",
            emp.rate_last_raised.isoformat() if emp.rate_last_raised else "",
        ])

    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="employees_all_")
    import os
    os.close(fd)
    wb.save(path)

    return FileResponse(
        path,
        filename=f"Все_сотрудники_{date.today()}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ==================== Пакет PDF анкет (настоящие PDF через reportlab) ====================


def _register_pdf_fonts():
    """Регистрация кириллических шрифтов для PDF."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from pathlib import Path

    candidates = [
        ("AppArial", "AppArial-Bold", Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        ("AppCalibri", "AppCalibri-Bold", Path(r"C:\Windows\Fonts\calibri.ttf"), Path(r"C:\Windows\Fonts\calibrib.ttf")),
        ("AppDejaVu", "AppDejaVu-Bold", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for reg, bold, reg_path, bold_path in candidates:
        if reg_path.exists() and bold_path.exists():
            if reg not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(reg, str(reg_path)))
                pdfmetrics.registerFont(TTFont(bold, str(bold_path)))
            return reg, bold
    return "Helvetica", "Helvetica-Bold"


def _build_anquet_pdf(emp: Employee, assignments: list, evaluations: list) -> bytes:
    """Создаёт PDF-анкету для сотрудника."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak

    font, font_bold = _register_pdf_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Анкета: {emp.fio}",
    )

    st_title = ParagraphStyle("title", fontName=font_bold, fontSize=16, spaceAfter=6, alignment=1)
    st_h1 = ParagraphStyle("h1", fontName=font_bold, fontSize=12, spaceBefore=10, spaceAfter=4)
    st_h2 = ParagraphStyle("h2", fontName=font_bold, fontSize=10, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#2563eb"))
    st_body = ParagraphStyle("body", fontName=font, fontSize=9, spaceAfter=2)
    st_bold = ParagraphStyle("bold", fontName=font_bold, fontSize=9, spaceAfter=2)

    story = []

    # Заголовок
    story.append(Paragraph("АНКЕТА ОЦЕНКИ ПЕРСОНАЛА", st_title))
    story.append(Spacer(1, 4 * mm))

    # Основная информация
    story.append(Paragraph("Основные данные", st_h1))
    info_data = [
        ["Табельный номер:", emp.tab_no],
        ["ФИО:", emp.fio],
        ["Должность:", emp.position_1c or "—"],
        ["Подразделение:", emp.department_1c or "—"],
        ["Разряд/категория:", emp.category or "—"],
        ["Территория/площадка:", emp.territory or "—"],
        ["Гражданство:", emp.citizenship or "—"],
        ["Дата приёма:", emp.hire_date.isoformat() if emp.hire_date else "—"],
        ["Состояние:", emp.state or "—"],
    ]
    info_table = Table([[Paragraph(str(v), st_body) for v in row] for row in info_data], colWidths=[45 * mm, None])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), font_bold),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(info_table)

    # ЧТС
    if emp.hourly_rate:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"ЧТС: <b>{emp.hourly_rate}</b>  |  Гражданство: <b>{emp.citizenship or '—'}</b>", st_body))

    # Оценки по назначениям
    for asg in assignments:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(f"Участок: {asg.site_name or '—'}", st_h2))

        # Ищем оценки для этого назначения
        asg_evals = [e for e in evaluations if e.assignment_id == asg.id]
        if not asg_evals:
            story.append(Paragraph("<i>Оценок пока нет</i>", st_body))
            continue

        for ev in asg_evals:
            evaluator_role = ev.evaluator_role.value if ev.evaluator_role else "—"
            avg = _avg(ev)

            scores = [
                ("Качество работы", ev.score_quality),
                ("Трудовая дисциплина", ev.score_discipline),
                ("Охрана труда", ev.score_safety),
                ("Проф. навыки", ev.score_skills),
                ("Универсальность", ev.score_versatility),
            ]
            score_data = [[Paragraph(s[0], st_body), Paragraph(str(s[1]) if s[1] is not None else "—", st_body)] for s in scores]
            score_data.append([Paragraph("<b>Средний балл</b>", st_bold), Paragraph(f"<b>{avg}</b>", st_bold)])

            score_table = Table(score_data, colWidths=[60 * mm, 25 * mm])
            score_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0e7ff")),
                ("FONTNAME", (0, -1), (-1, -1), font_bold),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(score_table)

            if ev.comment:
                story.append(Spacer(1, 2 * mm))
                story.append(Paragraph(f"Комментарий: {ev.comment}", st_body))

    # Подпись
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"Дата формирования: {date.today().strftime('%d.%m.%Y')}", ParagraphStyle("footer", fontName=font, fontSize=8, textColor=colors.grey, alignment=2)))

    doc.build(story)
    return buf.getvalue()


@router.post("/export-pdf")
def export_pdf_batch(
    employee_ids: list[int],
    user: User = Depends(require_roles(*ALLOWED_EXPORT_ROLES)),
    db: Session = Depends(get_db),
):
    """Создать ZIP с настоящими PDF анкетами для выбранных сотрудников."""
    if not employee_ids:
        raise HTTPException(status_code=400, detail="Не выбраны сотрудники")

    org, _ = ensure_org_by_id(db, user.organization_id)

    # Получаем сотрудников с назначениями и оценками
    employees = (
        db.query(Employee)
        .filter(
            Employee.id.in_(employee_ids),
            Employee.organization_id == org.id,
        )
        .all()
    )

    if len(employees) > 100:
        raise HTTPException(status_code=400, detail="Максимум 100 анкет за раз")

    # Загружаем назначения и оценки
    emp_ids = [e.id for e in employees]
    assignments = (
        db.query(Assignment)
        .filter(Assignment.employee_id.in_(emp_ids))
        .all()
    )
    evaluations = (
        db.query(Evaluation)
        .filter(Evaluation.assignment_id.in_([a.id for a in assignments]))
        .order_by(Evaluation.id)
        .all()
    )

    # Создаём ZIP с PDF
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest
        manifest_lines = [
            f"Период: {date.today()}",
            f"Кол-во анкет: {len(employees)}",
            "-" * 50,
        ]
        for emp in employees:
            manifest_lines.append(f"{emp.tab_no} — {emp.fio}")
        zf.writestr("manifest.txt", "\n".join(manifest_lines))

        # PDF-анкеты
        for emp in employees:
            emp_assigns = [a for a in assignments if a.employee_id == emp.id]
            emp_evals = [e for e in evaluations if e.assignment_id in [a.id for a in emp_assigns]]
            pdf_bytes = _build_anquet_pdf(emp, emp_assigns, emp_evals)
            safe_name = f"{emp.tab_no}_{emp.fio[:30].replace('/', '_')}.pdf"
            zf.writestr(safe_name, pdf_bytes)

    zip_buffer.seek(0)

    return StreamingResponse(
        iter([zip_buffer.read()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="Анкеты_{date.today()}.zip"'
        },
    )


# ==================== Импорт необходимых модулей ====================
import tempfile
import os
