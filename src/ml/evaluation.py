"""Avaliação de modelos de previsão de demanda."""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    r2_score,
    mean_absolute_percentage_error,
)

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """Calcula métricas estatísticas de avaliação para regressão de demanda."""

    @staticmethod
    def evaluate(
        y_true: np.ndarray | pd.Series,
        y_pred: np.ndarray | pd.Series
    ) -> dict[str, float]:
        """Calcula RMSE, MAE, MAPE, SMAPE e R2.
        
        Args:
            y_true: Valores reais
            y_pred: Valores previstos
            
        Returns:
            Dict contendo todas as métricas calculadas
        """
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)
        
        metrics = {
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "r2": float(r2_score(y_true, y_pred)),
        }
        
        mask = y_true != 0
        if mask.any():
            metrics["mape"] = float(
                mean_absolute_percentage_error(y_true[mask], y_pred[mask])
            )
        else:
            metrics["mape"] = float("inf")
        
        denominator = (np.abs(y_true) + np.abs(y_pred)) / 2
        mask_smape = denominator > 0
        if mask_smape.any():
            smape = np.mean(
                np.abs(y_true[mask_smape] - y_pred[mask_smape]) / denominator[mask_smape]
            )
            metrics["smape"] = float(smape)
        else:
            metrics["smape"] = 0.0
        
        return metrics

    @staticmethod
    def generate_report(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        feature_importance: Optional[dict[str, float]] = None
    ) -> str:
        """Gera relatório textual formatado para auditoria."""
        metrics = ModelEvaluator.evaluate(y_true, y_pred)
        
        report = []
        report.append("=" * 50)
        report.append("  RELATÓRIO DE AVALIAÇÃO DO MODELO")
        report.append("  TrendEcommerce AI - Previsão de Demanda")
        report.append("=" * 50)
        report.append(f"  RMSE:  {metrics['rmse']:.4f}")
        report.append(f"  MAE:   {metrics['mae']:.4f}")
        report.append(f"  R²:    {metrics['r2']:.4f}")
        report.append(f"  MAPE:  {metrics.get('mape', 'N/A')}")
        report.append(f"  SMAPE: {metrics.get('smape', 'N/A')}")
        report.append("")
        
        if feature_importance:
            report.append("TOP 10 FEATURES MAIS IMPORTANTES:")
            for i, (feat, imp) in enumerate(list(feature_importance.items())[:10], 1):
                report.append(f"  {i:2d}. {feat}: {imp:.4f}")
            report.append("")
            
        report.append("=" * 50)
        return "\n".join(report)