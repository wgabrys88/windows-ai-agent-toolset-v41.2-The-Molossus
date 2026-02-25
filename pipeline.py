from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineResult:
    ghosts: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    heat: list[dict[str, Any]] = field(default_factory=list)
    next_turn: str = ""
    raw_display: dict[str, Any] = field(default_factory=dict)


def _clamp(v: Any) -> int:
    try:
        n: int = int(float(v))
    except (ValueError, TypeError):
        return 0
    return max(0, min(1000, n))


def _parse_regions(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        coords: Any = r.get("bbox_2d")
        if not isinstance(coords, list) or len(coords) != 4:
            continue
        out.append({
            "bbox_2d": [_clamp(coords[0]), _clamp(coords[1]), _clamp(coords[2]), _clamp(coords[3])],
            "label": str(r.get("label", "")),
        })
    return out


def _parse_actions(raw: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a in raw:
        if not isinstance(a, dict):
            continue
        coords: Any = a.get("bbox_2d")
        if not isinstance(coords, list) or len(coords) != 4:
            continue
        action_type: str = str(a.get("type", "")).strip().lower()
        if not action_type:
            continue
        out.append({
            "type": action_type,
            "bbox_2d": [_clamp(coords[0]), _clamp(coords[1]), _clamp(coords[2]), _clamp(coords[3])],
            "params": str(a.get("params", "")),
        })
    return out


def _build_heat(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    heat: list[dict[str, Any]] = []
    drag_start: list[int] | None = None
    for a in actions:
        entry: dict[str, Any] = {"type": a["type"], "bbox_2d": list(a["bbox_2d"])}
        if a["type"] == "drag_start":
            c: list[int] = a["bbox_2d"]
            drag_start = [(c[0] + c[2]) // 2, (c[1] + c[3]) // 2]
        elif a["type"] == "drag_end" and drag_start is not None:
            entry["drag_start"] = drag_start
            drag_start = None
        heat.append(entry)
    return heat


def _build_display(obs: str, regions: list[dict[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "observation": obs,
        "regions": regions,
        "actions": actions,
    }


def process(raw: str) -> PipelineResult:
    raw = raw.strip()
    if not raw:
        return PipelineResult(next_turn="(no prior observation)")

    try:
        obj: Any = json.loads(raw)
    except json.JSONDecodeError:
        return PipelineResult(next_turn=raw, raw_display={"observation": raw, "regions": [], "actions": []})

    if not isinstance(obj, dict):
        return PipelineResult(next_turn=raw, raw_display={"observation": raw, "regions": [], "actions": []})

    obs: str = str(obj.get("observation", ""))
    regions: list[dict[str, Any]] = _parse_regions(obj.get("regions", []))
    actions: list[dict[str, Any]] = _parse_actions(obj.get("actions", []))
    heat: list[dict[str, Any]] = _build_heat(actions)
    display: dict[str, Any] = _build_display(obs, regions, actions)

    return PipelineResult(
        ghosts=regions,
        actions=actions,
        heat=heat,
        next_turn=obs,
        raw_display=display,
    )


def to_json(result: PipelineResult) -> str:
    return json.dumps({
        "ghosts": result.ghosts,
        "actions": result.actions,
        "heat": result.heat,
        "next_turn": result.next_turn,
        "raw_display": result.raw_display,
    }, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_text: str = open(sys.argv[1], encoding="utf-8").read()
    else:
        input_text = sys.stdin.read()
    result: PipelineResult = process(input_text)
    print(to_json(result))
