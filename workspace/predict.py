#!/usr/bin/env python3
"""Predict the hosted score of a candidate list from density measurements.

The hosted replay window is ~8750s per row. Given a template's measured
raw-per-second density (from Bedrock gpt-oss), the predicted row score is:

    raw_total = density * fill_seconds * fire_rate
    normalized = min(1000, raw_total / 200000 * 1000)
    public = mean(gpt_oss_row, gemma_row)

Bedrock gpt-oss is ~2.4x faster than the hosted llama.cpp gpt-oss (6s vs
~15s per single post), so a SPEED_RATIO is applied to map Bedrock elapsed
to hosted elapsed. This is the predictability model's one tunable knob.

Run from workspace/: .venv/bin/python predict.py
"""
from __future__ import annotations

REPLAY_WINDOW_S = 8750.0
NORMALIZE_DENOM = 200000.0
# hosted llama.cpp gpt-oss is slower than Bedrock by roughly this factor
SPEED_RATIO = 2.4

# measured on Bedrock gpt-oss (density_test.py), raw per Bedrock-second
BEDROCK_DENSITY = {
    "single_post": 2.7,      # 16 raw / ~6s
    "multi_post_4": 4.3,     # 48 raw / ~11s
    "multi_post_6": 4.5,     # 80 raw / ~18s
}


def hosted_density(template: str) -> float:
    """Map Bedrock raw/s to hosted raw/s (hosted model is slower)."""
    return BEDROCK_DENSITY[template] / SPEED_RATIO


def row_score(density: float, fill_fraction: float = 0.97,
              fire_rate: float = 1.0) -> float:
    raw = density * REPLAY_WINDOW_S * fill_fraction * fire_rate
    return min(1000.0, raw / NORMALIZE_DENOM * 1000.0)


def predict_public(gpt_template: str, gemma_template: str,
                   gemma_fire_rate: float = 1.0) -> float:
    """Predict public leaderboard = mean(gpt_row, gemma_row).

    gemma row is NOT measurable on Bedrock (different model gen), so it is
    parameterized by fire_rate — the fraction of the theoretical max that
    the hosted gemma actually achieves.
    """
    gpt = row_score(hosted_density(gpt_template))
    # gemma: single-post, fast row, ~900 candidates observed by nctuan
    gemma_raw = 900 * 18  # 900 single-post candidates × 18 raw
    gemma = min(1000.0, gemma_raw / NORMALIZE_DENOM * 1000.0 * gemma_fire_rate)
    return (gpt + gemma) / 2.0


def main():
    print("=" * 60)
    print("Hosted-score prediction (tunable: SPEED_RATIO, gemma_fire_rate)")
    print("=" * 60)
    for gpt_tmpl in ("single_post", "multi_post_4", "multi_post_6"):
        for gemma_fr in (1.0, 0.75, 0.5):
            pub = predict_public(gpt_tmpl, "single_post", gemma_fr)
            print(f"gpt={gpt_tmpl:14s} gemma_fire={gemma_fr:.2f} "
                  f"-> public {pub:6.1f}")
    print()
    print("Observed anchors: probe-D 65.2 (forged single), V6-A 58.7, "
          "evgendvorkin 88.5, leader 137")


if __name__ == "__main__":
    main()
