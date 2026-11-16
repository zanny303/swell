"""Conservative structure screening from neighbourhood-scale ground-motion estimates.

This is NOT a structural analysis or a building-safety classifier. It reports a
transparent kinematic upper bound (a hypothetical structure that follows the
estimated ground exactly). Building distortion guides are shown only as context;
they are not applied to roads or pipes and do not replace code-specific engineering.
"""
from __future__ import annotations
from typing import Literal

STRUCTURE_TYPES = {
    "Unreinforced slab on grade": {
        "family": "building",
        "response": "A shallow slab may follow differential near-surface ground movement; actual response depends on geometry, reinforcement, soil contact and load.",
        "review": "Obtain foundation drawings, geotechnical profile, crack survey and precise level survey."
    },
    "Stiffened (ribbed) slab": {
        "family": "building",
        "response": "Stiffening can redistribute differential movement, but the effect depends on the engineered slab design and soil-structure interaction.",
        "review": "Review structural calculations, beam/rib layout, reinforcement and site-specific geotechnical data."
    },
    "Post-tensioned slab": {
        "family": "building",
        "response": "Post-tensioning changes slab response; performance cannot be inferred from a generic structure label.",
        "review": "Have the original design engineer review tendon layout, stressing records, joints and measured distortion."
    },
    "Pier and beam (suspended floor)": {
        "family": "building",
        "response": "A suspended floor may decouple from shallow active soil if supports extend below the active zone; pier movement remains possible.",
        "review": "Establish pier depth, bearing stratum, support condition and differential pier movement."
    },
    "Flexible pavement (road)": {
        "family": "transport",
        "response": "Road distress depends on pavement layers, subgrade, drainage, traffic and maintenance. Building angular-distortion guides do not apply.",
        "review": "Inspect longitudinal/transverse cracking, rutting, profile and drainage; use pavement-specific condition standards."
    },
    "Buried pipe (segmented)": {
        "family": "utility",
        "response": "Pipe response depends on material, joints, burial depth, bedding, restraint, pressure and soil-pipe interaction. Building angular-distortion guides do not apply.",
        "review": "Join to the real asset inventory; inspect joints, leaks, pressure anomalies and measured alignment."
    },
}
BUILDING_GUIDES = [
    {"max_distortion": 1/500, "label": "below 1/500", "context": "A commonly cited conservative angular-distortion screening guide; not a guarantee of no cracking."},
    {"max_distortion": 1/300, "label": "1/500 to 1/300", "context": "A commonly cited range associated with possible damage to brittle finishes; context and building type matter."},
    {"max_distortion": 1/150, "label": "1/300 to 1/150", "context": "A commonly cited range associated with increasing damage concern; not a safety threshold."},
    {"max_distortion": float("inf"), "label": "above 1/150", "context": "High kinematic distortion estimate; urgent site-specific professional assessment may be warranted."},
]

def screen(free_field_mm: float, kind: str, edge_m: float = 1.5,
           edge_reduction: float = 0.0, structure_span_m: float = 10.0) -> dict:
    """Compute an upper-bound differential distortion scenario.

    Inputs are explicit user assumptions:
      free_field_mm: absolute ground displacement difference across the neighbourhood
      edge_m: assumed distance over which edge moisture transition occurs
      edge_reduction: hypothetical fractional reduction in edge movement [0,1]
      structure_span_m: illustrative span over which the user wants a gradient considered

    The proxy is deliberately not a stiffness model. It does not estimate structural
    response, crack probability, load capacity or safety.
    """
    if kind not in STRUCTURE_TYPES:
        raise ValueError(f"Unknown structure type: {kind}")
    if edge_m <= 0 or structure_span_m <= 0:
        raise ValueError("edge_m and structure_span_m must be positive")
    if not 0 <= edge_reduction <= 1:
        raise ValueError("edge_reduction must be between 0 and 1")
    if free_field_mm < 0:
        raise ValueError("free_field_mm must be non-negative; pass magnitude")
    edge_mm = free_field_mm * (1-edge_reduction)
    # Kinematic upper bound: assume the full edge-to-interior differential occurs
    # over the shorter of the moisture-transition length and selected structure span.
    # This is a geometric screening proxy, not a soil-structure interaction solution.
    gradient_length_m = min(edge_m, structure_span_m)
    distortion = (edge_mm / 1000.0) / gradient_length_m
    guide = None
    if STRUCTURE_TYPES[kind]["family"] == "building":
        guide = next(x for x in BUILDING_GUIDES if distortion <= x["max_distortion"])
    return {
        "structure": kind, "family": STRUCTURE_TYPES[kind]["family"],
        "free_field_movement_mm": free_field_mm, "edge_movement_mm": edge_mm,
        "edge_transition_distance_m": edge_m, "structure_span_m": structure_span_m,
        "assumed_edge_reduction_fraction": edge_reduction,
        "upper_bound_angular_distortion": distortion,
        "one_in_n": (round(1/distortion) if distortion > 0 else None),
        "building_guide": guide,
        "response_context": STRUCTURE_TYPES[kind]["response"],
        "professional_review": STRUCTURE_TYPES[kind]["review"],
        "limitations": [
            "Radar-derived ground motion is neighbourhood-scale (nominal GUNW posting about 80 m), not a foundation survey.",
            "The calculation assumes the entire selected differential displacement occurs across the user-entered structure span.",
            "No stiffness, reinforcement, foundation depth, load, soil-structure interaction or crack model is inferred.",
            "Building guide bands are context only; they do not apply to roads or buried pipes.",
            "This output cannot determine whether a structure is safe or damaged."
        ],
        "status": "SCREENING_SCENARIO_NOT_STRUCTURAL_ANALYSIS"
    }
