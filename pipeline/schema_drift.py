import hashlib
import json
from db.connection import get_db_connection, is_mock_mode


class SchemaDriftDetector:
    @staticmethod
    def extract_schema_structure(data: dict) -> dict:
        """Extracts nested keys and type names without data values."""
        if isinstance(data, dict):
            return {k: SchemaDriftDetector.extract_schema_structure(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            if data and len(data) > 0:
                return [SchemaDriftDetector.extract_schema_structure(data[0])]
            return []
        else:
            return type(data).__name__

    @classmethod
    def compute_schema_hash(cls, payload: dict) -> str:
        schema_dict = cls.extract_schema_structure(payload)
        schema_json = json.dumps(schema_dict, sort_keys=True)
        return hashlib.sha256(schema_json.encode('utf-8')).hexdigest()

    @classmethod
    def check_schema_drift(cls, api_source: str, endpoint: str, payload: dict) -> tuple[bool, str]:
        """
        Checks payload schema hash against baseline schema hash.
        If a drift is detected, logs it to schema_drift_logs.
        Returns (is_drifted, current_hash).
        """
        current_hash = cls.compute_schema_hash(payload)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT detected_schema_hash FROM schema_drift_logs
                    WHERE api_source = %s AND endpoint = %s
                    ORDER BY detected_at DESC LIMIT 1;
                """, (api_source, endpoint))
                row = cur.fetchone()

                if row and row[0] != current_hash:
                    # Schema drift detected!
                    cur.execute("""
                        INSERT INTO schema_drift_logs (api_source, endpoint, expected_schema_hash, detected_schema_hash, diff_details)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (api_source, endpoint, row[0], current_hash, json.dumps({"status": "DRIFT_DETECTED"})))
                    conn.commit()
                    return True, current_hash
                elif not row:
                    # Initial schema baseline
                    cur.execute("""
                        INSERT INTO schema_drift_logs (api_source, endpoint, expected_schema_hash, detected_schema_hash, diff_details)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (api_source, endpoint, current_hash, current_hash, json.dumps({"status": "INITIAL_BASELINE"})))
                    conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

        return False, current_hash
