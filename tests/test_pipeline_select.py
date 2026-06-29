"""Skill selection routing."""
from hermes.models import OemAlert
from hermes.pipeline import select_skill


def test_lock_routes_to_rca_oracle():
    a = OemAlert(alert_type="lock", target_name="t", message="ORA-00060")
    assert select_skill(a) == "rca_oracle"


def test_cpu_threshold_routes_to_awr():
    a = OemAlert(alert_type="threshold", target_name="t", metric_name="cpu", severity="critical")
    assert select_skill(a) == "awr_summary"


def test_generic_routes_to_analyze():
    a = OemAlert(alert_type="custom", target_name="t", metric_name="tablespace")
    assert select_skill(a) == "analyze_alert"
