import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text, JSON, UUID
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="operator")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    predictions = relationship("Prediction", back_populates="user")


class Reservoir(Base):
    __tablename__ = "reservoirs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    capacity_mcm = Column(Float, nullable=False)
    current_level_pct = Column(Float, nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)
    data_source = Column(String(255), nullable=True)
    observed_at = Column(String(32), nullable=True)  # ISO date from CWC CSV
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Groundwater(Base):
    __tablename__ = "groundwater"
    
    id = Column(String(100), primary_key=True)  # e.g. AQ-101 or CGWB station code
    name = Column(String(255), nullable=False)
    depth_to_water_m = Column(Float, nullable=False)
    depletion_rate_m_year = Column(Float, nullable=False)
    recharge_rate_m_year = Column(Float, nullable=False)
    storage_volume_mcm = Column(Float, nullable=False)
    safe_yield_mcm = Column(Float, nullable=False)
    projected_depletion_year = Column(Integer, nullable=False)
    soil_moisture_index = Column(Float, nullable=False)
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    state = Column(String(100), nullable=True)
    data_source = Column(String(255), nullable=True)
    observed_at = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Weather(Base):
    __tablename__ = "weather"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location = Column(String(255), nullable=False, index=True)
    temperature_c = Column(Float, nullable=False)
    humidity_pct = Column(Float, nullable=False)
    precipitation_mm = Column(Float, nullable=False)
    rainfall_deficit_pct = Column(Float, nullable=False)
    heatwave_warning = Column(Boolean, nullable=False, default=False)
    uv_index = Column(Float, nullable=False)
    evapotranspiration_rate_mm = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ConsumptionSeries(Base):
    """Daily municipal consumption / demand proxy (MGD) for WSI + shortage inputs."""

    __tablename__ = "consumption_series"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    region_id = Column(String(100), nullable=False, index=True, default="REG-1")
    observed_date = Column(Date, nullable=False, index=True)
    demand_mgd = Column(Float, nullable=False)
    population_thousands = Column(Float, nullable=True)
    source = Column(String(100), nullable=False, default="seeded_pilot")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class SensorData(Base):
    __tablename__ = "sensor_data"
    
    id = Column(String(100), primary_key=True)  # e.g. SNS-PL-101
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False, index=True)  # flow, pressure, acoustic, ph, turbidity, aquifer
    status = Column(String(50), nullable=False)  # normal, warning, critical, offline
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    battery_level = Column(Float, nullable=False)
    pipe_id = Column(String(100), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    address = Column(String(255), nullable=False)
    zone = Column(String(100), nullable=False, index=True)
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    alerts = relationship("Alert", back_populates="sensor")


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(String(100), primary_key=True)  # e.g. LEAK-2026-88
    sensor_id = Column(String(100), ForeignKey("sensor_data.id", ondelete="SET NULL"), nullable=True, index=True)
    location_name = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    zone = Column(String(100), nullable=False)
    pipe_material = Column(String(100), nullable=False)
    pipe_age_years = Column(Integer, nullable=False)
    detected_flow_drop_pct = Column(Float, nullable=False)
    anomaly_score = Column(Float, nullable=False)
    estimated_water_loss_lpm = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # critical, high, medium, low, info
    status = Column(String(50), nullable=False)  # active, investigating, repaired, false_positive
    ai_diagnostics = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    sensor = relationship("SensorData", back_populates="alerts")


class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False, index=True)
    input_parameters = Column(JSON, nullable=False)
    prediction_results = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=False)
    run_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    user = relationship("User", back_populates="predictions")


class Report(Base):
    __tablename__ = "reports"
    
    id = Column(String(100), primary_key=True)  # e.g. RPT-2026-001
    title = Column(String(255), nullable=False)
    date_generated = Column(Date, nullable=False)
    author = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)  # GROUNDWATER, LEAKAGE, SHORTAGE
    summary = Column(Text, nullable=False)
    key_metrics = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class PasswordResetToken(Base):
    """Per-user, single-use, expiring password-reset token.

    Replaces the old single shared PASSWORD_RESET_TOKEN env var (which let
    anyone holding that one string reset any account). No outbound email
    integration exists in this pilot, so the plaintext token is only ever
    returned to a trusted local channel (server log) — see
    routers/auth.py::request_password_reset for the documented limitation.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class VisionAnalysis(Base):
    """A single AquaLens analysis run — persisted so the module can show
    trends over time for a given asset rather than being a stateless,
    one-shot image classifier with no memory between uploads."""

    __tablename__ = "vision_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    asset_label = Column(String(255), nullable=True, index=True)  # optional user-supplied reservoir/site name
    vision_mode = Column(String(20), nullable=False, default="reservoir")  # reservoir | flood
    provider = Column(String(100), nullable=True)
    reservoir_health = Column(Integer, nullable=True)
    water_spread = Column(String(50), nullable=True)
    vegetation = Column(String(50), nullable=True)
    sedimentation = Column(String(50), nullable=True)
    dry_shoreline = Column(String(50), nullable=True)
    encroachment = Column(String(50), nullable=True)
    water_stress = Column(String(50), nullable=True)
    overall_risk = Column(String(50), nullable=True)
    turbidity_index = Column(Float, nullable=True)
    algae_bloom_risk = Column(String(50), nullable=True)
    shoreline_exposure_pct = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    recommendations = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    
    id = Column(String(100), primary_key=True)  # e.g. REC-001
    priority = Column(String(50), nullable=False)
    category = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    action_description = Column(Text, nullable=False)
    estimated_impact = Column(Text, nullable=False)
    target_sector = Column(String(255), nullable=False)
    region_id = Column(String(100), nullable=False, index=True)
    overall_health_index = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
