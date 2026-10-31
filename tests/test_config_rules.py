from reprokit.config_rules import check_config_consistency


def doc(start, end):
    return {"period": {"start": start, "end": end}}


def test_start_after_end_names_both_fields():
    problems = check_config_consistency(doc("2021-01-01", "2020-01-01"), "config.yaml")
    assert len(problems) == 1
    assert "period.start" in str(problems[0]) and "period.end" in str(problems[0])


def test_same_day_period_is_allowed():
    assert check_config_consistency(doc("2020-05-05", "2020-05-05"), "config.yaml") == []


def test_ordered_period_is_allowed():
    assert check_config_consistency(doc("2020-01-01", "2020-12-31"), "config.yaml") == []
