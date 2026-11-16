"""SYNTHETIC fixture. Not NASA data. Used only to test that the code recovers parameters it was given.

Everything written from this module is tagged source="SYNTHETIC". The fixture is processed the way real data is:
it is referenced to paved, low-clay, high-coherence ground, and it contains missing pixels.
`make(adversarial=...)` breaks one model assumption on purpose so the tests can be seen to FAIL when they should.
"""
from __future__ import annotations

import numpy as np

from . import physics as ph

TRUE = dict(alpha=6.0, b=0.6, T=14.0, tau=3, beta=9.0, inc_deg=37.0)


def _blobs(rng, n, k=5, scale=8.0):
    yy, xx = np.mgrid[0:n, 0:n]
    f = np.zeros((n, n))
    for _ in range(k):
        cy, cx = rng.uniform(0, n, 2)
        f += np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * scale ** 2))
    return f / f.max()


def make(seed: int = 7, n: int = 40, days: int = 150, noise_mm: float = 2.0, gps_noise_mm: float = 1.0,
         adversarial: str | None = None) -> dict:
    """adversarial: None | 'no_clay' (ground never moves; all phase change is artifact)
                         | 'control_moves' (the low-clay control ground really moves)
                         | 'wrong_soil_map' (the soil map handed to the model is unrelated to the real clay)"""
    rng = np.random.default_rng(seed)
    lep = 0.5 + 8.5 * _blobs(rng, n)            # % linear extensibility, 0.5..9
    lep[:, : n // 5] = 0.6                      # a low-clay strip
    paved = np.clip(1.6 * _blobs(rng, n, k=7, scale=7.0) - .1 + rng.normal(0, .05, (n, n)), 0, 1)
    paved[: n // 4, : n // 5] = 0.95            # paved low-clay block: the stable reference ground
    rain = np.zeros(days)                        # dry summer, storms from day 70
    for d in rng.choice(np.arange(70, days), 14, replace=False):
        rain[d] = rng.gamma(2.0, 12.0)
    rain[:70] += (rng.random(70) < 0.04) * rng.gamma(1.5, 4.0, 70)
    w = ph.wetness(rain)
    alpha = 0.0 if adversarial == "no_clay" else TRUE["alpha"]
    m = ph.motion(w, lep, paved, alpha, TRUE["b"], TRUE["T"], TRUE["tau"])   # (days, n, n)
    if adversarial == "control_moves":
        s = ph.unit_response(w, TRUE["T"], TRUE["tau"], s0=w[0])
        m = m + 25.0 * s[:, None, None] * ((lep < 1.5) & (paved < .5))[None]
    pass_days = np.array([d for d in range(0, days, 12) if not 40 <= d <= 54])        # 12-day repeat with a gap
    inc = np.radians(TRUE["inc_deg"] + np.linspace(-3, 3, n))[None, :] * np.ones((n, 1))   # incidence varies across track
    p0 = pass_days[0]
    los = np.stack([np.cos(inc) * (m[d] - m[p0]) + TRUE["beta"] * (1 - paved) * (w[d] - w[p0])
                    + rng.normal(0, noise_mm, (n, n)) for d in pass_days])
    coh = np.clip(0.75 - 0.65 * _blobs(rng, n, k=3, scale=4.0) + rng.normal(0, .03, (n, n)), 0.05, 0.99)
    los = los + rng.normal(0, 1, los.shape) * (6.0 * (coh < 0.3))[None]               # bad pixels are noisy
    ref = (paved > .8) & (lep < 1.5) & (coh > .5)
    los = los - np.nanmedian(los[:, ref], axis=1)[:, None, None]                      # referenced like real data
    miss = rng.random(los.shape) < 0.03; miss[0] = False
    los[miss] = np.nan                                                                # missing is missing, not zero
    gps_cells = [(5, 3), (12, 30), (28, 22), (33, 35)]
    gps = {f"SYN{i}": dict(cell=c, days=np.arange(days).tolist(),
                           up_mm=(m[:, c[0], c[1]] - m[p0, c[0], c[1]] + rng.normal(0, gps_noise_mm, days)).tolist())
           for i, c in enumerate(gps_cells)}
    lep_given = np.roll(lep, (n // 2, n // 3), (0, 1)) if adversarial == "wrong_soil_map" else lep
    return dict(source="SYNTHETIC", name="Synthetic test site" + (f" [{adversarial}]" if adversarial else ""), n=n, days=days,
                rain=rain, w=w, lep=lep_given, paved=paved, pass_days=pass_days, los=los, coh=coh, inc=np.degrees(inc),
                inc_deg=TRUE["inc_deg"], ref=ref, gps=gps, truth_motion=m, bbox=[-97.05, 32.60, -96.55, 33.00])
