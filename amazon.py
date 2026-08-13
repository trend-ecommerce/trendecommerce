import os
from api_guardian.runtime_guard import guarded_request

AMAZON_SP_API_BASE_URL = "https://sellingpartnerapi-na.amazon.com"


class AmazonClient:
    def __init__(self, lwa_token=None, sp_api_role=None):
        self.lwa_token = lwa_token or os.getenv("LWA_TOKEN")
        self.sp_api_role = sp_api_role or os.getenv("SP_API_ROLE")

    def _get_headers(self):
        headers = {}
        if self.lwa_token:
            headers["x-amz-access-token"] = self.lwa_token
        if self.sp_api_role:
            headers["x-amz-security-token"] = self.sp_api_role
        return headers

    def get_catalog_items(self, keywords=None, marketplace_ids=None):
        """
        Fetches Amazon SP-API Catalog Items.
        Endpoint: GET /catalog/2022-04-01/items
        """
        url = f"{AMAZON_SP_API_BASE_URL}/catalog/2022-04-01/items"
        params = {}
        if keywords:
            params["keywords"] = keywords
        if marketplace_ids:
            params["marketplaceIds"] = marketplace_ids

        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers(),
            params=params
        )

    def get_product_type_definition(self, product_type: str):
        """
        Fetches Amazon SP-API Product Type Definitions.
        Endpoint: GET /definitions/2020-09-01/productTypes/{type}
        """
        url = f"{AMAZON_SP_API_BASE_URL}/definitions/2020-09-01/productTypes/{product_type}"
        return guarded_request(
            method="GET",
            url=url,
            headers=self._get_headers()
        )
