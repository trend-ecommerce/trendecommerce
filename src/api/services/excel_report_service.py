"""Serviço de geração de relatórios executivos em Excel (.xlsx) para a IA Preditiva."""

from __future__ import annotations

import io
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# Paleta Corporativa TrendEcommerce AI
COLOR_NAVY = "07192E"
COLOR_NAVY_ALT = "0F2D52"
COLOR_ACCENT = "00AEEF"
COLOR_ZEBRA = "F8FAFC"
COLOR_WHITE = "FFFFFF"
COLOR_TOTAL_BG = "E2E8F0"
COLOR_META_BG = "F1F5F9"
COLOR_BORDER = "CBD5E1"
COLOR_TEXT_DARK = "0F172A"
COLOR_TEXT_MUTED = "475569"

COLOR_BADGE_HIGH_BG = "DCFCE7"
COLOR_BADGE_HIGH_FG = "166534"
COLOR_BADGE_MED_BG = "FEF9C3"
COLOR_BADGE_MED_FG = "854D0E"
COLOR_BADGE_NORM_BG = "F1F5F9"
COLOR_BADGE_NORM_FG = "334155"
COLOR_BADGE_LOW_BG = "FEE2E2"
COLOR_BADGE_LOW_FG = "991B1B"

FMT_CURRENCY = '"R$ "#,##0.00'
FMT_INTEGER = "#,##0"
FMT_DECIMAL = "#,##0.0"
FMT_DELTA = "+#,##0.0;-#,##0.0;0.0"
FMT_PERCENT = '0.0"%"'
FMT_DATE = "dd/mm/yyyy"


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    norm = unicodedata.normalize("NFKD", str(value).strip())
    ascii_str = "".join(ch for ch in norm if not unicodedata.combining(ch))
    return ascii_str.lower().strip()


def _is_all_categories(category: Optional[str]) -> bool:
    norm = _normalize_text(category)
    return norm in ("", "gerais", "geral", "todas", "todos", "todas as categorias")


def _parse_date_safe(date_str: str) -> Any:
    raw = str(date_str or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return raw


def _make_borders():
    thin_side = Side(style="thin", color=COLOR_BORDER)
    navy_side = Side(style="medium", color=COLOR_NAVY)
    double_side = Side(style="double", color=COLOR_NAVY)
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    header_border = Border(left=thin_side, right=thin_side, top=navy_side, bottom=navy_side)
    total_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=double_side)
    return cell_border, header_border, total_border


def _auto_adjust_column_widths(
    ws,
    min_width: int = 11,
    max_width: int = 46,
    skip_rows: Optional[set[int]] = None,
) -> None:
    skip = skip_rows or set()
    col_widths: Dict[int, int] = {}
    for row_idx, row in enumerate(ws.iter_rows(), start=1):
        if row_idx in skip:
            continue
        for cell in row:
            if cell.value is None:
                continue
            val_str = str(cell.value)
            # Evitar inflar colunas por causa de fórmulas longas (=SUM(...))
            if val_str.startswith("="):
                display_len = 14
            else:
                display_len = max((len(line) for line in val_str.splitlines()), default=0)
                if cell.number_format == FMT_CURRENCY:
                    display_len = max(display_len, 14)
            col_idx = cell.column
            if display_len > col_widths.get(col_idx, 0):
                col_widths[col_idx] = display_len

    for col_idx in range(1, ws.max_column + 1):
        width = min(max(col_widths.get(col_idx, min_width) + 4, min_width), max_width)
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _classify_priority(trend_pct: float, predicted_units: int, med_cutoff: float, high_cutoff: float) -> str:
    if trend_pct >= 10.0 or (high_cutoff > 0 and predicted_units >= high_cutoff):
        return "ALTA"
    if trend_pct >= 0.0 or (med_cutoff > 0 and predicted_units >= med_cutoff):
        return "MÉDIA"
    return "NORMAL"


def _classify_trend_status(trend_pct: float) -> str:
    if trend_pct >= 5.0:
        return "ACELERANDO"
    if trend_pct <= -5.0:
        return "DESACELERANDO"
    return "ESTÁVEL"


def _apply_badge_style(cell, label: str, font_bold: bool = True) -> None:
    upper = (label or "").upper()
    if upper in ("ALTA", "ACELERANDO"):
        cell.fill = PatternFill("solid", fgColor=COLOR_BADGE_HIGH_BG)
        cell.font = Font(name="Calibri", size=10, bold=font_bold, color=COLOR_BADGE_HIGH_FG)
    elif upper in ("MÉDIA", "ESTÁVEL"):
        cell.fill = PatternFill("solid", fgColor=COLOR_BADGE_MED_BG)
        cell.font = Font(name="Calibri", size=10, bold=font_bold, color=COLOR_BADGE_MED_FG)
    elif upper == "DESACELERANDO":
        cell.fill = PatternFill("solid", fgColor=COLOR_BADGE_LOW_BG)
        cell.font = Font(name="Calibri", size=10, bold=font_bold, color=COLOR_BADGE_LOW_FG)
    else:
        cell.fill = PatternFill("solid", fgColor=COLOR_BADGE_NORM_BG)
        cell.font = Font(name="Calibri", size=10, bold=font_bold, color=COLOR_BADGE_NORM_FG)
    cell.alignment = Alignment(horizontal="center", vertical="center")


def generate_forecast_excel_report(
    items: Sequence[Any],
    horizon_days: int,
    category: Optional[str] = None,
    product_id: Optional[int] = None,
    historical_stats: Optional[Dict[int, Dict[str, float]]] = None,
) -> io.BytesIO:
    """Gera workbook Excel (.xlsx) estilizado com 4 abas executivas em memória."""
    hist_map = historical_stats or {}
    all_items = list(items or [])

    # Filtrar por categoria caso informada e diferente de GERAIS
    if not _is_all_categories(category):
        target_cat_norm = _normalize_text(category)
        filtered_items = [
            it for it in all_items
            if _normalize_text(getattr(it, "category", "")) == target_cat_norm
        ]
        if not filtered_items:
            filtered_items = [
                it for it in all_items
                if target_cat_norm in _normalize_text(getattr(it, "category", ""))
            ]
        applied_category_label = str(category).strip()
    else:
        filtered_items = list(all_items)
        applied_category_label = "Todas (Gerais)"

    # Ordenação principal por faturamento projetado descendente
    filtered_items.sort(
        key=lambda x: (
            float(getattr(x, "total_projected_revenue", 0.0) or 0.0),
            int(getattr(x, "total_predicted_units", 0) or 0),
        ),
        reverse=True,
    )

    # Cutoffs para prioridade de reposição
    units_sorted = sorted(
        (int(getattr(it, "total_predicted_units", 0) or 0) for it in filtered_items)
    )
    n_items = len(units_sorted)
    med_cutoff = float(units_sorted[n_items // 2]) if n_items else 0.0
    high_cutoff = float(units_sorted[int(n_items * 0.75)]) if n_items else 0.0

    # Enriquecer registros com métricas históricas 30d e variação
    enriched: List[Dict[str, Any]] = []
    for it in filtered_items:
        pid = int(getattr(it, "product_id"))
        st = hist_map.get(pid, {})
        hist_30d_total = int(round(float(st.get("hist_30d_total", 0.0))))
        hist_30d_avg = round(float(st.get("hist_30d_avg", 0.0)), 1)
        daily_avg = round(float(getattr(it, "daily_average", 0.0) or 0.0), 1)
        pred_units = int(getattr(it, "total_predicted_units", 0) or 0)
        min_units = int(getattr(it, "min_predicted_units", 0) or 0)
        max_units = int(getattr(it, "max_predicted_units", 0) or 0)
        proj_rev = round(float(getattr(it, "total_projected_revenue", 0.0) or 0.0), 2)
        unit_price = round(float(getattr(it, "unit_price", 0.0) or 0.0), 2)
        rec_buffer = int(getattr(it, "recommended_stock_buffer", 0) or 0)

        if hist_30d_avg > 0:
            trend_pct = round(((daily_avg - hist_30d_avg) / hist_30d_avg) * 100.0, 1)
        else:
            trend_pct = 0.0

        priority = _classify_priority(trend_pct, pred_units, med_cutoff, high_cutoff)
        trend_status = _classify_trend_status(trend_pct)

        enriched.append(
            {
                "item": it,
                "product_id": pid,
                "product_title": str(getattr(it, "product_title", "") or ""),
                "category": str(getattr(it, "category", "Geral") or "Geral"),
                "unit_price": unit_price,
                "hist_30d_total": hist_30d_total,
                "hist_30d_avg": hist_30d_avg,
                "daily_avg": daily_avg,
                "daily_delta": round(daily_avg - hist_30d_avg, 1),
                "trend_pct": trend_pct,
                "total_predicted_units": pred_units,
                "min_predicted_units": min_units,
                "max_predicted_units": max_units,
                "total_projected_revenue": proj_rev,
                "recommended_stock_buffer": rec_buffer,
                "priority": priority,
                "trend_status": trend_status,
            }
        )

    # Localizar produto selecionado para destaque no Resumo Executivo
    focus_row: Optional[Dict[str, Any]] = None
    if product_id is not None:
        focus_row = next((r for r in enriched if r["product_id"] == int(product_id)), None)
        if focus_row is None:
            raw_focus = next((it for it in all_items if int(getattr(it, "product_id")) == int(product_id)), None)
            if raw_focus is not None:
                st = hist_map.get(int(product_id), {})
                hist_avg = round(float(st.get("hist_30d_avg", 0.0)), 1)
                d_avg = round(float(getattr(raw_focus, "daily_average", 0.0) or 0.0), 1)
                t_pct = round(((d_avg - hist_avg) / hist_avg) * 100.0, 1) if hist_avg > 0 else 0.0
                focus_row = {
                    "item": raw_focus,
                    "product_id": int(product_id),
                    "product_title": str(getattr(raw_focus, "product_title", "") or ""),
                    "category": str(getattr(raw_focus, "category", "Geral") or "Geral"),
                    "unit_price": round(float(getattr(raw_focus, "unit_price", 0.0) or 0.0), 2),
                    "hist_30d_total": int(round(float(st.get("hist_30d_total", 0.0)))),
                    "hist_30d_avg": hist_avg,
                    "daily_avg": d_avg,
                    "daily_delta": round(d_avg - hist_avg, 1),
                    "trend_pct": t_pct,
                    "total_predicted_units": int(getattr(raw_focus, "total_predicted_units", 0) or 0),
                    "min_predicted_units": int(getattr(raw_focus, "min_predicted_units", 0) or 0),
                    "max_predicted_units": int(getattr(raw_focus, "max_predicted_units", 0) or 0),
                    "total_projected_revenue": round(float(getattr(raw_focus, "total_projected_revenue", 0.0) or 0.0), 2),
                    "recommended_stock_buffer": int(getattr(raw_focus, "recommended_stock_buffer", 0) or 0),
                    "priority": _classify_priority(
                        t_pct,
                        int(getattr(raw_focus, "total_predicted_units", 0) or 0),
                        med_cutoff,
                        high_cutoff,
                    ),
                    "trend_status": _classify_trend_status(t_pct),
                }

    wb = Workbook()

    # Estilos compartilhados
    cell_border, header_border, total_border = _make_borders()
    fill_navy = PatternFill("solid", fgColor=COLOR_NAVY)
    fill_navy_alt = PatternFill("solid", fgColor=COLOR_NAVY_ALT)
    fill_zebra = PatternFill("solid", fgColor=COLOR_ZEBRA)
    fill_white = PatternFill("solid", fgColor=COLOR_WHITE)
    fill_total = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    fill_meta = PatternFill("solid", fgColor=COLOR_META_BG)

    font_banner = Font(name="Calibri", size=14, bold=True, color=COLOR_WHITE)
    font_subbanner = Font(name="Calibri", size=10, italic=True, color="BAE6FD")
    font_header = Font(name="Calibri", size=10, bold=True, color=COLOR_WHITE)
    font_section = Font(name="Calibri", size=11, bold=True, color=COLOR_WHITE)
    font_label = Font(name="Calibri", size=10, bold=True, color=COLOR_NAVY)
    font_data = Font(name="Calibri", size=10, color=COLOR_TEXT_DARK)
    font_total = Font(name="Calibri", size=10, bold=True, color=COLOR_NAVY)

    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_center = Alignment(horizontal="center", vertical="center")
    align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # =========================================================================
    # ABA 1: RESUMO EXECUTIVO
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Resumo Executivo"
    ws1.views.sheetView[0].showGridLines = True

    ws1.merge_cells("A1:G1")
    ws1["A1"] = "TRENDECOMMERCE AI — RELATÓRIO EXECUTIVO DE PREVISÃO DE DEMANDA"
    ws1["A1"].font = font_banner
    ws1["A1"].fill = fill_navy
    ws1["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[1].height = 30

    ws1.merge_cells("A2:G2")
    ws1["A2"] = f"Projeção Autoregressiva XGBoost | Horizonte de {horizon_days} dias | Categoria: {applied_category_label}"
    ws1["A2"].font = font_subbanner
    ws1["A2"].fill = fill_navy_alt
    ws1["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[2].height = 20

    # Bloco de Parâmetros e KPIs Gerais
    total_units_all = sum(r["total_predicted_units"] for r in enriched)
    total_rev_all = round(sum(r["total_projected_revenue"] for r in enriched), 2)
    total_daily_all = round(sum(r["daily_avg"] for r in enriched), 1)
    total_buffer_all = sum(r["recommended_stock_buffer"] for r in enriched)
    weighted_ticket = round(total_rev_all / total_units_all, 2) if total_units_all > 0 else 0.0

    ws1.merge_cells("A4:B4")
    ws1["A4"] = "PARÂMETROS DA ANÁLISE"
    ws1["A4"].font = font_section
    ws1["A4"].fill = fill_navy
    ws1["A4"].alignment = Alignment(horizontal="left", vertical="center", indent=1)

    ws1.merge_cells("D4:E4")
    ws1["D4"] = "KPIS GERAIS DA SELEÇÃO"
    ws1["D4"].font = font_section
    ws1["D4"].fill = fill_navy
    ws1["D4"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[4].height = 22

    meta_rows = [
        ("Data de Geração", datetime.now().strftime("%d/%m/%Y %H:%M"), None),
        ("Horizonte Projetado", f"{horizon_days} dias", None),
        ("Categoria Aplicada", applied_category_label, None),
        ("Produtos Analisados", len(enriched), FMT_INTEGER),
        ("Motor Preditivo", "XGBoost Autoregressivo v2", None),
    ]
    kpi_rows = [
        ("Demanda Total Prevista", total_units_all, FMT_INTEGER),
        ("Faturamento Projetado Total", total_rev_all, FMT_CURRENCY),
        ("Média Diária Agregada", total_daily_all, FMT_DECIMAL),
        ("Estoque de Segurança Total", total_buffer_all, FMT_INTEGER),
        ("Ticket Médio Ponderado", weighted_ticket, FMT_CURRENCY),
    ]

    for idx in range(5):
        r_num = 5 + idx
        ws1.row_dimensions[r_num].height = 20
        m_label, m_val, m_fmt = meta_rows[idx]
        c_ml = ws1.cell(row=r_num, column=1, value=m_label)
        c_mv = ws1.cell(row=r_num, column=2, value=m_val)
        c_ml.font = font_label
        c_ml.fill = fill_meta
        c_ml.alignment = align_left
        c_ml.border = cell_border
        c_mv.font = font_data
        c_mv.fill = fill_white
        c_mv.alignment = align_right if m_fmt else align_left
        c_mv.border = cell_border
        if m_fmt:
            c_mv.number_format = m_fmt

        k_label, k_val, k_fmt = kpi_rows[idx]
        c_kl = ws1.cell(row=r_num, column=4, value=k_label)
        c_kv = ws1.cell(row=r_num, column=5, value=k_val)
        c_kl.font = font_label
        c_kl.fill = fill_meta
        c_kl.alignment = align_left
        c_kl.border = cell_border
        c_kv.font = Font(name="Calibri", size=10, bold=True, color=COLOR_NAVY)
        c_kv.fill = fill_white
        c_kv.alignment = align_right
        c_kv.border = cell_border
        c_kv.number_format = k_fmt

    curr_row = 11

    # Destaque do Produto Selecionado (se enviado)
    if focus_row is not None:
        ws1.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=7)
        sec_cell = ws1.cell(
            row=curr_row,
            column=1,
            value=f"PRODUTO EM DESTAQUE (ID #{focus_row['product_id']}): {focus_row['product_title']}",
        )
        sec_cell.font = font_section
        sec_cell.fill = fill_navy
        sec_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws1.row_dimensions[curr_row].height = 22
        curr_row += 1

        focus_headers = [
            "Categoria",
            "Preço Unitário",
            "Média Hist. 30d",
            f"Demanda ({horizon_days}d)",
            "Faturamento Projetado",
            "Estoque Recomendado",
            "Prioridade",
        ]
        ws1.row_dimensions[curr_row].height = 24
        for col_i, h_text in enumerate(focus_headers, start=1):
            hc = ws1.cell(row=curr_row, column=col_i, value=h_text)
            hc.font = font_header
            hc.fill = fill_navy_alt
            hc.alignment = align_header
            hc.border = header_border
        curr_row += 1

        ws1.row_dimensions[curr_row].height = 22
        focus_vals = [
            (focus_row["category"], None, align_left),
            (focus_row["unit_price"], FMT_CURRENCY, align_right),
            (focus_row["hist_30d_avg"], FMT_DECIMAL, align_right),
            (focus_row["total_predicted_units"], FMT_INTEGER, align_right),
            (focus_row["total_projected_revenue"], FMT_CURRENCY, align_right),
            (focus_row["recommended_stock_buffer"], FMT_INTEGER, align_right),
            (focus_row["priority"], None, align_center),
        ]
        for col_i, (val, fmt, aln) in enumerate(focus_vals, start=1):
            vc = ws1.cell(row=curr_row, column=col_i, value=val)
            vc.font = font_data
            vc.fill = fill_white
            vc.alignment = aln
            vc.border = cell_border
            if fmt:
                vc.number_format = fmt
            if col_i == 7:
                _apply_badge_style(vc, str(val))
        curr_row += 2

    # Tabela Consolidada por Categoria
    ws1.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=7)
    cat_title_cell = ws1.cell(
        row=curr_row,
        column=1,
        value="CONSOLIDADO POR CATEGORIA (PARTICIPAÇÃO NO FATURAMENTO)",
    )
    cat_title_cell.font = font_section
    cat_title_cell.fill = fill_navy
    cat_title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws1.row_dimensions[curr_row].height = 22
    curr_row += 1

    cat_header_row = curr_row
    cat_headers = [
        "Categoria",
        "Qtd. Produtos",
        "Demanda Prevista (un)",
        "Média Diária (un/dia)",
        "Faturamento Projetado (R$)",
        "Participação % Faturamento",
        "Estoque Recomendado (un)",
    ]
    ws1.row_dimensions[cat_header_row].height = 26
    for col_i, h_text in enumerate(cat_headers, start=1):
        hc = ws1.cell(row=cat_header_row, column=col_i, value=h_text)
        hc.font = font_header
        hc.fill = fill_navy
        hc.alignment = align_header
        hc.border = header_border

    # Agrupar por categoria
    cat_agg: Dict[str, Dict[str, float]] = {}
    for r in enriched:
        cat_name = r["category"]
        bucket = cat_agg.setdefault(
            cat_name,
            {"count": 0, "units": 0, "daily": 0.0, "rev": 0.0, "buffer": 0},
        )
        bucket["count"] += 1
        bucket["units"] += r["total_predicted_units"]
        bucket["daily"] += r["daily_avg"]
        bucket["rev"] += r["total_projected_revenue"]
        bucket["buffer"] += r["recommended_stock_buffer"]

    cat_rows_sorted = sorted(cat_agg.items(), key=lambda kv: kv[1]["rev"], reverse=True)
    cat_first_data_row = cat_header_row + 1
    row_ptr = cat_first_data_row

    for idx, (cat_name, agg) in enumerate(cat_rows_sorted):
        ws1.row_dimensions[row_ptr].height = 20
        bg = fill_zebra if idx % 2 == 1 else fill_white
        share_pct = round((agg["rev"] / total_rev_all) * 100.0, 2) if total_rev_all > 0 else 0.0
        row_values = [
            (cat_name, None, align_left),
            (int(agg["count"]), FMT_INTEGER, align_right),
            (int(agg["units"]), FMT_INTEGER, align_right),
            (round(agg["daily"], 1), FMT_DECIMAL, align_right),
            (round(agg["rev"], 2), FMT_CURRENCY, align_right),
            (share_pct, FMT_PERCENT, align_right),
            (int(agg["buffer"]), FMT_INTEGER, align_right),
        ]
        for col_i, (val, fmt, aln) in enumerate(row_values, start=1):
            c = ws1.cell(row=row_ptr, column=col_i, value=val)
            c.font = font_data
            c.fill = bg
            c.alignment = aln
            c.border = cell_border
            if fmt:
                c.number_format = fmt
        row_ptr += 1

    cat_last_data_row = row_ptr - 1

    # Linha de Total usando fórmulas =SUM(...)
    total_row_ws1 = row_ptr
    ws1.row_dimensions[total_row_ws1].height = 22
    if cat_last_data_row >= cat_first_data_row:
        totals_ws1 = [
            ("TOTAL GERAL", None, align_left),
            (f"=SUM(B{cat_first_data_row}:B{cat_last_data_row})", FMT_INTEGER, align_right),
            (f"=SUM(C{cat_first_data_row}:C{cat_last_data_row})", FMT_INTEGER, align_right),
            (f"=SUM(D{cat_first_data_row}:D{cat_last_data_row})", FMT_DECIMAL, align_right),
            (f"=SUM(E{cat_first_data_row}:E{cat_last_data_row})", FMT_CURRENCY, align_right),
            (f"=SUM(F{cat_first_data_row}:F{cat_last_data_row})", FMT_PERCENT, align_right),
            (f"=SUM(G{cat_first_data_row}:G{cat_last_data_row})", FMT_INTEGER, align_right),
        ]
        ws1.auto_filter.ref = f"A{cat_header_row}:G{cat_last_data_row}"
    else:
        totals_ws1 = [
            ("TOTAL GERAL", None, align_left),
            (0, FMT_INTEGER, align_right),
            (0, FMT_INTEGER, align_right),
            (0.0, FMT_DECIMAL, align_right),
            (0.0, FMT_CURRENCY, align_right),
            (0.0, FMT_PERCENT, align_right),
            (0, FMT_INTEGER, align_right),
        ]

    for col_i, (val, fmt, aln) in enumerate(totals_ws1, start=1):
        tc = ws1.cell(row=total_row_ws1, column=col_i, value=val)
        tc.font = font_total
        tc.fill = fill_total
        tc.alignment = aln
        tc.border = total_border
        if fmt:
            tc.number_format = fmt

    ws1.freeze_panes = "A3"
    _auto_adjust_column_widths(ws1, skip_rows={1, 2, 4, 11})

    # =========================================================================
    # ABA 2: PREVISÃO POR PRODUTO
    # =========================================================================
    ws2 = wb.create_sheet(title="Previsão por Produto")
    ws2.views.sheetView[0].showGridLines = True

    ws2.merge_cells("A1:M1")
    ws2["A1"] = f"PREVISÃO DETALHADA POR PRODUTO — HORIZONTE DE {horizon_days} DIAS ({applied_category_label.upper()})"
    ws2["A1"].font = font_banner
    ws2["A1"].fill = fill_navy
    ws2["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws2.row_dimensions[1].height = 28

    prod_headers = [
        "ID",
        "Produto",
        "Categoria",
        "Preço Unitário (R$)",
        "Média Hist. 30d (un/dia)",
        "Variação / Tendência (%)",
        f"Demanda Prevista ({horizon_days}d)",
        "Mínimo (un)",
        "Máximo (un)",
        "Média Diária Prevista",
        "Faturamento Projetado (R$)",
        "Estoque Recomendado (un)",
        "Prioridade de Reposição",
    ]
    ws2.row_dimensions[2].height = 28
    for col_i, h_text in enumerate(prod_headers, start=1):
        hc = ws2.cell(row=2, column=col_i, value=h_text)
        hc.font = font_header
        hc.fill = fill_navy
        hc.alignment = align_header
        hc.border = header_border

    first_prod_row = 3
    row_ptr = first_prod_row
    for idx, rec in enumerate(enriched):
        ws2.row_dimensions[row_ptr].height = 20
        bg = fill_zebra if idx % 2 == 1 else fill_white
        row_cells = [
            (rec["product_id"], FMT_INTEGER, align_center),
            (rec["product_title"], None, align_left),
            (rec["category"], None, align_left),
            (rec["unit_price"], FMT_CURRENCY, align_right),
            (rec["hist_30d_avg"], FMT_DECIMAL, align_right),
            (rec["trend_pct"], FMT_PERCENT, align_right),
            (rec["total_predicted_units"], FMT_INTEGER, align_right),
            (rec["min_predicted_units"], FMT_INTEGER, align_right),
            (rec["max_predicted_units"], FMT_INTEGER, align_right),
            (rec["daily_avg"], FMT_DECIMAL, align_right),
            (rec["total_projected_revenue"], FMT_CURRENCY, align_right),
            (rec["recommended_stock_buffer"], FMT_INTEGER, align_right),
            (rec["priority"], None, align_center),
        ]
        for col_i, (val, fmt, aln) in enumerate(row_cells, start=1):
            c = ws2.cell(row=row_ptr, column=col_i, value=val)
            c.font = font_data
            c.fill = bg
            c.alignment = aln
            c.border = cell_border
            if fmt:
                c.number_format = fmt
            if col_i == 13:
                _apply_badge_style(c, str(val))
        row_ptr += 1

    last_prod_row = row_ptr - 1
    total_row_ws2 = row_ptr
    ws2.row_dimensions[total_row_ws2].height = 22

    if last_prod_row >= first_prod_row:
        ws2.auto_filter.ref = f"A2:M{last_prod_row}"
        totals_ws2 = [
            ("TOTAL", None, align_center),
            (f"=COUNTA(B{first_prod_row}:B{last_prod_row})", FMT_INTEGER, align_left),
            (applied_category_label, None, align_left),
            (f"=AVERAGE(D{first_prod_row}:D{last_prod_row})", FMT_CURRENCY, align_right),
            (f"=SUM(E{first_prod_row}:E{last_prod_row})", FMT_DECIMAL, align_right),
            (f"=AVERAGE(F{first_prod_row}:F{last_prod_row})", FMT_PERCENT, align_right),
            (f"=SUM(G{first_prod_row}:G{last_prod_row})", FMT_INTEGER, align_right),
            (f"=SUM(H{first_prod_row}:H{last_prod_row})", FMT_INTEGER, align_right),
            (f"=SUM(I{first_prod_row}:I{last_prod_row})", FMT_INTEGER, align_right),
            (f"=SUM(J{first_prod_row}:J{last_prod_row})", FMT_DECIMAL, align_right),
            (f"=SUM(K{first_prod_row}:K{last_prod_row})", FMT_CURRENCY, align_right),
            (f"=SUM(L{first_prod_row}:L{last_prod_row})", FMT_INTEGER, align_right),
            ("-", None, align_center),
        ]
    else:
        totals_ws2 = [("TOTAL", None, align_center)] + [("-", None, align_center)] * 12

    for col_i, (val, fmt, aln) in enumerate(totals_ws2, start=1):
        tc = ws2.cell(row=total_row_ws2, column=col_i, value=val)
        tc.font = font_total
        tc.fill = fill_total
        tc.alignment = aln
        tc.border = total_border
        if fmt:
            tc.number_format = fmt

    ws2.freeze_panes = "A3"
    _auto_adjust_column_widths(ws2, skip_rows={1})

    # =========================================================================
    # ABA 3: PROJEÇÃO DIÁRIA (pronta para Tabela Dinâmica)
    # =========================================================================
    ws3 = wb.create_sheet(title="Projeção Diária")
    ws3.views.sheetView[0].showGridLines = True

    daily_headers = [
        "Data",
        "Dia da Semana",
        "Produto",
        "Categoria",
        "Demanda Prevista",
        "IC Mín",
        "IC Máx",
        "Faturamento Diário",
    ]
    ws3.row_dimensions[1].height = 26
    for col_i, h_text in enumerate(daily_headers, start=1):
        hc = ws3.cell(row=1, column=col_i, value=h_text)
        hc.font = font_header
        hc.fill = fill_navy
        hc.alignment = align_header
        hc.border = header_border

    # Selecionar produto em foco (se houver) + Top 20 produtos da seleção sem duplicatas
    daily_targets: List[Dict[str, Any]] = []
    seen_pids = set()
    if focus_row is not None:
        daily_targets.append(focus_row)
        seen_pids.add(focus_row["product_id"])
    for rec in enriched:
        if len(daily_targets) >= (21 if focus_row is not None and focus_row["product_id"] not in {r["product_id"] for r in enriched[:20]} else 20):
            break
        if rec["product_id"] not in seen_pids:
            daily_targets.append(rec)
            seen_pids.add(rec["product_id"])

    row_ptr = 2
    for target in daily_targets:
        raw_days = getattr(target["item"], "days", []) or []
        for day in raw_days:
            ws3.row_dimensions[row_ptr].height = 19
            bg = fill_zebra if row_ptr % 2 == 1 else fill_white
            parsed_dt = _parse_date_safe(getattr(day, "date", ""))
            d_vals = [
                (parsed_dt, FMT_DATE if not isinstance(parsed_dt, str) else None, align_center),
                (str(getattr(day, "day_name", "") or ""), None, align_left),
                (target["product_title"], None, align_left),
                (target["category"], None, align_left),
                (int(getattr(day, "predicted_demand", 0) or 0), FMT_INTEGER, align_right),
                (int(getattr(day, "confidence_min", 0) or 0), FMT_INTEGER, align_right),
                (int(getattr(day, "confidence_max", 0) or 0), FMT_INTEGER, align_right),
                (round(float(getattr(day, "projected_revenue", 0.0) or 0.0), 2), FMT_CURRENCY, align_right),
            ]
            for col_i, (val, fmt, aln) in enumerate(d_vals, start=1):
                c = ws3.cell(row=row_ptr, column=col_i, value=val)
                c.font = font_data
                c.fill = bg
                c.alignment = aln
                c.border = cell_border
                if fmt:
                    c.number_format = fmt
            row_ptr += 1

    if row_ptr > 2:
        ws3.auto_filter.ref = f"A1:H{row_ptr - 1}"
    ws3.freeze_panes = "A2"
    _auto_adjust_column_widths(ws3)

    # =========================================================================
    # ABA 4: HISTÓRICO X PREVISÃO
    # =========================================================================
    ws4 = wb.create_sheet(title="Histórico x Previsão")
    ws4.views.sheetView[0].showGridLines = True

    ws4.merge_cells("A1:K1")
    ws4["A1"] = f"HISTÓRICO REAL (30 DIAS) VS. PREVISÃO XGBOOST ({horizon_days} DIAS) — RADAR DE ACELERAÇÃO"
    ws4["A1"].font = font_banner
    ws4["A1"].fill = fill_navy
    ws4["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws4.row_dimensions[1].height = 28

    comp_headers = [
        "ID",
        "Produto",
        "Categoria",
        "Vendas Reais 30d (un)",
        "Média Diária Real 30d",
        "Média Diária Prevista",
        f"Demanda Prevista ({horizon_days}d)",
        "Delta Diário (un/dia)",
        "Variação vs Histórico (%)",
        "Faturamento Projetado (R$)",
        "Tendência",
    ]
    ws4.row_dimensions[2].height = 28
    for col_i, h_text in enumerate(comp_headers, start=1):
        hc = ws4.cell(row=2, column=col_i, value=h_text)
        hc.font = font_header
        hc.fill = fill_navy
        hc.alignment = align_header
        hc.border = header_border

    # Destacar produtos em aceleração no topo e desaceleração na base
    comp_sorted = sorted(
        enriched,
        key=lambda r: (r["trend_pct"], r["total_projected_revenue"]),
        reverse=True,
    )

    row_ptr = 3
    for idx, rec in enumerate(comp_sorted):
        ws4.row_dimensions[row_ptr].height = 20
        bg = fill_zebra if idx % 2 == 1 else fill_white
        c_vals = [
            (rec["product_id"], FMT_INTEGER, align_center),
            (rec["product_title"], None, align_left),
            (rec["category"], None, align_left),
            (rec["hist_30d_total"], FMT_INTEGER, align_right),
            (rec["hist_30d_avg"], FMT_DECIMAL, align_right),
            (rec["daily_avg"], FMT_DECIMAL, align_right),
            (rec["total_predicted_units"], FMT_INTEGER, align_right),
            (rec["daily_delta"], FMT_DELTA, align_right),
            (rec["trend_pct"], FMT_PERCENT, align_right),
            (rec["total_projected_revenue"], FMT_CURRENCY, align_right),
            (rec["trend_status"], None, align_center),
        ]
        for col_i, (val, fmt, aln) in enumerate(c_vals, start=1):
            c = ws4.cell(row=row_ptr, column=col_i, value=val)
            c.font = font_data
            c.fill = bg
            c.alignment = aln
            c.border = cell_border
            if fmt:
                c.number_format = fmt
            if col_i == 11:
                _apply_badge_style(c, str(val))
        row_ptr += 1

    if row_ptr > 3:
        ws4.auto_filter.ref = f"A2:K{row_ptr - 1}"
    ws4.freeze_panes = "A3"
    _auto_adjust_column_widths(ws4, skip_rows={1})

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
