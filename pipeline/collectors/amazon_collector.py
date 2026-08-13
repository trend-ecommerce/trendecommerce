import json
from amazon import AmazonClient
from pipeline.collectors.base_collector import BaseCollector
from pipeline.validators import PayloadValidator
from pipeline.transformers import DataTransformer
from pipeline.resilience import retry_with_backoff


class AmazonCatalogCollector(BaseCollector):
    def __init__(self, lwa_token: str = None, sp_api_role: str = None):
        super().__init__(
            pipeline_name="Amazon_Catalog_Pipeline",
            api_source="Amazon_SP_API",
            endpoint="/catalog/2022-04-01/items"
        )
        self.client = AmazonClient(lwa_token=lwa_token, sp_api_role=sp_api_role)

    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def fetch_data(self, keywords: str = "laptop", marketplace_ids: str = "ATVPDKIKX0DER", **kwargs) -> tuple[dict, str, int]:
        response = self.client.get_catalog_items(keywords=keywords, marketplace_ids=marketplace_ids)
        if hasattr(response, 'read'):
            raw_body = response.read().decode('utf-8')
            payload = json.loads(raw_body)
            status_code = getattr(response, 'status', 200)
            url = getattr(response, 'url', "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items")
        else:
            payload = response if isinstance(response, dict) else {"items": []}
            status_code = 200
            url = "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items"

        return payload, url, status_code

    def validate_payload(self, raw_payload: dict) -> tuple[list, list]:
        return PayloadValidator.validate_amazon_catalog(raw_payload)

    def transform_item(self, item: dict) -> dict:
        return DataTransformer.transform_amazon_item(item)


if __name__ == "__main__":
    collector = AmazonCatalogCollector()
    res = collector.run(keywords="laptop")
    print("Amazon Collector Run Completed:", res)
