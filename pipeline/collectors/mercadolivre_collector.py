import json
from mercadolivre import MercadoLivreClient
from pipeline.collectors.base_collector import BaseCollector
from pipeline.validators import PayloadValidator
from pipeline.transformers import DataTransformer
from pipeline.resilience import retry_with_backoff


class MercadoLivreSearchCollector(BaseCollector):
    def __init__(self, access_token: str = None):
        super().__init__(
            pipeline_name="MercadoLivre_Search_Pipeline",
            api_source="MercadoLivre",
            endpoint="/sites/MLB/search"
        )
        self.client = MercadoLivreClient(access_token=access_token)

    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def fetch_data(self, query: str = "notebook", site_id: str = "MLB", **kwargs) -> tuple[dict, str, int]:
        response = self.client.search_items(query=query, site_id=site_id)
        if hasattr(response, 'read'):
            raw_body = response.read().decode('utf-8')
            payload = json.loads(raw_body)
            status_code = getattr(response, 'status', 200)
            url = getattr(response, 'url', f"https://api.mercadolibre.com/sites/{site_id}/search?q={query}")
        else:
            # Mock or mock executor response
            payload = response if isinstance(response, dict) else {"results": []}
            status_code = 200
            url = f"https://api.mercadolibre.com/sites/{site_id}/search?q={query}"

        return payload, url, status_code

    def validate_payload(self, raw_payload: dict) -> tuple[list, list]:
        return PayloadValidator.validate_ml_search(raw_payload)

    def transform_item(self, item: dict) -> dict:
        return DataTransformer.transform_ml_item(item, site_id="MLB")


if __name__ == "__main__":
    collector = MercadoLivreSearchCollector()
    # Sample dry run / mock run test
    res = collector.run(query="smartphone")
    print("Collector Run Completed:", res)
