/** Shapes for /performance (apps/api/app/modules/performance.py). */

export type PerfComponent = "production" | "quality" | "time";
export type Weights = Record<PerfComponent, number>;

export type RankingPolicy = {
  version_id: number | null;
  version: number;
  effective_from: string | null;
  weights: Weights;
  min_coverage_pct: number;
  period_days: number;
};

export type RankingRow = {
  worker: { id: number; name: string; code: string | null };
  operation: { id: number; name: string; smv: number };
  line_id: number | null;
  comparison_group: string;
  efficiency_pct: number | null;
  first_pass_pct: number | null;
  productive_pct: number | null;
  coverage_pct: number;
  eligible: boolean;
  exclusion_reason: string | null;
  scores: Weights | null;
  contributions: Weights | null;
  total: number | null;
  rank: number | null;
  group_size?: number;
};

export type Ranking = {
  period: { days: number; start: string; end: string };
  policy: RankingPolicy;
  policy_version_id: number | null;
  group: string | null;
  groups: { value: string; label: string }[];
  bonus_enabled: false;
  rows: RankingRow[];
};

export type Explanation = RankingRow & {
  period: Ranking["period"];
  policy_version_id: number | null;
  bonus_enabled: false;
  components: {
    key: PerfComponent;
    label: string;
    value: number | null;
    unit: string;
    score: number | null;
    weight: number;
    contribution: number | null;
    source: string;
  }[];
  excluded: { downtime_min: number; rejected_min: Record<string, number>; break_min: number; scheduled_min: number };
};

export const BAR: Record<PerfComponent, string> = {
  production: "var(--brand)",
  quality: "color-mix(in oklab, var(--brand) 55%, transparent)",
  time: "color-mix(in oklab, var(--brand) 25%, transparent)",
};
export const LABEL: Record<PerfComponent, string> = { production: "Production", quality: "Quality", time: "Productive time" };
export const COMPONENTS: PerfComponent[] = ["production", "quality", "time"];
