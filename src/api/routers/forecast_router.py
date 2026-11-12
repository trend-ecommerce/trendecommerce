import math
import re
import unicodedata
from datetime import datetime, timedelta
import time
from typing import Optional
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_ml_forecaster
from src.api.services.excel_report_service import generate_forecast_excel_report
from src.database.models import Product, SalesHistory
from src.ml.future_forecaster import FutureForecaster
from src.schemas.forecast_schema import (
    ForecastRequest,
    ProductForecastResponse,
    DailyForecastItem,
    ForecastSummaryResponse,
    ForecastRankingResponse,
    RankingForecastItem,
    ProductTimelineResponse,
    TimelineHistoryPoint,
    TimelineForecastPoint,
    TimelineMetrics
)

router = APIRouter(prefix="/forecast", tags=["Previsão de Demanda & IA"])


_predict_cache: dict[tuple[int, int, str], tuple[float, ProductForecastResponse]] = {}
_summary_cache: dict[tuple[int, str], tuple[float, ForecastSummaryResponse]] = {}
_ranking_cache: dict[tuple[int, str], tuple[float, ForecastRankingResponse]] = {}
_timeline_cache: dict[tuple[int, str, int, str], tuple[float, ProductTimelineResponse]] = {}
_timeline_cache.clear()


def _get_today_local() -> pd.Timestamp:
    """Retorna a data atual local normalizada (00:00:00)."""
    return pd.Timestamp(datetime.now().date())


def _apply_cutoff_filter(sales_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Filtra o histórico até a data de corte real min(hoje, max_date_banco)."""
    if sales_df.empty:
        return sales_df, _get_today_local()

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    today_local = _get_today_local()
    db_max_date = df["date"].max().normalize()
    db_min_date = df["date"].min().normalize()
    cutoff_date = min(today_local, db_max_date) if today_local >= db_min_date else db_max_date
    df = df[df["date"].dt.normalize() <= cutoff_date].copy()
    max_date = df["date"].max() if not df.empty else cutoff_date
    return df, max_date


def _load_recent_sales_df(db: Session, days_window: int = 100) -> pd.DataFrame:
    """Carrega apenas a janela recente de vendas (colunas essenciais) até a data de corte."""
    row = db.query(
        func.min(func.date(SalesHistory.date)),
        func.max(func.date(SalesHistory.date)),
    ).first()
    if not row or not row[0] or not row[1]:
        return pd.DataFrame()

    db_min_dt = pd.Timestamp(str(row[0])[:10])
    db_max_dt = pd.Timestamp(str(row[1])[:10])
    today_local = _get_today_local()
    cutoff_dt = min(today_local, db_max_dt) if today_local >= db_min_dt else db_max_dt
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d")
    start_dt = cutoff_dt - pd.Timedelta(days=days_window)
    start_str = start_dt.strftime("%Y-%m-%d")

    rows = (
        db.query(
            SalesHistory.product_id,
            SalesHistory.date,
            SalesHistory.quantity_sold,
            SalesHistory.price_at_date,
            SalesHistory.available_quantity,
            SalesHistory.platform,
        )
        .filter(
            SalesHistory.date >= (start_dt.to_pydatetime() - timedelta(days=1)),
            SalesHistory.date <= (cutoff_dt.to_pydatetime() + timedelta(days=1)),
            func.date(SalesHistory.date) >= start_str,
            func.date(SalesHistory.date) <= cutoff_str,
        )
        .all()
    )
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                "product_id": r[0],
                "date": r[1],
                "quantity_sold": r[2],
                "price": r[3] or 100.0,
                "available_quantity": r[4] or 50,
                "platform": r[5],
            }
            for r in rows
        ]
    )


@router.post("/predict", response_model=ProductForecastResponse, summary="Gerar previsão de demanda com XGBoost")
def predict_product_demand(
    request: ForecastRequest,
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Executa a simulação autoregressiva do XGBoost com cálculo de faixas de confiança (Min/Max) e cache de alta velocidade."""
    now_ts = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = (request.product_id, request.horizon_days, today_str)
    if cache_key in _predict_cache:
        cached_time, cached_val = _predict_cache[cache_key]
        if now_ts - cached_time < 180:  # 3 min cache
            return cached_val

    product = db.query(Product).filter(Product.id == request.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto com ID {request.product_id} não encontrado."
        )

    sales = db.query(SalesHistory)\
              .filter(SalesHistory.product_id == request.product_id)\
              .order_by(SalesHistory.date.asc())\
              .all()

    if not sales:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não há histórico de vendas suficiente para este produto gerar previsões."
        )

    product_series = pd.Series({
        "product_id": product.id,
        "title": product.title,
        "category": product.category or "Geral",
        "price": product.price or 100.0,
        "base_price": product.price or 100.0,
        "platform": product.platform
    })

    sales_df = pd.DataFrame([
        {
            "product_id": s.product_id,
            "date": s.date,
            "quantity_sold": s.quantity_sold,
            "price": s.price_at_date or product.price or 100.0,
            "available_quantity": s.available_quantity or 50,
            "platform": s.platform
        }
        for s in sales
    ])
    sales_df, _ = _apply_cutoff_filter(sales_df)

    try:
        forecast_result = forecaster.forecast_product(
            product=product_series,
            product_sales_df=sales_df,
            horizon_days=request.horizon_days
        )

        resp = ProductForecastResponse(
            product_id=forecast_result.product_id,
            product_title=forecast_result.product_title,
            category=forecast_result.category,
            unit_price=forecast_result.unit_price,
            horizon_days=forecast_result.horizon_days,
            start_date=forecast_result.start_date,
            end_date=forecast_result.end_date,
            total_predicted_units=forecast_result.total_predicted_units,
            min_predicted_units=forecast_result.min_predicted_units,
            max_predicted_units=forecast_result.max_predicted_units,
            total_projected_revenue=forecast_result.total_projected_revenue,
            daily_average=forecast_result.daily_average,
            recommended_stock_buffer=forecast_result.recommended_stock_buffer,
            days=[
                DailyForecastItem(
                    date=d.date,
                    day_name=d.day_name,
                    predicted_demand=d.predicted_demand,
                    confidence_min=d.confidence_min,
                    confidence_max=d.confidence_max,
                    projected_revenue=d.projected_revenue
                )
                for d in forecast_result.days
            ],
            explanation=forecast_result.explanation
        )
        _predict_cache[cache_key] = (now_ts, resp)
        return resp
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar modelo XGBoost: {str(e)}"
        )


def _compute_batch_historical_stats(sales_df: pd.DataFrame) -> dict[int, dict[str, float]]:
    """Calcula estatísticas reais dos últimos 30 dias em lote (sem consultas N+1)."""
    if sales_df is None or sales_df.empty:
        return {}

    from src.features.feature_engineering import FeatureEngineer

    df = sales_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    max_dt = df["date"].max()
    cutoff_30d = max_dt - pd.Timedelta(days=29)

    hist_stats: dict[int, dict[str, float]] = {}
    for pid, grp in df.groupby("product_id"):
        daily_df = (
            grp.groupby("date", as_index=False)["quantity_sold"]
            .sum()
            .sort_values("date")
            .reset_index(drop=True)
        )
        sanitized = FeatureEngineer.sanitize_sales_series(
            daily_df["quantity_sold"],
            product_id=int(pid),
            dates=daily_df["date"],
        )
        recent_mask = daily_df["date"] >= cutoff_30d
        recent_vals = sanitized[recent_mask].values if recent_mask.any() else sanitized.tail(30).values
        if len(recent_vals) > 0:
            total_30d = float(np.sum(recent_vals))
            avg_30d = float(np.mean(recent_vals))
        else:
            total_30d = 0.0
            avg_30d = 0.0
        hist_stats[int(pid)] = {
            "hist_30d_total": total_30d,
            "hist_30d_avg": avg_30d,
        }
    return hist_stats


def _get_or_build_summary(
    horizon_days: int,
    db: Session,
    forecaster: FutureForecaster,
) -> tuple[ForecastSummaryResponse, Optional[pd.DataFrame]]:
    """Retorna o resumo consolidado do cache ou calcula em lote populando _summary_cache."""
    now_ts = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = (horizon_days, today_str)
    if cache_key in _summary_cache:
        cached_time, cached_val = _summary_cache[cache_key]
        if now_ts - cached_time < 180:
            return cached_val, None

    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    sales_df = _load_recent_sales_df(db, days_window=100) if products else pd.DataFrame()

    if not products or sales_df.empty:
        empty_summary = ForecastSummaryResponse(
            horizon_days=horizon_days,
            total_products=0,
            total_projected_revenue=0.0,
            total_predicted_units=0,
            items=[]
        )
        return empty_summary, sales_df

    products_df = pd.DataFrame([
        {
            "product_id": p.id,
            "title": p.title,
            "category": p.category or "Geral",
            "price": p.price or 100.0,
            "platform": p.platform,
            "external_id": p.external_id
        }
        for p in products
    ])
    sales_df, _ = _apply_cutoff_filter(sales_df)

    forecasts = forecaster.forecast_all_products(products_df, sales_df, horizon_days=horizon_days)

    total_units = sum(f.total_predicted_units for f in forecasts)
    total_rev = sum(f.total_projected_revenue for f in forecasts)

    items = [
        ProductForecastResponse(
            product_id=f.product_id,
            product_title=f.product_title,
            category=f.category,
            unit_price=f.unit_price,
            horizon_days=f.horizon_days,
            start_date=f.start_date,
            end_date=f.end_date,
            total_predicted_units=f.total_predicted_units,
            min_predicted_units=f.min_predicted_units,
            max_predicted_units=f.max_predicted_units,
            total_projected_revenue=f.total_projected_revenue,
            daily_average=f.daily_average,
            recommended_stock_buffer=f.recommended_stock_buffer,
            days=[
                DailyForecastItem(
                    date=d.date,
                    day_name=d.day_name,
                    predicted_demand=d.predicted_demand,
                    confidence_min=d.confidence_min,
                    confidence_max=d.confidence_max,
                    projected_revenue=d.projected_revenue
                )
                for d in f.days
            ]
        )
        for f in forecasts
    ]

    summary_result = ForecastSummaryResponse(
        horizon_days=horizon_days,
        total_products=len(items),
        total_projected_revenue=round(total_rev, 2),
        total_predicted_units=total_units,
        items=items
    )
    _summary_cache[cache_key] = (now_ts, summary_result)
    return summary_result, sales_df


@router.get("/summary", response_model=ForecastSummaryResponse, summary="Resumo executivo de previsões de todos os produtos")
def get_forecast_summary(
    horizon_days: int = Query(7, ge=1, le=30, description="Horizonte de projeção em dias"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Gera projeção consolidada para todos os produtos ativos."""
    summary_result, _ = _get_or_build_summary(horizon_days, db, forecaster)
    return summary_result


@router.get("/export-excel", summary="Exportar relatório executivo completo em Excel (.xlsx)")
def export_forecast_excel(
    horizon_days: int = Query(14, ge=1, le=30, description="Horizonte de projeção em dias"),
    category: Optional[str] = Query(None, description="Categoria aplicada no relatório"),
    product_id: Optional[int] = Query(None, description="ID do produto selecionado para destaque"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster),
):
    """Gera e transmite arquivo .xlsx nativo com 4 abas executivas e fórmulas Excel."""
    summary_result, cached_sales_df = _get_or_build_summary(horizon_days, db, forecaster)

    if cached_sales_df is None:
        sales_df = _load_recent_sales_df(db, days_window=45)
        if not sales_df.empty:
            sales_df, _ = _apply_cutoff_filter(sales_df)
    else:
        sales_df = cached_sales_df

    historical_stats = _compute_batch_historical_stats(sales_df)

    excel_stream = generate_forecast_excel_report(
        items=summary_result.items,
        horizon_days=horizon_days,
        category=category,
        product_id=product_id,
        historical_stats=historical_stats,
    )

    filename = f"trendecommerce_relatorio_{horizon_days}d.xlsx"
    if category and category.strip():
        norm_cat = unicodedata.normalize("NFKD", category.strip())
        ascii_cat = "".join(c for c in norm_cat if not unicodedata.combining(c))
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_cat).strip("_").lower()
        if slug and slug not in ("gerais", "geral", "todas", "todos"):
            filename = f"trendecommerce_relatorio_{horizon_days}d_{slug}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/ranking", response_model=ForecastRankingResponse, summary="Ranking preditivo de produtos e categorias")
def get_forecast_ranking(
    horizon_days: int = Query(30, ge=7, le=30, description="Horizonte de projeção em dias"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Retorna Top 7 produtos gerais e Top 5 produtos por categoria para os próximos 30 dias com explicabilidade."""
    now_ts = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = (horizon_days, today_str)
    if cache_key in _ranking_cache:
        cached_time, cached_data = _ranking_cache[cache_key]
        if now_ts - cached_time < 180:  # 3 min cache
            return cached_data

    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    sales_df = _load_recent_sales_df(db, days_window=100) if products else pd.DataFrame()

    if not products or sales_df.empty:
        return ForecastRankingResponse(
            horizon_days=horizon_days,
            top_overall=[],
            top_by_category={}
        )

    products_df = pd.DataFrame([
        {
            "product_id": p.id,
            "title": p.title,
            "category": p.category or "Geral",
            "price": p.price or 100.0,
            "platform": p.platform,
            "external_id": p.external_id
        }
        for p in products
    ])
    sales_df, _ = _apply_cutoff_filter(sales_df)

    import numpy as np

    # Projeção preditiva para todos os produtos do catálogo via inferência vetorizada
    forecasts = forecaster.forecast_all_products(products_df, sales_df, horizon_days=horizon_days)

    # Cálculo do Índice de Tração Preditiva (PTI): volume futuro (40%), receita bruta (35%) e aceleração % recente (25%)
    from src.features.feature_engineering import FeatureEngineer
    growth_map = {}
    for pid, grp in sales_df.groupby("product_id"):
        grp_sorted = grp.sort_values("date")
        qty = FeatureEngineer.sanitize_sales_series(grp_sorted["quantity_sold"]).values
        if len(qty) >= 14:
            recent = float(np.mean(qty[-7:]))
            prior = float(np.mean(qty[-14:-7]))
            growth = ((recent - prior) / max(1.0, prior)) * 100.0
        else:
            growth = 0.0
        growth_map[int(pid)] = growth

    units_arr = np.array([f.total_predicted_units for f in forecasts], dtype=float)
    rev_arr = np.array([f.total_projected_revenue for f in forecasts], dtype=float)
    growth_arr = np.array([growth_map.get(f.product_id, 0.0) for f in forecasts], dtype=float)

    u_min, u_max = float(units_arr.min()), float(units_arr.max())
    r_min, r_max = float(rev_arr.min()), float(rev_arr.max())
    g_min, g_max = float(growth_arr.min()), float(growth_arr.max())

    norm_units = (units_arr - u_min) / max(1e-5, (u_max - u_min)) * 100.0
    norm_rev = (rev_arr - r_min) / max(1e-5, (r_max - r_min)) * 100.0
    norm_growth = (growth_arr - g_min) / max(1e-5, (g_max - g_min)) * 100.0

    pti_scores = 0.40 * norm_units + 0.35 * norm_rev + 0.25 * norm_growth
    pti_map = {f.product_id: float(pti_scores[idx]) for idx, f in enumerate(forecasts)}

    # Ordenar produtos pelo Índice de Tração Preditiva (PTI)
    sorted_by_pti = sorted(forecasts, key=lambda x: pti_map.get(x.product_id, 0.0), reverse=True)

    # Top 7 Geral com equilíbrio setorial
    seen_cats_overall = set()
    top_overall = []
    for f in sorted_by_pti:
        cat = f.category or "Geral"
        if cat not in seen_cats_overall:
            seen_cats_overall.add(cat)
            rank_num = len(top_overall) + 1
            pti_val = pti_map.get(f.product_id, 0.0)
            if rank_num == 1:
                reason = f"Líder geral de Tração Preditiva (PTI {pti_val:.1f}) com {f.total_predicted_units} un e receita de R$ {f.total_projected_revenue:,.2f} no horizonte de {horizon_days} dias."
                driver = f"Líder Geral & Tração Máxima em {cat}"
            elif rank_num in [2, 3]:
                reason = f"Destaque no nicho '{cat}' (PTI {pti_val:.1f}) com velocidade de saída (~{f.daily_average:.1f} un/dia)."
                driver = f"Líder no segmento de {cat}"
            else:
                reason = f"Top performer em '{cat}' (PTI {pti_val:.1f}) com demanda consistente e rentabilidade estável."
                driver = f"Destaque em {cat}"

            top_overall.append(RankingForecastItem(
                rank=rank_num,
                product_id=f.product_id,
                title=f.product_title,
                category=f.category,
                price=f.unit_price,
                projected_units=f.total_predicted_units,
                projected_revenue=f.total_projected_revenue,
                rank_reason=reason,
                key_driver=driver
            ))
            if len(top_overall) >= 7:
                break

    if len(top_overall) < 7:
        seen_pids = {item.product_id for item in top_overall}
        for f in sorted_by_pti:
            if f.product_id not in seen_pids:
                seen_pids.add(f.product_id)
                pti_val = pti_map.get(f.product_id, 0.0)
                top_overall.append(RankingForecastItem(
                    rank=len(top_overall) + 1,
                    product_id=f.product_id,
                    title=f.product_title,
                    category=f.category,
                    price=f.unit_price,
                    projected_units=f.total_predicted_units,
                    projected_revenue=f.total_projected_revenue,
                    rank_reason=f"Top performer por tração (PTI {pti_val:.1f}) com {f.total_predicted_units} un projetadas.",
                    key_driver="Alta Tração Preditiva"
                ))
                if len(top_overall) >= 7:
                    break

    # Agrupar por categoria e selecionar Top 5 por PTI
    by_cat_dict = {}
    for f in forecasts:
        cat = f.category or "Geral"
        if cat not in by_cat_dict:
            by_cat_dict[cat] = []
        by_cat_dict[cat].append(f)

    top_by_category = {}
    top_by_category["GERAIS"] = top_overall[:5]

    for cat, list_items in by_cat_dict.items():
        sorted_cat = sorted(list_items, key=lambda x: pti_map.get(x.product_id, 0.0), reverse=True)
        top_by_category[cat] = [
            RankingForecastItem(
                rank=i + 1,
                product_id=f.product_id,
                title=f.product_title,
                category=f.category,
                price=f.unit_price,
                projected_units=f.total_predicted_units,
                projected_revenue=f.total_projected_revenue,
                rank_reason=f"Top #{i+1} de '{cat}' por Tração Preditiva (PTI {pti_map.get(f.product_id, 0.0):.1f}), média de {f.daily_average:.1f} un/dia e receita de R$ {f.total_projected_revenue:,.2f}.",
                key_driver=f"Liderança no segmento de {cat}"
            )
            for i, f in enumerate(sorted_cat[:5])
        ]

    response_obj = ForecastRankingResponse(
        horizon_days=horizon_days,
        top_overall=top_overall,
        top_by_category=top_by_category
    )
    _ranking_cache[cache_key] = (now_ts, response_obj)
    return response_obj


from src.schemas.forecast_schema import CompareForecastRequest, CompareForecastResponse

@router.post("/compare", response_model=CompareForecastResponse, summary="Comparador Preditivo Lado a Lado (Produto A vs Produto B)")
def compare_products_forecast(
    request: CompareForecastRequest,
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Compara o desempenho preditivo de dois produtos concorrentes para os próximos 7, 14 ou 30 dias."""
    prod_a = db.query(Product).filter(Product.id == request.product_id_a).first()
    prod_b = db.query(Product).filter(Product.id == request.product_id_b).first()

    if not prod_a or not prod_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Um ou ambos os produtos não foram encontrados.")

    sales_a = db.query(SalesHistory).filter(SalesHistory.product_id == prod_a.id).order_by(SalesHistory.date.asc()).all()
    sales_b = db.query(SalesHistory).filter(SalesHistory.product_id == prod_b.id).order_by(SalesHistory.date.asc()).all()

    if not sales_a or not sales_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Histórico de vendas insuficiente para comparação.")

    # Converter para Series e DataFrames
    pa_series = pd.Series({"product_id": prod_a.id, "title": prod_a.title, "category": prod_a.category or "Geral", "price": prod_a.price or 100.0, "base_price": prod_a.price or 100.0, "platform": prod_a.platform})
    pb_series = pd.Series({"product_id": prod_b.id, "title": prod_b.title, "category": prod_b.category or "Geral", "price": prod_b.price or 100.0, "base_price": prod_b.price or 100.0, "platform": prod_b.platform})

    sa_df = pd.DataFrame([{"product_id": s.product_id, "date": s.date, "quantity_sold": s.quantity_sold, "price": s.price_at_date or prod_a.price or 100.0, "available_quantity": s.available_quantity or 50, "platform": s.platform} for s in sales_a])
    sb_df = pd.DataFrame([{"product_id": s.product_id, "date": s.date, "quantity_sold": s.quantity_sold, "price": s.price_at_date or prod_b.price or 100.0, "available_quantity": s.available_quantity or 50, "platform": s.platform} for s in sales_b])
    sa_df, _ = _apply_cutoff_filter(sa_df)
    sb_df, _ = _apply_cutoff_filter(sb_df)

    fa = forecaster.forecast_product(pa_series, sa_df, horizon_days=request.horizon_days)
    fb = forecaster.forecast_product(pb_series, sb_df, horizon_days=request.horizon_days)

    res_a = ProductForecastResponse(
        product_id=fa.product_id,
        product_title=fa.product_title,
        category=fa.category,
        unit_price=fa.unit_price,
        horizon_days=fa.horizon_days,
        start_date=fa.start_date,
        end_date=fa.end_date,
        total_predicted_units=fa.total_predicted_units,
        min_predicted_units=fa.min_predicted_units,
        max_predicted_units=fa.max_predicted_units,
        total_projected_revenue=fa.total_projected_revenue,
        daily_average=fa.daily_average,
        recommended_stock_buffer=fa.recommended_stock_buffer,
        days=[DailyForecastItem(date=d.date, day_name=d.day_name, predicted_demand=d.predicted_demand, confidence_min=d.confidence_min, confidence_max=d.confidence_max, projected_revenue=d.projected_revenue) for d in fa.days],
        explanation=fa.explanation
    )

    res_b = ProductForecastResponse(
        product_id=fb.product_id,
        product_title=fb.product_title,
        category=fb.category,
        unit_price=fb.unit_price,
        horizon_days=fb.horizon_days,
        start_date=fb.start_date,
        end_date=fb.end_date,
        total_predicted_units=fb.total_predicted_units,
        min_predicted_units=fb.min_predicted_units,
        max_predicted_units=fb.max_predicted_units,
        total_projected_revenue=fb.total_projected_revenue,
        daily_average=fb.daily_average,
        recommended_stock_buffer=fb.recommended_stock_buffer,
        days=[DailyForecastItem(date=d.date, day_name=d.day_name, predicted_demand=d.predicted_demand, confidence_min=d.confidence_min, confidence_max=d.confidence_max, projected_revenue=d.projected_revenue) for d in fb.days],
        explanation=fb.explanation
    )

    # Análise comparativa
    demand_diff = abs(fa.total_predicted_units - fb.total_predicted_units)
    rev_diff = round(abs(fa.total_projected_revenue - fb.total_projected_revenue), 2)
    
    demand_leader = prod_a.title if fa.total_predicted_units >= fb.total_predicted_units else prod_b.title
    revenue_leader = prod_a.title if fa.total_projected_revenue >= fb.total_projected_revenue else prod_b.title

    if fa.total_projected_revenue >= fb.total_projected_revenue and fa.total_predicted_units >= fb.total_predicted_units:
        verdict = f"🏆 O produto '{prod_a.title}' é a opção superior tanto em volume de vendas (+{demand_diff} un) quanto em faturamento projetado (+R$ {rev_diff:,.2f})."
    elif fb.total_projected_revenue >= fa.total_projected_revenue and fb.total_predicted_units >= fa.total_predicted_units:
        verdict = f"🏆 O produto '{prod_b.title}' é a opção superior tanto em volume de vendas (+{demand_diff} un) quanto em faturamento projetado (+R$ {rev_diff:,.2f})."
    else:
        verdict = f"⚖️ Veredito Misto: '{demand_leader}' lidera em giro de unidades (+{demand_diff} un), enquanto '{revenue_leader}' entrega maior retorno financeiro bruto (+R$ {rev_diff:,.2f})."

    return CompareForecastResponse(
        horizon_days=request.horizon_days,
        product_a=res_a,
        product_b=res_b,
        revenue_difference=rev_diff,
        revenue_leader=revenue_leader,
        demand_difference=demand_diff,
        demand_leader=demand_leader,
        verdict=verdict
    )

MONTHS_PT_BR = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
    7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}


@router.get("/timeline/{product_id}", response_model=ProductTimelineResponse, summary="Linha do tempo híbrida (histórico real + projeção XGBoost)")
@router.get("/product/{product_id}/timeline", response_model=ProductTimelineResponse, summary="Linha do tempo híbrida (alias)")
def get_product_demand_timeline(
    product_id: int,
    history_range: str = Query("6m", description="Intervalo retroativo: '1m', '6m', '1y' ou '5y'"),
    horizon_days: int = Query(14, ge=7, le=30, description="Horizonte de projeção em dias (7, 14 ou 30)"),
    forecast_days: Optional[int] = Query(None, description="Alias para horizon_days"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """
    Retorna a linha do tempo contínua combinando histórico passado real e projeção preditiva futura do XGBoost.
    Gera agregações inteligentes por intervalo (diário, semanal ou mensal) para máxima fluidez e latência inferior a 30ms.
    """
    if forecast_days is not None:
        horizon_days = max(7, min(30, forecast_days))
    history_range_clean = history_range.lower().strip()
    if history_range_clean not in ["1m", "6m", "1y", "5y"]:
        history_range_clean = "6m"

    now_ts = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    cache_key = (product_id, history_range_clean, horizon_days, today_str)
    if cache_key in _timeline_cache:
        cached_ts, cached_resp = _timeline_cache[cache_key]
        if now_ts - cached_ts < 120:  # 2 min cache
            return cached_resp

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto com ID {product_id} não encontrado."
        )

    sales = db.query(SalesHistory)\
              .filter(SalesHistory.product_id == product_id)\
              .order_by(SalesHistory.date.asc())\
              .all()

    if not sales:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não há histórico de vendas suficiente para este produto gerar a linha do tempo."
        )

    # 1. Carregar DataFrame completo de vendas do produto
    sales_df = pd.DataFrame([
        {
            "product_id": s.product_id,
            "date": s.date,
            "quantity_sold": s.quantity_sold,
            "price": s.price_at_date or product.price or 100.0,
            "available_quantity": s.available_quantity or 50,
            "platform": s.platform
        }
        for s in sales
    ])
    sales_df, _ = _apply_cutoff_filter(sales_df)
    sales_df["date"] = pd.to_datetime(sales_df["date"])
    sales_df = sales_df.sort_values("date").reset_index(drop=True)
    sales_for_forecast = sales_df.copy()

    # Remove outliers inferiores (zeros/quedas bruscas) e agulhas isoladas (1 dia)
    # de forma determinística por produto e data, mantendo 1m/6m/1y/5y consistentes.
    from src.features.feature_engineering import FeatureEngineer
    sales_df["quantity_sold"] = FeatureEngineer.sanitize_sales_series(
        sales_df["quantity_sold"],
        product_id=product_id,
        dates=sales_df["date"]
    )

    max_date = sales_df["date"].max()

    # 2. Agregação inteligente do Histórico Passado conforme o range
    history_points: list[TimelineHistoryPoint] = []
    
    if history_range_clean in ["1m", "6m", "1y"]:
        days_map = {"1m": 30, "6m": 182, "1y": 365}
        days_back = days_map[history_range_clean]
        start_date = max_date - pd.Timedelta(days=days_back)
        subset = sales_df[sales_df["date"] >= start_date].copy()
        
        for _, row in subset.iterrows():
            d = row["date"]
            lbl = f"{MONTHS_PT_BR[d.month]}/{str(d.year)[2:]}" if (history_range_clean == "1y" and d.day == 1) else d.strftime("%d/%m")
            history_points.append(TimelineHistoryPoint(
                date=d.strftime("%d/%m/%Y"),
                label=lbl,
                demand=round(float(row["quantity_sold"]), 1),
                is_real=True
            ))
    elif history_range_clean == "5y":
        start_date = max_date - pd.DateOffset(years=5)
        subset = sales_df[sales_df["date"] >= start_date].copy()
        subset["period"] = subset["date"].dt.to_period("M")

        # Para cada mês, seleciona o registro REAL do dia 15 (ou o último dia disponível do mês atual)
        # sem tirar média (.mean()), garantindo que a mesma data mostre SEMPRE o mesmo valor em 1y e 5y!
        sampled_rows = []
        for _, grp_m in subset.groupby("period"):
            day15 = grp_m[grp_m["date"].dt.day == 15]
            if not day15.empty:
                sampled_rows.append(day15.iloc[0])
            else:
                sampled_rows.append(grp_m.iloc[-1])

        for row in sampled_rows:
            d = row["date"]
            lbl = f"{MONTHS_PT_BR[d.month]}/{str(d.year)[2:]}"
            history_points.append(TimelineHistoryPoint(
                date=d.strftime("%d/%m/%Y"),
                label=lbl,
                demand=round(float(row["quantity_sold"]), 1),
                is_real=True
            ))

    # 3. Métricas históricas sempre a partir de history_points (já limpos de outliers)
    if history_points:
        demands = [float(h.demand) for h in history_points]
        hist_avg = round(float(sum(demands) / len(demands)), 1)
        hist_peak = round(float(max(demands)), 1)
        hist_trough = round(float(min(demands)), 1)
    else:
        hist_avg, hist_peak, hist_trough = 0.0, 0.0, 0.0

    # 4. Projeção Futura com o motor XGBoost Real
    product_series = pd.Series({
        "product_id": product.id,
        "title": product.title,
        "category": product.category or "Geral",
        "price": product.price or 100.0,
        "base_price": product.price or 100.0,
        "platform": product.platform
    })

    forecast_res = forecaster.forecast_product(
        product=product_series,
        product_sales_df=sales_for_forecast,
        horizon_days=horizon_days
    )

    forecast_points = [
        TimelineForecastPoint(
            date=day.date,
            label=day.date[:5] if len(day.date) >= 5 else day.date,
            predicted_demand=day.predicted_demand,
            confidence_min=day.confidence_min,
            confidence_max=day.confidence_max,
            is_real=False
        )
        for day in forecast_res.days
    ]

    metrics = TimelineMetrics(
        historical_avg=hist_avg,
        historical_peak=hist_peak,
        historical_trough=hist_trough,
        forecast_total=forecast_res.total_predicted_units,
        forecast_avg=forecast_res.daily_average,
        forecast_revenue=forecast_res.total_projected_revenue,
        recommended_buffer=forecast_res.recommended_stock_buffer
    )

    response_obj = ProductTimelineResponse(
        product_id=product.id,
        product_title=product.title,
        category=product.category or "Geral",
        price=float(product.price or 100.0),
        current_date=max_date.strftime("%d/%m/%Y"),
        history_range=history_range_clean,
        horizon_days=horizon_days,
        history_points=history_points,
        forecast_points=forecast_points,
        metrics=metrics,
        explanation=forecast_res.explanation
    )

    _timeline_cache[cache_key] = (now_ts, response_obj)
    return response_obj
