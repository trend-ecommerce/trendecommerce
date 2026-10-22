"""Módulo de comparação e auditoria (Real vs Previsto)."""

import logging
from dataclasses import dataclass
from typing import Optional, Any
import numpy as np
import pandas as pd

from src.features.feature_engineering import FeatureEngineer
from src.ml.trainer import DemandTrainer
from src.ml.predictor import DemandPredictor

logger = logging.getLogger(__name__)


@dataclass
class ValidationRow:
    product_id: int
    product_title: str
    target_date: str
    actual_demand: int
    predicted_demand: float
    error: float
    accuracy_pct: float
    status: str
    hit_interval: bool = True


@dataclass
class ValidationReport:
    total_predictions: int
    hit_rate_pct: float
    mean_accuracy_pct: float
    rmse: float
    mae: float
    rows: list[ValidationRow]


class DemandComparator:
    """Executa backtesting e gera relatórios de auditoria preditiva."""

    def __init__(self, db_manager: Optional[Any] = None):
        self.db_manager = db_manager
        self.engineer = FeatureEngineer()

    def run_backtest_validation(
        self,
        products_df: pd.DataFrame,
        sales_df: pd.DataFrame,
        test_days: int = 7
    ) -> ValidationReport:
        """Compara dados históricos reais contra inferências do modelo."""
        df_features = self.engineer.create_sales_features(sales_df)
        df_features = self.engineer.create_temporal_features(df_features)
        
        df_features["date"] = pd.to_datetime(df_features["date"])
        split_date = df_features["date"].max() - pd.Timedelta(days=test_days)
        
        train_df = df_features[df_features["date"] <= split_date]
        test_df = df_features[df_features["date"] > split_date]
        
        X_train, y_train = self.engineer.prepare_for_model(train_df)
        X_test, y_test = self.engineer.prepare_for_model(test_df)
        
        trainer = DemandTrainer(params={"n_estimators": 50, "max_depth": 4, "random_state": 42})
        trainer.train(X_train, y_train)
        
        predictor = DemandPredictor(trainer)
        preds = predictor.predict(X_test)
        
        validation_rows = []
        test_reset = test_df.reset_index(drop=True)
        
        for idx, row in test_reset.iterrows():
            actual = int(row["quantity_sold"])
            pred = float(preds[idx])
            error = pred - actual
            abs_err = abs(error)
            
            acc = max(0.0, 100.0 - ((abs_err / actual * 100) if actual > 0 else (100.0 if abs_err > 1 else 0.0)))
            hit = (abs_err <= max(1.0, actual * 0.25))
            status = "🎯 EXATO" if abs_err <= 1.0 else ("✅ NA MARGEM" if acc >= 75.0 else "❌ DESVIO")
            
            p_title = products_df[products_df["product_id"] == row["product_id"]]["title"].values
            title_str = str(p_title[0]) if len(p_title) > 0 else f"Produto {row['product_id']}"
            
            validation_rows.append(ValidationRow(
                product_id=int(row["product_id"]),
                product_title=title_str[:30],
                target_date=pd.to_datetime(row["date"]).strftime("%d/%m/%Y"),
                actual_demand=actual,
                predicted_demand=round(pred, 1),
                error=round(error, 1),
                accuracy_pct=round(acc, 1),
                status=status,
                hit_interval=hit
            ))
            
        y_true = np.array([r.actual_demand for r in validation_rows])
        y_pred = np.array([r.predicted_demand for r in validation_rows])
        
        return ValidationReport(
            total_predictions=len(validation_rows),
            hit_rate_pct=round(sum(1 for r in validation_rows if r.accuracy_pct >= 75) / max(1, len(validation_rows)) * 100, 2),
            mean_accuracy_pct=round(float(np.mean([r.accuracy_pct for r in validation_rows])), 2),
            rmse=round(float(np.sqrt(np.mean((y_true - y_pred) ** 2))), 2),
            mae=round(float(np.mean(np.abs(y_true - y_pred))), 2),
            rows=validation_rows
        )

    def format_terminal_table(self, report: ValidationReport) -> str:
        """Formata o relatório de auditoria para o terminal."""
        lines = [
            "=" * 60,
            "RELATÓRIO DE AUDITORIA (Real vs Previsto)",
            "=" * 60,
            f"Total de Previsões: {report.total_predictions}",
            f"Taxa de Acerto na Faixa: {report.hit_rate_pct}%",
            f"Acurácia Média: {report.mean_accuracy_pct}%",
            f"RMSE: {report.rmse} | MAE: {report.mae}",
            "-" * 60,
        ]
        for r in report.rows:
            lines.append(f"{r.product_title} | Data: {r.target_date} | Real: {r.actual_demand} | Previsto: {r.predicted_demand} | Erro: {r.error} | {r.status}")
        lines.append("=" * 60)
        return "\n".join(lines)
