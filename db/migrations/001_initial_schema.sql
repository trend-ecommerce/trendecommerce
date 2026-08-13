-- Migration 001: Initial Schema for Robust Data Pipeline Architecture

-- 0. Migration Tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 1. Metadata & Governance Layer
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id VARCHAR(64) PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    api_source VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL')),
    records_fetched INT DEFAULT 0,
    records_inserted INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    records_quarantined INT DEFAULT 0,
    error_message TEXT,
    execution_context JSONB
);

CREATE TABLE IF NOT EXISTS quarantine_records (
    id BIGSERIAL PRIMARY KEY,
    execution_id VARCHAR(64) REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    api_source VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    raw_payload JSONB NOT NULL,
    validation_errors JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_drift_logs (
    id BIGSERIAL PRIMARY KEY,
    api_source VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    expected_schema_hash VARCHAR(64) NOT NULL,
    detected_schema_hash VARCHAR(64) NOT NULL,
    diff_details JSONB,
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_quality_alerts (
    id BIGSERIAL PRIMARY KEY,
    execution_id VARCHAR(64) REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    description TEXT NOT NULL,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Raw Response Staging Layer
CREATE TABLE IF NOT EXISTS raw_api_responses (
    id BIGSERIAL PRIMARY KEY,
    execution_id VARCHAR(64) REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    api_source VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    http_status INT NOT NULL,
    payload JSONB NOT NULL,
    collected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Operational / Dimension Layer
CREATE TABLE IF NOT EXISTS dim_categories (
    category_id VARCHAR(100) PRIMARY KEY,
    site_id VARCHAR(10) NOT NULL,
    name VARCHAR(255) NOT NULL,
    parent_category_id VARCHAR(100),
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_products (
    product_id VARCHAR(100) PRIMARY KEY, -- e.g. MLB123456 or ASIN
    site_id VARCHAR(10) NOT NULL,
    title VARCHAR(500) NOT NULL,
    category_id VARCHAR(100) REFERENCES dim_categories(category_id) ON DELETE SET NULL,
    brand VARCHAR(255),
    seller_id VARCHAR(100),
    permalink TEXT,
    currency_id VARCHAR(10) DEFAULT 'BRL',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Historical Data Layer (Append-Only Temporal Ledger)
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id VARCHAR(100) NOT NULL REFERENCES dim_products(product_id) ON DELETE CASCADE,
    price NUMERIC(12, 2) NOT NULL,
    original_price NUMERIC(12, 2),
    currency_id VARCHAR(10) DEFAULT 'BRL',
    available_quantity INT,
    collected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_history_product_date 
    ON price_history(product_id, collected_at DESC);

CREATE TABLE IF NOT EXISTS sales_rank_history (
    id BIGSERIAL PRIMARY KEY,
    product_id VARCHAR(100) NOT NULL REFERENCES dim_products(product_id) ON DELETE CASCADE,
    category_id VARCHAR(100),
    rank_position INT NOT NULL,
    collected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sales_rank_history_product_date 
    ON sales_rank_history(product_id, collected_at DESC);

CREATE TABLE IF NOT EXISTS trend_history (
    id BIGSERIAL PRIMARY KEY,
    site_id VARCHAR(10) NOT NULL,
    keyword VARCHAR(255) NOT NULL,
    category_id VARCHAR(100),
    url TEXT,
    rank_position INT NOT NULL,
    collected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trend_history_site_keyword_date 
    ON trend_history(site_id, keyword, collected_at DESC);

-- 5. Analytical & ML Feature Store Layer (XGBoost Ready)
CREATE TABLE IF NOT EXISTS features_product_daily (
    product_id VARCHAR(100) NOT NULL REFERENCES dim_products(product_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    price_min NUMERIC(12, 2),
    price_max NUMERIC(12, 2),
    price_avg NUMERIC(12, 2),
    price_stddev NUMERIC(12, 2),
    price_change_pct_1d NUMERIC(8, 4),
    price_change_pct_7d NUMERIC(8, 4),
    rolling_avg_price_7d NUMERIC(12, 2),
    rolling_avg_price_30d NUMERIC(12, 2),
    sales_rank_avg NUMERIC(10, 2),
    availability_status VARCHAR(20),
    feature_calculated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, date)
);
