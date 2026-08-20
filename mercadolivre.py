import urllib.parse
from api_guardian.runtime_guard import guarded_request


class MercadoLivreClient:
    BASE_URL = "https://api.mercadolivre.com"

    def __init__(self, access_token: str = None):
        self.access_token = access_token

    def _get_headers(self) -> dict:
        headers = {"User-Agent": "TrendCommerceAI/1.0"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def search_items(self, query: str, site_id: str = "MLB", limit: int = 50, offset: int = 0) -> dict:
        endpoint = f"/sites/{site_id}/search"
        params = {"q": query, "limit": str(limit), "offset": str(offset)}
        url = f"{self.BASE_URL}{endpoint}?{urllib.parse.urlencode(params)}"
        return guarded_request("GET", url, headers=self._get_headers())

    def get_trends(self, site_id: str = "MLB") -> list:
        endpoint = f"/trends/{site_id}"
        url = f"{self.BASE_URL}{endpoint}"
        return guarded_request("GET", url, headers=self._get_headers())

    def get_highlights(self, category_id: str, site_id: str = "MLB") -> dict:
        endpoint = f"/highlights/{site_id}/category/{category_id}"
        url = f"{self.BASE_URL}{endpoint}"
        return guarded_request("GET", url, headers=self._get_headers())

    def get_item_details(self, item_id: str) -> dict:
        endpoint = f"/items/{item_id}"
        url = f"{self.BASE_URL}{endpoint}"
        return guarded_request("GET", url, headers=self._get_headers())

    def get_categories(self, site_id: str = "MLB") -> list:
        endpoint = f"/sites/{site_id}/categories"
        url = f"{self.BASE_URL}{endpoint}"
        return guarded_request("GET", url, headers=self._get_headers())

    # 1. Nova API 1 Autorizada: Descrição de Item (SEO / Atributos do Produto)
    def get_item_description(self, item_id: str) -> dict:
        endpoint = f"/items/{item_id}/description"
        url = f"{self.BASE_URL}{endpoint}"
        return guarded_request("GET", url, headers=self._get_headers())

    # 2. Nova API 2 Autorizada: Reputação & Métricas de Vendedor
    def get_seller_reputation(self, user_id: str) -> dict:
        endpoint = f"/users/{user_id}"
        url = f"{self.BASE_URL}{endpoint}"
        return guarded_request("GET", url, headers=self._get_headers())
