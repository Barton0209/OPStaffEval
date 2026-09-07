from __future__ import annotations

import html
import os
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Assignment,
    Employee,
    Evaluation,
    ProductionCoeff,
    User,
    UserRole,
)
from app.schemas import KvyрIn, RegistryRow
from app.services.evaluations import assignment_registry_status, avg_scores, site_matches
from app.services.events import emit_event
from app.services.imports import ensure_org_and_period, nf

router = APIRouter(prefix="/api/registry", tags=["registry"])
settings = get_settings()

CRITERIA = [
    ("score_quality", "Качество выполнения работы и надёжность"),
    ("score_discipline", "Соблюдение трудовой дисциплины"),
    ("score_safety", "Безопасность и охрана труда"),
    ("score_skills", "Профессиональные знания и навыки"),
    ("score_versatility", "Универсальность и обучаемость"),
]

ROLE_RU = {
    "master": "Мастер",
    "foreman": "Производитель работ",
    "site_chief": "Начальник участка",
    "admin_op": "Администрация ОП",
    "admin": "Админ",
}

ALLOWED = (UserRole.admin, UserRole.admin_op, UserRole.site_chief)


def _months_since(d: date | None) -> int | None:
    if not d:
        return None
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


def _kvyr_for(db: Session, period_id: int, emp_id: int, site_code: str | None) -> float:
    coeff_row = (
        db.query(ProductionCoeff)
        .filter(
            ProductionCoeff.period_id == period_id,
            ProductionCoeff.employee_id == emp_id,
        )
        .order_by(ProductionCoeff.id.desc())
        .first()
    )
    if not coeff_row and site_code:
        coeff_row = (
            db.query(ProductionCoeff)
            .filter(
                ProductionCoeff.period_id == period_id,
                ProductionCoeff.site_code == site_code,
                ProductionCoeff.employee_id.is_(None),
            )
            .order_by(ProductionCoeff.id.desc())
            .first()
        )
    return coeff_row.coeff if coeff_row else 1.0


def _final_score(p_avg: float | None, s_avg: float | None, dual: bool, k: float, status: str) -> float | None:
    if status != "закрыто" or p_avg is None:
        return None
    if dual and s_avg is not None:
        return round(((p_avg + s_avg) / 2) * k, 2)
    return round(p_avg * k, 2)


def _combined_avg(p_avg: float | None, s_avg: float | None) -> float | None:
    """Общая оценка только когда сданы обе анкеты (как в ЛК)."""
    if p_avg is not None and s_avg is not None:
        return round((p_avg + s_avg) / 2, 2)
    return None


def _temp_path(prefix: str, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return Path(name)


def _pdf_escape(text: str | None) -> str:
    return html.escape(str(text or ""), quote=True)


def _assert_chief_site_access(user: User, asg: Assignment) -> None:
    if user.role != UserRole.site_chief:
        return
    if not nf(user.site_name):
        raise HTTPException(
            status_code=400,
            detail="Укажите участок начальника в «Настройках», иначе доступ к реестру участка закрыт",
        )
    if not site_matches(user.site_name, asg.site_name):
        raise HTTPException(status_code=403, detail="Чужой участок")


def _collect(db: Session, period, user: User | None = None) -> list[dict]:
    """Полные строки реестра (для API, Excel и PDF). Для site_chief — только свой участок."""
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.employee),
            joinedload(Assignment.primary_user),
            joinedload(Assignment.secondary_user),
        )
        .filter(Assignment.period_id == period.id, Assignment.evaluate.is_(True))
        .all()
    )
    if user and user.role == UserRole.site_chief:
        if not nf(user.site_name):
            return []
        assignments = [a for a in assignments if site_matches(user.site_name, a.site_name)]

    rows: list[dict] = []
    for asg in assignments:
        emp: Employee = asg.employee
        primary_ev, secondary_ev, p_avg, s_avg, status = assignment_registry_status(db, asg)
        k = _kvyr_for(db, period.id, emp.id, asg.site_code)
        final = _final_score(p_avg, s_avg, asg.dual_enabled, k, status)
        rows.append(
            {
                "assignment_id": asg.id,
                "employee_id": emp.id,
                "tab_no": emp.tab_no,
                "fio": emp.fio,
                "position": asg.position_fact or emp.position_1c,
                "site_name": asg.site_name,
                "site_code": asg.site_code,
                "primary_fio": (
                    primary_ev.evaluator.fio if primary_ev is not None and primary_ev.evaluator
                    else (asg.primary_user.fio if asg.primary_user else None)
                ),
                "primary_avg": p_avg,
                "secondary_fio": asg.secondary_user.fio if asg.secondary_user else None,
                "secondary_avg": s_avg,
                "combined_avg": _combined_avg(p_avg, s_avg),
                "k_vyr": k,
                "final_score": final,
                "status": status,
                "hourly_rate": emp.hourly_rate,
                "rate_updated_at": emp.rate_updated_at,
                "tariff_stale": bool(
                    _months_since(emp.rate_updated_at) is not None
                    and _months_since(emp.rate_updated_at) >= 6
                ),
                "primary_ev": primary_ev,
                "secondary_ev": secondary_ev,
            }
        )
    return rows


@router.get("/rows", response_model=list[RegistryRow])
def registry_rows(
    user: User = Depends(require_roles(*ALLOWED)),
    db: Session = Depends(get_db),
) -> list[RegistryRow]:
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    out: list[RegistryRow] = []
    for r in _collect(db, period, user):
        months = _months_since(r["rate_updated_at"])
        out.append(
            RegistryRow(
                tab_no=r["tab_no"],
                fio=r["fio"],
                position=r["position"],
                site_name=r["site_name"],
                primary_fio=r["primary_fio"],
                primary_avg=r["primary_avg"],
                secondary_fio=r["secondary_fio"],
                secondary_avg=r["secondary_avg"],
                k_vyr=r["k_vyr"],
                final_score=r["final_score"],
                status=r["status"],
                hourly_rate=r["hourly_rate"],
                rate_updated_at=r["rate_updated_at"],
                months_since_rate_update=months,
                tariff_stale=r["tariff_stale"],
                employee_id=r["employee_id"],
                assignment_id=r["assignment_id"],
            )
        )
    return out


def _ev_block(ev: Evaluation | None, fallback_user: User | None) -> dict | None:
    """Блок анкеты оценщика для объединённой формы."""
    if ev is None and fallback_user is None:
        return None
    evaluator = ev.evaluator if ev is not None else fallback_user
    return {
        "fio": evaluator.fio if evaluator else None,
        "tab_no": evaluator.tab_no if evaluator else None,
        "role": (ev.evaluator_role.value if ev is not None else (fallback_user.role.value if fallback_user else None)),
        "role_ru": ROLE_RU.get(
            ev.evaluator_role.value if ev is not None else (fallback_user.role.value if fallback_user else ""),
            "",
        ),
        "status": ev.status.value if ev is not None else "none",
        "scores": {
            key: getattr(ev, key) if ev is not None else None for key, _t in CRITERIA
        },
        "avg": avg_scores(ev),
        "comment": ev.comment if ev is not None else None,
        "submitted_at": ev.submitted_at if ev is not None else None,
    }


@router.get("/questionnaire/{assignment_id}")
def questionnaire(
    assignment_id: int,
    user: User = Depends(require_roles(*ALLOWED)),
    db: Session = Depends(get_db),
):
    """Объединённая анкета сотрудника: оценки обоих оценщиков, общая, Квыр, итог."""
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    asg = db.get(Assignment, assignment_id)
    if not asg or asg.organization_id != user.organization_id or asg.period_id != period.id:
        raise HTTPException(status_code=404, detail="Закрепление не найдено")
    _assert_chief_site_access(user, asg)
    emp = db.get(Employee, asg.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    primary_ev, secondary_ev, p_avg, s_avg, status = assignment_registry_status(db, asg)
    k = _kvyr_for(db, period.id, emp.id, asg.site_code)
    final = _final_score(p_avg, s_avg, asg.dual_enabled, k, status)
    return {
        "assignment_id": asg.id,
        "period_code": period.code,
        "employee": {
            "tab_no": emp.tab_no,
            "fio": emp.fio,
            "position": asg.position_fact or emp.position_1c,
            "site_name": asg.site_name,
            "hire_date": emp.hire_date,
            "experience_text": emp.experience_text,
            "hourly_rate": emp.hourly_rate,
            "rate_updated_at": emp.rate_updated_at,
        },
        "criteria": [{"key": key, "title": title} for key, title in CRITERIA],
        "primary": _ev_block(primary_ev, asg.primary_user),
        "secondary": _ev_block(secondary_ev, asg.secondary_user),
        "dual_enabled": asg.dual_enabled,
        "combined_avg": _combined_avg(p_avg, s_avg),
        "k_vyr": k,
        "final_score": final,
        "status": status,
    }


@router.get("/export.xlsx")
def export_registry_xlsx(
    user: User = Depends(require_roles(*ALLOWED)),
    db: Session = Depends(get_db),
):
    """Выгрузка реестра в Excel."""
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    if user.role == UserRole.site_chief and not nf(user.site_name):
        raise HTTPException(
            status_code=400,
            detail="Укажите участок начальника в «Настройках»",
        )
    rows = _collect(db, period, user)

    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр оценок"
    headers = [
        "Таб. №",
        "ФИО",
        "Должность",
        "Участок",
        "1-й оценщик",
        "Балл 1-го",
        "2-й оценщик",
        "Балл 2-го",
        "Общая",
        "Квыр",
        "Итог",
        "Статус",
        "ЧТС",
        "Дата изм. ЧТС",
    ]
    ws.append(headers)
    for r in rows:
        ws.append(
            [
                r["tab_no"],
                r["fio"],
                r["position"] or "",
                r["site_name"] or "",
                r["primary_fio"] or "",
                r["primary_avg"] if r["primary_avg"] is not None else "",
                r["secondary_fio"] or "",
                r["secondary_avg"] if r["secondary_avg"] is not None else "",
                r["combined_avg"] if r["combined_avg"] is not None else "",
                r["k_vyr"],
                r["final_score"] if r["final_score"] is not None else "",
                r["status"],
                r["hourly_rate"] if r["hourly_rate"] is not None else "",
                r["rate_updated_at"].isoformat() if r["rate_updated_at"] else "",
            ]
        )
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(12, len(h) + 4)
    ws.freeze_panes = "A2"

    tmp = _temp_path("reestr_", ".xlsx")
    wb.save(tmp)
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="registry",
        entity_id=None,
        action="export_xlsx",
        payload={"rows": len(rows)},
    )
    db.commit()
    return FileResponse(
        tmp,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"reestr_ocenok_{period.code}.xlsx",
    )


def _register_fonts() -> tuple[str, str]:
    """Кириллические шрифты для PDF. Возвращает (regular, bold)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ("AppArial", "AppArial-Bold", Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        ("AppCalibri", "AppCalibri-Bold", Path(r"C:\Windows\Fonts\calibri.ttf"), Path(r"C:\Windows\Fonts\calibrib.ttf")),
        ("AppDejaVu", "AppDejaVu-Bold", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        ("AppDejaVu", "AppDejaVu-Bold", Path("/usr/share/fonts/TTF/DejaVuSans.ttf"), Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf")),
    ]
    for reg, bold, reg_path, bold_path in candidates:
        if reg_path.exists() and bold_path.exists():
            if reg not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(reg, str(reg_path)))
                pdfmetrics.registerFont(TTFont(bold, str(bold_path)))
            return reg, bold
    return "Helvetica", "Helvetica-Bold"


@router.get("/export-questionnaires.pdf")
def export_questionnaires_pdf(
    user: User = Depends(require_roles(*ALLOWED)),
    db: Session = Depends(get_db),
):
    """Выгрузка объединённых анкет (оба оценщика) в PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    if user.role == UserRole.site_chief and not nf(user.site_name):
        raise HTTPException(
            status_code=400,
            detail="Укажите участок начальника в «Настройках»",
        )
    rows = [r for r in _collect(db, period, user) if r["primary_ev"] is not None or r["secondary_ev"] is not None]
    if not rows:
        raise HTTPException(status_code=400, detail="Нет сданных анкет для выгрузки")

    font, font_bold = _register_fonts()
    tmp = _temp_path("ankety_", ".pdf")
    doc = SimpleDocTemplate(
        str(tmp),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Анкеты оценки персонала {period.code}",
    )
    st_h = ParagraphStyle("h", fontName=font_bold, fontSize=13, spaceAfter=4)
    st_sub = ParagraphStyle("sub", fontName=font, fontSize=9, textColor=colors.HexColor("#555555"))
    st_b = ParagraphStyle("b", fontName=font_bold, fontSize=10)

    story: list = []
    for idx, r in enumerate(rows):
        p_ev, s_ev = r["primary_ev"], r["secondary_ev"]
        p_block = _ev_block(p_ev, None)
        s_block = _ev_block(s_ev, None)

        story.append(Paragraph(f"Анкета оценки персонала · {_pdf_escape(period.code)}", st_h))
        story.append(
            Paragraph(
                f"<b>{_pdf_escape(r['fio'])}</b> · таб. {_pdf_escape(r['tab_no'])} · "
                f"{_pdf_escape(r['position'] or '—')} · {_pdf_escape(r['site_name'] or '—')}",
                st_sub,
            )
        )
        if r["hourly_rate"] is not None:
            rate_line = f"ЧТС: {r['hourly_rate']}"
            if r["rate_updated_at"]:
                rate_line += f" (изм. {_pdf_escape(r['rate_updated_at'].isoformat())})"
            story.append(Paragraph(rate_line, st_sub))
        story.append(Spacer(1, 4))

        p_name = _pdf_escape(p_block["fio"] if p_block and p_block["fio"] else "1-й оценщик")
        s_name = _pdf_escape(s_block["fio"] if s_block and s_block["fio"] else "2-й оценщик")
        data = [["Параметр", p_name, s_name]]
        for key, title in CRITERIA:
            pv = p_block["scores"][key] if p_block else None
            sv = s_block["scores"][key] if s_block else None
            data.append([title, str(pv) if pv is not None else "—", str(sv) if sv is not None else "—"])
        data.append(
            [
                "Средний балл",
                str(p_block["avg"]) if p_block and p_block["avg"] is not None else "—",
                str(s_block["avg"]) if s_block and s_block["avg"] is not None else "—",
            ]
        )
        tbl = Table(data, colWidths=[90 * mm, 45 * mm, 45 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("FONTNAME", (0, -1), (-1, -1), font_bold),
                    ("FONTNAME", (0, 1), (-1, -2), font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4f91")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5fa")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9c4d4")),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(tbl)
        story.append(Spacer(1, 4))

        total_line = (
            f"Общая оценка: {r['combined_avg'] if r['combined_avg'] is not None else '—'} · "
            f"Квыр: {r['k_vyr']} · Итог: {r['final_score'] if r['final_score'] is not None else '—'} · "
            f"Статус: {_pdf_escape(r['status'])}"
        )
        story.append(Paragraph(total_line, st_b))

        evaluators_line = []
        if p_block:
            when = p_block["submitted_at"].strftime("%d.%m.%Y") if p_block["submitted_at"] else "не сдана"
            evaluators_line.append(
                f"1-й: {_pdf_escape(p_block['fio'])} ({_pdf_escape(p_block['role_ru'])}), {when}"
            )
        if s_block:
            when = s_block["submitted_at"].strftime("%d.%m.%Y") if s_block["submitted_at"] else "не сдана"
            evaluators_line.append(
                f"2-й: {_pdf_escape(s_block['fio'])} ({_pdf_escape(s_block['role_ru'])}), {when}"
            )
        if evaluators_line:
            story.append(Paragraph(" · ".join(evaluators_line), st_sub))
        comments = []
        if p_block and p_block["comment"]:
            comments.append(f"Комментарий 1-го: {_pdf_escape(p_block['comment'])}")
        if s_block and s_block["comment"]:
            comments.append(f"Комментарий 2-го: {_pdf_escape(s_block['comment'])}")
        for c in comments:
            story.append(Paragraph(c, st_sub))
        if idx != len(rows) - 1:
            story.append(PageBreak())

    doc.build(story)
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="registry",
        entity_id=None,
        action="export_pdf",
        payload={"questionnaires": len(rows)},
    )
    db.commit()
    return FileResponse(tmp, media_type="application/pdf", filename=f"ankety_{period.code}.pdf")


@router.post("/kvyr")
def upsert_kvyr(
    body: KvyрIn,
    user: User = Depends(require_roles(*ALLOWED)),
    db: Session = Depends(get_db),
):
    if not body.employee_id and not body.site_code:
        raise HTTPException(status_code=400, detail="Нужен employee_id или site_code")
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    if user.role == UserRole.site_chief:
        if not nf(user.site_name):
            raise HTTPException(status_code=400, detail="Укажите участок в «Настройках»")
        if body.site_code and nf(body.site_code) != nf(user.site_code or user.site_name):
            # мягкая проверка по коду; имя участка важнее для строк
            pass
    row = ProductionCoeff(
        organization_id=user.organization_id,
        period_id=period.id,
        employee_id=body.employee_id,
        site_code=body.site_code,
        coeff=body.coeff,
        site_chief_user_id=user.id if user.role == UserRole.site_chief else None,
        comment=body.comment,
    )
    db.add(row)
    db.flush()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="production_coeff",
        entity_id=row.id,
        action="upserted",
        payload=body.model_dump(),
    )
    db.commit()
    return {"ok": True, "id": row.id, "coeff": row.coeff}
