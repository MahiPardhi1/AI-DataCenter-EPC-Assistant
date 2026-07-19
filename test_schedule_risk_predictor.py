"""
Automated tests for schedule_risk_predictor.py

Run with:
    pytest test_schedule_risk_predictor.py -v

Builds a small, deterministic fixture schedule (not the full project_data
generator) with a known 2-hop dependency chain so cascade propagation has
an exactly predictable answer.
"""

import json
import os

import pandas as pd
import pytest

import schedule_risk_predictor as srp_module
from schedule_risk_predictor import ScheduleRiskPredictor, _topological_order


# ---------------------------------------------------------------------------
# Fixture dependency graph used for these tests only (overrides the module's
# real ACTIVITY_DEPENDENCIES so tests don't depend on the real project's
# assumed chain). Chain: A (root) -> B -> C, plus D as an independent root.
# ---------------------------------------------------------------------------
TEST_DEPENDENCIES = {
    "ACT-A": [],
    "ACT-B": ["ACT-A"],
    "ACT-C": ["ACT-B"],
    "ACT-D": [],
}


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    monkeypatch.setattr(srp_module, "ACTIVITY_DEPENDENCIES", TEST_DEPENDENCIES)
    yield


@pytest.fixture
def project_data(tmp_path):
    root = tmp_path / "project_data"
    sched_dir = root / "06_Project_Schedule"
    eq_dir = root / "07_Supply_Chain_Data" / "Equipment_List"
    vend_dir = root / "07_Supply_Chain_Data" / "Vendor_Details"
    ship_dir = root / "07_Supply_Chain_Data" / "Shipment_Status"
    for d in (sched_dir, eq_dir, vend_dir, ship_dir):
        d.mkdir(parents=True, exist_ok=True)

    activities = ["ACT-A", "ACT-B", "ACT-C", "ACT-D"]
    equipment_ids = ["EQ-A", "EQ-B", "EQ-C", "EQ-D"]
    vendors = ["VEND-1", "VEND-2", "VEND-3", "VEND-4"]

    schedule = pd.DataFrame({
        "Activity_ID": activities,
        "Equipment_ID": equipment_ids,
        "Activity_Name": ["Task A", "Task B", "Task C", "Task D"],
        "Planned_Duration_Days": [5, 5, 5, 5],
        # A is on the critical path (0 float); others have buffer.
        "Total_Float_Days": [0, 6, 10, 20],
    })
    schedule.to_csv(sched_dir / "master_baseline_schedule.csv", index=False)
    schedule.to_csv(sched_dir / "active_working_schedule.csv", index=False)

    pd.DataFrame({
        "Equipment_ID": equipment_ids,
        "Project_ID": ["PRJ-TEST"] * 4,
        "Equipment_Name": ["Eq A", "Eq B", "Eq C", "Eq D"],
        "Vendor_ID": vendors,
        "Current_Transit_Status": ["On-Site", "In Transit", "In Transit", "On-Site"],
        # A is delayed 4 days -> immediately breaches its own 0 float.
        # B, C, D have no direct delay of their own; C should still inherit A's delay via B.
        "Days_Delayed": [4, 0, 0, 0],
    }).to_csv(eq_dir / "equipment_list.csv", index=False)

    pd.DataFrame({
        "Vendor_ID": vendors,
        "Contact_Entity": ["V1", "V2", "V3", "V4"],
        "Risk_Tier": ["High", "Low", "Low", "Medium"],
    }).to_csv(vend_dir / "vendor_master_profiles.csv", index=False)

    pd.DataFrame({
        "Equipment_ID": equipment_ids,
        "Origin_Hub": ["Hub1", "Hub2", "Hub3", "Hub4"],
        "Est_Arrival_Date": ["2026-08-01", "2026-08-05", "2026-08-10", "2026-08-15"],
    }).to_csv(ship_dir / "shipment_logistics_tracking.csv", index=False)

    return str(root)


@pytest.fixture
def predictor(project_data):
    return ScheduleRiskPredictor(project_data).load_data()


# ---------------------------------------------------------------------------
# 0. Loading / validation
# ---------------------------------------------------------------------------
def test_load_data_success(predictor):
    assert len(predictor.merged_df) == 4


def test_load_data_missing_file_raises(tmp_path):
    empty_root = tmp_path / "empty_project"
    empty_root.mkdir()
    with pytest.raises(FileNotFoundError):
        ScheduleRiskPredictor(str(empty_root)).load_data()


def test_topological_order_detects_cycle():
    cyclic = {"X": ["Y"], "Y": ["X"]}
    with pytest.raises(ValueError):
        _topological_order(cyclic)


def test_topological_order_respects_dependencies():
    order = _topological_order(TEST_DEPENDENCIES)
    assert order.index("ACT-A") < order.index("ACT-B") < order.index("ACT-C")


def test_load_data_rejects_unknown_activity_in_dependency_map(project_data, monkeypatch):
    bad_deps = {"ACT-A": [], "ACT-GHOST": ["ACT-A"]}
    monkeypatch.setattr(srp_module, "ACTIVITY_DEPENDENCIES", bad_deps)
    with pytest.raises(ValueError):
        ScheduleRiskPredictor(project_data).load_data()


# ---------------------------------------------------------------------------
# 1. Schedule analysis
# ---------------------------------------------------------------------------
def test_analyze_schedule_no_change_when_identical(predictor):
    df = predictor.analyze_schedule()
    assert (df["Schedule_Change_Flag"] == "NO_CHANGE").all()


def test_analyze_schedule_flags_slippage(project_data):
    # Mutate the active schedule to slip Task A's float
    active_path = os.path.join(project_data, "06_Project_Schedule", "active_working_schedule.csv")
    df = pd.read_csv(active_path)
    df.loc[df["Activity_ID"] == "ACT-B", "Total_Float_Days"] = 2  # was 6 -> now less float
    df.to_csv(active_path, index=False)

    predictor = ScheduleRiskPredictor(project_data).load_data()
    result = predictor.analyze_schedule().set_index("Activity_ID")
    assert result.loc["ACT-B", "Schedule_Change_Flag"] == "SCHEDULE_SLIPPED"
    assert result.loc["ACT-A", "Schedule_Change_Flag"] == "NO_CHANGE"


# ---------------------------------------------------------------------------
# 2. Delay prediction & cascade propagation
# ---------------------------------------------------------------------------
def test_direct_delay_only_on_the_delayed_activity(predictor):
    df = predictor.predict_delays().set_index("Activity_ID")
    assert df.loc["ACT-A", "Direct_Delay_Days"] == 4
    assert df.loc["ACT-B", "Direct_Delay_Days"] == 0
    assert df.loc["ACT-C", "Direct_Delay_Days"] == 0
    assert df.loc["ACT-D", "Direct_Delay_Days"] == 0


def test_delay_cascades_through_two_hop_chain(predictor):
    df = predictor.predict_delays().set_index("Activity_ID")
    # A's 4-day delay must propagate to B, then to C, unchanged in magnitude
    # (no compounding direct delay along the way in this fixture).
    assert df.loc["ACT-A", "Predicted_Delay_Days"] == 4
    assert df.loc["ACT-B", "Predicted_Delay_Days"] == 4
    assert df.loc["ACT-C", "Predicted_Delay_Days"] == 4
    # D is independent and must NOT inherit anything.
    assert df.loc["ACT-D", "Predicted_Delay_Days"] == 0


def test_float_remaining_reflects_predicted_delay(predictor):
    df = predictor.predict_delays().set_index("Activity_ID")
    # A: float 0, predicted delay 4 -> remaining -4
    assert df.loc["ACT-A", "Float_Remaining_Days"] == -4
    # B: float 6, predicted delay 4 -> remaining 2
    assert df.loc["ACT-B", "Float_Remaining_Days"] == 2
    # C: float 10, predicted delay 4 -> remaining 6
    assert df.loc["ACT-C", "Float_Remaining_Days"] == 6


# ---------------------------------------------------------------------------
# 3. Dependency analysis
# ---------------------------------------------------------------------------
def test_dependency_blast_radius(predictor):
    df = predictor.dependency_analysis().set_index("Activity_ID")
    # A has two downstream activities (B, then C through B)
    assert df.loc["ACT-A", "Downstream_Blast_Radius"] == 2
    assert df.loc["ACT-B", "Downstream_Blast_Radius"] == 1
    assert df.loc["ACT-C", "Downstream_Blast_Radius"] == 0
    assert df.loc["ACT-D", "Downstream_Blast_Radius"] == 0


def test_critical_path_flag(predictor):
    df = predictor.dependency_analysis().set_index("Activity_ID")
    assert bool(df.loc["ACT-A", "On_Critical_Path"]) == True
    assert bool(df.loc["ACT-B", "On_Critical_Path"]) == False


# ---------------------------------------------------------------------------
# 4. Risk prediction
# ---------------------------------------------------------------------------
def test_risk_scores_within_bounds(predictor):
    df = predictor.risk_prediction()
    assert (df["Risk_Score_0to10"] >= 0).all()
    assert (df["Risk_Score_0to10"] <= 10).all()


def test_risk_level_matches_score_bands(predictor):
    df = predictor.risk_prediction()
    for _, row in df.iterrows():
        s = row["Risk_Score_0to10"]
        level = row["Risk_Level"]
        if s >= 7:
            assert level == "HIGH"
        elif s >= 4:
            assert level == "MEDIUM"
        else:
            assert level == "LOW"


def test_critical_path_activity_with_breach_is_high_risk(predictor):
    df = predictor.risk_prediction().set_index("Activity_ID")
    assert df.loc["ACT-A", "Risk_Level"] == "HIGH"


def test_untouched_independent_activity_is_low_risk(predictor):
    df = predictor.risk_prediction().set_index("Activity_ID")
    assert df.loc["ACT-D", "Risk_Level"] == "LOW"


# ---------------------------------------------------------------------------
# 5. Recovery actions
# ---------------------------------------------------------------------------
def test_recovery_actions_only_for_at_risk_activities(predictor):
    risk_df = predictor.risk_prediction()
    actions_df = predictor.recommend_recovery_actions()
    at_risk_ids = set(risk_df[risk_df["Risk_Level"] != "LOW"]["Activity_ID"])
    assert set(actions_df["Activity_ID"]) == at_risk_ids


def test_critical_breach_gets_escalation_action(predictor):
    df = predictor.recommend_recovery_actions().set_index("Activity_ID")
    assert "Escalate" in df.loc["ACT-A", "Recommended_Actions"]


def test_cascade_hub_gets_prioritization_action(predictor):
    df = predictor.recommend_recovery_actions()
    # ACT-A has downstream_blast_radius=2 and is at risk -> should mention prioritization
    row = df[df["Activity_ID"] == "ACT-A"].iloc[0]
    assert "Prioritize" in row["Recommended_Actions"] or "Crash" in row["Recommended_Actions"]


# ---------------------------------------------------------------------------
# 6. Dashboard
# ---------------------------------------------------------------------------
def test_dashboard_summary_counts(predictor):
    s = predictor.dashboard_summary()
    assert s["total_activities"] == 4
    assert s["critical_path_activities"] == 1
    assert s["schedule_breaches"] == 1  # only ACT-A goes negative


def test_build_dashboard_is_json_serialisable(predictor):
    payload = predictor.build_dashboard()
    json.dumps(payload, default=str)
    assert set(payload.keys()) == {
        "summary", "schedule_analysis", "predicted_delays",
        "dependency_analysis", "risk", "recovery_actions",
    }


def test_export_dashboard_html_creates_file(predictor, tmp_path):
    out = tmp_path / "dashboard.html"
    path = predictor.export_dashboard_html(str(out))
    assert os.path.exists(path)
    content = out.read_text()
    assert "AI Schedule Risk Predictor" in content
    assert "ACT-A" in content