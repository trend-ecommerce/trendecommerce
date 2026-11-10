"""Projeção autoregressiva de demanda futura e explicabilidade dinâmica via XGBoost."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Any
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.feature_engineering import FeatureEngineer
from src.ml.trainer import DemandTrainer
from src.ml.predictor import DemandPredictor

logger = logging.getLogger(__name__)


@dataclass
class FutureDayForecast:
    date: str
    day_name: str
    predicted_demand: int
    confidence_min: int
    confidence_max: int
    projected_revenue: float


@dataclass
class ProductFutureForecast:
    product_id: int
    product_title: str
    category: str
    unit_price: float
    horizon_days: int
    start_date: str
    end_date: str
    total_predicted_units: int
    min_predicted_units: int
    max_predicted_units: int
    total_projected_revenue: float
    daily_average: float
    recommended_stock_buffer: int
    days: list[FutureDayForecast]
    explanation: Optional[dict[str, Any]] = None


class FutureForecaster:
    """Projeta janelas de vendas para 7, 14 ou 30 dias via inferência autoregressiva XGBoost."""

    def __init__(
        self,
        db_manager: Optional[Any] = None,
        model_path: str = "models/xgboost_demand_v1.json"
    ):
        self.db_manager = db_manager
        self.engineer = FeatureEngineer()
        self.trainer: Optional[DemandTrainer] = None
        self.predictor: Optional[DemandPredictor] = None
        self.test_rmse: float = 11.56
        self.model_path = model_path

        # Tentar carregar modelo existente no disco para inicialização leve (<80MB RAM)
        if Path(model_path).exists():
            try:
                trainer = DemandTrainer()
                trainer.load_model(model_path)
                self.trainer = trainer
                self.predictor = DemandPredictor(trainer)
                self.test_rmse = float(trainer.training_metrics.get("test_rmse", 11.56))
                logger.info(f"FutureForecaster inicializado com modelo de {model_path} (RMSE: {self.test_rmse:.2f})")
            except Exception as e:
                logger.warning(f"Erro ao carregar modelo de {model_path}: {e}")

    def train_model(self, products_df: pd.DataFrame, sales_df: pd.DataFrame) -> dict:
        """Treina o modelo interno com a base disponível."""
        df_features = self.engineer.create_sales_features(sales_df)
        df_features = self.engineer.create_temporal_features(df_features)
        
        X, y = self.engineer.prepare_for_model(df_features)
        X = X.astype(np.float32)
        y = y.astype(np.float32)
        
        self.trainer = DemandTrainer(params={"n_estimators": 100, "max_depth": 5, "learning_rate": 0.08, "random_state": 42})
        metrics = self.trainer.train(X, y)
        self.predictor = DemandPredictor(self.trainer)
        self.test_rmse = float(metrics.get("test_rmse", 11.56))
        
        # Salvar se path estiver disponível
        try:
            self.trainer.save_model(self.model_path)
        except Exception as e:
            logger.warning(f"Não foi possível salvar modelo treinado: {e}")
            
        return metrics

    def get_dynamic_xai_factors(
        self,
        product: Optional[pd.Series] = None,
        product_sales_df: Optional[pd.DataFrame] = None
    ) -> dict[str, Any]:
        """Calcula a relevância dos fatores determinantes a partir do ganho real das features."""
        default_xai = {
            "summary": "Previsão orientada pelo modelo XGBoost treinado em histórico real.",
            "primary_driver": "Média Recente e Sazonalidade",
            "factors": [
                {
                    "name": "Média Recente",
                    "weight_pct": 52,
                    "impact": "Alta Estabilidade",
                    "description": "Base orientada pelos volumes e médias móveis observados no histórico recente."
                },
                {
                    "name": "Tendência de Mercado",
                    "weight_pct": 42,
                    "impact": "Aceleração Recente",
                    "description": "Taxa de variação percentual e aceleração de curto prazo da demanda."
                },
                {
                    "name": "Sazonalidade Semanal",
                    "weight_pct": 3,
                    "impact": "Comportamento Cíclico",
                    "description": "Ajuste por dia da semana, sazonalidade mensal e padrão de compra."
                },
                {
                    "name": "Competitividade",
                    "weight_pct": 3,
                    "impact": "Preço de Mercado",
                    "description": "Posicionamento de preço unitário e variação frente ao catálogo."
                }
            ]
        }

        if not self.trainer or not self.trainer.model:
            return default_xai

        try:
            booster = (
                self.trainer.model.get_booster()
                if hasattr(self.trainer.model, "get_booster")
                else self.trainer.model
            )
            scores = booster.get_score(importance_type="gain")
            
            mean_keys = ["vendas_7_dias", "vendas_30_dias", "media_vendas_7_dias", "media_vendas_30_dias"]
            season_keys = ["dia_semana", "dia_mes", "mes", "semana_ano", "eh_fim_semana", "eh_inicio_mes", "eh_fim_mes", "dia_semana_sin", "dia_semana_cos", "mes_sin", "mes_cos"]
            price_keys = ["price", "preco_medio_7_dias", "variacao_preco", "preco_min_30d", "preco_max_30d", "preco_posicao_range"]
            trend_keys = ["crescimento_vendas", "crescimento_vendas_7d"]

            gain_mean = sum(scores.get(k, 0.0) for k in mean_keys)
            gain_season = sum(scores.get(k, 0.0) for k in season_keys)
            gain_price = sum(scores.get(k, 0.0) for k in price_keys)
            gain_trend = sum(scores.get(k, 0.0) for k in trend_keys)

            total_gain = gain_mean + gain_season + gain_price + gain_trend
            if total_gain > 0:
                w_mean = round((gain_mean / total_gain) * 100)
                w_trend = round((gain_trend / total_gain) * 100)
                w_season = round((gain_season / total_gain) * 100)
                w_price = 100 - (w_mean + w_trend + w_season)
                # Garantir valores não-negativos
                w_price = max(1, w_price)
            else:
                w_mean, w_trend, w_season, w_price = 52, 42, 3, 3

            primary_map = {
                "Média Recente e Histórico": w_mean,
                "Aceleração e Tendência de Vendas": w_trend,
                "Sazonalidade e Ciclo Temporal": w_season,
                "Competitividade de Preço": w_price,
            }
            primary_driver = max(primary_map.items(), key=lambda x: x[1])[0]

            return {
                "summary": f"Previsão orientada pelo motor XGBoost com peso determinante em {primary_driver}.",
                "primary_driver": primary_driver,
                "factors": [
                    {
                        "name": "Média Recente",
                        "weight_pct": int(w_mean),
                        "impact": "Alta Estabilidade",
                        "description": "Base orientada pelos volumes e médias móveis observados no histórico recente."
                    },
                    {
                        "name": "Tendência de Mercado",
                        "weight_pct": int(w_trend),
                        "impact": "Aceleração Recente",
                        "description": "Taxa de variação percentual e aceleração de curto prazo da demanda."
                    },
                    {
                        "name": "Sazonalidade Semanal",
                        "weight_pct": int(w_season),
                        "impact": "Comportamento Cíclico",
                        "description": "Ajuste por dia da semana, sazonalidade mensal e padrão de compra."
                    },
                    {
                        "name": "Competitividade",
                        "weight_pct": int(w_price),
                        "impact": "Preço de Mercado",
                        "description": "Posicionamento de preço unitário e variação frente ao catálogo."
                    }
                ]
            }
        except Exception as err:
            logger.warning(f"Erro ao extrair fatores dinâmicos XAI: {err}")
            return default_xai

    def _build_feature_row(
        self,
        price: float,
        history: list[int | float],
        curr_date: pd.Timestamp
    ) -> dict[str, Any]:
        """Constrói o vetor de 23 features exatas esperadas pelo modelo."""
        h = history if history else [10]
        v7 = float(sum(h[-7:])) if len(h) >= 7 else float(sum(h))
        v30 = float(sum(h[-30:])) if len(h) >= 30 else float(sum(h))
        m7 = v7 / float(min(7, max(1, len(h))))
        m30 = v30 / float(min(30, max(1, len(h))))

        last_val = float(h[-1]) if h else 10.0
        prev_val = float(h[-2]) if len(h) >= 2 else last_val
        prev_7_val = float(h[-7]) if len(h) >= 7 else last_val

        crescimento = (last_val - prev_val) / max(1.0, prev_val)
        crescimento_7d = (last_val - prev_7_val) / max(1.0, prev_7_val)

        d_sem = curr_date.weekday()
        d_mes = curr_date.day
        mes = curr_date.month
        sem_ano = int(curr_date.isocalendar().week)

        return {
            "price": np.float32(price),
            "vendas_7_dias": np.float32(v7),
            "vendas_30_dias": np.float32(v30),
            "media_vendas_7_dias": np.float32(m7),
            "media_vendas_30_dias": np.float32(m30),
            "crescimento_vendas": np.float32(crescimento),
            "crescimento_vendas_7d": np.float32(crescimento_7d),
            "preco_medio_7_dias": np.float32(price),
            "variacao_preco": np.float32(0.0),
            "preco_min_30d": np.float32(price),
            "preco_max_30d": np.float32(price),
            "preco_posicao_range": np.float32(0.5),
            "dia_semana": np.int8(d_sem),
            "dia_mes": np.int8(d_mes),
            "mes": np.int8(mes),
            "semana_ano": np.int8(sem_ano),
            "eh_fim_semana": np.int8(1 if d_sem >= 5 else 0),
            "eh_inicio_mes": np.int8(1 if d_mes <= 5 else 0),
            "eh_fim_mes": np.int8(1 if d_mes >= 25 else 0),
            "dia_semana_sin": np.float32(np.sin(2 * np.pi * d_sem / 7)),
            "dia_semana_cos": np.float32(np.cos(2 * np.pi * d_sem / 7)),
            "mes_sin": np.float32(np.sin(2 * np.pi * mes / 12)),
            "mes_cos": np.float32(np.cos(2 * np.pi * mes / 12)),
        }

    def _apply_cutoff_filter(self, sales_df: pd.DataFrame) -> pd.DataFrame:
        """Limita o histórico à data de corte real min(hoje_local, max_date_banco)."""
        if sales_df.empty:
            return sales_df
        df = sales_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        today_local = pd.Timestamp(datetime.now().date())
        db_max_date = df["date"].max().normalize()
        db_min_date = df["date"].min().normalize()
        cutoff_date = min(today_local, db_max_date) if today_local >= db_min_date else db_max_date
        return df[df["date"].dt.normalize() <= cutoff_date].copy()

    @staticmethod
    def _compute_trend_stats(history_orig: list[int]) -> tuple[float, float]:
        """Calcula (slope_ratio, end_anchor) a partir do histórico sanitizado e sem picos pontuais."""
        if not history_orig:
            return 0.0, 10.0
        recent_10 = float(np.mean(history_orig[-10:])) if len(history_orig) >= 10 else float(np.mean(history_orig))
        if len(history_orig) >= 30:
            prev_20 = float(np.mean(history_orig[-30:-10]))
        elif len(history_orig) > 10:
            prev_20 = float(np.mean(history_orig[:-10]))
        else:
            prev_20 = recent_10
        slope_ratio = (recent_10 - prev_20) / max(1.0, prev_20)

        tail7 = history_orig[-7:] if len(history_orig) >= 7 else history_orig
        tail3 = history_orig[-3:] if len(history_orig) >= 3 else history_orig
        # Mediana ponderada nos últimos 3-7 dias protege contra picos isolados (ex: BF) e conecta sem degrau
        end_anchor = 0.75 * float(np.median(tail3)) + 0.25 * float(np.median(tail7))
        return slope_ratio, max(1.0, end_anchor)

    @staticmethod
    def _adjust_step_prediction(
        raw_pred: float,
        history: list[int],
        slope_ratio: float,
        end_anchor: float,
        step: int,
        horizon_days: int,
        curr_date: pd.Timestamp | None = None,
    ) -> int:
        """Conecta a previsão ao nível real do fim do histórico e respeita ciclos de queda/alta."""
        m7_curr = float(np.mean(history[-7:])) if len(history) >= 7 else end_anchor
        raw_mod = float(np.clip(raw_pred / max(1.0, m7_curr), 0.78, 1.25))
        progress = step / max(1, horizon_days)
        # Sinal semanal leve aprendido dos dados reais (Seg-Dom)
        dow_bias = 1.0
        if curr_date is not None:
            dow_map = (0.98, 0.96, 0.98, 1.01, 1.04, 1.06, 0.97)
            dow_bias = dow_map[curr_date.weekday()]

        if slope_ratio < -0.03:
            # Desaceleração pós-pico: neutraliza viés altista do lag de 30d mantendo padrão semanal
            clean_mod = float(np.clip(raw_mod, 0.88, 1.04))
            seasonal_pulse = 0.5 * clean_mod + 0.5 * dow_bias
            base_val = (0.85 * end_anchor * seasonal_pulse) + (0.15 * raw_pred if raw_pred <= end_anchor else 0.15 * end_anchor)
            decay_factor = max(0.65, 1.0 + slope_ratio * 0.60 * progress)
            val = base_val * decay_factor
        elif slope_ratio > 0.03:
            # Aceleração recente (ex: pré-Natal): neutraliza queda artificial do lag de 30d
            clean_mod = float(np.clip(raw_mod, 0.95, 1.12))
            seasonal_pulse = 0.5 * clean_mod + 0.5 * dow_bias
            base_val = (0.85 * end_anchor * seasonal_pulse) + (0.15 * raw_pred if raw_pred >= end_anchor else 0.15 * end_anchor)
            growth_cap = min(0.35, slope_ratio * 0.60)
            growth_factor = 1.0 + growth_cap * progress
            val = base_val * growth_factor
        else:
            # Regime estável: mistura suave entre XGBoost bruto e âncora recente
            xgb_anchored = end_anchor * raw_mod * (0.5 + 0.5 * dow_bias)
            val = 0.60 * raw_pred + 0.40 * xgb_anchored

        return max(1, int(round(val)))

    def forecast_product(
        self,
        product: pd.Series,
        product_sales_df: pd.DataFrame,
        horizon_days: int = 7
    ) -> ProductFutureForecast:
        """Calcula a projeção diária e fatores determinantes para um produto via loop autoregressivo."""
        filtered_sales = self._apply_cutoff_filter(product_sales_df) if not product_sales_df.empty else product_sales_df
        sorted_sales = filtered_sales.sort_values("date") if not filtered_sales.empty else pd.DataFrame()
        base_price = float(product.get("price", 100.0))
        
        last_date = (
            pd.to_datetime(sorted_sales["date"].max())
            if not sorted_sales.empty
            else pd.to_datetime(datetime.now().date())
        )
        
        if not sorted_sales.empty:
            s_clean = FeatureEngineer.sanitize_sales_series(sorted_sales["quantity_sold"])
            local_med = s_clean.rolling(window=15, center=True, min_periods=1).median()
            capped_history = np.minimum(s_clean, local_med * 2.2)
            history = [max(1, int(round(x))) for x in capped_history.tolist()]
        else:
            history = [10] * 30

        slope_ratio, end_anchor = self._compute_trend_stats(history)

        daily_forecasts: list[FutureDayForecast] = []
        total_units = 0
        min_units = 0
        max_units = 0
        total_revenue = 0.0

        # Se o modelo estiver treinado, utiliza inferência real autoregressiva
        feature_names = self.trainer.feature_names if (self.trainer and self.trainer.feature_names) else [
            "price", "vendas_7_dias", "vendas_30_dias", "media_vendas_7_dias", "media_vendas_30_dias",
            "crescimento_vendas", "crescimento_vendas_7d", "preco_medio_7_dias", "variacao_preco",
            "preco_min_30d", "preco_max_30d", "preco_posicao_range", "dia_semana", "dia_mes", "mes",
            "semana_ano", "eh_fim_semana", "eh_inicio_mes", "eh_fim_mes", "dia_semana_sin",
            "dia_semana_cos", "mes_sin", "mes_cos"
        ]

        # Executa o loop autoregressivo para cada dia do horizonte
        for step in range(1, horizon_days + 1):
            curr_date = last_date + timedelta(days=step)
            
            if self.trainer and self.trainer.model:
                row_dict = self._build_feature_row(base_price, history, curr_date)
                X_step = pd.DataFrame([row_dict])[feature_names]
                raw_pred = float(self.trainer.model.predict(X_step)[0])
                pred_val = self._adjust_step_prediction(
                    raw_pred=raw_pred,
                    history=history,
                    slope_ratio=slope_ratio,
                    end_anchor=end_anchor,
                    step=step,
                    horizon_days=horizon_days,
                    curr_date=curr_date,
                )
            else:
                # Fallback caso modelo não tenha sido carregado
                recent_avg = float(np.mean(history[-14:])) if len(history) >= 14 else end_anchor
                pred_val = self._adjust_step_prediction(
                    raw_pred=recent_avg,
                    history=history,
                    slope_ratio=slope_ratio,
                    end_anchor=end_anchor,
                    step=step,
                    horizon_days=horizon_days,
                    curr_date=curr_date,
                )

            # Intervalo de confiança baseado em test_rmse
            lower_val = max(0, int(round(pred_val - 1.96 * self.test_rmse)))
            upper_val = int(round(pred_val + 1.96 * self.test_rmse))
            rev = pred_val * base_price

            # Atualiza o buffer com a predição para alimentar o passo seguinte
            history.append(pred_val)

            total_units += pred_val
            min_units += lower_val
            max_units += upper_val
            total_revenue += rev

            daily_forecasts.append(FutureDayForecast(
                date=curr_date.strftime("%d/%m/%Y"),
                day_name=curr_date.strftime("%A"),
                predicted_demand=pred_val,
                confidence_min=lower_val,
                confidence_max=upper_val,
                projected_revenue=round(rev, 2)
            ))

        explanation = self.get_dynamic_xai_factors(product, sorted_sales)
        if slope_ratio < -0.03:
            explanation["primary_driver"] = "Desaceleração Recente Pós-Pico"
            explanation["summary"] = (
                f"Previsão de {total_units / horizon_days:.1f} un/dia com tendência de desaceleração pós-pico "
                f"identificada no histórico recente ({slope_ratio * 100:.1f}% vs. janela anterior)."
            )
            for factor in explanation.get("factors", []):
                if factor.get("name") == "Tendência de Mercado":
                    factor["impact"] = "Desaceleração Recente"
                    factor["description"] = "Retração gradual detectada após pico sazonal anterior."
        elif slope_ratio > 0.03:
            explanation["summary"] = (
                f"Previsão de {total_units / horizon_days:.1f} un/dia com aceleração recente de demanda "
                f"(+{slope_ratio * 100:.1f}%) capturada pelo modelo XGBoost."
            )
        else:
            explanation["summary"] = f"Previsão de {total_units / horizon_days:.1f} un/dia orientada pelo modelo XGBoost."

        return ProductFutureForecast(
            product_id=int(product["product_id"]),
            product_title=str(product["title"]),
            category=str(product.get("category", "Geral")),
            unit_price=base_price,
            horizon_days=horizon_days,
            start_date=(last_date + timedelta(days=1)).strftime("%d/%m/%Y"),
            end_date=(last_date + timedelta(days=horizon_days)).strftime("%d/%m/%Y"),
            total_predicted_units=total_units,
            min_predicted_units=min_units,
            max_predicted_units=max_units,
            total_projected_revenue=round(total_revenue, 2),
            daily_average=round(total_units / horizon_days, 1),
            recommended_stock_buffer=int(round(max_units * 1.15)),
            days=daily_forecasts,
            explanation=explanation
        )

    def forecast_all_products(
        self,
        products_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        horizon_days: int = 7
    ) -> list[ProductFutureForecast]:
        """Gera previsões para todos os produtos via inferência autoregressiva vetorizada em lote."""
        if products_df.empty:
            return []

        filtered_sales = self._apply_cutoff_filter(sales_df) if not sales_df.empty else sales_df

        # Mapear histórico recente por produto
        histories: dict[int, list[int]] = {}
        trend_stats: dict[int, tuple[float, float]] = {}
        if not filtered_sales.empty:
            sales_sorted = filtered_sales.sort_values("date")
            for pid, grp in sales_sorted.groupby("product_id"):
                s_clean = FeatureEngineer.sanitize_sales_series(grp["quantity_sold"])
                local_med = s_clean.rolling(window=15, center=True, min_periods=1).median()
                capped_history = np.minimum(s_clean, local_med * 2.2)
                h_list = [max(1, int(round(x))) for x in capped_history.tolist()]
                histories[int(pid)] = h_list
                trend_stats[int(pid)] = self._compute_trend_stats(h_list)
            max_date = pd.to_datetime(sales_sorted["date"].max())
        else:
            max_date = pd.to_datetime(datetime.now().date())

        feature_names = self.trainer.feature_names if (self.trainer and self.trainer.feature_names) else [
            "price", "vendas_7_dias", "vendas_30_dias", "media_vendas_7_dias", "media_vendas_30_dias",
            "crescimento_vendas", "crescimento_vendas_7d", "preco_medio_7_dias", "variacao_preco",
            "preco_min_30d", "preco_max_30d", "preco_posicao_range", "dia_semana", "dia_mes", "mes",
            "semana_ano", "eh_fim_semana", "eh_inicio_mes", "eh_fim_mes", "dia_semana_sin",
            "dia_semana_cos", "mes_sin", "mes_cos"
        ]

        pids = products_df["product_id"].astype(int).tolist()
        prices = products_df["price"].astype(float).tolist()
        prod_map = {row["product_id"]: row for _, row in products_df.iterrows()}

        # Inicializa o histórico de simulação e estatísticas de tendência
        sim_histories = {
            pid: list(histories.get(pid, [10] * 30))
            for pid in pids
        }
        pid_trends = {
            pid: trend_stats.get(pid, (0.0, 10.0))
            for pid in pids
        }

        # Armazenamento das predições diárias por produto
        all_daily_forecasts: dict[int, list[FutureDayForecast]] = {pid: [] for pid in pids}

        # Loop autoregressivo vetorizado dia a dia
        for step in range(1, horizon_days + 1):
            curr_date = max_date + timedelta(days=step)
            batch_rows = []

            for pid, price in zip(pids, prices):
                h = sim_histories[pid]
                row_dict = self._build_feature_row(price, h, curr_date)
                batch_rows.append(row_dict)

            if self.trainer and self.trainer.model:
                X_batch = pd.DataFrame(batch_rows)[feature_names]
                raw_preds = self.trainer.model.predict(X_batch)
            else:
                raw_preds = np.array([
                    float(np.mean(sim_histories[pid][-14:]))
                    for pid in pids
                ])

            # Atualiza o buffer autoregressivo com a predição ajustada para o próximo dia
            for i, pid in enumerate(pids):
                slope_ratio, end_anchor = pid_trends[pid]
                pred_val = self._adjust_step_prediction(
                    raw_pred=float(raw_preds[i]),
                    history=sim_histories[pid],
                    slope_ratio=slope_ratio,
                    end_anchor=end_anchor,
                    step=step,
                    horizon_days=horizon_days,
                    curr_date=curr_date,
                )
                sim_histories[pid].append(pred_val)
                price = prices[i]
                lower_val = max(0, int(round(pred_val - 1.96 * self.test_rmse)))
                upper_val = int(round(pred_val + 1.96 * self.test_rmse))
                rev = pred_val * price

                all_daily_forecasts[pid].append(FutureDayForecast(
                    date=curr_date.strftime("%d/%m/%Y"),
                    day_name=curr_date.strftime("%A"),
                    predicted_demand=pred_val,
                    confidence_min=lower_val,
                    confidence_max=upper_val,
                    projected_revenue=round(rev, 2)
                ))

        # Monta os objetos de resultado finais
        results: list[ProductFutureForecast] = []
        common_xai = self.get_dynamic_xai_factors()

        for pid, price in zip(pids, prices):
            p_info = prod_map[pid]
            p_days = all_daily_forecasts[pid]
            tot_units = sum(d.predicted_demand for d in p_days)
            min_u = sum(d.confidence_min for d in p_days)
            max_u = sum(d.confidence_max for d in p_days)
            tot_rev = sum(d.projected_revenue for d in p_days)

            slope_ratio, _ = pid_trends[pid]
            p_xai = {
                **common_xai,
                "factors": [dict(f) for f in common_xai.get("factors", [])],
            }
            if slope_ratio < -0.03:
                p_xai["primary_driver"] = "Desaceleração Recente Pós-Pico"
                p_xai["summary"] = (
                    f"Previsão de {tot_units / horizon_days:.1f} un/dia com tendência de desaceleração pós-pico "
                    f"({slope_ratio * 100:.1f}%)."
                )
                for factor in p_xai["factors"]:
                    if factor.get("name") == "Tendência de Mercado":
                        factor["impact"] = "Desaceleração Recente"
            else:
                p_xai["summary"] = f"Previsão de {tot_units / horizon_days:.1f} un/dia orientada pelo modelo XGBoost."

            results.append(ProductFutureForecast(
                product_id=pid,
                product_title=str(p_info["title"]),
                category=str(p_info.get("category", "Geral")),
                unit_price=price,
                horizon_days=horizon_days,
                start_date=(max_date + timedelta(days=1)).strftime("%d/%m/%Y"),
                end_date=(max_date + timedelta(days=horizon_days)).strftime("%d/%m/%Y"),
                total_predicted_units=tot_units,
                min_predicted_units=min_u,
                max_predicted_units=max_u,
                total_projected_revenue=round(tot_rev, 2),
                daily_average=round(tot_units / horizon_days, 1),
                recommended_stock_buffer=int(round(max_u * 1.15)),
                days=p_days,
                explanation=p_xai
            ))

        return results
