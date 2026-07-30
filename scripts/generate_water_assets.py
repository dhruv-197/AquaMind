"""Generate national Water Assets geospatial dataset for AquaMind.

Run:  py -3 scripts/generate_water_assets.py

Adding a reservoir later: append a record to data/geospatial/water_assets.json
(or re-run this script after editing RESERVOIRS). No frontend changes required.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "geospatial" / "water_assets.json"

# Curated major / medium Indian reservoirs & dams (approx. lat/lng, capacity MCM).
# Sources: public CWC / state WRD catalogues (approximate coordinates for mapping).
RESERVOIRS: list[tuple[str, str, float, float, float]] = [
    ("Bhakra", "Himachal Pradesh", 31.4100, 76.4330, 9620),
    ("Pong (Maharana Pratap Sagar)", "Himachal Pradesh", 31.9700, 76.0500, 8570),
    ("Tehri", "Uttarakhand", 30.3780, 78.4800, 3540),
    ("Ramganga", "Uttarakhand", 29.5200, 78.7600, 2440),
    ("Rihand", "Uttar Pradesh", 24.2000, 83.0000, 10600),
    ("Matatila", "Uttar Pradesh", 25.1000, 78.4000, 1130),
    ("Gandhi Sagar", "Madhya Pradesh", 24.7000, 75.6300, 7320),
    ("Indira Sagar", "Madhya Pradesh", 22.2800, 76.4700, 12220),
    ("Omkareshwar", "Madhya Pradesh", 22.2400, 76.1500, 987),
    ("Bargi", "Madhya Pradesh", 22.9400, 79.9200, 3920),
    ("Tawa", "Madhya Pradesh", 22.5600, 77.9700, 2310),
    ("Sardar Sarovar", "Gujarat", 21.8300, 73.7500, 9500),
    ("Ukai", "Gujarat", 21.2600, 73.5900, 8511),
    ("Kadana", "Gujarat", 23.3000, 73.8400, 1542),
    ("Dharoi", "Gujarat", 24.0000, 72.8500, 908),
    ("Shetrunji", "Gujarat", 21.4700, 71.6500, 307),
    ("Koyna", "Maharashtra", 17.4000, 73.7500, 2797),
    ("Jayakwadi", "Maharashtra", 19.4900, 75.3700, 2909),
    ("Ujjani", "Maharashtra", 18.0700, 75.1200, 3170),
    ("Isapur", "Maharashtra", 19.7600, 77.4200, 1265),
    ("Upper Vaitarna", "Maharashtra", 19.7000, 73.5000, 331),
    ("Bhatsa", "Maharashtra", 19.5200, 73.4000, 976),
    ("Tansa", "Maharashtra", 19.5600, 73.2500, 184),
    ("Vihar", "Maharashtra", 19.1400, 72.9100, 27),
    ("Powai", "Maharashtra", 19.1200, 72.9100, 5),
    ("Mulshi", "Maharashtra", 18.4900, 73.5000, 523),
    ("Panshet", "Maharashtra", 18.3800, 73.6200, 303),
    ("Khadakwasla", "Maharashtra", 18.4000, 73.7700, 56),
    ("Yeldari", "Maharashtra", 19.7200, 76.7300, 934),
    ("Totladoh (Pench)", "Maharashtra", 21.6400, 79.2800, 1241),
    ("Nagarjuna Sagar", "Telangana", 16.5700, 79.3100, 11560),
    ("Sriram Sagar", "Telangana", 18.9700, 78.3400, 3172),
    ("Singur", "Telangana", 17.8000, 77.9000, 850),
    ("Lower Manair", "Telangana", 18.4000, 79.1000, 680),
    ("Srisailam", "Andhra Pradesh", 16.0800, 78.9000, 8720),
    ("Pulichintala", "Andhra Pradesh", 16.7600, 80.0600, 1296),
    ("Somasila", "Andhra Pradesh", 14.5000, 79.3000, 2210),
    ("Yeleru", "Andhra Pradesh", 17.3000, 82.0000, 680),
    ("Tungabhadra", "Karnataka", 15.2700, 76.3300, 3766),
    ("Almatti", "Karnataka", 16.3300, 75.8900, 6337),
    ("Narayanpur", "Karnataka", 16.2100, 76.2200, 1071),
    ("Krishnaraja Sagara", "Karnataka", 12.4200, 76.5700, 1369),
    ("Kabini", "Karnataka", 11.9700, 76.3500, 553),
    ("Harangi", "Karnataka", 12.4900, 75.9100, 235),
    ("Hemavathi", "Karnataka", 12.9000, 76.0000, 1050),
    ("Bhadra", "Karnataka", 13.7000, 75.6400, 2025),
    ("Linganamakki", "Karnataka", 14.1500, 74.8500, 4417),
    ("Supa", "Karnataka", 15.3100, 74.4000, 4178),
    ("Vani Vilasa Sagara", "Karnataka", 14.0000, 76.5000, 850),
    ("Mettur (Stanley)", "Tamil Nadu", 11.7900, 77.8000, 2647),
    ("Bhavanisagar", "Tamil Nadu", 11.4700, 77.1100, 929),
    ("Vaigai", "Tamil Nadu", 10.0700, 77.5800, 172),
    ("Sathanur", "Tamil Nadu", 12.1800, 78.8500, 230),
    ("Aliyar", "Tamil Nadu", 10.5000, 76.9700, 110),
    ("Periyar (Mullaperiyar)", "Kerala", 9.5300, 77.1500, 443),
    ("Idukki", "Kerala", 9.8400, 76.9700, 1996),
    ("Malampuzha", "Kerala", 10.8300, 76.6800, 226),
    ("Parambikulam", "Kerala", 10.3900, 76.7600, 380),
    ("Hirakud", "Odisha", 21.5200, 83.8700, 5818),
    ("Rengali", "Odisha", 21.2800, 85.0300, 5150),
    ("Upper Kolab", "Odisha", 18.8000, 82.6000, 935),
    ("Indravati", "Odisha", 19.2700, 82.8200, 2300),
    ("Machkund", "Odisha", 18.3000, 82.3000, 890),
    ("Maithon", "Jharkhand", 23.7800, 86.8100, 1066),
    ("Panchet", "Jharkhand", 23.6800, 86.7500, 1497),
    ("Tenughat", "Jharkhand", 23.7300, 85.8300, 1000),
    ("Chandil", "Jharkhand", 22.9700, 86.0000, 1400),
    ("Damodar Valley — Konar", "Jharkhand", 23.9400, 85.7600, 337),
    ("Kangsabati", "West Bengal", 22.9500, 86.7800, 1036),
    ("Teesta Barrage", "West Bengal", 26.5300, 88.7500, 450),
    ("Mayurakshi", "West Bengal", 23.9700, 87.3500, 548),
    ("Durgapur Barrage", "West Bengal", 23.4800, 87.3100, 200),
    ("Umiam", "Meghalaya", 25.6500, 91.8800, 140),
    ("Kopili", "Assam", 25.9000, 92.8000, 520),
    ("Karbi Langpi", "Assam", 26.0000, 92.5000, 180),
    ("Loktak", "Manipur", 24.5500, 93.7800, 500),
    ("Chamera", "Himachal Pradesh", 32.5600, 76.0000, 240),
    ("Nathpa Jhakri", "Himachal Pradesh", 31.5500, 77.9800, 340),
    ("Ranjit Sagar", "Punjab", 32.4500, 75.7300, 3280),
    ("Thein", "Punjab", 32.4500, 75.7300, 3280),
    ("Gobind Sagar (Bhakra lake)", "Himachal Pradesh", 31.4100, 76.4300, 9620),
    ("Bisalpur", "Rajasthan", 25.9200, 75.4500, 3156),
    ("Rana Pratap Sagar", "Rajasthan", 24.9200, 75.5800, 2900),
    ("Mahi Bajaj Sagar", "Rajasthan", 23.5600, 74.4000, 2180),
    ("Jawai", "Rajasthan", 25.1000, 73.1500, 300),
    ("Isarda", "Rajasthan", 26.3000, 76.2000, 280),
    ("Chambal — Kota Barrage", "Rajasthan", 25.1800, 75.8500, 120),
    ("Gandak Barrage", "Bihar", 26.7000, 84.9000, 180),
    ("Kosi Barrage", "Bihar", 26.5000, 86.9000, 200),
    ("Nagi Dam", "Bihar", 24.9000, 86.2000, 90),
    ("Chandan Dam", "Bihar", 25.0000, 86.5000, 110),
    ("Ban Sagar", "Madhya Pradesh", 24.2000, 81.3000, 5410),
    ("Bansagar", "Madhya Pradesh", 24.1900, 81.2900, 5410),
    ("Rajghat", "Madhya Pradesh", 24.7000, 78.3000, 850),
    ("Barna", "Madhya Pradesh", 22.9000, 77.8000, 540),
    ("Kolar Dam", "Madhya Pradesh", 23.2000, 77.3000, 270),
    ("Hasdeo Bango", "Chhattisgarh", 22.6000, 82.6000, 3410),
    ("Minimata (Hasdeo)", "Chhattisgarh", 22.6100, 82.6100, 3410),
    ("Ravishankar Sagar", "Chhattisgarh", 20.7000, 81.9000, 910),
    ("Dudhawa", "Chhattisgarh", 20.3000, 81.0000, 290),
    ("Gangrel", "Chhattisgarh", 20.5500, 81.6500, 767),
    ("Mahanadi Reservoir Complex", "Chhattisgarh", 21.2000, 81.7000, 1200),
    ("Balimela", "Odisha", 18.2500, 82.1000, 3610),
    ("Jalaput", "Odisha", 18.4500, 82.5500, 940),
    ("Salandi", "Odisha", 21.1000, 86.3000, 560),
    ("Subarnarekha (Chandil+)", "Jharkhand", 22.9700, 86.0200, 1960),
    ("Getalsud", "Jharkhand", 23.4500, 85.5500, 290),
    ("Massanjore", "Jharkhand", 24.1000, 87.3000, 620),
    ("Tilaiya", "Jharkhand", 24.3200, 85.5300, 394),
    ("Konar", "Jharkhand", 23.9400, 85.7700, 337),
    ("Dantiwada", "Gujarat", 24.3300, 72.3300, 907),
    ("Sipu", "Gujarat", 24.2000, 72.1000, 180),
    ("Watrak", "Gujarat", 23.2000, 73.3000, 220),
    ("Panam", "Gujarat", 22.9000, 73.7000, 500),
    ("Karjan", "Gujarat", 21.8000, 73.5000, 630),
    ("Hatnur", "Maharashtra", 21.1000, 75.9000, 380),
    ("Girna", "Maharashtra", 20.7000, 74.6000, 524),
    ("Nandur Madhmeshwar", "Maharashtra", 20.0000, 74.1000, 280),
    ("Manjara", "Maharashtra", 18.5000, 76.3000, 450),
    ("Lower Terna", "Maharashtra", 18.2000, 76.7000, 320),
    ("Siddeshwar", "Maharashtra", 19.7000, 76.9000, 250),
    ("Arunavati", "Maharashtra", 20.2000, 77.3000, 180),
    ("Upper Wardha", "Maharashtra", 21.3000, 78.2000, 564),
    ("Itiadoh", "Maharashtra", 21.0000, 79.8000, 290),
    ("Gosikhurd", "Maharashtra", 20.8000, 79.6000, 1145),
    ("Dindi", "Telangana", 16.8000, 78.9000, 280),
    ("Koilsagar", "Telangana", 16.5000, 77.9000, 190),
    ("Wyra", "Telangana", 17.2000, 80.4000, 120),
    ("Kaddam", "Telangana", 19.1000, 78.8000, 340),
    ("Nizam Sagar", "Telangana", 18.2000, 77.9000, 724),
    ("Priyadarshini Jurala", "Telangana", 16.0000, 77.7000, 600),
    ("Rajolibanda", "Karnataka", 16.1000, 77.3000, 180),
    ("Malaprabha", "Karnataka", 15.8000, 75.1000, 1070),
    ("Ghataprabha", "Karnataka", 16.2000, 74.5000, 1390),
    ("Hidkal", "Karnataka", 16.1500, 74.6400, 1390),
    ("Renuka Sagar (Gayathri)", "Karnataka", 14.2000, 76.3000, 240),
    ("Markonahalli", "Karnataka", 13.0000, 77.1000, 90),
    ("Manchanabele", "Karnataka", 12.8000, 77.3000, 35),
    ("Tippagondanahalli", "Karnataka", 12.9700, 77.3400, 120),
    ("Hesaraghatta", "Karnataka", 13.1500, 77.4800, 30),
]


def _stable_float(seed: str, lo: float, hi: float) -> float:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return lo + (h % 10_000) / 10_000 * (hi - lo)


def _risk(storage: float) -> str:
    if storage < 20:
        return "critical"
    if storage < 40:
        return "high"
    if storage < 60:
        return "moderate"
    return "healthy"


def _proxy(i: int) -> str:
    return ("RES-A", "RES-B", "RES-C")[i % 3]


def build() -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    assets: list[dict] = []

    for i, (name, state, lat, lng, cap) in enumerate(RESERVOIRS):
        current = round(_stable_float(f"cur-{name}", 18, 92), 1)
        # Mild forecast drift based on hash
        drift = _stable_float(f"drift-{name}", -12, 6)
        forecast = round(max(5.0, min(98.0, current + drift)), 1)
        conf = round(_stable_float(f"conf-{name}", 0.62, 0.93), 2)
        rid = f"RSV-IND-{i + 1:03d}"
        assets.append(
            {
                "id": rid,
                "type": "reservoir",
                "name": name,
                "state": state,
                "lat": lat,
                "lng": lng,
                "capacity_mcm": float(cap),
                "current_storage_pct": current,
                "forecast_storage_pct": forecast,
                "risk_level": _risk(current),
                "confidence": conf,
                "last_updated": now,
                "meta": {
                    "forecast_proxy_id": _proxy(i),
                    "country": "IN",
                    "asset_class": "surface_storage",
                },
            }
        )

    # Companion dams (linked to nearby reservoirs)
    dam_seeds = [
        ("Bhakra Dam", "Himachal Pradesh", 31.4105, 76.4340, "RSV-IND-001"),
        ("Tehri Dam", "Uttarakhand", 30.3775, 78.4805, "RSV-IND-003"),
        ("Sardar Sarovar Dam", "Gujarat", 21.8305, 73.7495, "RSV-IND-012"),
        ("Koyna Dam", "Maharashtra", 17.4010, 73.7510, "RSV-IND-017"),
        ("Nagarjuna Sagar Dam", "Telangana", 16.5750, 79.3120, "RSV-IND-031"),
        ("Hirakud Dam", "Odisha", 21.5300, 83.8720, "RSV-IND-059"),
        ("Idukki Arch Dam", "Kerala", 9.8430, 76.9750, "RSV-IND-057"),
        ("Almatti Dam", "Karnataka", 16.3310, 75.8920, "RSV-IND-040"),
        ("Mettur Dam", "Tamil Nadu", 11.7860, 77.8020, "RSV-IND-050"),
        ("Indira Sagar Dam", "Madhya Pradesh", 22.2820, 76.4720, "RSV-IND-008"),
    ]
    for i, (name, state, lat, lng, parent) in enumerate(dam_seeds):
        assets.append(
            {
                "id": f"DAM-IND-{i + 1:03d}",
                "type": "dam",
                "name": name,
                "state": state,
                "lat": lat,
                "lng": lng,
                "capacity_mcm": None,
                "current_storage_pct": None,
                "forecast_storage_pct": None,
                "risk_level": "healthy",
                "confidence": 0.9,
                "last_updated": now,
                "meta": {"parent_reservoir_id": parent, "country": "IN"},
            }
        )

    # Groundwater monitoring stations (sample national coverage)
    gw = [
        ("CGWB Delhi Ridge", "Delhi", 28.6100, 77.2000, 18.4),
        ("CGWB Jaipur", "Rajasthan", 26.9100, 75.7900, 32.1),
        ("CGWB Lucknow", "Uttar Pradesh", 26.8500, 80.9500, 14.2),
        ("CGWB Patna", "Bihar", 25.6000, 85.1400, 9.8),
        ("CGWB Bhopal", "Madhya Pradesh", 23.2600, 77.4100, 16.5),
        ("CGWB Ahmedabad", "Gujarat", 23.0300, 72.5800, 28.7),
        ("CGWB Pune", "Maharashtra", 18.5200, 73.8600, 22.3),
        ("CGWB Hyderabad", "Telangana", 17.3900, 78.4900, 19.6),
        ("CGWB Bengaluru", "Karnataka", 12.9700, 77.5900, 24.8),
        ("CGWB Chennai", "Tamil Nadu", 13.0800, 80.2700, 11.2),
        ("CGWB Kochi", "Kerala", 9.9300, 76.2700, 6.4),
        ("CGWB Bhubaneswar", "Odisha", 20.2700, 85.8400, 8.9),
        ("CGWB Kolkata", "West Bengal", 22.5700, 88.3600, 7.1),
        ("CGWB Guwahati", "Assam", 26.1400, 91.7400, 5.6),
        ("CGWB Chandigarh", "Chandigarh", 30.7300, 76.7800, 15.3),
        ("CGWB Nagpur", "Maharashtra", 21.1500, 79.0900, 17.8),
        ("CGWB Indore", "Madhya Pradesh", 22.7200, 75.8600, 21.4),
        ("CGWB Surat", "Gujarat", 21.1700, 72.8300, 12.6),
        ("CGWB Coimbatore", "Tamil Nadu", 11.0200, 76.9600, 18.9),
        ("CGWB Vizag", "Andhra Pradesh", 17.6900, 83.2200, 10.5),
    ]
    for i, (name, state, lat, lng, depth) in enumerate(gw):
        assets.append(
            {
                "id": f"GW-IND-{i + 1:03d}",
                "type": "groundwater_station",
                "name": name,
                "state": state,
                "lat": lat,
                "lng": lng,
                "capacity_mcm": None,
                "current_storage_pct": None,
                "forecast_storage_pct": None,
                "risk_level": "high" if depth > 25 else "moderate" if depth > 15 else "healthy",
                "confidence": 0.8,
                "last_updated": now,
                "meta": {"depth_to_water_m": depth, "country": "IN"},
            }
        )

    # Demand / stress / leak zones (city-scale centroids)
    demand_regions = [
        ("Mumbai Metro Demand", "Maharashtra", 19.0760, 72.8777),
        ("Delhi NCT Demand", "Delhi", 28.6139, 77.2090),
        ("Bengaluru Urban Demand", "Karnataka", 12.9716, 77.5946),
        ("Chennai Metro Demand", "Tamil Nadu", 13.0827, 80.2707),
        ("Hyderabad GHMC Demand", "Telangana", 17.3850, 78.4867),
        ("Pune Urban Demand", "Maharashtra", 18.5204, 73.8567),
        ("Ahmedabad AUDA Demand", "Gujarat", 23.0225, 72.5714),
        ("Kolkata KMA Demand", "West Bengal", 22.5726, 88.3639),
        ("Jaipur Urban Demand", "Rajasthan", 26.9124, 75.7873),
        ("Lucknow Demand", "Uttar Pradesh", 26.8467, 80.9462),
        ("Indore Demand", "Madhya Pradesh", 22.7196, 75.8577),
        ("Surat Demand", "Gujarat", 21.1702, 72.8311),
    ]
    for i, (name, state, lat, lng) in enumerate(demand_regions):
        assets.append(
            {
                "id": f"DEM-IND-{i + 1:03d}",
                "type": "demand_region",
                "name": name,
                "state": state,
                "lat": lat,
                "lng": lng,
                "capacity_mcm": None,
                "current_storage_pct": None,
                "forecast_storage_pct": None,
                "risk_level": "moderate",
                "confidence": 0.75,
                "last_updated": now,
                "meta": {"country": "IN", "region_kind": "municipal"},
            }
        )

    stress_regions = [
        ("Marathwada Stress Corridor", "Maharashtra", 19.1500, 76.5000, "high"),
        ("Bundelkhand Stress Belt", "Uttar Pradesh", 25.4500, 78.5700, "critical"),
        ("Saurashtra Stress Zone", "Gujarat", 21.7600, 70.8000, "high"),
        ("Rayalaseema Stress Zone", "Andhra Pradesh", 14.6800, 78.0000, "high"),
        ("Vidarbha Stress Zone", "Maharashtra", 21.1500, 79.0900, "moderate"),
        ("Western Rajasthan Stress", "Rajasthan", 26.9000, 70.9000, "critical"),
        ("North Karnataka Stress", "Karnataka", 15.8500, 75.7000, "moderate"),
        ("Telangana Interior Stress", "Telangana", 18.0000, 79.0000, "moderate"),
    ]
    for i, (name, state, lat, lng, risk) in enumerate(stress_regions):
        assets.append(
            {
                "id": f"WSI-IND-{i + 1:03d}",
                "type": "water_stress_region",
                "name": name,
                "state": state,
                "lat": lat,
                "lng": lng,
                "capacity_mcm": None,
                "current_storage_pct": None,
                "forecast_storage_pct": None,
                "risk_level": risk,
                "confidence": 0.78,
                "last_updated": now,
                "meta": {"country": "IN"},
            }
        )

    leak_zones = [
        ("Mumbai Island City DMA", "Maharashtra", 18.9500, 72.8200),
        ("Delhi Central DMA", "Delhi", 28.6300, 77.2200),
        ("Bengaluru South DMA", "Karnataka", 12.9100, 77.6000),
        ("Chennai North DMA", "Tamil Nadu", 13.1200, 80.2800),
        ("Hyderabad Old City DMA", "Telangana", 17.3600, 78.4700),
        ("Pune Cantonment DMA", "Maharashtra", 18.5100, 73.8800),
        ("Ahmedabad East DMA", "Gujarat", 23.0300, 72.6200),
        ("Kolkata Howrah DMA", "West Bengal", 22.5900, 88.3100),
    ]
    for i, (name, state, lat, lng) in enumerate(leak_zones):
        assets.append(
            {
                "id": f"LEAK-IND-{i + 1:03d}",
                "type": "leak_zone",
                "name": name,
                "state": state,
                "lat": lat,
                "lng": lng,
                "capacity_mcm": None,
                "current_storage_pct": None,
                "forecast_storage_pct": None,
                "risk_level": "high" if i % 3 == 0 else "moderate",
                "confidence": 0.7,
                "last_updated": now,
                "meta": {"country": "IN", "monitoring": "acoustic"},
            }
        )

    reservoir_count = sum(1 for a in assets if a["type"] == "reservoir")
    return {
        "version": "1.0.0",
        "updated_at": now,
        "source": "AquaMind national water assets catalogue",
        "counts": {
            "total": len(assets),
            "reservoir": reservoir_count,
            "dam": sum(1 for a in assets if a["type"] == "dam"),
            "groundwater_station": sum(1 for a in assets if a["type"] == "groundwater_station"),
            "demand_region": sum(1 for a in assets if a["type"] == "demand_region"),
            "water_stress_region": sum(1 for a in assets if a["type"] == "water_stress_region"),
            "leak_zone": sum(1 for a in assets if a["type"] == "leak_zone"),
        },
        "assets": assets,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build()
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({payload['counts']})")


if __name__ == "__main__":
    main()
