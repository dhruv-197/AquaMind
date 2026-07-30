from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime

# ==========================================================
# 1. WATER SHORTAGE PREDICTION SCHEMAS
# ==========================================================
class ShortagePredictionRequest(BaseModel):
    reservoir_capacity_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Current live-storage fill percentage (0–100)", example=34.2
    )
    rainfall_deficit_pct: float = Field(
        ...,
        ge=-100.0,
        le=100.0,
        description=(
            "Rainfall anomaly (%) vs ~30-day mean: negative = drier than normal, "
            "positive = wetter. Field name kept for API compatibility with the trained model."
        ),
        example=-20.0,
    )
    temperature_c: float = Field(
        ..., ge=0.0, le=50.0, description="Current ambient temperature in °C (typical India range 0–50)", example=32.0
    )
    daily_demand_mgd: float = Field(
        ..., ge=0.0, description="Target daily consumption volume in Million Gallons per Day (MGD)", example=88.0
    )
    day_of_month: Optional[int] = Field(
        None, ge=1, le=31, description="Calendar day used by the trained model (defaults to today)"
    )
    live_capacity_mcm: Optional[float] = Field(
        None, ge=0.0, description="Optional live capacity in MCM — used only for UI supply warnings"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reservoir_capacity_pct": 34.2,
                "rainfall_deficit_pct": -20.0,
                "temperature_c": 32.0,
                "daily_demand_mgd": 88.0,
                "day_of_month": 15,
                "live_capacity_mcm": 9500.0,
            }
        }
    )

class ShortagePredictionData(BaseModel):
    predicted_risk_score: float = Field(..., description="Numeric risk index from 0 to 100")
    predicted_risk_stage: int = Field(..., description="Shortage stage level (0: Safe, 1: Stage 1, 2: Stage 2, 3: Critical)")
    risk_label: str = Field(..., description="Human-readable risk classification")
    confidence: float = Field(..., description="Holdout-error-derived pilot reliability indicator; not a calibrated probability")
    recommended_mitigation: str = Field(..., description="Actionable mitigation strategy")
    forecast_storage_pct: Optional[float] = Field(None, description="Next-day forecast storage percentage when available")
    multi_horizon: Optional[Dict[str, Any]] = Field(
        None,
        description="Pilot 7/30-day storage extrapolation from the 1-day RF (disclosed heuristic, not a trained multi-horizon model)",
    )
    technical_accuracy_note: Optional[str] = Field(
        None,
        description="Whether the trained model beats a naive 'no change' persistence baseline on held-out test data.",
    )

class ShortagePredictionResponse(BaseModel):
    success: bool = True
    message: str = "Water shortage risk assessment completed successfully."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: ShortagePredictionData


# ==========================================================
# 2. GROUNDWATER PREDICTION SCHEMAS (legacy — formula-based, kept for compat)
# ==========================================================
class GroundwaterPredictionRequest(BaseModel):
    initial_depth_m: float = Field(..., ge=0.0, description="Current depth to water table in meters", example=124.8)
    annual_rainfall_mm: float = Field(..., ge=0.0, description="Annual monsoon/seasonal rainfall in mm", example=580.0)
    pumping_extraction_mld: float = Field(..., ge=0.0, description="Daily groundwater extraction rate in MLD", example=52.0)
    aquifer_recharge_factor: float = Field(default=0.20, ge=0.0, le=1.0, description="Soil recharge coefficient (0.0 - 1.0)", example=0.18)
    soil_porosity_idx: float = Field(default=0.25, ge=0.0, le=1.0, description="Soil porosity index (0.0 - 1.0)", example=0.22)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "initial_depth_m": 124.8,
                "annual_rainfall_mm": 580.0,
                "pumping_extraction_mld": 52.0,
                "aquifer_recharge_factor": 0.18,
                "soil_porosity_idx": 0.22
            }
        }
    )

class GroundwaterPredictionData(BaseModel):
    projected_depth_m: float = Field(..., description="Projected depth to water table (meters)")
    drawdown_rate_m: float = Field(..., description="Net drawdown or recharge rate in meters")
    aquifer_status: str = Field(..., description="Aquifer health status classification")
    depletion_trend: str = Field(..., description="Trend projection (e.g., Accelerating, Stable, Recharging)")

class GroundwaterPredictionResponse(BaseModel):
    success: bool = True
    message: str = "Groundwater depth projection calculated successfully."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: GroundwaterPredictionData


# ==========================================================
# 2b. GROUNDWATER WELL PREDICTION SCHEMAS (dataset-backed CGWB model)
# ==========================================================
class GroundwaterWellRequest(BaseModel):
    current_depth_m: float = Field(
        ..., ge=0.0, description="Current observed water-table depth to ground (metres).", example=25.4
    )
    station_code: Optional[str] = Field(
        None, description="CGWB station code. If supplied, latitude/longitude/well_depth/well_type are auto-filled from training metadata.", example="112"
    )
    latitude: Optional[float] = Field(None, description="Decimal degrees latitude (required if station_code not supplied).", example=28.58)
    longitude: Optional[float] = Field(None, description="Decimal degrees longitude (required if station_code not supplied).", example=77.05)
    well_depth: Optional[float] = Field(None, ge=0.0, description="Well depth in metres.", example=80.0)
    well_type: Optional[str] = Field(None, description="Well type: Bore well, Dug well, Tube well, Piezometer, etc.", example="Bore well")
    observation_month: int = Field(5, ge=1, le=12, description="Calendar month of this observation (1=Jan … 12=Dec).", example=5)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_depth_m": 25.4,
                "latitude": 28.58,
                "longitude": 77.05,
                "well_depth": 80.0,
                "well_type": "Bore well",
                "observation_month": 5
            }
        }
    )

class GroundwaterWellData(BaseModel):
    projected_depth_m: float = Field(..., description="Predicted next-observation water depth (m).")
    drawdown_rate_m: float = Field(..., description="Change vs current observation: positive = deeper (depletion), negative = shallower (recharge).")
    aquifer_status: str
    depletion_trend: str
    station_name: str
    latitude: float
    longitude: float
    well_depth_m: float
    well_type: str
    observation_month: int
    confidence: float = Field(..., description="Indicator derived from held-out test MAE; not a calibrated probability.")
    model_scope: str

class GroundwaterWellResponse(BaseModel):
    success: bool = True
    message: str = "CGWB well pilot forecast completed. Verify with field measurement before acting."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: GroundwaterWellData


# ==========================================================
# 3. WATER DEMAND PREDICTION SCHEMAS
# ==========================================================
class DemandPredictionRequest(BaseModel):
    population_thousands: float = Field(..., ge=0.0, description="Service area population in thousands", example=1850.0)
    temperature_c: float = Field(..., ge=-20.0, le=60.0, description="Expected peak temperature in Celsius", example=40.2)
    industrial_activity_idx: float = Field(default=50.0, ge=0.0, le=100.0, description="Industrial consumption index", example=92.0)
    is_weekend: int = Field(default=0, ge=0, le=1, description="Binary flag indicating weekend (1) or weekday (0)", example=0)
    is_heatwave: int = Field(default=0, ge=0, le=1, description="Binary flag indicating active heatwave condition", example=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "population_thousands": 1850.0,
                "temperature_c": 40.2,
                "industrial_activity_idx": 92.0,
                "is_weekend": 0,
                "is_heatwave": 1
            }
        }
    )

class DemandPredictionData(BaseModel):
    forecasted_demand_mgd: float = Field(..., description="Forecasted daily demand in Million Gallons per Day")
    forecasted_demand_mld: float = Field(..., description="Forecasted daily demand in Million Liters per Day")
    peak_surge_risk: str = Field(..., description="Surge risk evaluation category")
    suggested_grid_allocation: str = Field(..., description="Recommended distribution adjustment")
    peak_hour_demand_mgd: Optional[float] = Field(None, description="Estimated peak-hour demand MGD")
    climate_base_mgd: Optional[float] = Field(None, description="Climate-only model output before population/industrial scale")
    confidence: Optional[float] = Field(None, description="Pilot reliability indicator from holdout MAE")
    model_scope: Optional[str] = Field(None, description="Training data scope note")
    test_mae_mgd: Optional[float] = Field(None, description="Holdout MAE in MGD when available")

class DemandPredictionResponse(BaseModel):
    success: bool = True
    message: str = "Municipal water demand forecast generated successfully."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: DemandPredictionData


# ==========================================================
# 4. LEAK DETECTION SCHEMAS (legacy manual-field, kept for compat)
# ==========================================================
class LeakDetectionRequest(BaseModel):
    pressure_bar: float = Field(..., ge=0.0, le=20.0, description="Legacy field (not a model feature of the trained acoustic classifier).", example=1.6)
    pressure_drop_bar: float = Field(..., ge=0.0, le=20.0, description="Legacy field.", example=2.8)
    acoustic_vibration_db: float = Field(..., ge=0.0, le=150.0, description="Legacy field.", example=88.2)
    flow_velocity_m_s: float = Field(..., ge=0.0, le=20.0, description="Legacy field.", example=4.1)
    frequency_spike_hz: float = Field(default=1000.0, ge=0.0, le=10000.0, description="Legacy field.", example=2800.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pressure_bar": 1.6,
                "pressure_drop_bar": 2.8,
                "acoustic_vibration_db": 88.2,
                "flow_velocity_m_s": 4.1,
                "frequency_spike_hz": 2800.0
            }
        }
    )

class LeakDetectionData(BaseModel):
    is_leak_detected: bool
    leak_probability: float
    severity: str
    note: str = Field(..., description="Scope and limitation note.")

class LeakDetectionResponse(BaseModel):
    success: bool = True
    message: str = "Acoustic leak detection pilot completed."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: LeakDetectionData


# ==========================================================
# 4b. SIGNAL-BASED LEAK DETECTION SCHEMAS (dataset-backed acoustic classifier)
# ==========================================================
class LeakSignalData(BaseModel):
    is_leak_detected: bool
    leak_probability: float = Field(..., description="Probability from RF classifier (0–1).")
    severity: str
    model_scope: str
    test_f1: float = Field(..., description="Held-out test F1 score of the trained classifier.")
    note: str
    test_accuracy: Optional[float] = None
    windows_scored: Optional[int] = Field(
        None, description="Number of training-sized windows averaged for this prediction."
    )
    estimated_water_loss_lpm: Optional[float] = Field(
        None, description="Heuristic orifice volumetric loss (L/min) — not from acoustic labels."
    )
    daily_loss_mld: Optional[float] = Field(None, description="Extrapolated daily loss in MLD.")
    loss_confidence: Optional[float] = Field(None, description="Heuristic confidence for loss estimate.")
    loss_method: Optional[str] = Field(None, description="e.g. heuristic_orifice")

class LeakSignalResponse(BaseModel):
    success: bool = True
    message: str = "Acoustic signal classification completed. Lab-trained pilot — field verification required."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: LeakSignalData


# ==========================================================
# 4c. WATER INTELLIGENCE / WATER STRESS INDEX
# ==========================================================
class WaterIntelligenceRequest(BaseModel):
    """Optional overrides; omitted fields are filled from live DB + local models."""
    reservoir_capacity_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    rainfall_deficit_pct: Optional[float] = Field(None, ge=-100.0, le=100.0)
    temperature_c: Optional[float] = Field(None, ge=-20.0, le=60.0)
    daily_demand_mgd: Optional[float] = Field(None, ge=0.0)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    leak_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    estimated_water_loss_lpm: Optional[float] = Field(None, ge=0.0)
    is_leak_detected: Optional[bool] = None
    current_depth_m: Optional[float] = Field(None, ge=0.0)
    depletion_rate_m_year: Optional[float] = None
    population_thousands: Optional[float] = Field(None, ge=0.0)
    industrial_activity_idx: Optional[float] = Field(None, ge=0.0, le=100.0)
    is_weekend: Optional[int] = Field(None, ge=0, le=1)
    is_heatwave: Optional[int] = Field(None, ge=0, le=1)
    spi3_proxy: Optional[float] = Field(None, description="Optional SPI-3 z-score proxy from Climate Risk")
    heatwave_warning: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reservoir_capacity_pct": 34.2,
                "rainfall_deficit_pct": -20.0,
                "temperature_c": 36.0,
                "daily_demand_mgd": 95.0,
                "spi3_proxy": -1.2,
            }
        }
    )


class WaterStressComponent(BaseModel):
    score: float
    weight: float
    contribution: float
    detail: str


class WaterStressDriver(BaseModel):
    component: str
    contribution: float
    detail: str


class WaterStressIndexData(BaseModel):
    water_stress_index: float
    stage: str
    components: Dict[str, WaterStressComponent]
    weights: Dict[str, float]
    drivers: List[WaterStressDriver]
    data_sources: Dict[str, str]
    method: str
    note: str


class WaterIntelligenceData(BaseModel):
    water_stress: WaterStressIndexData
    shortage: Dict[str, Any]
    leak: Dict[str, Any]
    groundwater: Dict[str, Any]
    demand: Dict[str, Any]
    climate: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


class WaterIntelligenceResponse(BaseModel):
    success: bool = True
    message: str = "Water intelligence fusion completed (shortage, leak, groundwater, demand, climate)."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: WaterIntelligenceData


class WaterStressAnalyticsResponse(BaseModel):
    success: bool = True
    message: str = "Live water-stress index from model telemetry."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: WaterIntelligenceData


# ==========================================================
# 5. RECOMMENDATION SCHEMAS
# ==========================================================
class RecommendationRequest(BaseModel):
    region_id: Optional[str] = Field("REG-NORTH-01", description="Smart city region identifier")
    shortage_stage: Optional[int] = Field(1, description="Active shortage risk stage (0 - 3)")
    leak_alerts_count: Optional[int] = Field(3, description="Count of active unresolved leak alerts")
    groundwater_depletion_m: Optional[float] = Field(2.5, description="Recent groundwater drawdown rate in meters")
    force_refresh: bool = Field(False, description="Bypass recommendation cache")

class RecommendationItem(BaseModel):
    id: str
    priority: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW")
    category: str = Field(..., description="INFRASTRUCTURE, CONSERVATION, ALLOCATION, EMERGENCY")
    title: str
    action_description: str
    estimated_impact: str
    target_sector: str

class RecommendationData(BaseModel):
    region_id: str
    overall_health_index: float
    recommendations: List[RecommendationItem]
    policy_guidelines: List[str]

class RecommendationResponse(BaseModel):
    success: bool = True
    message: str = "AI recommendation policies synthesized successfully."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: RecommendationData


# ==========================================================
# 6. WEATHER SCHEMAS
# ==========================================================
class WeatherData(BaseModel):
    location: str
    temperature_c: float
    humidity_pct: float
    precipitation_mm: float
    rainfall_deficit_pct: float
    heatwave_warning: bool
    uv_index: float
    evapotranspiration_rate_mm: float
    forecast_5_day: List[Dict[str, Any]]

class WeatherResponse(BaseModel):
    success: bool = True
    message: str = "Weather & hydro-meteorological telemetry retrieved."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: WeatherData


# ==========================================================
# 7. REPORTS SCHEMAS
# ==========================================================
class ReportItem(BaseModel):
    report_id: str
    title: str
    date_generated: str
    author: str
    category: str
    summary: str
    key_metrics: Dict[str, Any]
    status: str

class ReportListData(BaseModel):
    total_reports: int
    filter_applied: Optional[str]
    reports: List[ReportItem]

class ReportResponse(BaseModel):
    success: bool = True
    message: str = "Water resource intelligence reports fetched."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: ReportListData


# ==========================================================
# 8. AI RECOMMENDATION ENGINE SCHEMAS
# ==========================================================
class AIRecommendationEngineRequest(BaseModel):
    water_shortage_prediction: Dict[str, Any] = Field(
        ...,
        description="Dictionary output from the water shortage prediction model",
        example={
            "predicted_risk_score": 68.2,
            "predicted_risk_stage": 1,
            "risk_label": "Moderate Risk (Stage 1)",
            "confidence": 0.88,
            "reservoir_capacity_pct": 34.2
        }
    )
    leak_detection: Dict[str, Any] = Field(
        ...,
        description="Dictionary output from the leak detection model",
        example={
            "is_leak_detected": True,
            "leak_probability": 0.89,
            "estimated_water_loss_lpm": 624.0,
            "severity": "CRITICAL BURST",
            "zone": "Zone 3"
        }
    )
    groundwater_prediction: Dict[str, Any] = Field(
        ...,
        description="Dictionary output from the groundwater level prediction model",
        example={
            "projected_depth_m": 128.0,
            "drawdown_rate_m": 3.2,
            "aquifer_status": "Critical Over-Exploited"
        }
    )
    water_demand: Dict[str, Any] = Field(
        ...,
        description="Dictionary output from the water demand prediction model",
        example={
            "forecasted_demand_mgd": 120.5,
            "peak_surge_risk": "Critical Surge"
        }
    )
    force_refresh: bool = Field(
        False,
        description="If true, bypass recommendation cache and call Gemini again",
    )

class AIRecommendationEngineData(BaseModel):
    recommendations: List[str] = Field(..., description="List of actionable text recommendations")
    expected_saving: str = Field(..., description="Formatted string indicating expected water savings")
    text_summary: str = Field(..., description="Single composite text summary of recommendations")
    source: Optional[str] = Field(None, description="gemini | cache | rules_fallback")
    provider: Optional[str] = Field(None, description="Gemini model id or local-rules")
    inputs: Optional[Dict[str, Any]] = Field(None, description="Model/DB telemetry used for synthesis")

class AIRecommendationEngineResponse(BaseModel):
    success: bool = True
    message: str = "AI recommendations synthesized successfully."
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: AIRecommendationEngineData


# ==========================================================
# 9. AUTHENTICATION & ROLE SCHEMAS
# ==========================================================
class UserSignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., description="Email address for authentication")
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field("user", description="Roles: admin, government_officer, industry, user")

class UserLoginRequest(BaseModel):
    email: str
    password: str

class RequestPasswordResetRequest(BaseModel):
    email: str = Field(..., description="Account email to issue a one-time reset token for")


class ForgotPasswordRequest(BaseModel):
    email: str
    new_password: str = Field(..., min_length=6, max_length=100)
    reset_token: str = Field(..., min_length=8, description="One-time token issued by /auth/request-password-reset")


class PromoteUserRequest(BaseModel):
    email: str = Field(..., description="Email of the account to change the role of")
    role: str = Field(..., description="New role: admin, government_officer, industry, user")


class AuthResponseData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    email: str

class AuthResponse(BaseModel):
    success: bool = True
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: AuthResponseData
