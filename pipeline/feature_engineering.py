from datetime import date, timedelta
from db.connection import get_db_connection, is_mock_mode


class FeatureEngineer:
    @staticmethod
    def calculate_daily_features(product_id: str, target_date: date = None) -> dict:
        """
        Calculates time-series ML features for XGBoost for a product on target_date
        without temporal data leakage.
        """
        if target_date is None:
            target_date = date.today()

        conn = get_db_connection()
        if is_mock_mode():
            return {
                "product_id": product_id,
                "date": target_date,
                "price_avg": 100.0,
                "rolling_avg_price_7d": 100.0,
                "rolling_avg_price_30d": 100.0,
                "price_change_pct_7d": 0.0
            }

        try:
            with conn.cursor() as cur:
                # 1. Fetch prices up to target_date (Strictly no future leakage)
                cur.execute("""
                    SELECT price, collected_at FROM price_history
                    WHERE product_id = %s AND collected_at <= %s
                    ORDER BY collected_at DESC;
                """, (product_id, target_date))
                rows = cur.fetchall()

                if not rows:
                    return {}

                prices_today = [r[0] for r in rows if r[1].date() == target_date]
                if not prices_today:
                    prices_today = [rows[0][0]]

                price_min = float(min(prices_today))
                price_max = float(max(prices_today))
                price_avg = float(sum(prices_today) / len(prices_today))

                # 7-day rolling average
                d7 = target_date - timedelta(days=7)
                prices_7d = [float(r[0]) for r in rows if r[1].date() >= d7]
                rolling_avg_7d = float(sum(prices_7d) / len(prices_7d)) if prices_7d else price_avg

                # 30-day rolling average
                d30 = target_date - timedelta(days=30)
                prices_30d = [float(r[0]) for r in rows if r[1].date() >= d30]
                rolling_avg_30d = float(sum(prices_30d) / len(prices_30d)) if prices_30d else price_avg

                price_change_pct_7d = float((price_avg - rolling_avg_7d) / rolling_avg_7d * 100.0) if rolling_avg_7d > 0 else 0.0

                feature_record = {
                    "product_id": product_id,
                    "date": target_date,
                    "price_min": price_min,
                    "price_max": price_max,
                    "price_avg": price_avg,
                    "price_change_pct_7d": price_change_pct_7d,
                    "rolling_avg_price_7d": rolling_avg_7d,
                    "rolling_avg_price_30d": rolling_avg_30d,
                    "availability_status": "IN_STOCK"
                }

                # Upsert into features_product_daily
                cur.execute("""
                    INSERT INTO features_product_daily (
                        product_id, date, price_min, price_max, price_avg,
                        price_change_pct_7d, rolling_avg_price_7d, rolling_avg_price_30d, availability_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (product_id, date) DO UPDATE SET
                        price_min = EXCLUDED.price_min,
                        price_max = EXCLUDED.price_max,
                        price_avg = EXCLUDED.price_avg,
                        price_change_pct_7d = EXCLUDED.price_change_pct_7d,
                        rolling_avg_price_7d = EXCLUDED.rolling_avg_price_7d,
                        rolling_avg_price_30d = EXCLUDED.rolling_avg_price_30d,
                        feature_calculated_at = CURRENT_TIMESTAMP;
                """, (
                    product_id, target_date, price_min, price_max, price_avg,
                    price_change_pct_7d, rolling_avg_7d, rolling_avg_30d, "IN_STOCK"
                ))
                conn.commit()
                return feature_record
        except Exception:
            conn.rollback()
            return {}
        finally:
            conn.close()
