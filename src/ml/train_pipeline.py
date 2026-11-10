"""Pipeline executável de treinamento do modelo XGBoost de previsão de demanda.

Treina o modelo sobre 100% dos dados históricos (1.25M registros) utilizando
downcasting de tipos para manter o consumo de memória controlado e exporta
os artefatos otimizados para produção no Render.
"""

import sys
import time
import logging
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path caso executado diretamente
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
from src.database.connection import get_engine
from src.features.feature_engineering import FeatureEngineer
from src.ml.trainer import DemandTrainer, load_sales_data_low_memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrainPipeline")


def run_training_pipeline(
    model_output_path: str = "models/xgboost_demand_v1.json",
    sample_limit: int | None = None
) -> dict:
    """Executa o pipeline completo de treinamento e persistência."""
    t0 = time.time()
    logger.info("Iniciando pipeline de treinamento XGBoost...")

    engine = get_engine()
    
    # 1. Ingestão de baixa memória
    logger.info("Carregando histórico de vendas com downcasting de tipos...")
    sales_df = load_sales_data_low_memory(engine)
    if sample_limit and sample_limit < len(sales_df):
        logger.info(f"Aplicando limite de amostragem para teste: {sample_limit} linhas")
        sales_df = sales_df.tail(sample_limit)
        
    logger.info(f"Total de registros carregados: {len(sales_df):,} linhas.")

    # 2. Engenharia de Features
    logger.info("Gerando variáveis de histórico de vendas e temporais...")
    fe = FeatureEngineer()
    df_features = fe.create_sales_features(sales_df)
    df_features = fe.create_temporal_features(df_features)

    # 3. Preparação das matrizes numéricas com float32
    X, y = fe.prepare_for_model(df_features)
    X = X.astype(np.float32)
    y = y.astype(np.float32)
    logger.info(f"Matriz de features preparada: {X.shape[0]:,} amostras, {X.shape[1]} features.")

    # 4. Treinamento
    logger.info("Treinando XGBoost Regressor (100 árvores, max_depth=5, lr=0.08)...")
    trainer = DemandTrainer()
    metrics = trainer.train(X, y, test_size=0.2, random_state=42)

    # 5. Exportação dos artefatos
    logger.info(f"Salvando artefatos em {model_output_path}...")
    trainer.save_model(model_output_path)

    elapsed = time.time() - t0
    logger.info(f"Pipeline concluído com sucesso em {elapsed:.2f} segundos!")
    logger.info(f"Métricas finais -> Test RMSE: {metrics['test_rmse']:.4f} | Test R²: {metrics['test_r2']:.4f} | Test MAE: {metrics['test_mae']:.4f}")

    return {
        "elapsed_seconds": elapsed,
        "metrics": metrics,
        "model_path": model_output_path
    }


if __name__ == "__main__":
    run_training_pipeline()
