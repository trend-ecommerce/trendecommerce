from db.connection import get_db_connection, is_mock_mode


class DataQualityChecker:
    @staticmethod
    def check_volume_anomaly(execution_id: str, fetched_count: int, expected_min: int = 1) -> bool:
        """Alerts if fetched record count drops below expected threshold."""
        if fetched_count < expected_min:
            DataQualityChecker._log_alert(
                execution_id=execution_id,
                alert_type="VOLUME_DROP",
                severity="HIGH",
                description=f"Volume anômalo detectado: {fetched_count} registros recebidos (esperado no mínimo {expected_min})."
            )
            return False
        return True

    @staticmethod
    def check_item_quality(execution_id: str, items: list) -> int:
        """Checks list of items for null fields or invalid values and logs alerts if breaches occur."""
        anomalies = 0
        for item in items:
            price = item.get("price")
            if price is not None and price <= 0:
                anomalies += 1

        if anomalies > 0:
            DataQualityChecker._log_alert(
                execution_id=execution_id,
                alert_type="PRICE_ANOMALY",
                severity="MEDIUM",
                description=f"{anomalies} itens com preços zerados ou inválidos detectados."
            )
        return anomalies

    @staticmethod
    def _log_alert(execution_id: str, alert_type: str, severity: str, description: str):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                if is_mock_mode():
                    return
                cur.execute("""
                    INSERT INTO data_quality_alerts (execution_id, alert_type, severity, description)
                    VALUES (%s, %s, %s, %s);
                """, (execution_id, alert_type, severity, description))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()
