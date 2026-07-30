import os
import sys
from datetime import datetime, date

# Add workspace directory to path
SYS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if SYS_PATH not in sys.path:
    sys.path.append(SYS_PATH)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi_app.database.models import (
    Base, User, Reservoir, Groundwater, Weather, SensorData, Alert, Prediction, Report, AIRecommendation
)

def run_test():
    print("Initializing test in-memory SQLite database...")
    engine = create_engine("sqlite:///:memory:", echo=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Creating all tables via Base.metadata.create_all...")
    Base.metadata.create_all(engine)
    print("Tables created successfully!")

    try:
        # 1. Insert User
        print("\nTesting User CRUD...")
        test_user = User(
            username="admin_test",
            email="admin@aquamind.io",
            password_hash="pbkdf2_sha256_mock_hash",
            role="admin"
        )
        session.add(test_user)
        session.commit()
        print(f"User created: ID={test_user.id}, Username={test_user.username}")

        # 2. Insert Reservoir
        print("\nTesting Reservoir CRUD...")
        res = Reservoir(
            name="Central Reservoir",
            capacity_mcm=150.0,
            current_level_pct=72.5,
            location_lat=37.7749,
            location_lng=-122.4194
        )
        session.add(res)
        session.commit()
        print(f"Reservoir created: {res.name}")

        # 3. Insert Groundwater
        print("\nTesting Groundwater CRUD...")
        gw = Groundwater(
            id="AQ-TEST-01",
            name="Deep Sandstone Aquifer",
            depth_to_water_m=124.8,
            depletion_rate_m_year=3.8,
            recharge_rate_m_year=0.9,
            storage_volume_mcm=420.0,
            safe_yield_mcm=35.0,
            projected_depletion_year=2038,
            soil_moisture_index=0.22
        )
        session.add(gw)
        session.commit()
        print(f"Groundwater created: {gw.name} ({gw.id})")

        # 4. Insert Weather
        print("\nTesting Weather CRUD...")
        weather = Weather(
            location="Metropolitan Watershed Region A",
            temperature_c=38.5,
            humidity_pct=34.0,
            precipitation_mm=0.2,
            rainfall_deficit_pct=-42.5,
            heatwave_warning=True,
            uv_index=9.4,
            evapotranspiration_rate_mm=6.8
        )
        session.add(weather)
        session.commit()
        print(f"Weather logged for: {weather.location}")

        # 5. Insert SensorData
        print("\nTesting SensorData CRUD...")
        sensor = SensorData(
            id="SNS-PL-101",
            name="North Grid Pressure Transducer #12",
            type="pressure",
            status="critical",
            value=38.4,
            unit="PSI",
            battery_level=92.0,
            pipe_id="PIPE-MAIN-N4",
            lat=37.7749,
            lng=-122.4194,
            address="District 4 - Metro North Main",
            zone="North Industrial Sector"
        )
        session.add(sensor)
        session.commit()
        print(f"Sensor registered: {sensor.name} ({sensor.id})")

        # 6. Insert Alert (Foreign Key to SensorData)
        print("\nTesting Alert CRUD (FK Relation to SensorData)...")
        alert = Alert(
            id="LEAK-2026-88",
            sensor_id="SNS-PL-101",
            location_name="North Industrial Pipeline Segment 4B",
            lat=37.7749,
            lng=-122.4194,
            zone="North Industrial Sector",
            pipe_material="Ductile Iron",
            pipe_age_years=28,
            detected_flow_drop_pct=31.5,
            anomaly_score=0.89,
            estimated_water_loss_lpm=420.0,
            severity="critical",
            status="active",
            ai_diagnostics="Isolation Forest anomaly detected pressure drop."
        )
        session.add(alert)
        session.commit()
        print(f"Alert registered: {alert.id} referencing Sensor: {alert.sensor.name}")

        # 7. Insert Prediction (Foreign Key to User)
        print("\nTesting Prediction CRUD (FK Relation to User)...")
        pred = Prediction(
            model_name="water_shortage",
            input_parameters={"reservoir_capacity_pct": 34.2, "temperature_c": 38.5},
            prediction_results={"predicted_risk_score": 68.2, "risk_label": "Stage 1"},
            confidence_score=0.88,
            run_by_user_id=test_user.id
        )
        session.add(pred)
        session.commit()
        print(f"Prediction generated: ID={pred.id} run by: {pred.user.username}")

        # 8. Insert Report
        print("\nTesting Report CRUD...")
        rep = Report(
            id="RPT-2026-001",
            title="Q2 Comprehensive Groundwater Depletion Briefing",
            date_generated=date(2026, 7, 1),
            author="AquaMind Analytics Unit",
            category="GROUNDWATER",
            summary="Drawdown of 2.8m across the sandstone aquifer.",
            key_metrics={"mean_drawdown_m": 2.8, "critical_wells": 3},
            status="PUBLISHED"
        )
        session.add(rep)
        session.commit()
        print(f"Report generated: {rep.title}")

        # 9. Insert AIRecommendation
        print("\nTesting AIRecommendation CRUD...")
        rec = AIRecommendation(
            id="REC-001",
            priority="CRITICAL",
            category="INFRASTRUCTURE",
            title="Automated Valve Deployment",
            action_description="Shut down solenoid valve to halt leak.",
            estimated_impact="Saves 898,560 Liters/day",
            target_sector="North Industrial District",
            region_id="REG-NORTH-01",
            overall_health_index=72.4
        )
        session.add(rec)
        session.commit()
        print(f"AI Recommendation created: {rec.title} ({rec.id})")

        print("\nALL DATABASE MODELS VERIFIED AND COMPILED SUCCESSFULLY!")

    except Exception as e:
        session.rollback()
        print(f"\nTEST FAILED WITH ERROR: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    run_test()
