"""
Module 4 - AI Supply Chain Tracker
====================================
Project: PRJ-MUM-2026

Reads the relational supply-chain data produced by the project's dataset
generator and provides:

    1. Equipment delivery tracking      -> track_deliveries()
    2. Shipment delay detection         -> detect_delays()
    3. Supply chain risk analysis       -> risk_analysis()
    4. Alternative supplier recommender -> recommend_alternatives()
    5. Equipment tracking dashboard     -> build_dashboard() / export_dashboard_html()

Data sources consumed (all relative to --data-root, default "project_data"):
    07_Supply_Chain_Data/Equipment_List/equipment_list.csv
    07_Supply_Chain_Data/Vendor_Details/vendor_master_profiles.csv
    07_Supply_Chain_Data/Shipment_Status/shipment_logistics_tracking.csv
    06_Project_Schedule/active_working_schedule.csv
    02_Vendor_Documents/vendor_equipment_map.csv   (optional, for contract refs)

Usage
-----
    python supply_chain_tracker.py                       # prints full report
    python supply_chain_tracker.py --data-root project_data --out reports/
    python supply_chain_tracker.py --dashboard-only

As a library:
    from supply_chain_tracker import SupplyChainTracker
    tracker = SupplyChainTracker("project_data")
    tracker.load_data()
    df = tracker.track_deliveries()
    delays = tracker.detect_delays()
    risk = tracker.risk_analysis()
    recs = tracker.recommend_alternatives()
    tracker.export_dashboard_html("dashboard.html")
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Static knowledge base: which vendors are viable alternates for a given
# equipment category, in case the primary vendor is high-risk / delayed.
# In a production system this would live in its own CSV/DB table; it's kept
# here as a simple, editable lookup so the recommender has real candidates
# to reason over instead of only ever repeating the incumbent.
# ---------------------------------------------------------------------------
ALTERNATE_SUPPLIER_POOL = {
    "UPS": ["VEND-DELTA", "VEND-SCHNEIDER", "VEND-VERTIV"],
    "CHILLER": ["VEND-YORK", "VEND-CATERPILLAR"],
    "GENERATOR": ["VEND-CATERPILLAR", "VEND-DELTA"],
    "BATTERY": ["VEND-SCHNEIDER", "VEND-DELTA"],
    "CRAH": ["VEND-VERTIV", "VEND-YORK"],
}

RISK_WEIGHTS = {"Low": 1, "Medium": 2, "High": 3}


_CATEGORY_ALIASES = {
    "UPS": "UPS",
    "CHILL": "CHILLER",
    "GEN": "GENERATOR",
    "BATT": "BATTERY",
    "CRAH": "CRAH",
}


def _equipment_category(equipment_id: str) -> str:
    """EQ-UPS-101 -> UPS, EQ-CHILL-202 -> CHILLER, EQ-GEN-303 -> GENERATOR, etc."""
    parts = equipment_id.split("-")
    code = parts[1].upper() if len(parts) >= 2 else equipment_id.upper()
    return _CATEGORY_ALIASES.get(code, code)


@dataclass
class SupplyChainTracker:
    data_root: str = "project_data"
    equipment_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    vendor_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    shipment_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    schedule_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    merged_df: pd.DataFrame = field(default_factory=pd.DataFrame)

    # ------------------------------------------------------------------
    # 0. Data loading
    # ------------------------------------------------------------------
    def load_data(self) -> "SupplyChainTracker":
        eq_path = os.path.join(self.data_root, "07_Supply_Chain_Data", "Equipment_List", "equipment_list.csv")
        vendor_path = os.path.join(self.data_root, "07_Supply_Chain_Data", "Vendor_Details", "vendor_master_profiles.csv")
        shipment_path = os.path.join(self.data_root, "07_Supply_Chain_Data", "Shipment_Status", "shipment_logistics_tracking.csv")
        schedule_path = os.path.join(self.data_root, "06_Project_Schedule", "active_working_schedule.csv")

        for path, label in [(eq_path, "Equipment_List"), (vendor_path, "Vendor_Details"),
                             (shipment_path, "Shipment_Status"), (schedule_path, "Project_Schedule")]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Required {label} file not found at: {path}")

        self.equipment_df = pd.read_csv(eq_path)
        self.vendor_df = pd.read_csv(vendor_path)
        self.shipment_df = pd.read_csv(shipment_path)
        self.schedule_df = pd.read_csv(schedule_path)

        self.shipment_df["Est_Arrival_Date"] = pd.to_datetime(self.shipment_df["Est_Arrival_Date"], errors="coerce")

        # Build the master merged table: Equipment + Vendor + Shipment + Schedule float
        merged = self.equipment_df.merge(self.vendor_df, on="Vendor_ID", how="left")
        merged = merged.merge(self.shipment_df, on="Equipment_ID", how="left")
        merged = merged.merge(
            self.schedule_df[["Equipment_ID", "Activity_Name", "Planned_Duration_Days", "Total_Float_Days"]],
            on="Equipment_ID", how="left"
        )
        merged["Equipment_Category"] = merged["Equipment_ID"].apply(_equipment_category)
        self.merged_df = merged
        return self

    def _ensure_loaded(self):
        if self.merged_df.empty:
            self.load_data()

    # ------------------------------------------------------------------
    # 1. Equipment delivery tracking
    # ------------------------------------------------------------------
    def track_deliveries(self) -> pd.DataFrame:
        """Return a clean, human-readable delivery status table per equipment item."""
        self._ensure_loaded()
        cols = [
            "Equipment_ID", "Equipment_Name", "Vendor_ID", "Contact_Entity",
            "Current_Transit_Status", "Origin_Hub", "Est_Arrival_Date", "Days_Delayed",
        ]
        out = self.merged_df[cols].copy()
        out = out.sort_values("Days_Delayed", ascending=False).reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    # 2. Shipment delay detection
    # ------------------------------------------------------------------
    def detect_delays(self) -> pd.DataFrame:
        """
        Flags each shipment against its own schedule float (Total_Float_Days).
        A delay only becomes schedule-critical once Days_Delayed exceeds the
        float the activity has to absorb it -- so a 2-day delay on an item
        with 7 days of float is a non-event, while the same 2-day delay on
        an item with 0 float is a live problem.
        """
        self._ensure_loaded()
        df = self.merged_df.copy()
        df["Float_Remaining_Days"] = df["Total_Float_Days"] - df["Days_Delayed"]

        def classify(row):
            if row["Days_Delayed"] <= 0:
                return "ON_TIME"
            if row["Float_Remaining_Days"] < 0:
                return "CRITICAL_DELAY - SCHEDULE BREACH"
            if row["Float_Remaining_Days"] <= 2:
                return "AT_RISK - FLOAT NEARLY EXHAUSTED"
            return "DELAYED - WITHIN FLOAT"

        df["Delay_Classification"] = df.apply(classify, axis=1)
        cols = [
            "Equipment_ID", "Equipment_Name", "Vendor_ID", "Activity_Name",
            "Days_Delayed", "Total_Float_Days", "Float_Remaining_Days",
            "Delay_Classification", "Current_Transit_Status",
        ]
        out = df[cols].sort_values("Float_Remaining_Days").reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    # 3. Supply chain risk analysis
    # ------------------------------------------------------------------
    def risk_analysis(self) -> pd.DataFrame:
        """
        Composite risk score (0-10) per equipment item, combining:
          - Vendor risk tier (Low/Medium/High)
          - Schedule breach severity (float already exhausted or negative)
          - Delay magnitude relative to planned duration
        """
        self._ensure_loaded()
        df = self.detect_delays().merge(
            self.merged_df[["Equipment_ID", "Planned_Duration_Days"]], on="Equipment_ID", how="left"
        )
        vendor_risk = self.vendor_df.set_index("Vendor_ID")["Risk_Tier"].to_dict()
        eq_vendor = self.merged_df.set_index("Equipment_ID")["Vendor_ID"].to_dict()

        def score(row):
            vtier = vendor_risk.get(eq_vendor.get(row["Equipment_ID"]), "Medium")
            vendor_component = RISK_WEIGHTS.get(vtier, 2) * 2          # 0-6
            breach_component = 4 if row["Float_Remaining_Days"] < 0 else (
                2 if row["Float_Remaining_Days"] <= 2 else 0)          # 0-4
            magnitude_component = 0
            if row["Planned_Duration_Days"]:
                ratio = row["Days_Delayed"] / row["Planned_Duration_Days"]
                magnitude_component = min(2, round(ratio * 2, 1))      # 0-2
            return round(vendor_component + breach_component + magnitude_component, 1)

        df["Vendor_Risk_Tier"] = df["Equipment_ID"].map(eq_vendor).map(vendor_risk)
        df["Risk_Score_0to10"] = df.apply(score, axis=1)

        def tier(s):
            if s >= 7:
                return "HIGH"
            if s >= 4:
                return "MEDIUM"
            return "LOW"

        df["Risk_Level"] = df["Risk_Score_0to10"].apply(tier)
        cols = [
            "Equipment_ID", "Equipment_Name", "Vendor_ID", "Vendor_Risk_Tier",
            "Days_Delayed", "Float_Remaining_Days", "Risk_Score_0to10", "Risk_Level",
        ]
        out = df[cols].sort_values("Risk_Score_0to10", ascending=False).reset_index(drop=True)
        return out

    # ------------------------------------------------------------------
    # 4. Recommend alternative suppliers
    # ------------------------------------------------------------------
    def recommend_alternatives(self, risk_threshold: str = "MEDIUM") -> pd.DataFrame:
        """
        For every equipment item whose risk level is at/above `risk_threshold`,
        suggest alternate vendors capable of supplying that equipment category
        (from ALTERNATE_SUPPLIER_POOL), ranked by the alternate's own risk tier
        and excluding the current, already-struggling vendor.
        """
        self._ensure_loaded()
        order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        threshold = order.get(risk_threshold.upper(), 1)

        risk_df = self.risk_analysis()
        risk_df = risk_df[risk_df["Risk_Level"].map(order) >= threshold]

        vendor_risk = self.vendor_df.set_index("Vendor_ID")["Risk_Tier"].to_dict()
        vendor_contact = self.vendor_df.set_index("Vendor_ID")["Contact_Entity"].to_dict()

        rows = []
        for _, r in risk_df.iterrows():
            category = _equipment_category(r["Equipment_ID"])
            candidates = [v for v in ALTERNATE_SUPPLIER_POOL.get(category, []) if v != r["Vendor_ID"]]
            candidates_ranked = sorted(candidates, key=lambda v: RISK_WEIGHTS.get(vendor_risk.get(v, "Medium"), 2))

            if not candidates_ranked:
                rows.append({
                    "Equipment_ID": r["Equipment_ID"],
                    "Equipment_Name": r["Equipment_Name"],
                    "Current_Vendor": r["Vendor_ID"],
                    "Current_Risk_Level": r["Risk_Level"],
                    "Recommended_Alternate": "None available in pool",
                    "Alternate_Risk_Tier": "-",
                    "Alternate_Contact": "-",
                    "Rationale": "No qualified alternate vendor configured for this equipment category.",
                })
                continue

            best = candidates_ranked[0]
            rows.append({
                "Equipment_ID": r["Equipment_ID"],
                "Equipment_Name": r["Equipment_Name"],
                "Current_Vendor": r["Vendor_ID"],
                "Current_Risk_Level": r["Risk_Level"],
                "Recommended_Alternate": best,
                "Alternate_Risk_Tier": vendor_risk.get(best, "Unknown"),
                "Alternate_Contact": vendor_contact.get(best, "-"),
                "Rationale": (
                    f"Current vendor is {r['Risk_Level']} risk with {r['Days_Delayed']} day(s) delay "
                    f"({r['Float_Remaining_Days']} day(s) float remaining). "
                    f"{best} carries {vendor_risk.get(best, 'Unknown')} risk tier for this equipment category."
                ),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 5. Equipment tracking dashboard
    # ------------------------------------------------------------------
    def dashboard_summary(self) -> dict:
        """KPI roll-up used to drive the dashboard header cards."""
        self._ensure_loaded()
        delays = self.detect_delays()
        risk = self.risk_analysis()
        total = len(self.merged_df)
        delayed = int((delays["Days_Delayed"] > 0).sum())
        breached = int((delays["Delay_Classification"] == "CRITICAL_DELAY - SCHEDULE BREACH").sum())
        high_risk = int((risk["Risk_Level"] == "HIGH").sum())
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_equipment": total,
            "delayed_shipments": delayed,
            "schedule_breaches": breached,
            "high_risk_items": high_risk,
            "on_time_pct": round(100 * (total - delayed) / total, 1) if total else 0,
        }

    def build_dashboard(self) -> dict:
        """Returns a JSON-serialisable dict bundling every module output -
        the payload a front-end (web dashboard, BI tool, chat UI) would consume."""
        self._ensure_loaded()
        return {
            "summary": self.dashboard_summary(),
            "deliveries": self.track_deliveries().to_dict(orient="records"),
            "delays": self.detect_delays().to_dict(orient="records"),
            "risk": self.risk_analysis().to_dict(orient="records"),
            "recommendations": self.recommend_alternatives().to_dict(orient="records"),
        }

    def export_dashboard_html(self, out_path: str = "supply_chain_dashboard.html") -> str:
        """Renders a single self-contained HTML dashboard (no external JS deps)."""
        data = self.build_dashboard()
        s = data["summary"]

        def rows_html(records, columns):
            head = "".join(f"<th>{c}</th>" for c in columns)
            body = ""
            for r in records:
                cells = "".join(f"<td>{r.get(c, '')}</td>" for c in columns)
                risk_or_status = str(r.get("Risk_Level") or r.get("Delay_Classification") or "")
                row_class = ""
                if "HIGH" in risk_or_status or "BREACH" in risk_or_status:
                    row_class = "row-high"
                elif "MEDIUM" in risk_or_status or "AT_RISK" in risk_or_status:
                    row_class = "row-medium"
                body += f"<tr class='{row_class}'>{cells}</tr>"
            return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Supply Chain Tracker Dashboard</title>
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
  <h1>AI Supply Chain Tracker &mdash; Equipment Dashboard</h1>
  <div class="meta">Generated {s['generated_at']} &bull; Project PRJ-MUM-2026</div>

  <div class="cards">
    <div class="card"><div class="label">Total Equipment</div><div class="value">{s['total_equipment']}</div></div>
    <div class="card"><div class="label">Delayed Shipments</div><div class="value">{s['delayed_shipments']}</div></div>
    <div class="card"><div class="label">Schedule Breaches</div><div class="value">{s['schedule_breaches']}</div></div>
    <div class="card"><div class="label">High Risk Items</div><div class="value">{s['high_risk_items']}</div></div>
    <div class="card"><div class="label">On-Time %</div><div class="value">{s['on_time_pct']}%</div></div>
  </div>

  <h2>Equipment Delivery Tracking</h2>
  {rows_html(data['deliveries'], ["Equipment_ID","Equipment_Name","Vendor_ID","Contact_Entity","Current_Transit_Status","Origin_Hub","Est_Arrival_Date","Days_Delayed"])}

  <h2>Shipment Delay Detection</h2>
  {rows_html(data['delays'], ["Equipment_ID","Activity_Name","Days_Delayed","Total_Float_Days","Float_Remaining_Days","Delay_Classification"])}

  <h2>Supply Chain Risk Analysis</h2>
  {rows_html(data['risk'], ["Equipment_ID","Vendor_ID","Vendor_Risk_Tier","Days_Delayed","Risk_Score_0to10","Risk_Level"])}

  <h2>Recommended Alternative Suppliers</h2>
  {rows_html(data['recommendations'], ["Equipment_ID","Current_Vendor","Current_Risk_Level","Recommended_Alternate","Alternate_Risk_Tier","Rationale"])}

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
    parser = argparse.ArgumentParser(description="Module 4 - AI Supply Chain Tracker")
    parser.add_argument("--data-root", default="project_data", help="Path to project_data folder")
    parser.add_argument("--out", default=".", help="Directory to write dashboard/report outputs")
    parser.add_argument("--dashboard-only", action="store_true", help="Only build the HTML dashboard, skip console report")
    args = parser.parse_args()

    tracker = SupplyChainTracker(args.data_root).load_data()
    os.makedirs(args.out, exist_ok=True)

    if not args.dashboard_only:
        _print_section("Equipment Delivery Tracking", tracker.track_deliveries())
        _print_section("Shipment Delay Detection", tracker.detect_delays())
        _print_section("Supply Chain Risk Analysis", tracker.risk_analysis())
        _print_section("Recommended Alternative Suppliers", tracker.recommend_alternatives())
        print("\n=== Dashboard Summary ===")
        print(json.dumps(tracker.dashboard_summary(), indent=2))

    html_path = os.path.join(args.out, "supply_chain_dashboard.html")
    tracker.export_dashboard_html(html_path)
    json_path = os.path.join(args.out, "supply_chain_dashboard.json")
    with open(json_path, "w") as f:
        json.dump(tracker.build_dashboard(), f, indent=2, default=str)

    print(f"\nDashboard written to: {html_path}")
    print(f"Raw JSON payload written to: {json_path}")


if __name__ == "__main__":
    main()