import uuid
from datetime import datetime
from db.connection import get_db_connection


class PipelineTracker:
    def __init__(self, pipeline_name: str, api_source: str, endpoint: str):
        self.run_id = str(uuid.uuid4())
        self.pipeline_name = pipeline_name
        self.api_source = api_source
        self.endpoint = endpoint
        self.start_time = datetime.utcnow()
        self.records_fetched = 0
        self.records_inserted = 0
        self.records_updated = 0
        self.records_quarantined = 0

    def __enter__(self):
        self._save_run("RUNNING")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._save_run("FAILED", error_message=str(exc_val))
        else:
            self._save_run("SUCCESS")

    def increment_fetched(self, count: int = 1):
        self.records_fetched += count

    def increment_inserted(self, count: int = 1):
        self.records_inserted += count

    def increment_updated(self, count: int = 1):
        self.records_updated += count

    def increment_quarantined(self, count: int = 1):
        self.records_quarantined += count

    def _save_run(self, status: str, error_message: str = None):
        end_time = datetime.utcnow() if status != "RUNNING" else None
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs (
                        id, pipeline_name, api_source, endpoint, start_time, end_time, status,
                        records_fetched, records_inserted, records_updated, records_quarantined, error_message
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        end_time = EXCLUDED.end_time,
                        status = EXCLUDED.status,
                        records_fetched = EXCLUDED.records_fetched,
                        records_inserted = EXCLUDED.records_inserted,
                        records_updated = EXCLUDED.records_updated,
                        records_quarantined = EXCLUDED.records_quarantined,
                        error_message = EXCLUDED.error_message;
                """, (
                    self.run_id, self.pipeline_name, self.api_source, self.endpoint, self.start_time,
                    end_time, status, self.records_fetched, self.records_inserted, self.records_updated,
                    self.records_quarantined, error_message
                ))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()
