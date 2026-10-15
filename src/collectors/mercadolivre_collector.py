"""Coletor de dados da API do Mercado Livre.

Endpoints utilizados:
- Search: busca de produtos
- Items: informações de produtos/anúncios
- Categories: categorias
- Trends: tendências
- Highlights: produtos destacados
"""

import os
import logging
from typing import Any, Optional

import requests

from .base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class MercadoLivreCollector(BaseCollector):
    """Coletor de dados do Mercado Livre.
    
    Alguns endpoints são públicos (não requerem autenticação),
    outros requerem OAuth.
    
    Variáveis de ambiente opcionais:
    - MELI_APP_ID
    - MELI_CLIENT_SECRET
    - MELI_ACCESS_TOKEN
    """

    BASE_URL = "https://api.mercadolibre.com"
    DEFAULT_SITE_ID = "MLB"  # Brasil

    def __init__(self, site_id: str = "MLB"):
        super().__init__(name="Mercado Livre")
        self.site_id = site_id
        self.app_id = os.getenv("MELI_APP_ID")
        self.client_secret = os.getenv("MELI_CLIENT_SECRET")
        self.access_token = os.getenv("MELI_ACCESS_TOKEN")

    def authenticate(self) -> bool:
        """Autentica com a API do Mercado Livre.
        
        Muitos endpoints são públicos. A autenticação é necessária
        apenas para endpoints que requerem OAuth.
        
        Returns:
            True (endpoints públicos não requerem autenticação)
        """
        # Verificar se temos credenciais para endpoints autenticados
        if self.access_token:
            self._is_authenticated = True
            logger.info("Token de acesso do Mercado Livre configurado")
        else:
            # Endpoints públicos funcionam sem autenticação
            self._is_authenticated = True
            logger.info(
                "Mercado Livre: usando apenas endpoints públicos "
                "(sem token de acesso configurado)"
            )
        return True

    def collect(self, **kwargs) -> CollectorResult:
        """Coleta dados do Mercado Livre.
        
        Kwargs:
            endpoint: 'search', 'items', 'categories', 'trends', 'highlights'
            query: Termo de busca (para search)
            item_id: ID do item (para items)
            category_id: ID da categoria
            
        Returns:
            Resultado da coleta
        """
        endpoint = kwargs.get("endpoint", "search")
        
        try:
            collectors = {
                "search": self._collect_search,
                "items": self._collect_items,
                "categories": self._collect_categories,
                "trends": self._collect_trends,
                "highlights": self._collect_highlights,
            }
            
            collector_fn = collectors.get(endpoint)
            if not collector_fn:
                return self._create_error_result(
                    f"Endpoint não suportado: {endpoint}"
                )
            
            return collector_fn(**kwargs)
        except requests.RequestException as e:
            logger.error(f"Erro na coleta Mercado Livre: {e}")
            return self._create_error_result(str(e))

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    def _collect_search(self, query: str = "", **kwargs) -> CollectorResult:
        """Busca produtos no Mercado Livre."""
        if not query:
            return self._create_error_result("Parâmetro 'query' é obrigatório para busca")
        
        url = f"{self.BASE_URL}/sites/{self.site_id}/search"
        params = {
            "q": query,
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
        }
        
        headers = self.DEFAULT_HEADERS.copy()
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(f"Erro na busca: {response.status_code}")
        
        data = response.json()
        results = data.get("results", [])
        
        normalized = []
        for item in results:
            normalized.append({
                "source": "mercadolivre",
                "product_id": item.get("id", ""),
                "title": item.get("title", ""),
                "price": item.get("price", 0),
                "currency": item.get("currency_id", "BRL"),
                "category_id": item.get("category_id", ""),
                "sold_quantity": item.get("sold_quantity", 0),
                "available_quantity": item.get("available_quantity", 0),
                "condition": item.get("condition", ""),
                "permalink": item.get("permalink", ""),
                "raw_data": item,
            })
        
        return self._create_success_result(normalized)

    def _collect_items(self, item_id: str = "", **kwargs) -> CollectorResult:
        """Coleta informações de um item específico."""
        if not item_id:
            return self._create_error_result("Parâmetro 'item_id' é obrigatório")
        
        url = f"{self.BASE_URL}/items/{item_id}"
        headers = self.DEFAULT_HEADERS.copy()
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        response = requests.get(url, headers=headers, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(f"Erro ao buscar item: {response.status_code}")
        
        data = response.json()
        normalized = [{
            "source": "mercadolivre",
            "product_id": data.get("id", ""),
            "title": data.get("title", ""),
            "price": data.get("price", 0),
            "currency": data.get("currency_id", "BRL"),
            "category_id": data.get("category_id", ""),
            "sold_quantity": data.get("sold_quantity", 0),
            "available_quantity": data.get("available_quantity", 0),
            "condition": data.get("condition", ""),
            "raw_data": data,
        }]
        
        return self._create_success_result(normalized)

    def _collect_categories(self, **kwargs) -> CollectorResult:
        """Coleta categorias do Mercado Livre."""
        category_id = kwargs.get("category_id")
        
        if category_id:
            url = f"{self.BASE_URL}/categories/{category_id}"
        else:
            url = f"{self.BASE_URL}/sites/{self.site_id}/categories"
        
        response = requests.get(url, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(f"Erro ao buscar categorias: {response.status_code}")
        
        data = response.json()
        
        if isinstance(data, list):
            normalized = [
                {
                    "source": "mercadolivre",
                    "category_id": cat.get("id", ""),
                    "name": cat.get("name", ""),
                }
                for cat in data
            ]
        else:
            normalized = [{
                "source": "mercadolivre",
                "category_id": data.get("id", ""),
                "name": data.get("name", ""),
                "children_categories": data.get("children_categories", []),
            }]
        
        return self._create_success_result(normalized)

    def _collect_trends(self, **kwargs) -> CollectorResult:
        """Coleta tendências do Mercado Livre."""
        category_id = kwargs.get("category_id", "")
        
        if category_id:
            url = f"{self.BASE_URL}/trends/{self.site_id}/{category_id}"
        else:
            url = f"{self.BASE_URL}/trends/{self.site_id}"
        
        response = requests.get(url, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(f"Erro ao buscar tendências: {response.status_code}")
        
        data = response.json()
        
        if isinstance(data, list):
            normalized = [
                {
                    "source": "mercadolivre",
                    "type": "trend",
                    "keyword": item.get("keyword", ""),
                    "url": item.get("url", ""),
                }
                for item in data
            ]
        else:
            normalized = [{"source": "mercadolivre", "type": "trend", "data": data}]
        
        return self._create_success_result(normalized)

    def _collect_highlights(self, **kwargs) -> CollectorResult:
        """Coleta produtos destacados do Mercado Livre."""
        url = f"{self.BASE_URL}/highlights/{self.site_id}"
        
        response = requests.get(url, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(f"Erro ao buscar highlights: {response.status_code}")
        
        data = response.json()
        
        if isinstance(data, dict):
            content = data.get("content", [])
            normalized = [
                {
                    "source": "mercadolivre",
                    "type": "highlight",
                    "data": item,
                }
                for item in content
            ]
        else:
            normalized = [{"source": "mercadolivre", "type": "highlight", "data": data}]
        
        return self._create_success_result(normalized)

    def validate_response(self, response: Any) -> bool:
        """Valida a resposta da API do Mercado Livre."""
        if not hasattr(response, "status_code"):
            return False
        return response.status_code == 200
