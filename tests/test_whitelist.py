import pytest
from src.guardian.whitelist import APIWhitelist, AllowedEndpoint


class TestAPIWhitelist:
    """Testes da whitelist de APIs autorizadas."""

    def setup_method(self):
        self.whitelist = APIWhitelist()

    def test_default_endpoints_loaded(self):
        """Verifica se os endpoints padrão foram carregados."""
        endpoints = self.whitelist.list_endpoints()
        assert len(endpoints) > 0

    def test_amazon_catalog_allowed(self):
        """Verifica se o endpoint de catálogo da Amazon está permitido."""
        url = "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_amazon_definitions_allowed(self):
        """Verifica se o endpoint de definições da Amazon está permitido."""
        url = "https://sellingpartnerapi-na.amazon.com/definitions/2020-09-01"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_mercadolivre_search_allowed(self):
        """Verifica se a busca do Mercado Livre está permitida."""
        url = "https://api.mercadolibre.com/sites/MLB/search"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_mercadolivre_items_allowed(self):
        """Verifica se itens do Mercado Livre estão permitidos."""
        url = "https://api.mercadolibre.com/items/MLB123456"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_mercadolivre_categories_allowed(self):
        """Verifica se categorias do Mercado Livre estão permitidas."""
        url = "https://api.mercadolibre.com/sites/MLB/categories"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_mercadolivre_trends_allowed(self):
        """Verifica se tendências do Mercado Livre estão permitidas."""
        url = "https://api.mercadolibre.com/trends/MLB"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_mercadolivre_highlights_allowed(self):
        """Verifica se highlights do Mercado Livre estão permitidos."""
        url = "https://api.mercadolibre.com/highlights/MLB"
        assert self.whitelist.is_allowed(url, "GET") is True

    def test_unknown_api_blocked(self):
        """Verifica se APIs desconhecidas são bloqueadas."""
        url = "https://api.exemplo.com/dados"
        assert self.whitelist.is_allowed(url, "GET") is False

    def test_unauthorized_endpoint_blocked(self):
        """Verifica se endpoints não autorizados são bloqueados."""
        url = "https://api.mercadolibre.com/users/me"
        assert self.whitelist.is_allowed(url, "GET") is False

    def test_post_method_blocked_for_get_only(self):
        """Verifica se método POST é bloqueado em endpoints GET-only."""
        url = "https://api.mercadolibre.com/sites/MLB/search"
        assert self.whitelist.is_allowed(url, "POST") is False

    def test_add_custom_endpoint(self):
        """Verifica adição de endpoint customizado."""
        self.whitelist.add_endpoint(AllowedEndpoint(
            name="Custom API",
            base_url="https://api.custom.com",
            path_pattern="/v1/data",
            methods=["GET", "POST"],
        ))
        assert self.whitelist.is_allowed("https://api.custom.com/v1/data", "GET") is True
        assert self.whitelist.is_allowed("https://api.custom.com/v1/data", "POST") is True

    def test_remove_endpoint(self):
        """Verifica remoção de endpoint."""
        initial_count = len(self.whitelist.list_endpoints())
        self.whitelist.remove_endpoint("Amazon Catalog Items")
        assert len(self.whitelist.list_endpoints()) == initial_count - 1

    def test_get_endpoint_info(self):
        """Verifica obtenção de informações do endpoint."""
        url = "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items"
        info = self.whitelist.get_endpoint_info(url)
        assert info is not None
        assert info.name == "Amazon Catalog Items"
        assert info.requires_auth is True