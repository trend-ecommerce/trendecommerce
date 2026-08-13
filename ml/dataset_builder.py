from datetime import date
from db.connection import get_db_connection


class MLDatasetBuilder:
    """
    Builds time-series feature matrices from the 11,000+ products in the database.
    Target classes for trend classification:
    0: Diminuir (Decline)
    1: Estagnar (Stable)
    2: Aumentar (Growth)
    """

    FEATURE_COLUMNS = [
        "current_price",
        "rolling_avg_7d",
        "rolling_avg_30d",
        "price_change_pct_7d",
        "stock_quantity",
        "month",
        "day_of_week"
    ]

    @classmethod
    def build_training_sample(cls) -> tuple[list, list, list]:
        conn = get_db_connection()
        X, y_reg, y_clf = [], [], []

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT dp.product_id, dp.title, dp.category_id,
                           COALESCE(fp.price_avg, 100.0) as price,
                           COALESCE(fp.rolling_avg_price_7d, 100.0) as r7d,
                           COALESCE(fp.rolling_avg_price_30d, 100.0) as r30d,
                           COALESCE(fp.price_change_pct_7d, 0.0) as pct_7d
                    FROM dim_products dp
                    JOIN features_product_daily fp ON dp.product_id = fp.product_id;
                """)
                rows = cur.fetchall()

                today = date.today()
                for row in rows:
                    price = float(row[3])
                    r7d = float(row[4])
                    r30d = float(row[5])
                    pct_7d = float(row[6])

                    feature_vector = [
                        price,
                        r7d,
                        r30d,
                        pct_7d,
                        50.0,
                        float(today.month),
                        float(today.weekday())
                    ]

                    # Target continuous regression (Demand Score)
                    reg_target = max(1.0, 100.0 + (pct_7d * 2.5) + ((price - r30d) / r30d * 10.0))

                    # Target classification (0 = Diminuir, 1 = Estagnar, 2 = Aumentar)
                    if pct_7d > 2.0:
                        clf_target = 2 # Aumentar
                    elif pct_7d < -2.0:
                        clf_target = 0 # Diminuir
                    else:
                        clf_target = 1 # Estagnar

                    X.append(feature_vector)
                    y_reg.append(reg_target)
                    y_clf.append(clf_target)
        finally:
            conn.close()

        return X, y_reg, y_clf
