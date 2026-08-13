import os
from api_guardian.runtime_guard import guarded_request

MERCADO_LIVRE_BASE_URL = "https://api.mercadolibre.com"


class MercadoLivreClient:
    def __init__(self, access_token=None):
        self.access_token = access_token or os.getenv("ACCESS_TOKEN")

    def _get_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def search_items(self, query: str, site_id: str = "MLB"):
        """
        Searches Mercado Livre items.
        Endpoint: GET /sites/MLB/search
        """
        url = f"{MERCADO_LIVRE_BASE_URL}/sites/{site_id}/search"
        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers(),
            params={"q": query}
        )

    def get_item(self, item_id: str):
        """
        Gets details for a specific item.
        Endpoint: GET /items/{item_id}
        """
        url = f"{MERCADO_LIVRE_BASE_URL}/items/{item_id}"
        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers()
        )

    def get_categories(self, site_id: str = "MLB"):
        """
        Gets site categories.
        Endpoint: GET /sites/MLB/categories
        """
        url = f"{MERCADO_LIVRE_BASE_URL}/sites/{site_id}/categories"
        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers()
        )

    def get_trends(self, site_id: str = "MLB"):
        """
        Gets trending searches (Requires OAuth).
        Endpoint: GET /trends/MLB
        """
        url = f"{MERCADO_LIVRE_BASE_URL}/trends/{site_id}"
        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers()
        )

    def get_highlights(self, category_id: str, site_id: str = "MLB"):
        """
        Gets highlighted products for a category (Requires OAuth).
        Endpoint: GET /highlights/MLB/category/{category_id}
        """
        url = f"{MERCADO_LIVRE_BASE_URL}/highlights/{site_id}/category/{category_id}"
        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers()
        )
