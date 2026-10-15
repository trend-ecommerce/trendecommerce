import time
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_ml_forecaster
from src.database.models import Product, SalesHistory
from src.ml.future_forecaster import FutureForecaster
from src.schemas.forecast_schema import (
    ForecastRequest,
    ProductForecastResponse,
    DailyForecastItem,
    ForecastSummaryResponse,
    ForecastRankingResponse,
    RankingForecastItem
)

router = APIRouter(prefix="/forecast", tags=["Previsão de Demanda & IA"])


_predict_cache: dict[tuple[int, int], tuple[float, ProductForecastResponse]] = {}
_summary_cache: dict[int, tuple[float, ForecastSummaryResponse]] = {}
_ranking_cache: dict[int, tuple[float, ForecastRankingResponse]] = {}


@router.post("/predict", response_model=ProductForecastResponse, summary="Gerar previsão de demanda com XGBoost")
def predict_product_demand(
    request: ForecastRequest,
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Executa a simulação autoregressiva do XGBoost com cálculo de faixas de confiança (Min/Max) e cache de alta velocidade."""
    now_ts = time.time()
    cache_key = (request.product_id, request.horizon_days)
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


@router.get("/summary", response_model=ForecastSummaryResponse, summary="Resumo executivo de previsões de todos os produtos")
def get_forecast_summary(
    horizon_days: int = Query(7, ge=1, le=30, description="Horizonte de projeção em dias"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Gera projeção consolidada para todos os produtos ativos."""
    now_ts = time.time()
    if horizon_days in _summary_cache:
        cached_time, cached_val = _summary_cache[horizon_days]
        if now_ts - cached_time < 180:
            return cached_val

    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    sales = db.query(SalesHistory).all()

    if not products or not sales:
        return ForecastSummaryResponse(
            horizon_days=horizon_days,
            total_products=0,
            total_projected_revenue=0.0,
            total_predicted_units=0,
            items=[]
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
    sales_df = pd.DataFrame([
        {
            "product_id": s.product_id,
            "date": s.date,
            "quantity_sold": s.quantity_sold,
            "price": s.price_at_date or 100.0,
            "available_quantity": s.available_quantity or 50,
            "platform": s.platform
        }
        for s in sales
    ])

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
    _summary_cache[horizon_days] = (now_ts, summary_result)
    return summary_result


_ranking_cache: dict[int, tuple[float, ForecastRankingResponse]] = {}

@router.get("/ranking", response_model=ForecastRankingResponse, summary="Ranking preditivo de produtos e categorias")
def get_forecast_ranking(
    horizon_days: int = Query(30, ge=7, le=30, description="Horizonte de projeção em dias"),
    db: Session = Depends(get_db),
    forecaster: FutureForecaster = Depends(get_ml_forecaster)
):
    """Retorna Top 7 produtos gerais e Top 5 produtos por categoria para os próximos 30 dias com explicabilidade."""
    now_ts = time.time()
    if horizon_days in _ranking_cache:
        cached_time, cached_data = _ranking_cache[horizon_days]
        if now_ts - cached_time < 180:  # 3 min cache
            return cached_data

    products = db.query(Product).filter(Product.is_active.is_(True)).all()
    sales = db.query(SalesHistory).all()

    if not products or not sales:
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
    sales_df = pd.DataFrame([
        {
            "product_id": s.product_id,
            "date": s.date,
            "quantity_sold": s.quantity_sold,
            "price": s.price_at_date or 100.0,
            "available_quantity": s.available_quantity or 50,
            "platform": s.platform
        }
        for s in sales
    ])

    # Selecionar candidatos líderes por categoria (top 6 por volume histórico) para performance instantânea
    sales_summary = sales_df.groupby("product_id")["quantity_sold"].sum().reset_index()
    merged_candidates = products_df.merge(sales_summary, on="product_id", how="left").fillna(0)
    
    candidate_ids = set()
    for _, cat_group in merged_candidates.groupby("category"):
        top_in_cat = cat_group.sort_values("quantity_sold", ascending=False).head(6)
        candidate_ids.update(top_in_cat["product_id"].tolist())

    filtered_products_df = products_df[products_df["product_id"].isin(candidate_ids)]
    forecasts = forecaster.forecast_all_products(filtered_products_df, sales_df, horizon_days=horizon_days)

    # Ordenar por demanda e faturamento projetado
    sorted_by_demand = sorted(forecasts, key=lambda x: x.total_predicted_units, reverse=True)

    # Top 7 produtos gerais: Líderes Top 1 de cada nicho/categoria
    seen_cats_overall = set()
    top_overall = []
    for f in sorted_by_demand:
        cat = f.category or "Geral"
        if cat not in seen_cats_overall:
            seen_cats_overall.add(cat)
            rank_num = len(top_overall) + 1
            if rank_num == 1:
                reason = f"Líder absoluto de demanda com {f.total_predicted_units} un e faturamento projetado de R$ {f.total_projected_revenue:,.2f} no horizonte de {horizon_days} dias."
                driver = f"Líder Geral & Tração Máxima em {cat}"
            elif rank_num in [2, 3]:
                reason = f"Líder no nicho '{cat}' com altíssima velocidade de saída (~{f.daily_average:.1f} un/dia) e picos nos finais de semana."
                driver = f"Líder no segmento de {cat}"
            else:
                reason = f"Produto #1 no nicho '{cat}' com performance consistente e margem de segurança estável."
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

    # Se ainda houver vagas para 7 e poucas categorias distintas, preenche com os próximos melhores
    if len(top_overall) < 7:
        seen_pids = {item.product_id for item in top_overall}
        for f in sorted_by_demand:
            if f.product_id not in seen_pids:
                seen_pids.add(f.product_id)
                top_overall.append(RankingForecastItem(
                    rank=len(top_overall) + 1,
                    product_id=f.product_id,
                    title=f.product_title,
                    category=f.category,
                    price=f.unit_price,
                    projected_units=f.total_predicted_units,
                    projected_revenue=f.total_projected_revenue,
                    rank_reason=f"Top performer com {f.total_predicted_units} unidades projetadas.",
                    key_driver="Alta Tração de Demanda"
                ))
                if len(top_overall) >= 7:
                    break

    # Agrupar por categoria e pegar top 5 com justificativas
    by_cat_dict = {}
    for f in forecasts:
        cat = f.category or "Geral"
        if cat not in by_cat_dict:
            by_cat_dict[cat] = []
        by_cat_dict[cat].append(f)

    top_by_category = {}
    top_by_category["GERAIS"] = top_overall[:5]

    for cat, list_items in by_cat_dict.items():
        sorted_cat = sorted(list_items, key=lambda x: x.total_predicted_units, reverse=True)
        top_by_category[cat] = [
            RankingForecastItem(
                rank=i + 1,
                product_id=f.product_id,
                title=f.product_title,
                category=f.category,
                price=f.unit_price,
                projected_units=f.total_predicted_units,
                projected_revenue=f.total_projected_revenue,
                rank_reason=f"Top #{i+1} da categoria '{cat}' com média de {f.daily_average:.1f} un/dia e receita de R$ {f.total_projected_revenue:,.2f}.",
                key_driver=f"Liderança no segmento de {cat}"
            )
            for i, f in enumerate(sorted_cat[:5])
        ]

    response_obj = ForecastRankingResponse(
        horizon_days=horizon_days,
        top_overall=top_overall,
        top_by_category=top_by_category
    )
    _ranking_cache[horizon_days] = (now_ts, response_obj)
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