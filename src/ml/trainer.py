"""Treinamento do modelo XGBoost para previsão de demanda com baixo consumo de memória."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score

logger = logging.getLogger(__name__)


def load_sales_data_low_memory(engine_or_conn) -> pd.DataFrame:
    """Carrega todo o histórico de vendas do banco com downcasting agressivo de tipos.
    
    Otimizado para suportar mais de 1.25 milhão de registros dentro do limite de 512MB do Render.
    """
    query = """
        SELECT product_id, date, quantity_sold, price_at_date as price 
        FROM sales_history 
        ORDER BY product_id, date ASC
    """
    df = pd.read_sql_query(query, engine_or_conn)
    df["product_id"] = df["product_id"].astype("int16")
    df["quantity_sold"] = df["quantity_sold"].astype("int16")
    df["price"] = df["price"].astype("float32")
    try:
        df["date"] = pd.to_datetime(df["date"]).astype("datetime64[D]")
    except Exception:
        df["date"] = pd.to_datetime(df["date"]).astype("datetime64[s]")
    return df


class DemandTrainer:
    """Gerencia o treinamento, validação cruzada e persistência do XGBoost."""

    DEFAULT_PARAMS = {
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "max_depth": 5,
        "learning_rate": 0.08,
        "n_estimators": 100,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "n_jobs": -1,
        "random_state": 42
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
        """Treina o XGBRegressor com 100% dos dados fornecidos e registra métricas de validação."""
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
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "n_features": int(len(self.feature_names)),
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

    def save_model(self, path: str = "models/xgboost_demand_v1.json"):
        """Salva os pesos do modelo e metadados de features."""
        if self.model is None:
            raise ValueError("Nenhum modelo treinado para salvar")
        
        model_path = Path(path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(model_path))
        
        # Salva metadados dedicados
        metadata = {
            "feature_names": self.feature_names,
            "params": self.params,
            "training_metrics": self.training_metrics,
        }
        
        features_meta_path = model_path.parent / "features_metadata.json"
        features_meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        
        meta_path = model_path.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        logger.info(f"Modelo salvo em {model_path} e metadados em {features_meta_path}")

    def load_model(self, path: str = "models/xgboost_demand_v1.json"):
        """Carrega modelo pré-treinado e metadados do disco."""
        model_path = Path(path)
        if not model_path.exists():
            raise FileNotFoundError(f"Arquivo de modelo não encontrado: {model_path}")

        self.model = xgb.XGBRegressor()
        self.model.load_model(str(model_path))
        
        # Tenta carregar metadata
        features_meta_path = model_path.parent / "features_metadata.json"
        meta_path = model_path.with_suffix(".meta.json")
        
        target_meta = features_meta_path if features_meta_path.exists() else meta_path
        if target_meta.exists():
            metadata = json.loads(target_meta.read_text(encoding="utf-8"))
            self.feature_names = metadata.get("feature_names", [])
            self.params = metadata.get("params", self.DEFAULT_PARAMS)
            self.training_metrics = metadata.get("training_metrics", {})
            
        logger.info(f"Modelo carregado de {model_path}")
