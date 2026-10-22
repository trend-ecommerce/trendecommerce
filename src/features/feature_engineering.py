"""Feature Engineering para o modelo XGBoost.

Transforma dados brutos coletados pelas APIs em features
numéricas e categóricas que possam ser utilizadas pelo modelo.

Exemplos de features geradas:
- preco_medio_7_dias
- vendas_7_dias / vendas_30_dias
- crescimento_vendas
- crescimento_pesquisas
- media_pesquisas
- variacao_preco
- tendencia_pesquisa
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Gera features para o modelo XGBoost.
    
    Transforma dados de produtos, vendas e tendências
    em features numéricas úteis para previsão de demanda.
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

    def create_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria features baseadas em tendências de pesquisa.
        
        Args:
            df: DataFrame com colunas ['keyword', 'date', 'interest_score']
            
        Returns:
            DataFrame com features de tendência
        """
        if df.empty:
            return df
        
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["keyword", "date"])
        
        grouped = df.groupby("keyword")
        
        # Médias de pesquisa
        df["media_pesquisas_7d"] = grouped["interest_score"].transform(
            lambda x: x.rolling(window=7, min_periods=1).mean()
        )
        df["media_pesquisas_30d"] = grouped["interest_score"].transform(
            lambda x: x.rolling(window=30, min_periods=1).mean()
        )
        
        # Crescimento de pesquisas
        df["crescimento_pesquisas"] = grouped["interest_score"].transform(
            lambda x: x.pct_change()
        ).fillna(0)
        
        df["crescimento_pesquisas_7d"] = grouped["interest_score"].transform(
            lambda x: x.pct_change(periods=7)
        ).fillna(0)
        
        # Tendência (regressão linear simplificada)
        df["tendencia_pesquisa"] = grouped["interest_score"].transform(
            lambda x: x.rolling(window=7, min_periods=3).apply(
                self._calculate_trend, raw=True
            )
        ).fillna(0)
        
        # Volatilidade
        df["volatilidade_pesquisa"] = grouped["interest_score"].transform(
            lambda x: x.rolling(window=7, min_periods=2).std()
        ).fillna(0)
        
        logger.info(f"Features de tendência criadas: {len(df.columns)} colunas")
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

    def merge_features(
        self,
        sales_df: pd.DataFrame,
        trends_df: pd.DataFrame,
        merge_key: Optional[str] = None,
        date_key: str = "date"
    ) -> pd.DataFrame:
        """Combina features de vendas e tendências.
        
        Args:
            sales_df: DataFrame com features de vendas
            trends_df: DataFrame com features de tendências
            merge_key: Chave para merge (produto/keyword)
            date_key: Coluna de data para merge
            
        Returns:
            DataFrame combinado
        """
        if sales_df.empty:
            return trends_df
        if trends_df.empty:
            return sales_df
        
        # Merge por data
        merged = pd.merge(
            sales_df, 
            trends_df,
            on=date_key,
            how="left",
            suffixes=("_sales", "_trends")
        )
        
        return merged

    def create_exogenous_features(
        self,
        df: pd.DataFrame,
        macro_df: Optional[pd.DataFrame] = None,
        feedbacks_df: Optional[pd.DataFrame] = None,
        date_col: str = "date"
    ) -> pd.DataFrame:
        """Enriquece o DataFrame com variáveis exógenas (Feriados, Dólar PTAX, Selic, Dúvidas de Compradores).
        
        Args:
            df: DataFrame base contendo a coluna de data e produto
            macro_df: DataFrame com indicadores da BrasilAPI, BCB SGS e Nager.Date
            feedbacks_df: DataFrame com métricas de perguntas e avaliações do Mercado Livre
            date_col: Nome da coluna de data
            
        Returns:
            DataFrame enriquecido com covariáveis exógenas
        """
        if df.empty:
            return df

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col]).dt.normalize()

        # 1. Features de Calendário e Feriados
        df["dia_semana"] = df[date_col].dt.dayofweek
        df["is_weekend"] = df["dia_semana"].isin([4, 5, 6]).astype(int)
        df["dia_mes"] = df[date_col].dt.day
        df["mes"] = df[date_col].dt.month

        # Identificar feriados
        holiday_dates = set()
        if macro_df is not None and not macro_df.empty:
            h_rows = macro_df[macro_df["indicator_type"] == "holiday"]
            if not h_rows.empty:
                holiday_dates = set(pd.to_datetime(h_rows["date"]).dt.normalize())

        df["is_holiday"] = df[date_col].isin(holiday_dates).astype(int)

        # Distância aproximada para o próximo feriado (em dias)
        if holiday_dates:
            sorted_holidays = sorted(list(holiday_dates))
            def get_min_dist(d):
                future = [h for h in sorted_holidays if h >= d]
                if future:
                    return (future[0] - d).days
                return 30
            df["days_to_holiday"] = df[date_col].apply(get_min_dist)
        else:
            df["days_to_holiday"] = 15

        # 2. Features Macroeconômicas (Dólar PTAX e Selic do Banco Central)
        if macro_df is not None and not macro_df.empty:
            dolar_rows = macro_df[macro_df["indicator_type"] == "dolar_ptax"].copy()
            if not dolar_rows.empty:
                dolar_rows["date_norm"] = pd.to_datetime(dolar_rows["date"]).dt.normalize()
                dolar_map = dolar_rows.set_index("date_norm")["value"].to_dict()
                df["dolar_ptax"] = df[date_col].map(dolar_map).ffill().bfill().fillna(5.50)
                df["dolar_var_7d"] = df["dolar_ptax"].pct_change(periods=7).fillna(0)
            else:
                df["dolar_ptax"] = 5.50
                df["dolar_var_7d"] = 0.0

            selic_rows = macro_df[macro_df["indicator_type"] == "selic"]
            if not selic_rows.empty:
                df["taxa_selic"] = float(selic_rows["value"].iloc[-1])
            else:
                df["taxa_selic"] = 10.50
        else:
            df["dolar_ptax"] = 5.50
            df["dolar_var_7d"] = 0.0
            df["taxa_selic"] = 10.50

        # 3. Features de Engajamento de Marketplace (Perguntas & Avaliações)
        if feedbacks_df is not None and not feedbacks_df.empty and "product_id" in df.columns:
            fb_summary = feedbacks_df.groupby("product_id").agg({
                "questions_count": "max",
                "average_rating": "mean"
            }).reset_index()
            fb_summary.rename(columns={
                "questions_count": "volume_perguntas_7d",
                "average_rating": "rating_medio"
            }, inplace=True)
            df = pd.merge(df, fb_summary, on="product_id", how="left")
            df["volume_perguntas_7d"] = df["volume_perguntas_7d"].fillna(10)
            df["rating_medio"] = df["rating_medio"].fillna(4.5)
        else:
            df["volume_perguntas_7d"] = 10
            df["rating_medio"] = 4.5

        logger.info(f"Features exógenas criadas. Total colunas: {len(df.columns)}")
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

    @staticmethod
    def _calculate_trend(values: np.ndarray) -> float:
        """Calcula tendência via regressão linear."""
        if len(values) < 2:
            return 0.0
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        return float(coeffs[0])
