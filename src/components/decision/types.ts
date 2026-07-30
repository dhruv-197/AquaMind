/** Types for Decision Intelligence workspace. */

export type DecisionAction = {
  id: string;
  title: string;
  description: string;
  decision_type: string;
  priority_level: string;
  implementation_priority: string;
  timeline_bucket: string;
  why: string;
  contributing_models: string[];
  expected_benefits: string[];
  estimated_water_saved_mcm: number;
  population_protected: number;
  estimated_cost_inr: number;
  estimated_benefit_inr: number;
  impact_score: number;
  risk_reduction_score: number;
  confidence: number;
  optimization_score?: number;
  rank?: number;
  ai_reasoning?: {
    why: string;
    contributing_models: string[];
    expected_impact: string[];
    confidence: number;
  };
};

export type TimelineBucket = {
  bucket: string;
  label: string;
  count: number;
  actions: Array<{
    id?: string;
    title?: string;
    priority_level?: string;
    decision_type?: string;
    rank?: number;
    estimated_water_saved_mcm?: number;
    population_protected?: number;
  }>;
};

export type StrategySide = {
  strategy: string;
  label: string;
  description: string;
  water_saved_mcm: number;
  risk_reduction: number;
  population_protected: number;
  estimated_cost_inr: number;
  estimated_benefit_inr?: number;
  projected_wsi?: number;
  risk_label?: string;
  projected_storage_pct?: number;
  population_at_risk?: number;
};

export type DecisionWorkspaceData = {
  mode?: string;
  priority_level?: string;
  recommended_actions?: DecisionAction[];
  top_recommendations?: DecisionAction[];
  priority_queue?: Array<{
    rank: number;
    id: string;
    title: string;
    priority_level: string;
    decision_type: string;
    optimization_score: number;
    timeline_bucket: string;
  }>;
  operational_timeline?: TimelineBucket[];
  expected_outcomes?: {
    estimated_water_saved_mcm?: number;
    population_protected?: number;
    estimated_cost_inr?: number;
    estimated_benefit_inr?: number;
    net_benefit_inr?: number;
    average_risk_reduction?: number;
    actions_count?: number;
    baseline_wsi?: number;
  };
  ai_reasoning?: string[];
  scenario_comparison?: {
    current: StrategySide;
    optimized: StrategySide;
    delta: {
      water_saved_mcm: number;
      risk_reduction: number;
      population_protected: number;
      estimated_cost_inr: number;
      wsi_improvement?: number;
      net_benefit_inr?: number;
    };
  };
  upstream_ready?: { demand?: boolean; reservoir?: boolean; stress?: boolean };
  region_id?: string;
  message?: string;
};

export type DecisionStatus = {
  success: boolean;
  ready: boolean;
  module: string;
  module_version: string;
  upstream: Record<string, unknown>;
  message: string;
};
