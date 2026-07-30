-- =============================================================================
-- Reference schema for a PostgreSQL deployment (DATABASE_URL pointing at a
-- managed Postgres instance). NOT executed at runtime — the app always
-- provisions its schema via SQLAlchemy's Base.metadata.create_all() against
-- whatever DATABASE_URL resolves to (SQLite by default; see
-- fastapi_app/database/connection.py and models.py, which are the source of
-- truth). Keep this file in sync with models.py when adding/changing tables
-- so anyone provisioning Postgres by hand has an accurate reference.
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for users
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 2. Reservoir Table
CREATE TABLE IF NOT EXISTS reservoirs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    capacity_mcm DOUBLE PRECISION NOT NULL,
    current_level_pct DOUBLE PRECISION NOT NULL,
    location_lat DOUBLE PRECISION NOT NULL,
    location_lng DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Groundwater Table
CREATE TABLE IF NOT EXISTS groundwater (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    depth_to_water_m DOUBLE PRECISION NOT NULL,
    depletion_rate_m_year DOUBLE PRECISION NOT NULL,
    recharge_rate_m_year DOUBLE PRECISION NOT NULL,
    storage_volume_mcm DOUBLE PRECISION NOT NULL,
    safe_yield_mcm DOUBLE PRECISION NOT NULL,
    projected_depletion_year INTEGER NOT NULL,
    soil_moisture_index DOUBLE PRECISION NOT NULL,
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    state VARCHAR(100),
    data_source VARCHAR(255),
    observed_at VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2b. Reservoir optional sync columns (ORM-aligned)
-- data_source / observed_at added via ALTER for existing DBs
ALTER TABLE reservoirs ADD COLUMN IF NOT EXISTS data_source VARCHAR(255);
ALTER TABLE reservoirs ADD COLUMN IF NOT EXISTS observed_at VARCHAR(32);

-- 4. Weather Table
CREATE TABLE IF NOT EXISTS weather (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location VARCHAR(255) NOT NULL,
    temperature_c DOUBLE PRECISION NOT NULL,
    humidity_pct DOUBLE PRECISION NOT NULL,
    precipitation_mm DOUBLE PRECISION NOT NULL,
    rainfall_deficit_pct DOUBLE PRECISION NOT NULL,
    heatwave_warning BOOLEAN NOT NULL DEFAULT FALSE,
    uv_index DOUBLE PRECISION NOT NULL,
    evapotranspiration_rate_mm DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weather_location ON weather(location);

-- 5. SensorData Table
CREATE TABLE IF NOT EXISTS sensor_data (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(20) NOT NULL,
    battery_level DOUBLE PRECISION NOT NULL,
    pipe_id VARCHAR(100),
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    address VARCHAR(255) NOT NULL,
    zone VARCHAR(100) NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sensor_data_type ON sensor_data(type);
CREATE INDEX IF NOT EXISTS idx_sensor_data_zone ON sensor_data(zone);

-- 6. Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    id VARCHAR(100) PRIMARY KEY,
    sensor_id VARCHAR(100) REFERENCES sensor_data(id) ON DELETE SET NULL,
    location_name VARCHAR(255) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    zone VARCHAR(100) NOT NULL,
    pipe_material VARCHAR(100) NOT NULL,
    pipe_age_years INTEGER NOT NULL,
    detected_flow_drop_pct DOUBLE PRECISION NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    estimated_water_loss_lpm DOUBLE PRECISION NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(50) NOT NULL,
    ai_diagnostics TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_sensor_id ON alerts(sensor_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);

-- 7. Predictions Table
CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_name VARCHAR(100) NOT NULL,
    input_parameters JSONB NOT NULL,
    prediction_results JSONB NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL,
    run_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_name);

-- 8. Reports Table
CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    date_generated DATE NOT NULL,
    author VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    summary TEXT NOT NULL,
    key_metrics JSONB NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reports_category ON reports(category);

-- 9. AIRecommendations Table
CREATE TABLE IF NOT EXISTS ai_recommendations (
    id VARCHAR(100) PRIMARY KEY,
    priority VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    action_description TEXT NOT NULL,
    estimated_impact TEXT NOT NULL,
    target_sector VARCHAR(255) NOT NULL,
    region_id VARCHAR(100) NOT NULL,
    overall_health_index DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_recs_region ON ai_recommendations(region_id);

-- 10. Consumption series (municipal demand / MGD proxy for WSI)
CREATE TABLE IF NOT EXISTS consumption_series (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    region_id VARCHAR(100) NOT NULL DEFAULT 'REG-1',
    observed_date DATE NOT NULL,
    demand_mgd DOUBLE PRECISION NOT NULL,
    population_thousands DOUBLE PRECISION,
    source VARCHAR(100) NOT NULL DEFAULT 'seeded_pilot',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consumption_region ON consumption_series(region_id);
CREATE INDEX IF NOT EXISTS idx_consumption_date ON consumption_series(observed_date);

-- 11. Password reset tokens (per-user, single-use, expiring)
-- Replaces the old single shared PASSWORD_RESET_TOKEN env var.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_token_hash ON password_reset_tokens(token_hash);

-- 12. AquaLens vision analyses (persisted so trends can be shown over time)
CREATE TABLE IF NOT EXISTS vision_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    asset_label VARCHAR(255),
    vision_mode VARCHAR(20) NOT NULL DEFAULT 'reservoir',
    provider VARCHAR(100),
    reservoir_health INTEGER,
    water_spread VARCHAR(50),
    vegetation VARCHAR(50),
    sedimentation VARCHAR(50),
    dry_shoreline VARCHAR(50),
    encroachment VARCHAR(50),
    water_stress VARCHAR(50),
    overall_risk VARCHAR(50),
    turbidity_index DOUBLE PRECISION,
    algae_bloom_risk VARCHAR(50),
    shoreline_exposure_pct DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    summary TEXT,
    recommendations JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vision_asset_label ON vision_analyses(asset_label);
CREATE INDEX IF NOT EXISTS idx_vision_created_at ON vision_analyses(created_at);

