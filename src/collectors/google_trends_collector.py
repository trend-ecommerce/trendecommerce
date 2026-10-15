"""Coletor de dados de tendências de pesquisa.

NOTA IMPORTANTE: O Google Trends não disponibiliza uma API pública
oficial simples e gratuita equivalente a uma API convencional.

Este coletor serve como uma interface preparada para quando houver
uma fonte autorizada de dados de tendências de pesquisa disponível.

A utilização de dados de pesquisa deve respeitar as condições de
uso da fonte.
"""

import logging
from typing import Any, Optional
from datetime import datetime, timedelta

from .base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class GoogleTrendsCollector(BaseCollector):
    """Coletor de dados de tendências de pesquisa.
    
    ATENÇÃO: Este coletor é uma interface preparatória.
    O Google Trends não possui uma API pública oficial
    gratuita para este tipo de uso.
    
    Quando uma fonte autorizada estiver disponível, este
    coletor será atualizado para utilizá-la.
    
    Por enquanto, pode ser utilizado com dados simulados
    para desenvolvimento e testes do pipeline.
    """

    def __init__(self):
        super().__init__(name="Google Trends")
        self._data_source_available = False

    def authenticate(self) -> bool:
        """Verifica disponibilidade da fonte de dados.
        
        Returns:
            True (preparado, mas sem fonte real)
        """
        logger.warning(
            "GoogleTrendsCollector: Nenhuma API oficial pública disponível. "
            "Utilize dados simulados para desenvolvimento ou configure "
            "uma fonte de dados autorizada."
        )
        self._is_authenticated = True
        return True

    def collect(self, **kwargs) -> CollectorResult:
        """Coleta dados de tendências.
        
        Kwargs:
            keywords: Lista de palavras-chave
            start_date: Data inicial (YYYY-MM-DD)
            end_date: Data final (YYYY-MM-DD)
            use_mock: Se True, retorna dados simulados
            
        Returns:
            Resultado da coleta
        """
        use_mock = kwargs.get("use_mock", True)
        
        if use_mock:
            return self._collect_mock_data(**kwargs)
        
        if not self._data_source_available:
            return self._create_error_result(
                "Fonte de dados de tendências não disponível. "
                "O Google Trends não possui API pública oficial. "
                "Use use_mock=True para dados simulados."
            )
        
        return self._create_error_result("Fonte de dados não configurada")

    def _collect_mock_data(
        self, 
        keywords: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> CollectorResult:
        """Gera dados simulados de tendências para desenvolvimento.
        
        Os dados simulados permitem testar o pipeline completo
        sem depender de uma API externa.
        """
        if not keywords:
            keywords = ["notebook", "smartphone", "tablet"]
        
        if not end_date:
            end = datetime.now()
        else:
            end = datetime.fromisoformat(end_date)
        
        if not start_date:
            start = end - timedelta(days=30)
        else:
            start = datetime.fromisoformat(start_date)
        
        import random
        random.seed(42)  # Reprodutibilidade
        
        normalized = []
        current = start
        
        while current <= end:
            for keyword in keywords:
                # Gerar interesse simulado (0-100)
                base_interest = random.randint(20, 80)
                trend_factor = random.uniform(0.8, 1.2)
                interest = min(100, int(base_interest * trend_factor))
                
                normalized.append({
                    "source": "google_trends_mock",
                    "type": "search_trend",
                    "keyword": keyword,
                    "date": current.strftime("%Y-%m-%d"),
                    "interest": interest,
                    "is_mock": True,
                })
            
            current += timedelta(days=1)
        
        logger.info(
            f"Dados simulados gerados: {len(normalized)} registros "
            f"para {len(keywords)} keywords"
        )
        
        return self._create_success_result(normalized)

    def validate_response(self, response: Any) -> bool:
        """Valida resposta (placeholder)."""
        return response is not None
