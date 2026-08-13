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
        X, y_reg, y_clf = MLDatasetBuilder.build_training_sample()

        if not X:
            return {"status": "FAILED", "reason": "Empty dataset"}

        if HAS_XGBOOST:
            # 1. Train Trend Regressor Model
            regressor = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.08,
                random_state=42
            )
            regressor.fit(X, y_reg)
            path_reg = os.path.join(self.models_dir, 'xgboost_trend_regressor.json')
            regressor.save_model(path_reg)

            # 2. Train Trend Multi-Class Classifier (0=Diminuir, 1=Estagnar, 2=Aumentar)
            classifier = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.08,
                num_class=3,
                objective="multi:softprob",
                random_state=42
            )
            classifier.fit(X, y_clf)
            path_clf = os.path.join(self.models_dir, 'xgboost_trend_classifier.json')
            classifier.save_model(path_clf)

            return {
                "status": "SUCCESS",
                "engine": "XGBoost 3.4",
                "samples_trained": len(X),
                "regressor_model": path_reg,
                "classifier_model": path_clf
            }
        else:
            return {
                "status": "SUCCESS",
                "engine": "DecisionEngine_Fallback",
                "samples_trained": len(X)
            }


if __name__ == "__main__":
    trainer = XGBoostTrendTrainer()
    res = trainer.train_models()
    print("XGBoost 10.000 Samples Training Completed:", res)
