from reprokit.profiles import StepNeeds, check_spend, choose_backend
from reprokit.validate import validate_document


def compute():
    return {"local": {"ram_gb": 8, "gpu": False}, "preference_order": ["local", "cluster"], "backends": [{"name": "cluster"}]}


def agents():
    return {"api_offload": {"warn_above_usd": 1.0, "ceiling_usd": 10.0}}


def test_local_chosen_when_it_fits():
    assert choose_backend(compute(), StepNeeds(4, False)) == "local"


def test_falls_through_to_next_backend_when_ram_too_small():
    assert choose_backend(compute(), StepNeeds(16, False)) == "cluster"


def test_gpu_need_skips_local_without_gpu():
    assert choose_backend(compute(), StepNeeds(4, True)) == "cluster"


def test_none_when_no_backend_qualifies():
    profile = compute()
    profile["preference_order"] = ["local"]
    assert choose_backend(profile, StepNeeds(16, False)) is None


def test_spend_at_warn_threshold_is_ok():
    assert check_spend(1.0, agents()) == "ok"


def test_spend_just_over_threshold_confirms():
    assert check_spend(1.01, agents()) == "confirm"


def test_spend_over_ceiling_refuses():
    assert check_spend(10.01, agents()) == "refuse"


def test_schemas_accept_minimal_valid_profiles(tmp_path):
    compute_path = tmp_path / "compute.yaml"
    compute_path.write_text("schema_version: 0.1.0\nlocal: {ram_gb: 8, cores: 4, gpu: false}\npreference_order: [local]\nbackends: []\n")
    agent_path = tmp_path / "agents.yaml"
    agent_path.write_text("schema_version: 0.1.0\nsubscriptions: []\nai_preference: local\napi_offload: {allowed: false, providers: [], warn_above_usd: 1.0, ceiling_usd: 10.0}\n")
    assert validate_document(compute_path, "compute") == []
    assert validate_document(agent_path, "agents") == []

def test_negative_spend_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="estimated_usd"):
        check_spend(-0.01, agents())


def test_nan_spend_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="estimated_usd"):
        check_spend(float("nan"), agents())
