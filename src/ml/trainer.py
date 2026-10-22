"""Treinamento do modelo XGBoost para previsão de demanda."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score

logger = logging.getLogger(__name__)


class DemandTrainer:
    """Gerencia o treinamento, validação cruzada e persistência do XGBoost."""

    DEFAULT_PARAMS = {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "max_depth": 6,
        "learning_rate": 0.1,
        "n_estimators": 100,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
        "n_jobs": -1,
    }

    def __init__(self, params: Optional[dict[str, Any]] = None):
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.model: Optional[xgb.XGBRegressor] = None
        self.feature_names: list[str] = []
        self.training_metrics: dict[str, float] = {}

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> dict[str, float]:
        """Treina o XGBRegressor e registra métricas de validação."""
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        
        self.feature_names = list(X.columns)
        self.model = xgb.XGBRegressor(**self.params)
        
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
        train_pred = self.model.predict(X_train)
        test_pred = self.model.predict(X_test)
        
        self.training_metrics = {
            "train_rmse": float(np.sqrt(np.mean((y_train - train_pred) ** 2))),
            "test_rmse": float(np.sqrt(np.mean((y_test - test_pred) ** 2))),
            "train_mae": float(np.mean(np.abs(y_train - train_pred))),
            "test_mae": float(np.mean(np.abs(y_test - test_pred))),
            "train_r2": float(self.model.score(X_train, y_train)),
            "test_r2": float(self.model.score(X_test, y_test)),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "n_features": len(self.feature_names),
        }
        
        logger.info(f"Modelo treinado - Test RMSE: {self.training_metrics['test_rmse']:.4f}, Test R²: {self.training_metrics['test_r2']:.4f}")
        return self.training_metrics

    def get_feature_importance(self) -> dict[str, float]:
        """Retorna importância das features."""
        if self.model is None or not hasattr(self.model, "feature_importances_"):
            return {}
        importances = self.model.feature_importances_
        return {
            name: float(imp)
            for name, imp in zip(self.feature_names, importances)
        }

    def cross_validate(self, X: pd.DataFrame, y: pd.Series, cv: int = 5) -> dict[str, float]:
        """Realiza validação cruzada K-Fold."""
        if self.model is None:
            self.model = xgb.XGBRegressor(**self.params)
        
        scores = cross_val_score(
            self.model, X, y, cv=cv, scoring="neg_root_mean_squared_error"
        )
        return {
            "cv_rmse_mean": float(-scores.mean()),
            "cv_rmse_std": float(scores.std()),
            "cv_folds": cv,
        }

    def save_model(self, path: str):
        """Salva os pesos e metadados do modelo."""
        if self.model is None:
            raise ValueError("Nenhum modelo treinado para salvar")
        
        model_path = Path(path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(model_path))
        
        meta_path = model_path.with_suffix(".meta.json")
        metadata = {
            "feature_names": self.feature_names,
            "params": self.params,
            "training_metrics": self.training_metrics,
        }
        meta_path.write_text(json.dumps(metadata, indent=2))
        logger.info(f"Modelo e metadados salvos em {model_path}")

    def load_model(self, path: str):
        """Carrega modelo pré-treinado do disco."""
        model_path = Path(path)
        self.model = xgb.XGBRegressor()
        self.model.load_model(str(model_path))
        
        meta_path = model_path.with_suffix(".meta.json")
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            self.feature_names = metadata.get("feature_names", [])
            self.params = metadata.get("params", self.DEFAULT_PARAMS)
            self.training_metrics = metadata.get("training_metrics", {})
        logger.info(f"Modelo carregado de {model_path}")
