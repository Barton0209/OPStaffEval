# -*- coding: utf-8 -*-
"""Convert current 03_Карнет into new template format."""
from pathlib import Path
from collections import Counter
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import re

BASE = Path(r"C:\My_Project\System_Ocenok\Files")
OUT = BASE / "03_Карнет.xlsx"
REPORT = Path(r"C:\My_Project\System_Ocenok\docs\Карнет_конвертация_отчёт.md")
BACKUP = BASE / "OLD" / "03_Карнет_до_конвертации.xlsx"

SITE_MAP = {
    "Участок по монтажу теплоизоляции": ("ТИ", "Участок по монтажу теплоизоляции"),
    "Участок по антикоррозийной защите": ("АКЗ", "Участок по антикоррозийной защите"),
    "Участок по монтажу строительных лесов": ("ЛС", "Участок по монтажу строительных лесов"),
    "Участок монолитно-бетонных работ": ("МБР", "Участок монолитно-бетонных работ"),
}

ALLOWED_EVAL_ROLES = {"Мастер", "Производитель работ"}


def dig(t):
    m = re.search(r"(\d{5,})", str(t or "").upper().replace(" ", ""))
    return m.group(1) if m else ""


def nf(t):
    return " ".join(str(t or "").strip().upper().split())


def load_users():
    wb = load_workbook(BASE / "02_Пользователи.xlsx", read_only=True, data_only=True)
    by_fio = {}
    by_tab = {}
    for i, r in enumerate(wb.active.iter_rows(values_only=True), 1):
        if i == 1 or not r[0]:
            continue
        rec = {
            "tab": str(r[0]).strip(),
            "fio": str(r[1] or "").strip(),
            "role": str(r[2] or "").strip(),
            "status": str(r[5] or "").strip(),
            "site_code": str(r[3] or "").strip(),
        }
        by_fio[nf(rec["fio"])] = rec
        by_tab[dig(rec["tab"])] = rec
    wb.close()
    return by_fio, by_tab


def load_baza():
    wb = load_workbook(BASE / "01_База_1С.xlsx", read_only=True, data_only=True)
    by_tab = {}
    for i, r in enumerate(wb.active.iter_rows(values_only=True), 1):
        if i == 1 or not r[0]:
            continue
        by_tab[dig(r[0])] = {
            "tab": str(r[0]).strip(),
            "fio": str(r[1] or "").strip(),
        }
    wb.close()
    return by_tab


def resolve_user(name, by_fio):
    name = str(name or "").strip()
    if not name:
        return None
    return by_fio.get(nf(name))


def pick_primary(master_name, foreman_name, by_fio):
    """Return (user_rec|None, source, issues). Prefer valid master col, else valid foreman col."""
    issues = []
    m = resolve_user(master_name, by_fio)
    f = resolve_user(foreman_name, by_fio)

    def ok(u):
        return u and u["role"] in ALLOWED_EVAL_ROLES and u["status"] == "Активен"

    if ok(m):
        # note if old foreman was also a valid evaluator (potential dual candidate)
        dual_hint = ok(f) and dig(f["tab"]) != dig(m["tab"])
        return m, "master_col", dual_hint, issues

    if m and m["role"] not in ALLOWED_EVAL_ROLES:
        issues.append(f"master_col role={m['role']} ({master_name})")
    elif master_name and not m:
        issues.append(f"master_col not in users ({master_name})")

    if ok(f):
        return f, "foreman_col", False, issues

    if f and f["role"] not in ALLOWED_EVAL_ROLES:
        issues.append(f"foreman_col role={f['role']} ({foreman_name})")
    elif foreman_name and not f:
        issues.append(f"foreman_col not in users ({foreman_name})")

    return None, None, False, issues


def main():
    by_fio, by_tab = load_users()
    baza = load_baza()

    src = BASE / "03_Карнет.xlsx"
    # backup current
    BACKUP.parent.mkdir(exist_ok=True)
    import shutil

    shutil.copy2(src, BACKUP)

    wb = load_workbook(src, read_only=True, data_only=True)
    rows_in = []
    for i, r in enumerate(wb.active.iter_rows(values_only=True), 1):
        if i == 1:
            continue
        if not r[0]:
            continue
        rows_in.append(r)
    wb.close()

    out_rows = []
    stats = Counter()
    missing_primary = []
    not_in_baza = []
    fio_mismatch = []
    unknown_site = []
    dual_candidates = []
    primary_from = Counter()
    primary_role = Counter()
    evaluate_c = Counter()

    for r in rows_in:
        tab = str(r[0]).strip()
        fio = str(r[1] or "").strip()
        site_raw = str(r[2] or "").strip()
        position_fact = str(r[3] or "").strip()
        master_name = str(r[4] or "").strip()
        foreman_name = str(r[5] or "").strip()
        status = str(r[6] or "").strip()
        shift_start = r[7]
        last_score = r[8]
        # old evaluate ignored (was empty)

        d = dig(tab)
        stats["total"] += 1

        # site
        if site_raw in SITE_MAP:
            site_code, site_name = SITE_MAP[site_raw]
        elif site_raw == "???":
            site_code, site_name = "???", "???"
            unknown_site.append((tab, fio))
            stats["site_unknown"] += 1
        else:
            site_code, site_name = "", site_raw
            unknown_site.append((tab, fio, site_raw))
            stats["site_unknown"] += 1

        # baza check
        b = baza.get(d)
        if not b:
            not_in_baza.append((tab, fio))
            stats["not_in_baza"] += 1
        elif nf(b["fio"]) != nf(fio):
            fio_mismatch.append((tab, fio, b["fio"]))
            stats["fio_mismatch"] += 1
        else:
            stats["baza_ok"] += 1

        primary, source, dual_hint, issues = pick_primary(master_name, foreman_name, by_fio)

        if status in ("Работает", "На межвахте"):
            evaluate = "yes"
        else:
            evaluate = "no"
        evaluate_c[evaluate] += 1

        if primary:
            primary_tab = primary["tab"]
            primary_fio = primary["fio"]
            primary_from[source] += 1
            primary_role[primary["role"]] += 1
            stats["primary_ok"] += 1
            if dual_hint:
                # second valid evaluator existed in old file — do NOT auto-enable dual
                f_user = resolve_user(foreman_name, by_fio)
                dual_candidates.append(
                    {
                        "tab": tab,
                        "fio": fio,
                        "primary": primary_fio,
                        "primary_role": primary["role"],
                        "candidate_secondary": f_user["fio"] if f_user else foreman_name,
                        "candidate_role": f_user["role"] if f_user else "?",
                        "candidate_tab": f_user["tab"] if f_user else "",
                    }
                )
                stats["dual_candidate"] += 1
        else:
            primary_tab = ""
            primary_fio = ""
            stats["primary_missing"] += 1
            missing_primary.append(
                {
                    "tab": tab,
                    "fio": fio,
                    "site": site_raw,
                    "status": status,
                    "master_old": master_name,
                    "foreman_old": foreman_name,
                    "issues": "; ".join(issues) if issues else "нет валидного Мастер/ПР",
                }
            )

        # If evaluate=yes but no primary — still write row, flag in report
        out_rows.append(
            [
                tab,
                fio,
                site_code,
                site_name,
                position_fact,
                primary_tab,
                primary_fio,
                status,
                shift_start,
                last_score if last_score is not None else "",
                evaluate,
                "no",  # dual_enabled default
                "",  # secondary_tab
                "",  # secondary_fio
            ]
        )

    # Write workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Карнет"
    headers = [
        "tab_no",
        "fio",
        "site_code",
        "site_name",
        "position_fact",
        "primary_tab",
        "primary_fio",
        "status",
        "shift_start",
        "last_final_score",
        "evaluate",
        "dual_enabled",
        "secondary_tab",
        "secondary_fio",
    ]
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True)
    miss_fill = PatternFill("solid", fgColor="FDEBD0")
    thin = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin

    for r_i, row in enumerate(out_rows, 2):
        for c_i, val in enumerate(row, 1):
            cell = ws.cell(r_i, c_i, val)
            cell.border = thin
            if not row[5]:  # no primary_tab
                cell.fill = miss_fill

    widths = [14, 32, 10, 40, 40, 14, 32, 16, 12, 12, 10, 12, 14, 32]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:N{len(out_rows)+1}"

    # Sheet: нет primary
    ws2 = wb.create_sheet("Нет_primary")
    h2 = ["tab_no", "fio", "site", "status", "master_old", "foreman_old", "issues"]
    for c, h in enumerate(h2, 1):
        cell = ws2.cell(1, c, h)
        cell.fill = header_fill
        cell.font = header_font
    for r_i, item in enumerate(missing_primary, 2):
        ws2.cell(r_i, 1, item["tab"])
        ws2.cell(r_i, 2, item["fio"])
        ws2.cell(r_i, 3, item["site"])
        ws2.cell(r_i, 4, item["status"])
        ws2.cell(r_i, 5, item["master_old"])
        ws2.cell(r_i, 6, item["foreman_old"])
        ws2.cell(r_i, 7, item["issues"])
    for i, w in enumerate([14, 32, 36, 14, 32, 32, 50], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # Sheet: кандидаты на dual (не включены)
    ws3 = wb.create_sheet("Кандидаты_dual")
    h3 = [
        "tab_no",
        "fio",
        "primary_fio",
        "primary_role",
        "candidate_secondary_tab",
        "candidate_secondary_fio",
        "candidate_role",
        "note",
    ]
    for c, h in enumerate(h3, 1):
        cell = ws3.cell(1, c, h)
        cell.fill = header_fill
        cell.font = header_font
    for r_i, item in enumerate(dual_candidates, 2):
        ws3.cell(r_i, 1, item["tab"])
        ws3.cell(r_i, 2, item["fio"])
        ws3.cell(r_i, 3, item["primary"])
        ws3.cell(r_i, 4, item["primary_role"])
        ws3.cell(r_i, 5, item["candidate_tab"])
        ws3.cell(r_i, 6, item["candidate_secondary"])
        ws3.cell(r_i, 7, item["candidate_role"])
        ws3.cell(r_i, 8, "dual НЕ включён — решить Админ_ОП")
    for i, w in enumerate([14, 32, 32, 18, 14, 32, 18, 36], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    # Sheet: прочее
    ws4 = wb.create_sheet("Прочее_замечания")
    ws4.cell(1, 1, "type")
    ws4.cell(1, 2, "tab_no")
    ws4.cell(1, 3, "fio")
    ws4.cell(1, 4, "detail")
    ws4.cell(1, 1).fill = header_fill
    ws4.cell(1, 1).font = header_font
    rr = 2
    for tab, fio in [(x[0], x[1]) for x in not_in_baza]:
        ws4.cell(rr, 1, "not_in_baza")
        ws4.cell(rr, 2, tab)
        ws4.cell(rr, 3, fio)
        rr += 1
    for item in fio_mismatch:
        ws4.cell(rr, 1, "fio_mismatch")
        ws4.cell(rr, 2, item[0])
        ws4.cell(rr, 3, item[1])
        ws4.cell(rr, 4, f"в Базе: {item[2]}")
        rr += 1
    for item in unknown_site:
        ws4.cell(rr, 1, "unknown_site")
        ws4.cell(rr, 2, item[0])
        ws4.cell(rr, 3, item[1])
        ws4.cell(rr, 4, item[2] if len(item) > 2 else "???")
        rr += 1

    wb.save(OUT)

    # Markdown report
    lines = []
    lines.append("# Отчёт конвертации 03_Карнет")
    lines.append("")
    lines.append(f"- Исходник сохранён: `{BACKUP.name}`")
    lines.append(f"- Результат: `{OUT.name}`")
    lines.append("")
    lines.append("## Сводка")
    lines.append("")
    lines.append(f"| Метрика | Значение |")
    lines.append(f"|---|---|")
    lines.append(f"| Всего строк | {stats['total']} |")
    lines.append(f"| Primary назначен | {stats['primary_ok']} |")
    lines.append(f"| **Нет primary (нужно вам)** | **{stats['primary_missing']}** |")
    lines.append(f"| Совпадение с Базой (ФИО) | {stats['baza_ok']} |")
    lines.append(f"| Нет в Базе | {stats['not_in_baza']} |")
    lines.append(f"| ФИО ≠ База | {stats['fio_mismatch']} |")
    lines.append(f"| Участок ??? / неизвестен | {stats['site_unknown']} |")
    lines.append(f"| Кандидаты на dual (не включены) | {stats['dual_candidate']} |")
    lines.append(f"| evaluate=yes/no | {dict(evaluate_c)} |")
    lines.append(f"| dual_enabled | все `no` |")
    lines.append("")
    lines.append("### Откуда взят primary")
    lines.append(f"- {dict(primary_from)}")
    lines.append(f"- роли: {dict(primary_role)}")
    lines.append("")
    lines.append("## Что сделать вам")
    lines.append("")
    lines.append("1. Открыть лист **`Нет_primary`** в новом `03_Карнет.xlsx` — назначить Мастера или ПР.")
    lines.append("2. Проверить **`???` участки** (лист Прочее_замечания).")
    lines.append("3. При необходимости добавить в `02_Пользователи` отсутствующих (напр. Мавлянов).")
    lines.append("4. Лист **`Кандидаты_dual`** — это пары, где в старом файле был валидный 2-й; dual **не включал** (по вашей логике через Админ_ОП).")
    lines.append("5. Заполнить в Базе `hourly_rate` и `rate_updated_at` (пока пустые у всех) — отдельно.")
    lines.append("6. Создать `04_Квыр.xlsx`, когда будут коэффициенты.")
    lines.append("")
    if missing_primary:
        lines.append("## Примеры без primary (первые 15)")
        lines.append("")
        for item in missing_primary[:15]:
            lines.append(
                f"- `{item['tab']}` {item['fio']} | old master: {item['master_old']} | "
                f"old foreman: {item['foreman_old']} | {item['issues']}"
            )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("DONE", stats)
    print("missing_primary", stats["primary_missing"])
    print("report", REPORT)


if __name__ == "__main__":
    main()
