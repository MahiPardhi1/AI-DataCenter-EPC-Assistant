"""
Module 3 - AI Schedule Risk Predictor
========================================
Project: PRJ-MUM-2026

Reads the project schedule + supply-chain data produced by the dataset
generator and provides:

    1. Schedule analysis (baseline vs. active)   -> analyze_schedule()
    2. Delay prediction (equipment -> activity)   -> predict_delays()
    3. Dependency analysis / cascade impact       -> dependency_analysis()
    4. Composite schedule risk prediction         -> risk_prediction()
    5. Recovery action recommendations            -> recommend_recovery_actions()
    6. Dashboard export                           -> build_dashboard() / export_dashboard_html()

Data sources consumed (all relative to --data-root, default "project_data"):
    06_Project_Schedule/master_baseline_schedule.csv
    06_Project_Schedule/active_working_schedule.csv
    07_Supply_Chain_Data/Equipment_List/equipment_list.csv
    07_Supply_Chain_Data/Vendor_Details/vendor_master_profiles.csv
    07_Supply_Chain_Data/Shipment_Status/shipment_logistics_tracking.csv

IMPORTANT ASSUMPTION - dependency graph:
    Your dataset does not include an explicit predecessor/successor column
    on the schedule (no "Predecessor_Activity_ID" field). Real activity
    dependencies were therefore inferred from construction logic and are
    declared explicitly in ACTIVITY_DEPENDENCIES below, the same way
    Module 4's ALTERNATE_SUPPLIER_POOL was declared. If you add a real
    dependency column to the schedule CSV later, replace
    ACTIVITY_DEPENDENCIES with a loader that reads it directly - everything
    downstream (propagation, risk, recovery actions) will keep working
    unchanged since it only consumes the resulting {activity: [predecessors]} dict.

Usage
-----
    python schedule_risk_predictor.py                        # prints full report
    python schedule_risk_predictor.py --data-root project_data --out reports/
    python schedule_risk_predictor.py --dashboard-only

As a library:
    from schedule_risk_predictor import ScheduleRiskPredictor
    srp = ScheduleRiskPredictor("project_data")
    srp.load_data()
    schedule_diff = srp.analyze_schedule()
    delays = srp.predict_delays()
    deps = srp.dependency_analysis()
    risk = srp.risk_prediction()
    actions = srp.recommend_recovery_actions()
    srp.export_dashboard_html("schedule_dashboard.html")
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

import pandas as pd


# ---------------------------------------------------------------------------
# Assumed activity dependency graph (predecessor -> successor), inferred
# from construction sequencing logic since the dataset has no explicit
# dependency column. See module docstring above.
#
#   ACT-E10 (Electrical Hookup & UPS Mount)      -> ACT-B40 (Battery Bank Grid Setup)
#       electrical infrastructure must be live before the battery bank can
#       be tied into the grid.
#   ACT-E10 (Electrical Hookup & UPS Mount)      -> ACT-C30 (Generator Load Testing)
#       the ATS/generator transfer test requires the electrical distribution
#       side to already be energized.
#   ACT-M20 (Chilled Water Piping Connection)    -> ACT-H50 (CRAH Thermal Balancing)
#       CRAH airflow/humidity balancing needs chilled water already flowing.
# ---------------------------------------------------------------------------
ACTIVITY_DEPENDENCIES: Dict[str, List[str]] = {
    "ACT-E10": [],
    "ACT-M20": [],
    "ACT-C30": ["ACT-E10"],
    "ACT-B40": ["ACT-E10"],
    "ACT-H50": ["ACT-M20"],
}

RISK_WEIGHTS = {"Low": 0.5, "Medium": 1.0, "High": 2.0}


def _topological_order(dependencies: Dict[str, List[str]]) -> List[str]:
    """Standard Kahn's-algorithm topological sort. Raises ValueError on a cycle
    so a bad/edited dependency map fails loudly instead of silently mispropagating."""
    in_degree = {node: 0 for node in dependencies}
    for node, preds in dependencies.items():
        for p in preds:
            in_degree.setdefault(p, 0)
            in_degree[node] += 1

    queue = [n for n, d in in_degree.items() if d == 0]
    order = []
    successors_map = {n: [] for n in in_degree}
    for node, preds in dependencies.items():
        for p in preds:
            successors_map.setdefault(p, []).append(node)

    remaining = dict(in_degree)
    while queue:
        n = queue.pop(0)
        order.append(n)
        for succ in successors_map.get(n, []):
            remaining[succ] -= 1
            if remaining[succ] == 0:
                queue.append(succ)

    if len(order) != len(in_degree):
        raise ValueError("Cycle detected in ACTIVITY_DEPENDENCIES - cannot compute a valid schedule order.")
    return order


@dataclass
class ScheduleRiskPredictor:
    data_root: str = "project_data"
    baseline_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    active_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    equipment_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    vendor_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    shipment_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    merged_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    # ------------------------------------------------------------------
    # 0. Data loading
    # ------------------------------------------------------------------
    def load_data(self) -> "ScheduleRiskPredictor":
        base_path = os.path.join(self.data_root, "06_Project_Schedule", "master_baseline_schedule.csv")
        active_path = os.path.join(self.data_root, "06_Project_Schedule", "active_working_schedule.csv")
        eq_path = os.path.join(self.data_root, "07_Supply_Chain_Data", "Equipment_List", "equipment_list.csv")
        vendor_path = os.path.join(self.data_root, "07_Supply_Chain_Data", "Vendor_Details", "vendor_master_profiles.csv")
        shipment_path = os.path.join(self.data_root, "07_Supply_Chain_Data", "Shipment_Status", "shipment_logistics_tracking.csv")

        for path, label in [(base_path, "master_baseline_schedule"), (active_path, "active_working_schedule"),
                             (eq_path, "Equipment_List"), (vendor_path, "Vendor_Details"),
                             (shipment_path, "Shipment_Status")]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Required {label} file not found at: {path}")

        self.baseline_df = pd.read_csv(base_path)
        self.active_df = pd.read_csv(active_path)
        self.equipment_df = pd.read_csv(eq_path)
        self.vendor_df = pd.read_csv(vendor_path)
        self.shipment_df = pd.read_csv(shipment_path)
        self.shipment_df["Est_Arrival_Date"] = pd.to_datetime(self.shipment_df["Est_Arrival_Date"], errors="coerce")

        merged = self.active_df.merge(self.equipment_df, on="Equipment_ID", how="left")
        merged = merged.merge(self.vendor_df, on="Vendor_ID", how="left")
        merged = merged.merge(self.shipment_df, on="Equipment_ID", how="left")
        self.merged_df = merged

        # Fail loudly if someone edits ACTIVITY_DEPENDENCIES with an activity
        # that doesn't exist in the loaded schedule, or introduces a cycle.
        known_activities = set(self.active_df["Activity_ID"])
        unknown = set(ACTIVITY_DEPENDENCIES) - known_activities
        if unknown:
            raise ValueError(f"ACTIVITY_DEPENDENCIES references unknown Activity_ID(s): {unknown}")
        _topological_order(ACTIVITY_DEPENDENCIES)  # raises on cycle
        return self

    def _ensure_loaded(self):
        if self.merged_df.empty:
            self.load_data()

    # ------------------------------------------------------------------
    # 1. Analyze project schedules (baseline vs. active)
    # ------------------------------------------------------------------
    def analyze_schedule(self) -> pd.DataFrame:
        """
        Compares the master baseline schedule against the current active
        working schedule and flags any variance in planned duration or
        float. If the two are identical (as in a fresh project snapshot),
        every row reports NO_CHANGE - this is a live diff, not a static report,
        so it stays useful once the active schedule starts moving.
        """
        self._ensure_loaded()
        merged = self.baseline_df.merge(
            self.active_df, on=["Activity_ID", "Equipment_ID"], suffixes=("_Baseline", "_Active"), how="outer"
        )
        merged["Duration_Variance_Days"] = merged["Planned_Duration_Days_Active"] - merged["Planned_Duration_Days_Baseline"]
        merged["Float_Variance_Days"] = merged["Total_Float_Days_Active"] - merged["Total_Float_Days_Baseline"]

        def flag(row):
            if pd.isna(row["Duration_Variance_Days"]) or pd.isna(row["Float_Variance_Days"]):
                return "MISSING_IN_ONE_SCHEDULE"
            if row["Duration_Variance_Days"] == 0 and row["Float_Variance_Days"] == 0:
                return "NO_CHANGE"
            if row["Float_Variance_Days"] < 0:
                return "SCHEDULE_SLIPPED"
            return "SCHEDULE_IMPROVED"

        merged["Schedule_Change_Flag"] = merged.apply(flag, axis=1)
        cols = [
            "Activity_ID", "Equipment_ID", "Activity_Name_Active",
            "Planned_Duration_Days_Baseline", "Planned_Duration_Days_Active", "Duration_Variance_Days",
            "Total_Float_Days_Baseline", "Total_Float_Days_Active", "Float_Variance_Days",
            "Schedule_Change_Flag",
        ]
        out = merged[cols].rename(columns={"Activity_Name_Active": "Activity_Name"})
        return out.sort_values("Activity_ID").reset_index(drop=True)

    # ------------------------------------------------------------------
    # 2. Predict delays (equipment delay -> activity delay, with cascade)
    # ------------------------------------------------------------------
    def predict_delays(self) -> pd.DataFrame:
        """
        For each activity, computes:
          Direct_Delay_Days   - the delay coming from that activity's own
                                 equipment shipment (Days_Delayed).
          Inherited_Delay_Days- delay pushed onto this activity because a
                                 predecessor activity is predicted to finish
                                 late (propagated in topological order, so a
                                 3-activity chain compounds correctly).
          Predicted_Delay_Days- Direct + Inherited (the total lateness this
                                 activity is predicted to finish with).
          Float_Remaining_Days- Total_Float_Days - Predicted_Delay_Days.
        """
        self._ensure_loaded()
        order = _topological_order(ACTIVITY_DEPENDENCIES)
        by_activity = self.merged_df.set_index("Activity_ID")

        direct_delay = by_activity["Days_Delayed"].fillna(0).to_dict()
        predicted_delay: Dict[str, float] = {}

        for act in order:
            preds = ACTIVITY_DEPENDENCIES.get(act, [])
            inherited = max([predicted_delay.get(p, 0) for p in preds], default=0)
            predicted_delay[act] = direct_delay.get(act, 0) + inherited

        rows = []
        for act in by_activity.index:
            row = by_activity.loc[act]
            preds = ACTIVITY_DEPENDENCIES.get(act, [])
            inherited = max([predicted_delay.get(p, 0) for p in preds], default=0)
            total_delay = predicted_delay.get(act, direct_delay.get(act, 0))
            rows.append({
                "Activity_ID": act,
                "Activity_Name": row["Activity_Name"],
                "Equipment_ID": row["Equipment_ID"],
                "Direct_Delay_Days": direct_delay.get(act, 0),
                "Inherited_Delay_Days": inherited,
                "Predicted_Delay_Days": total_delay,
                "Total_Float_Days": row["Total_Float_Days"],
                "Float_Remaining_Days": row["Total_Float_Days"] - total_delay,
            })
        out = pd.DataFrame(rows).sort_values("Float_Remaining_Days").reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    # 3. Dependency analysis
    # ------------------------------------------------------------------
    def dependency_analysis(self) -> pd.DataFrame:
        """
        Per activity: its predecessors, its direct successors, whether it
        sits on the (zero-float) critical path, and how many downstream
        activities would inherit a delay if this one slips - a simple
        "blast radius" metric that tells you which activities are worth
        protecting first.
        """
        self._ensure_loaded()
        successors_map: Dict[str, List[str]] = {a: [] for a in ACTIVITY_DEPENDENCIES}
        for act, preds in ACTIVITY_DEPENDENCIES.items():
            for p in preds:
                successors_map.setdefault(p, []).append(act)

        def downstream_count(act, seen=None):
            seen = seen or set()
            for s in successors_map.get(act, []):
                if s not in seen:
                    seen.add(s)
                    downstream_count(s, seen)
            return len(seen)

        by_activity = self.merged_df.set_index("Activity_ID")
        rows = []
        for act in ACTIVITY_DEPENDENCIES:
            row = by_activity.loc[act]
            rows.append({
                "Activity_ID": act,
                "Activity_Name": row["Activity_Name"],
                "Predecessors": ", ".join(ACTIVITY_DEPENDENCIES[act]) or "None",
                "Direct_Successors": ", ".join(successors_map.get(act, [])) or "None",
                "Downstream_Blast_Radius": downstream_count(act),
                "On_Critical_Path": bool(row["Total_Float_Days"] == 0),
            })
        out = pd.DataFrame(rows).sort_values(
            ["On_Critical_Path", "Downstream_Blast_Radius"], ascending=[False, False]
        ).reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    # 4. Composite schedule risk prediction
    # ------------------------------------------------------------------
    def risk_prediction(self) -> pd.DataFrame:
        """
        Composite 0-10 risk score per activity, combining:
          - Critical path membership (0 float in baseline)     -> up to 3 pts
          - Predicted float exhaustion (from predict_delays)   -> up to 4 pts
          - Vendor risk tier of the equipment feeding it        -> up to 2 pts
          - Cascade weight (has downstream dependents at risk)  -> up to 1 pt
        """
        self._ensure_loaded()
        delays = self.predict_delays().set_index("Activity_ID")
        deps = self.dependency_analysis().set_index("Activity_ID")
        vendor_risk = self.vendor_df.set_index("Vendor_ID")["Risk_Tier"].to_dict()
        eq_vendor = self.equipment_df.set_index("Equipment_ID")["Vendor_ID"].to_dict()

        rows = []
        for act in delays.index:
            d = delays.loc[act]
            dep = deps.loc[act]
            vtier = vendor_risk.get(eq_vendor.get(d["Equipment_ID"]), "Medium")

            critical_component = 3 if dep["On_Critical_Path"] else 0
            if d["Float_Remaining_Days"] < 0:
                float_component = 4
            elif d["Float_Remaining_Days"] <= 2:
                float_component = 2
            else:
                float_component = 0
            vendor_component = RISK_WEIGHTS.get(vtier, 1.0)
            cascade_component = 1 if (dep["Downstream_Blast_Radius"] > 0 and d["Predicted_Delay_Days"] > 0) else 0

            score = round(min(10, critical_component + float_component + vendor_component + cascade_component), 1)
            level = "HIGH" if score >= 7 else ("MEDIUM" if score >= 4 else "LOW")

            rows.append({
                "Activity_ID": act,
                "Activity_Name": d["Activity_Name"],
                "Equipment_ID": d["Equipment_ID"],
                "On_Critical_Path": dep["On_Critical_Path"],
                "Predicted_Delay_Days": d["Predicted_Delay_Days"],
                "Float_Remaining_Days": d["Float_Remaining_Days"],
                "Vendor_Risk_Tier": vtier,
                "Downstream_Blast_Radius": dep["Downstream_Blast_Radius"],
                "Risk_Score_0to10": score,
                "Risk_Level": level,
            })
        out = pd.DataFrame(rows).sort_values("Risk_Score_0to10", ascending=False).reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    # 5. Suggest recovery actions
    # ------------------------------------------------------------------
    def recommend_recovery_actions(self) -> pd.DataFrame:
        """
        For every activity at MEDIUM or HIGH risk, produces one or more
        concrete recovery actions with a short rationale, driven by which
        risk factors actually fired for that activity (not a single generic
        recommendation).
        """
        self._ensure_loaded()
        risk_df = self.risk_prediction()
        rows = []
        for _, r in risk_df.iterrows():
            if r["Risk_Level"] == "LOW":
                continue
            actions = []
            if r["On_Critical_Path"] and r["Predicted_Delay_Days"] > 0:
                actions.append("Crash the activity: add shifts/crew or overlap tasks to recover lost critical-path days.")
            if r["Float_Remaining_Days"] < 0:
                actions.append("Escalate to project management immediately - float is already exhausted, this is a live schedule breach.")
            elif r["Float_Remaining_Days"] <= 2:
                actions.append("Fast-track: begin any preparatory work that doesn't require the delayed equipment, to protect the remaining float.")
            if r["Vendor_Risk_Tier"] == "High":
                actions.append(f"Engage an alternate/dual-source vendor for {r['Equipment_ID']} - current vendor carries a High risk rating.")
            if r["Downstream_Blast_Radius"] > 0:
                actions.append(f"Prioritize this activity in recovery planning - {r['Downstream_Blast_Radius']} downstream activity(ies) will inherit any further slip.")
            if not actions:
                actions.append("Monitor closely; no immediate action required yet.")

            rows.append({
                "Activity_ID": r["Activity_ID"],
                "Activity_Name": r["Activity_Name"],
                "Risk_Level": r["Risk_Level"],
                "Predicted_Delay_Days": r["Predicted_Delay_Days"],
                "Recommended_Actions": " | ".join(actions),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 6. Dashboard
    # ------------------------------------------------------------------
    def dashboard_summary(self) -> dict:
        self._ensure_loaded()
        risk = self.risk_prediction()
        delays = self.predict_delays()
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_activities": len(risk),
            "activities_at_risk": int((risk["Risk_Level"] != "LOW").sum()),
            "critical_path_activities": int(risk["On_Critical_Path"].sum()),
            "schedule_breaches": int((delays["Float_Remaining_Days"] < 0).sum()),
            "avg_predicted_delay_days": round(float(delays["Predicted_Delay_Days"].mean()), 1),
        }

    def build_dashboard(self) -> dict:
        self._ensure_loaded()
        return {
            "summary": self.dashboard_summary(),
            "schedule_analysis": self.analyze_schedule().to_dict(orient="records"),
            "predicted_delays": self.predict_delays().to_dict(orient="records"),
            "dependency_analysis": self.dependency_analysis().to_dict(orient="records"),
            "risk": self.risk_prediction().to_dict(orient="records"),
            "recovery_actions": self.recommend_recovery_actions().to_dict(orient="records"),
        }

    def export_dashboard_html(self, out_path: str = "schedule_dashboard.html") -> str:
        data = self.build_dashboard()
        s = data["summary"]

        def rows_html(records, columns):
            head = "".join(f"<th>{c}</th>" for c in columns)
            body = ""
            for r in records:
                cells = "".join(f"<td>{r.get(c, '')}</td>" for c in columns)
                marker = str(r.get("Risk_Level") or r.get("Schedule_Change_Flag") or "")
                row_class = ""
                if "HIGH" in marker or "SLIP" in marker:
                    row_class = "row-high"
                elif "MEDIUM" in marker:
                    row_class = "row-medium"
                body += f"<tr class='{row_class}'>{cells}</tr>"
            return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Schedule Risk Predictor Dashboard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#f4f6f8; margin:0; padding:24px; color:#1c2530; }}
  h1 {{ font-size:22px; margin-bottom:4px; }}
  .meta {{ color:#667; font-size:13px; margin-bottom:20px; }}
  .cards {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }}
  .card {{ background:#fff; border-radius:10px; padding:16px 20px; min-width:150px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
  .card .label {{ font-size:12px; color:#667; text-transform:uppercase; letter-spacing:.03em; }}
  .card .value {{ font-size:26px; font-weight:700; margin-top:4px; }}
  h2 {{ font-size:16px; margin-top:36px; border-bottom:2px solid #e2e6ea; padding-bottom:6px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; font-size:13px; box-shadow:0 1px 3px rgba(0,0,0,0.06); }}
  th {{ background:#1c2530; color:#fff; text-align:left; padding:8px 10px; font-weight:600; }}
  td {{ padding:7px 10px; border-bottom:1px solid #eef0f2; }}
  tr.row-high {{ background:#fdecea; }}
  tr.row-medium {{ background:#fff8e6; }}
</style>
</head>
<body>
  <h1>AI Schedule Risk Predictor &mdash; Activity Dashboard</h1>
  <div class="meta">Generated {s['generated_at']} &bull; Project PRJ-MUM-2026</div>

  <div class="cards">
    <div class="card"><div class="label">Total Activities</div><div class="value">{s['total_activities']}</div></div>
    <div class="card"><div class="label">Activities At Risk</div><div class="value">{s['activities_at_risk']}</div></div>
    <div class="card"><div class="label">Critical Path Items</div><div class="value">{s['critical_path_activities']}</div></div>
    <div class="card"><div class="label">Schedule Breaches</div><div class="value">{s['schedule_breaches']}</div></div>
    <div class="card"><div class="label">Avg Predicted Delay</div><div class="value">{s['avg_predicted_delay_days']}d</div></div>
  </div>

  <h2>Schedule Analysis (Baseline vs Active)</h2>
  {rows_html(data['schedule_analysis'], ["Activity_ID","Activity_Name","Planned_Duration_Days_Baseline","Planned_Duration_Days_Active","Total_Float_Days_Baseline","Total_Float_Days_Active","Schedule_Change_Flag"])}

  <h2>Predicted Delays (Direct + Inherited)</h2>
  {rows_html(data['predicted_delays'], ["Activity_ID","Activity_Name","Direct_Delay_Days","Inherited_Delay_Days","Predicted_Delay_Days","Total_Float_Days","Float_Remaining_Days"])}

  <h2>Dependency Analysis</h2>
  {rows_html(data['dependency_analysis'], ["Activity_ID","Predecessors","Direct_Successors","Downstream_Blast_Radius","On_Critical_Path"])}

  <h2>Schedule Risk Prediction</h2>
  {rows_html(data['risk'], ["Activity_ID","On_Critical_Path","Predicted_Delay_Days","Float_Remaining_Days","Vendor_Risk_Tier","Risk_Score_0to10","Risk_Level"])}

  <h2>Recommended Recovery Actions</h2>
  {rows_html(data['recovery_actions'], ["Activity_ID","Risk_Level","Predicted_Delay_Days","Recommended_Actions"])}

</body>
</html>"""
        with open(out_path, "w") as f:
            f.write(html)
        return out_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _print_section(title: str, df: pd.DataFrame):
    print(f"\n=== {title} ===")
    if df.empty:
        print("(no rows)")
    else:
        print(df.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Module 3 - AI Schedule Risk Predictor")
    parser.add_argument("--data-root", default="project_data", help="Path to project_data folder")
    parser.add_argument("--out", default=".", help="Directory to write dashboard/report outputs")
    parser.add_argument("--dashboard-only", action="store_true", help="Only build the HTML dashboard, skip console report")
    args = parser.parse_args()

    srp = ScheduleRiskPredictor(args.data_root).load_data()
    os.makedirs(args.out, exist_ok=True)

    if not args.dashboard_only:
        _print_section("Schedule Analysis (Baseline vs Active)", srp.analyze_schedule())
        _print_section("Predicted Delays", srp.predict_delays())
        _print_section("Dependency Analysis", srp.dependency_analysis())
        _print_section("Schedule Risk Prediction", srp.risk_prediction())
        _print_section("Recommended Recovery Actions", srp.recommend_recovery_actions())
        print("\n=== Dashboard Summary ===")
        print(json.dumps(srp.dashboard_summary(), indent=2))

    html_path = os.path.join(args.out, "schedule_dashboard.html")
    srp.export_dashboard_html(html_path)
    json_path = os.path.join(args.out, "schedule_dashboard.json")
    with open(json_path, "w") as f:
        json.dump(srp.build_dashboard(), f, indent=2, default=str)

    print(f"\nDashboard written to: {html_path}")
    print(f"Raw JSON payload written to: {json_path}")


if __name__ == "__main__":
    main()