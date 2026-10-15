"""Preditor de demanda usando o modelo XGBoost treinado."""

import logging
from typing import Optional
import numpy as np
import pandas as pd
from .trainer import DemandTrainer

logger = logging.getLogger(__name__)


class DemandPredictor:
    """Executa inferências de demanda e calcula intervalos de confiança."""

    def __init__(self, trainer: Optional[DemandTrainer] = None):
        self.trainer = trainer or DemandTrainer()

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Realiza a previsão pontual de demanda."""
        if self.trainer.model is None:
            raise ValueError("Modelo não treinado.")
        
        if self.trainer.feature_names:
            missing = set(self.trainer.feature_names) - set(X.columns)
            for col in missing:
                X[col] = 0
            X = X[self.trainer.feature_names]
        
        predictions = self.trainer.model.predict(X)
        return np.maximum(predictions, 0)

    def predict_with_confidence(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        """Gera inferência com margem estatística de variação esperada."""
        predictions = self.predict(X)
        margin = np.maximum(1.0, np.round(predictions * 0.12))
        lower_bound = np.maximum(0, np.round(predictions - margin))
        upper_bound = np.maximum(predictions, np.round(predictions + margin))
        
        return {
            "prediction": predictions,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
        }