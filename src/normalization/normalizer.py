"""Normalização de dados de diferentes plataformas.

Amazon, Mercado Livre e Google possuem estruturas e métricas
diferentes. Os dados precisam ser normalizados antes do
treinamento do modelo.
"""

import logging
from datetime import datetime
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataNormalizer:
    """Normaliza dados de diferentes plataformas para formato unificado.
    
    Responsável por transformar dados brutos de diferentes
    fontes (Amazon, Mercado Livre, Google) em um formato
    padronizado para armazenamento e processamento.
    """

    # Mapeamento de campos por plataforma
    PLATFORM_MAPPINGS = {
        "amazon": {
            "id_field": "product_id",
            "title_field": "title",
            "price_field": "price",
            "category_field": "category",
        },
        "mercadolivre": {
            "id_field": "product_id",
            "title_field": "title",
            "price_field": "price",
            "category_field": "category_id",
            "sales_field": "sold_quantity",
        },
        "google_trends_mock": {
            "keyword_field": "keyword",
            "interest_field": "interest",
            "date_field": "date",
        },
    }

    def normalize_products(self, raw_data: list[dict], platform: str) -> pd.DataFrame:
        """Normaliza dados de produtos para formato padrão.
        
        Args:
            raw_data: Dados brutos coletados
            platform: Nome da plataforma de origem
            
        Returns:
            DataFrame normalizado
        """
        if not raw_data:
            return pd.DataFrame()
        
        mapping = self.PLATFORM_MAPPINGS.get(platform, {})
        
        normalized = []
        for item in raw_data:
            record = {
                "external_id": str(item.get(mapping.get("id_field", "product_id"), "")),
                "platform": platform,
                "title": str(item.get(mapping.get("title_field", "title"), "")),
                "category": str(item.get(mapping.get("category_field", "category"), "")),
                "price": self._normalize_price(item.get(mapping.get("price_field", "price"))),
                "currency": item.get("currency", "BRL"),
                "collected_at": datetime.now().isoformat(),
            }
            
            # Campos opcionais
            if "sold_quantity" in item:
                record["sold_quantity"] = int(item.get("sold_quantity", 0))
            if "available_quantity" in item:
                record["available_quantity"] = int(item.get("available_quantity", 0))
            if "condition" in item:
                record["condition"] = str(item.get("condition", ""))
            
            normalized.append(record)
        
        df = pd.DataFrame(normalized)
        logger.info(f"Normalizados {len(df)} registros de {platform}")
        return df

    def normalize_trends(self, raw_data: list[dict]) -> pd.DataFrame:
        """Normaliza dados de tendências de pesquisa.
        
        Args:
            raw_data: Dados brutos de tendências
            
        Returns:
            DataFrame normalizado
        """
        if not raw_data:
            return pd.DataFrame()
        
        normalized = []
        for item in raw_data:
            record = {
                "keyword": str(item.get("keyword", "")),
                "date": item.get("date", datetime.now().strftime("%Y-%m-%d")),
                "interest_score": int(item.get("interest", 0)),
                "source": item.get("source", "unknown"),
                "is_mock": item.get("is_mock", False),
            }
            normalized.append(record)
        
        df = pd.DataFrame(normalized)
        
        # Garantir tipo de data
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        
        return df

    def merge_platform_data(
        self, 
        dataframes: dict[str, pd.DataFrame],
        on: str = "external_id"
    ) -> pd.DataFrame:
        """Combina dados de diferentes plataformas.
        
        Args:
            dataframes: Dict com nome da plataforma e DataFrame
            on: Coluna para merge
            
        Returns:
            DataFrame combinado
        """
        combined = pd.DataFrame()
        
        for platform, df in dataframes.items():
            if combined.empty:
                combined = df.copy()
            else:
                combined = pd.concat([combined, df], ignore_index=True)
        
        logger.info(f"Dados combinados: {len(combined)} registros totais")
        return combined

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        """Normaliza um valor de preço."""
        if price is None:
            return None
        try:
            return round(float(price), 2)
        except (ValueError, TypeError):
            return None
