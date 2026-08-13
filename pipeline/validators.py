import json
from db.connection import get_db_connection, is_mock_mode


class PayloadValidator:
    @staticmethod
    def validate_ml_search(payload: dict) -> tuple[list, list]:
        """
        Validates Mercado Livre search payload.
        Returns (valid_items, quarantined_items).
        """
        valid_items = []
        quarantined = []

        if not isinstance(payload, dict):
            return [], [{"payload": payload, "reason": "Payload is not a dictionary"}]

        results = payload.get("results")
        if not isinstance(results, list):
            return [], [{"payload": payload, "reason": "Missing or non-list 'results' field"}]

        for item in results:
            if not isinstance(item, dict):
                quarantined.append({"item": item, "reason": "Item is not a dictionary"})
                continue

            item_id = item.get("id")
            title = item.get("title")
            price = item.get("price")

            errors = []
            if not item_id or not isinstance(item_id, str):
                errors.append("Invalid or missing 'id'")
            if not title or not isinstance(title, str):
                errors.append("Invalid or missing 'title'")
            if price is None or not isinstance(price, (int, float)) or price < 0:
                errors.append("Invalid or missing 'price'")

            if errors:
                quarantined.append({"item": item, "reason": "; ".join(errors)})
            else:
                valid_items.append(item)

        return valid_items, quarantined

    @staticmethod
    def validate_amazon_catalog(payload: dict) -> tuple[list, list]:
        """
        Validates Amazon Catalog Items payload.
        Returns (valid_items, quarantined_items).
        """
        valid_items = []
        quarantined = []

        if not isinstance(payload, dict):
            return [], [{"payload": payload, "reason": "Payload is not a dictionary"}]

        items = payload.get("items", [])
        if not isinstance(items, list):
            return [], [{"payload": payload, "reason": "Missing or non-list 'items' field"}]

        for item in items:
            if not isinstance(item, dict):
                quarantined.append({"item": item, "reason": "Item is not a dictionary"})
                continue

            asin = item.get("asin")
            if not asin or not isinstance(asin, str):
                quarantined.append({"item": item, "reason": "Missing or invalid 'asin'"})
            else:
                valid_items.append(item)

        return valid_items, quarantined


def send_to_quarantine(execution_id: str, api_source: str, endpoint: str, raw_payload: dict, errors: list):
    """Saves invalid records into quarantine_records table."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quarantine_records (execution_id, api_source, endpoint, raw_payload, validation_errors)
                VALUES (%s, %s, %s, %s, %s);
            """, (execution_id, api_source, endpoint, json.dumps(raw_payload), json.dumps(errors)))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
