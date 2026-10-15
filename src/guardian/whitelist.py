"""Whitelist de APIs autorizadas para o TrendCommerce AI.

Define quais endpoints podem ser acessados pelo sistema.
Endpoints fora da whitelist serão bloqueados pelo Guardian.
"""

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


@dataclass
class AllowedEndpoint:
    """Representa um endpoint autorizado."""
    name: str
    base_url: str
    path_pattern: str
    methods: list[str] = field(default_factory=lambda: ["GET"])
    requires_auth: bool = False
    description: str = ""


class APIWhitelist:
    """Gerencia a whitelist de APIs autorizadas.
    
    Mantém uma lista de endpoints permitidos e fornece
    métodos para verificar se uma URL está autorizada.
    """

    def __init__(self):
        self._endpoints: list[AllowedEndpoint] = []
        self._load_default_whitelist()

    def _load_default_whitelist(self):
        """Carrega a whitelist padrão com as APIs autorizadas."""
        
        # Amazon SP-API - Catalog Items
        self._endpoints.append(AllowedEndpoint(
            name="Amazon Catalog Items",
            base_url="https://sellingpartnerapi-na.amazon.com",
            path_pattern="/catalog/2022-04-01/items",
            methods=["GET"],
            requires_auth=True,
            description="Consulta de catálogo/produtos da Amazon"
        ))
        
        # Amazon SP-API - Product Type Definitions
        self._endpoints.append(AllowedEndpoint(
            name="Amazon Product Type Definitions",
            base_url="https://sellingpartnerapi-na.amazon.com",
            path_pattern="/definitions/2020-09-01",
            methods=["GET"],
            requires_auth=True,
            description="Definições de tipos de produtos da Amazon"
        ))
        
        # Mercado Livre - Search
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Search",
            base_url="https://api.mercadolibre.com",
            path_pattern="/sites/{site_id}/search",
            methods=["GET"],
            requires_auth=False,
            description="Busca de produtos no Mercado Livre"
        ))
        
        # Mercado Livre - Items
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Items",
            base_url="https://api.mercadolibre.com",
            path_pattern="/items/{item_id}",
            methods=["GET"],
            requires_auth=False,
            description="Informações de produtos/anúncios"
        ))
        
        # Mercado Livre - Categories
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Categories",
            base_url="https://api.mercadolibre.com",
            path_pattern="/sites/{site_id}/categories",
            methods=["GET"],
            requires_auth=False,
            description="Categorias do Mercado Livre"
        ))
        
        # Mercado Livre - Trends
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Trends",
            base_url="https://api.mercadolibre.com",
            path_pattern="/trends/{site_id}",
            methods=["GET"],
            requires_auth=False,
            description="Tendências do Mercado Livre"
        ))
        
        # Mercado Livre - Highlights
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Highlights",
            base_url="https://api.mercadolibre.com",
            path_pattern="/highlights/{site_id}",
            methods=["GET"],
            requires_auth=False,
            description="Produtos destacados/populares"
        ))

        # Mercado Livre - Questions (Público)
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Questions",
            base_url="https://api.mercadolibre.com",
            path_pattern="/questions/search",
            methods=["GET"],
            requires_auth=False,
            description="Volume e histórico de perguntas de compradores"
        ))

        # Mercado Livre - Reviews (Público)
        self._endpoints.append(AllowedEndpoint(
            name="Mercado Livre Reviews",
            base_url="https://api.mercadolibre.com",
            path_pattern="/reviews/item/{item_id}",
            methods=["GET"],
            requires_auth=False,
            description="Avaliações e notas médias de produtos"
        ))

        # BrasilAPI - Feriados Nacionais
        self._endpoints.append(AllowedEndpoint(
            name="BrasilAPI Feriados",
            base_url="https://brasilapi.com.br",
            path_pattern="/api/feriados/v1/{ano}",
            methods=["GET"],
            requires_auth=False,
            description="Feriados nacionais brasileiros e pontos facultativos"
        ))

        # Banco Central do Brasil - SGS (Séries Temporais: Dólar PTAX, Selic, IPCA)
        self._endpoints.append(AllowedEndpoint(
            name="BCB SGS Series",
            base_url="https://api.bcb.gov.br",
            path_pattern="/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}",
            methods=["GET"],
            requires_auth=False,
            description="Cotações oficiais diárias do Dólar PTAX, Selic e IPCA"
        ))

        # IBGE - Dados Agregados
        self._endpoints.append(AllowedEndpoint(
            name="IBGE Dados Agregados",
            base_url="https://servicodados.ibge.gov.br",
            path_pattern="/api/v3/agregados",
            methods=["GET"],
            requires_auth=False,
            description="Índices de inflação e comércio varejista do IBGE"
        ))

        # Nager.Date - Feriados Mundiais e Datas Comerciais
        self._endpoints.append(AllowedEndpoint(
            name="Nager Date Holidays",
            base_url="https://date.nager.at",
            path_pattern="/api/v3/PublicHolidays/{year}/{country_code}",
            methods=["GET"],
            requires_auth=False,
            description="Calendário internacional com datas como Black Friday e Cyber Monday"
        ))

        # CoinGecko - Câmbio e Liquidez
        self._endpoints.append(AllowedEndpoint(
            name="CoinGecko Price",
            base_url="https://api.coingecko.com",
            path_pattern="/api/v3/simple/price",
            methods=["GET"],
            requires_auth=False,
            description="Índices de liquidez financeira e câmbio em tempo real"
        ))

        # OpenWeatherMap - Clima & Temperatura
        self._endpoints.append(AllowedEndpoint(
            name="OpenWeatherMap Weather",
            base_url="https://api.openweathermap.org",
            path_pattern="/data/2.5/weather",
            methods=["GET"],
            requires_auth=False,
            description="Temperatura e condições climáticas atuais"
        ))

        # WeatherAPI - Previsão Meteorológica
        self._endpoints.append(AllowedEndpoint(
            name="WeatherAPI Forecast",
            base_url="https://api.weatherapi.com",
            path_pattern="/v1/forecast.json",
            methods=["GET"],
            requires_auth=False,
            description="Histórico e previsão meteorológica por região"
        ))

    def add_endpoint(self, endpoint: AllowedEndpoint):
        """Adiciona um endpoint à whitelist."""
        self._endpoints.append(endpoint)

    def remove_endpoint(self, name: str) -> bool:
        """Remove um endpoint da whitelist pelo nome."""
        original_count = len(self._endpoints)
        self._endpoints = [e for e in self._endpoints if e.name != name]
        return len(self._endpoints) < original_count

    def is_allowed(self, url: str, method: str = "GET") -> bool:
        """Verifica se uma URL está na whitelist.
        
        Args:
            url: URL completa da requisição
            method: Método HTTP (GET, POST, etc.)
            
        Returns:
            True se a URL está autorizada, False caso contrário
        """
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path
        
        for endpoint in self._endpoints:
            if self._matches_base_url(base, endpoint.base_url):
                if self._matches_path(path, endpoint.path_pattern):
                    if method.upper() in endpoint.methods:
                        return True
        return False

    def get_endpoint_info(self, url: str) -> Optional[AllowedEndpoint]:
        """Retorna informações do endpoint se estiver na whitelist."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path
        
        for endpoint in self._endpoints:
            if self._matches_base_url(base, endpoint.base_url):
                if self._matches_path(path, endpoint.path_pattern):
                    return endpoint
        return None

    def list_endpoints(self) -> list[AllowedEndpoint]:
        """Retorna todos os endpoints na whitelist."""
        return list(self._endpoints)

    @staticmethod
    def _matches_base_url(url_base: str, whitelist_base: str) -> bool:
        """Verifica se a base da URL corresponde."""
        return url_base.rstrip("/") == whitelist_base.rstrip("/")

    @staticmethod
    def _matches_path(path: str, pattern: str) -> bool:
        """Verifica se o path corresponde ao padrão (suporta {param})."""
        path_parts = path.strip("/").split("/")
        pattern_parts = pattern.strip("/").split("/")
        
        if len(path_parts) < len(pattern_parts):
            return False
        
        for i, pattern_part in enumerate(pattern_parts):
            if pattern_part.startswith("{") and pattern_part.endswith("}"):
                continue  # Wildcard - aceita qualquer valor
            if i >= len(path_parts) or path_parts[i] != pattern_part:
                return False
        return True
