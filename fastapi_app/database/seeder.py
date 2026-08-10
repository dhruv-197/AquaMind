import os
from datetime import datetime, date
from sqlalchemy.orm import Session
from fastapi_app.database.models import (
    User, Reservoir, Groundwater, Weather, SensorData, Alert, Report, AIRecommendation,
    ConsumptionSeries,
)
from fastapi_app.services.auth_service import AuthService

def seed_database(db: Session):
    """
    Seeds the database with initial Indian hydro-geographical telemetry records.
    Only seeds if the User table is empty (preventing duplicates).
    Always ensures a pilot consumption series exists for WSI / shortage demand.
    """
    # 1. Check if already seeded — catch IntegrityError so multi-worker
    # startups racing the empty-table check do not crash the process.
    if db.query(User).first() is not None:
        print("[Seeder] Database already seeded. Skipping core seed...")
        _ensure_consumption_series(db)
        return

    print("[Seeder] Seeding database with Indian hydro-geographical data...")

    try:
        _seed_core(db)
    except Exception as exc:
        db.rollback()
        # Another worker likely completed the seed first.
        if db.query(User).first() is not None:
            print(f"[Seeder] Concurrent seed detected ({type(exc).__name__}); continuing.")
            _ensure_consumption_series(db)
            return
        raise


def _seed_core(db: Session):
    # 2. Seed Users
    admin_user = User(
        username="Admin",
        email="admin@centralvalleywater.gov",
        password_hash=AuthService.hash_password("password123"),
        role="admin"
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    # 3. Seed Reservoirs
    reservoirs = [
        Reservoir(
            name="Indira Sagar Reservoir",
            capacity_mcm=12200.0,
            current_level_pct=68.0,
            location_lat=22.2882,
            location_lng=76.4526
        ),
        Reservoir(
            name="Nagarjuna Sagar Reservoir",
            capacity_mcm=11500.0,
            current_level_pct=32.0,
            location_lat=16.5750,
            location_lng=79.3125
        ),
        Reservoir(
            name="Sardar Sarovar Reservoir",
            capacity_mcm=9500.0,
            current_level_pct=51.5,
            location_lat=21.8315,
            location_lng=73.7485
        ),
        Reservoir(
            name="Mettur Reservoir",
            capacity_mcm=2700.0,
            current_level_pct=28.0,
            location_lat=11.8020,
            location_lng=77.8010
        ),
        Reservoir(
            name="Bhakra Reservoir",
            capacity_mcm=9300.0,
            current_level_pct=75.0,
            location_lat=31.4111,
            location_lng=76.4428
        )
    ]
    db.add_all(reservoirs)

    # 4. Seed Groundwater (Aquifers)
    groundwaters = [
        Groundwater(
            id="AQ-101",
            name="Indo-Gangetic Basin Deep Aquifer",
            depth_to_water_m=142.5,
            depletion_rate_m_year=4.2,
            recharge_rate_m_year=0.9,
            storage_volume_mcm=420.0,
            safe_yield_mcm=35.0,
            projected_depletion_year=2038,
            soil_moisture_index=0.22
        ),
        Groundwater(
            id="AQ-102",
            name="Deccan Trap Basaltic Aquifer",
            depth_to_water_m=88.2,
            depletion_rate_m_year=2.1,
            recharge_rate_m_year=1.8,
            storage_volume_mcm=180.0,
            safe_yield_mcm=22.0,
            projected_depletion_year=2065,
            soil_moisture_index=0.54
        ),
        Groundwater(
            id="AQ-103",
            name="Western Thar Aquifer (Rajasthan)",
            depth_to_water_m=185.0,
            depletion_rate_m_year=5.5,
            recharge_rate_m_year=0.1,
            storage_volume_mcm=95.0,
            safe_yield_mcm=8.0,
            projected_depletion_year=2031,
            soil_moisture_index=0.12
        )
    ]
    db.add_all(groundwaters)

    # 5. Seed SensorData
    sensors = [
        SensorData(
            id="SNS-PL-101",
            name="Dwarka Grid Pressure Transducer #12",
            type="pressure",
            status="critical",
            value=38.4,
            unit="PSI",
            battery_level=92.0,
            pipe_id="PIPE-MAIN-DL4",
            lat=28.5830,
            lng=77.0500,
            address="Sector 11 Dwarka - Metro Delhi Main",
            zone="Delhi NCT Sector 4"
        ),
        SensorData(
            id="SNS-AC-204",
            name="Acoustic Leak Sensor - Bandra Zone",
            type="acoustic",
            status="warning",
            value=68.2,
            unit="dB",
            battery_level=85.0,
            pipe_id="PIPE-FEED-MH2",
            lat=19.0596,
            lng=72.8295,
            address="Bandra West Promenade Road",
            zone="Mumbai Ward H-West"
        ),
        SensorData(
            id="SNS-FL-309",
            name="Ultrasonic Flow Meter - Whitefield Feed",
            type="flow",
            status="normal",
            value=1240.0,
            unit="GPM",
            battery_level=98.0,
            pipe_id="PIPE-AQU-KA3",
            lat=12.9698,
            lng=77.7500,
            address="Whitefield IT Aqueduct Feeder #3",
            zone="Bengaluru East Grid"
        ),
        SensorData(
            id="SNS-GW-412",
            name="Jodhpur Basin Piezometer Well #8",
            type="aquifer",
            status="critical",
            value=185.0,
            unit="m Depth",
            battery_level=78.0,
            lat=26.2389,
            lng=73.0243,
            address="Thar Groundwater Observation Basin",
            zone="Rajasthan West Groundwater"
        ),
        SensorData(
            id="SNS-PH-501",
            name="Latur Water Quality pH Node",
            type="ph",
            status="warning",
            value=7.4,
            unit="pH",
            battery_level=100.0,
            lat=18.4088,
            lng=76.5604,
            address="Manjra River Intake Purifier #1",
            zone="Maharashtra Latur District"
        )
    ]
    db.add_all(sensors)
    db.commit()  # commit sensors so Alerts FK works

    # 6. Seed Alerts
    alerts = [
        Alert(
            id="LEAK-2026-88",
            sensor_id="SNS-PL-101",
            location_name="Dwarka Sector 11 Main Feeder - Segment 4B",
            lat=28.5830,
            lng=77.0500,
            zone="Delhi NCT Sector 4",
            pipe_material="Ductile Iron (Class 52)",
            pipe_age_years=28,
            detected_flow_drop_pct=31.5,
            anomaly_score=0.89,
            estimated_water_loss_lpm=450.0,
            severity="critical",
            status="active",
            ai_diagnostics="Acoustic anomaly screening (seeded pilot example) — not a confirmed field observation"
        ),
        Alert(
            id="LEAK-2026-89",
            sensor_id="SNS-AC-204",
            location_name="Bandra West Trunkline - Substation 2",
            lat=19.0596,
            lng=72.8295,
            zone="Mumbai Ward H-West",
            pipe_material="Prestressed Concrete Cylinder",
            pipe_age_years=34,
            detected_flow_drop_pct=14.2,
            anomaly_score=0.74,
            estimated_water_loss_lpm=220.0,
            severity="high",
            status="investigating",
            ai_diagnostics="Acoustic telemetry indicates persistent high-frequency sound wave signatures consistent with micro-cracking in circumferential welds."
        )
    ]
    db.add_all(alerts)

    # 7. Seed Weather
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
    db.add(weather)

    # 8. Seed Recommendations
    recs = [
        AIRecommendation(
            id="REC-001",
            priority="CRITICAL",
            category="INFRASTRUCTURE",
            title="Automated Isolation Valve Deployment - Sector North",
            action_description="Execute instant solenoid remote valve shutdown on Feed PIPE-MAIN-DL4 to halt 450 LPM loss.",
            estimated_impact="Saves 648,000 liters/day; restores network pressure by +0.8 Bar.",
            target_sector="North Industrial District",
            region_id="REG-NORTH-01",
            overall_health_index=72.4
        ),
        AIRecommendation(
            id="REC-002",
            priority="HIGH",
            category="CONSERVATION",
            title="Stage 2 Voluntary Municipal Water Restrictions",
            action_description="Issue automated SMS alerts restricting residential irrigation to alternate evenings (8 PM - 6 AM).",
            estimated_impact="Reduces peak residential demand by 14.2 MGD during current heatwave.",
            target_sector="Central Valley Region",
            region_id="REG-CENTRAL-VALLEY",
            overall_health_index=62.5
        )
    ]
    db.add_all(recs)

    # 9. Seed Reports
    reports = [
        Report(
            id="RPT-2026-001",
            title="Q2 Comprehensive Aquifer & Groundwater Depletion Briefing",
            date_generated=date(2026, 7, 1),
            author="AquaMind AI Hydro-Analytics Unit",
            category="GROUNDWATER",
            summary="Analysis of regional monitoring borewells indicates a mean drawdown of 2.8m across the Deep Sandstone Formation.",
            key_metrics={"mean_drawdown_m": 2.8, "critical_wells": 3, "safe_yield_mcm": 145.0},
            status="PUBLISHED"
        ),
        Report(
            id="RPT-2026-002",
            title="Hydro-Acoustic Leakage Assessment - North Main Grid",
            date_generated=date(2026, 7, 15),
            author="Smart Pipeline Telemetry Engine",
            category="LEAKAGE",
            summary="Isolation forest anomaly detection detected 12 micro-fissures and 1 major burst in sector N4.",
            key_metrics={"total_leaks": 13, "estimated_loss_lpm": 624.0, "recovered_val_usd": 45000},
            status="ACTION_REQUIRED"
        )
    ]
    db.add_all(reports)

    # 10. Seed daily consumption series (municipal demand proxy for WSI / shortage)
    _ensure_consumption_series(db)

    db.commit()
    print("[Seeder] Database seeding completed successfully!")


def _ensure_consumption_series(db: Session) -> None:
    """Idempotent pilot MGD series so WSI has a real consumption signal."""
    from datetime import timedelta

    if db.query(ConsumptionSeries).first() is not None:
        return
    today = date.today()
    rows = []
    for i in range(14, -1, -1):
        d = today - timedelta(days=i)
        base = 88.0 + (4.0 if d.weekday() < 5 else -3.0)
        heat_bump = 6.0 if i < 5 else 0.0
        rows.append(
            ConsumptionSeries(
                region_id="REG-1",
                observed_date=d,
                demand_mgd=round(base + heat_bump + (i % 3) * 0.7, 2),
                population_thousands=850.0,
                source="seeded_pilot",
                notes="Pilot municipal MGD series — replace with AMI/billed consumption for production",
            )
        )
    db.add_all(rows)
    db.commit()
    print("[Seeder] Consumption series seeded.")
