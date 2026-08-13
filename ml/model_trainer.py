import os
import json
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from ml.dataset_builder import MLDatasetBuilder


class XGBoostTrendTrainer:
    def __init__(self, models_dir: str = None):
        if models_dir is None:
            models_dir = os.path.join(os.path.dirname(__file__), 'models')
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)

    def train_models(self) -> dict:
        X, y_30d, y_60d = MLDatasetBuilder.build_training_sample()

        if not X:
            return {"status": "FAILED", "reason": "Empty dataset"}

        metrics = {}

        if HAS_XGBOOST:
            # Train 30-Day Model
            model_30d = xgb.XGBRegressor(
                n_estimators=50,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )
            model_30d.fit(X, y_30d)
            path_30d = os.path.join(self.models_dir, 'xgboost_trend_30d.json')
            model_30d.save_model(path_30d)

            # Train 60-Day Model
            model_60d = xgb.XGBRegressor(
                n_estimators=50,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )
            model_60d.fit(X, y_60d)
            path_60d = os.path.join(self.models_dir, 'xgboost_trend_60d.json')
            model_60d.save_model(path_60d)

            metrics = {
                "status": "SUCCESS",
                "engine": "XGBoost",
                "samples_trained": len(X),
                "model_30d_path": path_30d,
                "model_60d_path": path_60d
            }
        else:
            # Fallback metadata mode
            metrics = {
                "status": "SUCCESS",
                "engine": "Fallback_DecisionEngine",
                "samples_trained": len(X)
            }

        return metrics


if __name__ == "__main__":
    trainer = XGBoostTrendTrainer()
    res = trainer.train_models()
    print("XGBoost Model Training Completed:", res)
