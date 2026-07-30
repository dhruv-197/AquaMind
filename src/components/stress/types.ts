/** Types for Water Stress Intelligence workspace. */

export type StressSeriesPoint = {
  date: string;
  historical: number | null;
  forecast: number | null;
  baseline_forecast?: number | null;
  lower: number | null;
  upper: number | null;
  confidence: number | null;
  risk: string | null;
};

export type MapRegion = {
  region_id: string;
  name: string;
  region_type: string;
  population: number;
  lat: number;
  lng: number;
  polygon?: number[][];
  reservoir_id?: string;
  water_stress_index: number;
  risk_label: string;
  map_color: string;
  population_impact: number;
  confidence: number;
  expected_stress_date?: string | null;
};

export type StressAction = {
  id: string;
  title: string;
  description: string;
  priority?: string;
};

export type StressScenario = {
  rainfall_delta_pct?: number;
  population_delta_pct?: number;
  demand_delta_pct?: number;
  temperature_delta_c?: number;
  reservoir_delta_pct?: number;
  reservoir_level_pct?: number;
  reservoir_id?: string;
};

export type StressWorkspaceData = {
  mode?: string;
  region?: {
    region_id: string;
    name: string;
    region_type: string;
    population: number;
    lat: number;
    lng: number;
    reservoir_id?: string;
  };
  water_stress_index?: number;
  risk_level?: string;
  risk_label?: string;
  map_color?: string;
  confidence?: number;
  expected_stress_date?: string | null;
  population_impact?: number;
  affected_regions?: { region_id: string; name: string; wsi: number; risk_label: string }[];
  summary?: {
    current_stress?: number;
    predicted_stress?: number;
    peak_forecast_stress?: number;
    highest_risk_region?: string;
    population_affected?: number;
    expected_shortage_date?: string | null;
    confidence?: number;
    risk_label?: string;
    baseline_stress?: number;
    delta_vs_baseline?: number;
  };
  components?: Record<string, { score: number; weight: number; contribution: number; detail: string }>;
  recommended_actions?: StressAction[];
  executive_insights?: string[];
  series?: StressSeriesPoint[];
  forecast_series?: StressSeriesPoint[];
  regional_comparison?: {
    region_id: string;
    name: string;
    region_type: string;
    wsi: number;
    baseline_wsi?: number;
    delta_wsi?: number;
    risk_label: string;
    population_impact: number;
  }[];
  map_regions?: MapRegion[];
  scenario?: StressScenario;
  has_scenario?: boolean;
  what_if_presets?: { id: string; label: string; scenario: StressScenario }[];
  upstream_status?: { demand_trained?: boolean; reservoir_trained?: boolean };
  message?: string;
};

export type StressStatus = {
  success: boolean;
  ready: boolean;
  module: string;
  module_version: string;
  upstream: Record<string, unknown>;
  regions: Array<{
    region_id: string;
    name: string;
    region_type: string;
    population: number;
    lat: number;
    lng: number;
    reservoir_id?: string;
  }>;
  what_if_presets: { id: string; label: string; scenario: StressScenario }[];
  message: string;
};
