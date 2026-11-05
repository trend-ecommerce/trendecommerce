"""Feature Engineering para o modelo XGBoost.

Transforma dados brutos do histórico de vendas (API_Historico_Vendas) em features
numéricas e temporais que possam ser utilizadas pelo modelo preditivo.

Exemplos de features geradas:
- preco_medio_7_dias
- vendas_7_dias / vendas_30_dias
- crescimento_vendas / crescimento_vendas_7d
- variacao_preco / preco_posicao_range
- dia_semana, mes, sazonalidade cíclica (seno/cosseno)
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Gera features para o modelo XGBoost.
    
    Transforma dados de produtos e histórico de vendas
    em features numéricas e temporais úteis para previsão de demanda.
    """

    def create_sales_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria features baseadas no histórico de vendas.
        
        Args:
            df: DataFrame com colunas ['product_id', 'date', 'quantity_sold', 'price']
            
        Returns:
            DataFrame com features adicionais
        """
        if df.empty:
            return df
        
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        
        # Garantir coluna de preço (pode vir como price_at_date ou price)
        if "price" not in df.columns and "price_at_date" in df.columns:
            df["price"] = df["price_at_date"]
        elif "price" not in df.columns:
            df["price"] = 0.0
            
        df = df.sort_values(["product_id", "date"])
        
        grouped = df.groupby("product_id")
        
        # Vendas - médias móveis
        df["vendas_7_dias"] = grouped["quantity_sold"].transform(
            lambda x: x.rolling(window=7, min_periods=1).sum()
        )
        df["vendas_30_dias"] = grouped["quantity_sold"].transform(
            lambda x: x.rolling(window=30, min_periods=1).sum()
        )
        df["media_vendas_7_dias"] = grouped["quantity_sold"].transform(
            lambda x: x.rolling(window=7, min_periods=1).mean()
        )
        df["media_vendas_30_dias"] = grouped["quantity_sold"].transform(
            lambda x: x.rolling(window=30, min_periods=1).mean()
        )
        
        # Crescimento de vendas
        df["crescimento_vendas"] = grouped["quantity_sold"].transform(
            lambda x: x.pct_change()
        ).fillna(0)
        
        df["crescimento_vendas_7d"] = grouped["quantity_sold"].transform(
            lambda x: x.pct_change(periods=7)
        ).fillna(0)
        
        # Preço - features
        df["preco_medio_7_dias"] = grouped["price"].transform(
            lambda x: x.rolling(window=7, min_periods=1).mean()
        )
        df["variacao_preco"] = grouped["price"].transform(
            lambda x: x.pct_change()
        ).fillna(0)
        
        df["preco_min_30d"] = grouped["price"].transform(
            lambda x: x.rolling(window=30, min_periods=1).min()
        )
        df["preco_max_30d"] = grouped["price"].transform(
            lambda x: x.rolling(window=30, min_periods=1).max()
        )
        
        # Variação de preço em relação ao range
        price_range = df["preco_max_30d"] - df["preco_min_30d"]
        df["preco_posicao_range"] = np.where(
            price_range > 0,
            (df["price"] - df["preco_min_30d"]) / price_range,
            0.5
        )
        
        logger.info(f"Features de vendas criadas: {len(df.columns)} colunas")
        return df

    def create_temporal_features(self, df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        """Cria features temporais a partir da coluna de data.
        
        Args:
            df: DataFrame com coluna de data
            date_col: Nome da coluna de data
            
        Returns:
            DataFrame com features temporais
        """
        if df.empty or date_col not in df.columns:
            return df
        
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        
        df["dia_semana"] = df[date_col].dt.dayofweek
        df["dia_mes"] = df[date_col].dt.day
        df["mes"] = df[date_col].dt.month
        df["semana_ano"] = df[date_col].dt.isocalendar().week.astype(int)
        df["eh_fim_semana"] = (df["dia_semana"] >= 5).astype(int)
        df["eh_inicio_mes"] = (df["dia_mes"] <= 5).astype(int)
        df["eh_fim_mes"] = (df["dia_mes"] >= 25).astype(int)
        
        # Codificação cíclica do dia da semana
        df["dia_semana_sin"] = np.sin(2 * np.pi * df["dia_semana"] / 7)
        df["dia_semana_cos"] = np.cos(2 * np.pi * df["dia_semana"] / 7)
        
        # Codificação cíclica do mês
        df["mes_sin"] = np.sin(2 * np.pi * df["mes"] / 12)
        df["mes_cos"] = np.cos(2 * np.pi * df["mes"] / 12)
        
        return df

    def prepare_for_model(
        self,
        df: pd.DataFrame,
        target_col: str = "quantity_sold",
        exclude_cols: Optional[list[str]] = None
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Prepara os dados para treinamento do XGBoost.
        
        Args:
            df: DataFrame com todas as features
            target_col: Coluna alvo (variável de previsão)
            exclude_cols: Colunas para excluir das features
            
        Returns:
            Tupla (X features, y target)
        """
        if exclude_cols is None:
            exclude_cols = ["date", "product_id", "keyword", "platform", "title", "external_id"]
        
        # Separar target se existir
        if target_col and target_col in df.columns:
            y = df[target_col].copy()
            cols_to_drop_target = [target_col]
        else:
            y = None
            cols_to_drop_target = []
        
        # Remover colunas não-features
        cols_to_drop = [c for c in exclude_cols if c in df.columns] + cols_to_drop_target
        X = df.drop(columns=cols_to_drop, errors="ignore")
        
        # Remover colunas não-numéricas restantes
        X = X.select_dtypes(include=[np.number])
        
        # Preencher NaN
        X = X.fillna(0)
        
        # Substituir infinitos
        X = X.replace([np.inf, -np.inf], 0)
        
        logger.info(f"Dados preparados: {X.shape[0]} amostras, {X.shape[1]} features")
        return X, y
