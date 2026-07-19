"""
Automated tests for supply_chain_tracker.py

Run with:
    pytest test_supply_chain_tracker.py -v

These tests build a small, deterministic fixture dataset (not the full
project_data generator) so every expected number is known in advance and
the tests aren't at the mercy of random telemetry or a changing schedule.
"""

import json
import os

import pandas as pd
import pytest

from supply_chain_tracker import SupplyChainTracker, _equipment_category


# ---------------------------------------------------------------------------
# Fixture: builds a minimal project_data/ tree with 4 hand-picked equipment
# items chosen to hit every code path:
#   EQ-UPS-101   -> on time, low risk               (baseline "everything fine")
#   EQ-CHILL-202 -> delayed but within float          (DELAYED_WITHIN_FLOAT)
#   EQ-GEN-303   -> delayed, float nearly exhausted    (AT_RISK)
#   EQ-BATT-404  -> delayed past float, high risk vendor (CRITICAL breach + HIGH risk)
# ---------------------------------------------------------------------------
@pytest.fixture
def project_data(tmp_path):
    root = tmp_path / "project_data"

    eq_dir = root / "07_Supply_Chain_Data" / "Equipment_List"
    vend_dir = root / "07_Supply_Chain_Data" / "Vendor_Details"
    ship_dir = root / "07_Supply_Chain_Data" / "Shipment_Status"
    sched_dir = root / "06_Project_Schedule"
    for d in (eq_dir, vend_dir, ship_dir, sched_dir):
        d.mkdir(parents=True, exist_ok=True)

    equipment_ids = ["EQ-UPS-101", "EQ-CHILL-202", "EQ-GEN-303", "EQ-BATT-404"]
    vendors = ["VEND-DELTA", "VEND-YORK", "VEND-CATERPILLAR", "VEND-SCHNEIDER"]

    pd.DataFrame({
        "Equipment_ID": equipment_ids,
        "Project_ID": ["PRJ-TEST"] * 4,
        "Equipment_Name": ["Test UPS", "Test Chiller", "Test Generator", "Test Battery"],
        "Vendor_ID": vendors,
        "Current_Transit_Status": ["On-Site", "In Transit", "In Transit", "Stuck at Port"],
        "Days_Delayed": [0, 2, 5, 10],
    }).to_csv(eq_dir / "equipment_list.csv", index=False)

    pd.DataFrame({
        "Vendor_ID": vendors,
        "Contact_Entity": ["Delta Logistics", "York India", "Cat Systems", "Schneider Supply"],
        "Risk_Tier": ["Low", "Low", "Medium", "High"],
    }).to_csv(vend_dir / "vendor_master_profiles.csv", index=False)

    pd.DataFrame({
        "Equipment_ID": equipment_ids,
        "Origin_Hub": ["Bangalore", "Chennai", "Mumbai Factory", "Hyderabad"],
        "Est_Arrival_Date": ["2026-07-25", "2026-08-01", "2026-08-05", "2026-08-10"],
    }).to_csv(ship_dir / "shipment_logistics_tracking.csv", index=False)

    pd.DataFrame({
        "Activity_ID": ["ACT-1", "ACT-2", "ACT-3", "ACT-4"],
        "Equipment_ID": equipment_ids,
        "Activity_Name": ["UPS Install", "Chiller Piping", "Gen Testing", "Battery Setup"],
        "Planned_Duration_Days": [6, 10, 5, 4],
        "Total_Float_Days": [3, 8, 6, 7],   # UPS:3, Chiller:8, Gen:6, Battery:7
    }).to_csv(sched_dir / "active_working_schedule.csv", index=False)

    return str(root)


@pytest.fixture
def tracker(project_data):
    return SupplyChainTracker(project_data).load_data()


# ---------------------------------------------------------------------------
# 0. Loading
# ---------------------------------------------------------------------------
def test_load_data_success(tracker):
    assert len(tracker.merged_df) == 4
    assert set(tracker.merged_df["Equipment_ID"]) == {
        "EQ-UPS-101", "EQ-CHILL-202", "EQ-GEN-303", "EQ-BATT-404"
    }


def test_load_data_missing_file_raises(tmp_path):
    empty_root = tmp_path / "empty_project"
    empty_root.mkdir()
    with pytest.raises(FileNotFoundError):
        SupplyChainTracker(str(empty_root)).load_data()


def test_category_extraction():
    assert _equipment_category("EQ-UPS-101") == "UPS"
    assert _equipment_category("EQ-CHILL-202") == "CHILLER"
    assert _equipment_category("EQ-GEN-303") == "GENERATOR"
    assert _equipment_category("EQ-BATT-404") == "BATTERY"
    assert _equipment_category("EQ-CRAH-505") == "CRAH"


# ---------------------------------------------------------------------------
# 1. Delivery tracking
# ---------------------------------------------------------------------------
def test_track_deliveries_columns_and_sort(tracker):
    df = tracker.track_deliveries()
    expected_cols = {
        "Equipment_ID", "Equipment_Name", "Vendor_ID", "Contact_Entity",
        "Current_Transit_Status", "Origin_Hub", "Est_Arrival_Date", "Days_Delayed",
    }
    assert expected_cols.issubset(df.columns)
    # sorted descending by Days_Delayed -> most delayed item first
    assert df.iloc[0]["Equipment_ID"] == "EQ-BATT-404"
    assert df.iloc[-1]["Days_Delayed"] == 0


# ---------------------------------------------------------------------------
# 2. Delay detection
# ---------------------------------------------------------------------------
def test_detect_delays_classification(tracker):
    df = tracker.detect_delays().set_index("Equipment_ID")

    # UPS: 0 delay -> ON_TIME
    assert df.loc["EQ-UPS-101", "Delay_Classification"] == "ON_TIME"

    # Chiller: 2 delayed, float 8 -> 6 remaining -> comfortably within float
    assert df.loc["EQ-CHILL-202", "Delay_Classification"] == "DELAYED - WITHIN FLOAT"
    assert df.loc["EQ-CHILL-202", "Float_Remaining_Days"] == 6

    # Generator: 5 delayed, float 6 -> 1 remaining -> AT_RISK (<=2)
    assert df.loc["EQ-GEN-303", "Delay_Classification"] == "AT_RISK - FLOAT NEARLY EXHAUSTED"
    assert df.loc["EQ-GEN-303", "Float_Remaining_Days"] == 1

    # Battery: 10 delayed, float 7 -> -3 remaining -> CRITICAL breach
    assert df.loc["EQ-BATT-404", "Delay_Classification"] == "CRITICAL_DELAY - SCHEDULE BREACH"
    assert df.loc["EQ-BATT-404", "Float_Remaining_Days"] == -3


def test_detect_delays_never_negative_for_on_time(tracker):
    df = tracker.detect_delays()
    on_time = df[df["Days_Delayed"] == 0]
    assert (on_time["Delay_Classification"] == "ON_TIME").all()


# ---------------------------------------------------------------------------
# 3. Risk analysis
# ---------------------------------------------------------------------------
def test_risk_scores_within_bounds(tracker):
    df = tracker.risk_analysis()
    assert (df["Risk_Score_0to10"] >= 0).all()
    assert (df["Risk_Score_0to10"] <= 10).all()


def test_risk_level_matches_score_bands(tracker):
    df = tracker.risk_analysis()
    for _, row in df.iterrows():
        s = row["Risk_Score_0to10"]
        level = row["Risk_Level"]
        if s >= 7:
            assert level == "HIGH"
        elif s >= 4:
            assert level == "MEDIUM"
        else:
            assert level == "LOW"


def test_high_risk_vendor_with_schedule_breach_scores_highest(tracker):
    # Battery: High risk vendor + schedule breach should be the top risk item
    df = tracker.risk_analysis()
    assert df.iloc[0]["Equipment_ID"] == "EQ-BATT-404"
    assert df.iloc[0]["Risk_Level"] == "HIGH"


# ---------------------------------------------------------------------------
# 4. Alternative supplier recommendations
# ---------------------------------------------------------------------------
def test_recommendations_exclude_current_vendor(tracker):
    df = tracker.recommend_alternatives(risk_threshold="LOW")  # include everything
    for _, row in df.iterrows():
        assert row["Recommended_Alternate"] != row["Current_Vendor"]


def test_recommendations_only_include_at_or_above_threshold(tracker):
    df_medium = tracker.recommend_alternatives(risk_threshold="MEDIUM")
    assert set(df_medium["Current_Risk_Level"]).issubset({"MEDIUM", "HIGH"})
    assert "LOW" not in set(df_medium["Current_Risk_Level"])


def test_recommendations_handle_empty_pool_gracefully(tracker):
    # Sanity: function should not raise even if a category has no configured
    # alternates; it should fall back to the "None available" row instead.
    df = tracker.recommend_alternatives(risk_threshold="LOW")
    assert "Rationale" in df.columns
    assert df["Rationale"].notna().all()


# ---------------------------------------------------------------------------
# 5. Dashboard
# ---------------------------------------------------------------------------
def test_dashboard_summary_counts(tracker):
    s = tracker.dashboard_summary()
    assert s["total_equipment"] == 4
    assert s["delayed_shipments"] == 3          # chiller, gen, battery
    assert s["schedule_breaches"] == 1          # battery only
    assert 0 <= s["on_time_pct"] <= 100


def test_build_dashboard_is_json_serialisable(tracker):
    payload = tracker.build_dashboard()
    # will raise if anything (e.g. a Timestamp) isn't serialisable
    json.dumps(payload, default=str)
    assert set(payload.keys()) == {"summary", "deliveries", "delays", "risk", "recommendations"}


def test_export_dashboard_html_creates_file(tracker, tmp_path):
    out = tmp_path / "dashboard.html"
    path = tracker.export_dashboard_html(str(out))
    assert os.path.exists(path)
    content = out.read_text()
    assert "AI Supply Chain Tracker" in content
    assert "EQ-BATT-404" in content  # the critical item should actually appear in the table