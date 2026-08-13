import json
from abc import ABC, abstractmethod
from pipeline.execution_tracker import PipelineTracker
from pipeline.repository import DataRepository
from pipeline.schema_drift import SchemaDriftDetector
from pipeline.data_quality import DataQualityChecker
from pipeline.feature_engineering import FeatureEngineer
from pipeline.validators import send_to_quarantine


class BaseCollector(ABC):
    def __init__(self, pipeline_name: str, api_source: str, endpoint: str):
        self.pipeline_name = pipeline_name
        self.api_source = api_source
        self.endpoint = endpoint

    @abstractmethod
    def fetch_data(self, **kwargs) -> dict:
        """Executes API call through API Guardian guarded_request."""
        pass

    @abstractmethod
    def validate_payload(self, raw_payload: dict) -> tuple[list, list]:
        """Validates payload. Returns (valid_items, quarantined_items)."""
        pass

    @abstractmethod
    def transform_item(self, item: dict) -> dict:
        """Transforms a valid raw item into product & price_history entities."""
        pass

    def run(self, **kwargs) -> dict:
        """
        Executes full end-to-end robust data pipeline run.
        """
        with PipelineTracker(self.pipeline_name, self.api_source, self.endpoint) as tracker:
            # 1. Fetch data from API via Guardian
            raw_payload, url, http_status = self.fetch_data(**kwargs)

            # 2. Save raw response into Staging Layer
            DataRepository.save_raw_response(
                execution_id=tracker.run_id,
                api_source=self.api_source,
                endpoint=self.endpoint,
                url=url,
                http_status=http_status,
                payload=json.dumps(raw_payload)
            )

            # 3. Check Schema Drift
            SchemaDriftDetector.check_schema_drift(self.api_source, self.endpoint, raw_payload)

            # 4. Validate Payload Structure
            valid_items, quarantined = self.validate_payload(raw_payload)
            tracker.increment_fetched(len(valid_items) + len(quarantined))

            # Quarantine invalid items
            for q in quarantined:
                send_to_quarantine(
                    execution_id=tracker.run_id,
                    api_source=self.api_source,
                    endpoint=self.endpoint,
                    raw_payload=q.get("item", q),
                    errors=[q.get("reason", "Validation error")]
                )
                tracker.increment_quarantined()

            # 5. Data Quality Checks
            DataQualityChecker.check_volume_anomaly(tracker.run_id, len(valid_items), expected_min=1)
            DataQualityChecker.check_item_quality(tracker.run_id, valid_items)

            # 6. Transform, Idempotent Upsert & Historical Append
            for item in valid_items:
                transformed = self.transform_item(item)
                product_dim = transformed["product"]
                price_entry = transformed["price_history"]

                # Idempotent Upsert into dim_products
                is_new = DataRepository.upsert_product(product_dim)
                if is_new:
                    tracker.increment_inserted()
                else:
                    tracker.increment_updated()

                # Append into price_history ledger
                DataRepository.insert_price_history(price_entry)

                # 7. Generate ML Features for XGBoost
                FeatureEngineer.calculate_daily_features(product_dim["product_id"])

            return {
                "run_id": tracker.run_id,
                "status": "SUCCESS",
                "fetched": tracker.records_fetched,
                "inserted": tracker.records_inserted,
                "updated": tracker.records_updated,
                "quarantined": tracker.records_quarantined
            }
