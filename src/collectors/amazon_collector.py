"""Coletor de dados da Amazon SP-API.

Utiliza a Amazon Selling Partner API para coletar dados de
catálogo e definições de tipos de produtos.

Endpoints utilizados:
- GET /catalog/2022-04-01/items (Catalog Items)
- GET /definitions/2020-09-01 (Product Type Definitions)
"""

import os
import logging
from typing import Any, Optional

import requests

from .base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class AmazonCollector(BaseCollector):
    """Coletor de dados da Amazon SP-API.
    
    Requer as seguintes variáveis de ambiente:
    - AMAZON_CLIENT_ID
    - AMAZON_CLIENT_SECRET
    - AMAZON_REFRESH_TOKEN
    - AMAZON_MARKETPLACE_ID
    """

    BASE_URL = "https://sellingpartnerapi-na.amazon.com"
    CATALOG_ENDPOINT = "/catalog/2022-04-01/items"
    DEFINITIONS_ENDPOINT = "/definitions/2020-09-01"

    def __init__(self):
        super().__init__(name="Amazon SP-API")
        self.client_id = os.getenv("AMAZON_CLIENT_ID")
        self.client_secret = os.getenv("AMAZON_CLIENT_SECRET")
        self.refresh_token = os.getenv("AMAZON_REFRESH_TOKEN")
        self.marketplace_id = os.getenv("AMAZON_MARKETPLACE_ID")
        self._access_token: Optional[str] = None

    def authenticate(self) -> bool:
        """Autentica com a Amazon SP-API usando OAuth.
        
        A Amazon SP-API utiliza mecanismos de autenticação e
        autorização complexos. As credenciais devem estar
        configuradas via variáveis de ambiente.
        
        Returns:
            True se a autenticação foi bem-sucedida
        """
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            logger.error(
                "Credenciais da Amazon não configuradas. "
                "Configure AMAZON_CLIENT_ID, AMAZON_CLIENT_SECRET e AMAZON_REFRESH_TOKEN."
            )
            self._is_authenticated = False
            return False

        try:
            # Token endpoint da Amazon
            token_url = "https://api.amazon.com/auth/o2/token"
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            
            response = requests.post(token_url, data=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self._access_token = data.get("access_token")
                self._is_authenticated = True
                logger.info("Autenticação com Amazon SP-API bem-sucedida")
                return True
            else:
                logger.error(f"Falha na autenticação: {response.status_code}")
                self._is_authenticated = False
                return False
        except requests.RequestException as e:
            logger.error(f"Erro na autenticação com Amazon: {e}")
            self._is_authenticated = False
            return False

    def collect(self, **kwargs) -> CollectorResult:
        """Coleta dados de catálogo da Amazon.
        
        Kwargs:
            keywords: Termos de busca
            identifiers: Lista de ASINs
            endpoint: 'catalog' ou 'definitions'
            
        Returns:
            Resultado da coleta
        """
        if not self.is_authenticated:
            return self._create_error_result(
                "Não autenticado. Execute authenticate() primeiro."
            )

        endpoint = kwargs.get("endpoint", "catalog")
        
        try:
            if endpoint == "catalog":
                return self._collect_catalog_items(**kwargs)
            elif endpoint == "definitions":
                return self._collect_product_definitions(**kwargs)
            else:
                return self._create_error_result(
                    f"Endpoint não suportado: {endpoint}"
                )
        except requests.RequestException as e:
            logger.error(f"Erro na coleta Amazon: {e}")
            return self._create_error_result(str(e))

    def _collect_catalog_items(
        self, 
        keywords: Optional[str] = None,
        identifiers: Optional[list[str]] = None,
        **kwargs
    ) -> CollectorResult:
        """Coleta itens do catálogo."""
        url = f"{self.BASE_URL}{self.CATALOG_ENDPOINT}"
        
        params = {
            "marketplaceIds": self.marketplace_id,
        }
        
        if keywords:
            params["keywords"] = keywords
        if identifiers:
            params["identifiers"] = ",".join(identifiers)
            params["identifiersType"] = "ASIN"
        
        headers = {
            "x-amz-access-token": self._access_token,
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(
                f"Resposta inválida da Amazon: {response.status_code}"
            )
        
        data = response.json()
        items = data.get("items", [])
        
        # Normalizar dados para formato padrão
        normalized = []
        for item in items:
            normalized.append({
                "source": "amazon",
                "product_id": item.get("asin", ""),
                "title": self._extract_title(item),
                "category": self._extract_category(item),
                "attributes": item.get("attributes", {}),
                "raw_data": item,
            })
        
        return self._create_success_result(normalized)

    def _collect_product_definitions(self, **kwargs) -> CollectorResult:
        """Coleta definições de tipos de produtos."""
        url = f"{self.BASE_URL}{self.DEFINITIONS_ENDPOINT}"
        
        headers = {
            "x-amz-access-token": self._access_token,
            "Content-Type": "application/json",
        }
        
        params = {
            "marketplaceIds": self.marketplace_id,
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if not self.validate_response(response):
            return self._create_error_result(
                f"Resposta inválida: {response.status_code}"
            )
        
        data = response.json()
        definitions = data.get("productTypes", [])
        
        return self._create_success_result(
            [{"source": "amazon", "type": "definitions", "data": definitions}]
        )

    def validate_response(self, response: Any) -> bool:
        """Valida a resposta da API da Amazon."""
        if not hasattr(response, "status_code"):
            return False
        return response.status_code == 200

    @staticmethod
    def _extract_title(item: dict) -> str:
        """Extrai o título do item."""
        summaries = item.get("summaries", [])
        if summaries:
            return summaries[0].get("itemName", "")
        return ""

    @staticmethod
    def _extract_category(item: dict) -> str:
        """Extrai a categoria do item."""
        classifications = item.get("classifications", [])
        if classifications:
            return classifications[0].get("displayName", "")
        return ""
