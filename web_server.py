import os
import sys
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_db_connection
from ml.predictor import TrendPredictor

app = FastAPI(title="TrendCommerce AI Platform", version="2.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")


@app.get("/api/products")
def get_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    category: str = Query("ALL"),
    search: str = Query("")
):
    """Fetches paged products from dim_products along with latest price history."""
    conn = get_db_connection()
    products_list = []
    total_count = 0

    offset = (page - 1) * limit
    try:
        with conn.cursor() as cur:
            # Base query
            where_clauses = []
            params = []

            if category and category != "ALL":
                where_clauses.append("dp.category_id = %s")
                params.append(category)

            if search:
                where_clauses.append("(LOWER(dp.title) LIKE %s OR LOWER(dp.product_id) LIKE %s)")
                params.append(f"%{search.lower()}%")
                params.append(f"%{search.lower()}%")

            where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Count query
            count_sql = f"SELECT COUNT(*) FROM dim_products dp {where_str};"
            cur.execute(count_sql, params)
            total_count = cur.fetchone()[0]

            # Data query
            data_sql = f"""
                SELECT dp.product_id, dp.site_id, dp.title, dp.category_id, dp.brand,
                       COALESCE(ph.price, 0.0) as current_price,
                       COALESCE(ph.original_price, 0.0) as original_price,
                       COALESCE(ph.available_quantity, 0) as available_quantity,
                       COALESCE(ph.collected_at, CURRENT_TIMESTAMP) as last_updated
                FROM dim_products dp
                LEFT JOIN price_history ph ON dp.product_id = ph.product_id
                {where_str}
                GROUP BY dp.product_id
                ORDER BY dp.product_id DESC
                LIMIT %s OFFSET %s;
            """
            cur.execute(data_sql, params + [limit, offset])
            rows = cur.fetchall()

            for r in rows:
                products_list.append({
                    "product_id": r[0],
                    "site_id": r[1],
                    "title": r[2],
                    "category_id": r[3],
                    "brand": r[4] or "Marca Geral",
                    "current_price": float(r[5]),
                    "original_price": float(r[6]) if r[6] else None,
                    "available_quantity": int(r[7]),
                    "last_updated": str(r[8])
                })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        conn.close()

    return {
        "status": "SUCCESS",
        "total": total_count,
        "page": page,
        "limit": limit,
        "products": products_list
    }


@app.get("/api/top10")
def get_top_10_products():
    """Returns Top 10 Ranked Products evaluated by XGBoost."""
    try:
        predictor = TrendPredictor()
        res = predictor.predict_trends()
        return {
            "status": "SUCCESS",
            "top_10_products": res.get("top_10_best_products", [])
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/predictions")
def get_predictions():
    """Executes XGBoost ML Trend Predictor for AUMENTAR, DIMINUIR, and ESTAGNAR classes."""
    try:
        predictor = TrendPredictor()
        res = predictor.predict_trends()
        return res
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/telemetry")
def get_telemetry():
    """Fetches SRE execution telemetry from pipeline_runs."""
    conn = get_db_connection()
    runs = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, pipeline_name, api_source, status, records_fetched, records_inserted, start_time
                FROM pipeline_runs
                ORDER BY start_time DESC LIMIT 10;
            """)
            rows = cur.fetchall()
            for r in rows:
                runs.append({
                    "run_id": r[0],
                    "pipeline_name": r[1],
                    "api_source": r[2],
                    "status": r[3],
                    "records_fetched": r[4],
                    "records_inserted": r[5],
                    "start_time": str(r[6])
                })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        conn.close()

    return {"status": "SUCCESS", "runs": runs}


if os.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
