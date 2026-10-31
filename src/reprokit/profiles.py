from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class StepNeeds:
    ram_gb: float
    gpu: bool


def choose_backend(profile: dict, needs: StepNeeds) -> str | None:
    known = {backend["name"] for backend in profile["backends"]}
    for name in profile["preference_order"]:
        if name == "local":
            local = profile["local"]
            if local["ram_gb"] >= needs.ram_gb and (not needs.gpu or local["gpu"]):
                return "local"
        elif name in known:
            return name
    return None


def check_spend(estimated_usd: float, agents: dict) -> Literal["ok", "confirm", "refuse"]:
    offload = agents["api_offload"]
    if estimated_usd > offload["ceiling_usd"]:
        return "refuse"
    if estimated_usd > offload["warn_above_usd"]:
        return "confirm"
    return "ok"