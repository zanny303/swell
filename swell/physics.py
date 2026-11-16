"""SWELL physics: the equations the twin runs. Everything here is plain numpy and deterministic.

Measurement model (per cell i, pass time t, relative to the first pass):
    y_i(t) = cos(inc) * m_i(t) + beta * [w_i(t) - w_i(t0)] + noise
        y     line-of-sight distance from phase (mm):  y = -(lambda / 4 pi) * phase
        m     real vertical ground motion (mm)
        beta  radar moisture artifact (mm of apparent motion per unit wetness), learned on low-clay ground
        w     wetness index, 0..1

Clay dynamics (daily step):
    m_i(t+1) = m_i(t) + (G_i * w_i(t - tau) - m_i(t)) / T
    G_i      = alpha * LEP_i * (1 - b * paved_i)
        LEP    soil-map shrink-swell rating (linear extensibility, %)
        T      relaxation time (days), tau = delay (days); alpha, b fitted

Rain memory:
    A(t) = k * A(t-1) + P(t)        (k = 0.9), wetness w = A / (A + A_half)
"""
from __future__ import annotations

import numpy as np

WAVELENGTH_MM = 238.4  # NISAR L-band, 1.2575 GHz
K_RAIN = 0.9
A_HALF = 40.0  # mm of rain index at which wetness = 0.5


def phase_to_los_mm(phase_rad: np.ndarray) -> np.ndarray:
    """Unwrapped phase (rad) to line-of-sight distance (mm). Sign convention: check on a known feature."""
    return -(WAVELENGTH_MM / (4.0 * np.pi)) * phase_rad


def rain_index(rain_mm: np.ndarray, k: float = K_RAIN, a0: float = 0.0) -> np.ndarray:
    a = np.empty(len(rain_mm))
    prev = a0
    for t, p in enumerate(rain_mm):
        prev = k * prev + p
        a[t] = prev
    return a


def wetness(rain_mm: np.ndarray, k: float = K_RAIN, a_half: float = A_HALF, reduction: float = 0.0) -> np.ndarray:
    """Wetness 0..1 from daily rain. `reduction` (0..1) = assumed cut in effective wetting (e.g. drainage)."""
    a = rain_index(np.asarray(rain_mm, float) * (1.0 - reduction), k)
    return a / (a + a_half)


def unit_response(w: np.ndarray, T: float, tau: int, s0: float = 0.0) -> np.ndarray:
    """Response s(t) of a cell with gain 1: s(t+1) = s(t) + (w(t - tau) - s(t)) / T.
    Dynamics are linear in the gain, so m_i(t) = G_i * s(t)."""
    s = np.empty(len(w))
    prev = s0
    for t in range(len(w)):
        drive = w[max(t - tau, 0)]
        prev = prev + (drive - prev) / T
        s[t] = prev
    return s


def gain(lep: np.ndarray, paved: np.ndarray, alpha: float, b: float) -> np.ndarray:
    return alpha * lep * (1.0 - b * paved)


def motion(w: np.ndarray, lep: np.ndarray, paved: np.ndarray, alpha: float, b: float, T: float, tau: int,
           s0: float | None = None) -> np.ndarray:
    """Vertical motion (days, *grid) in mm, relative to nothing: absolute swell state."""
    s = unit_response(w, T, tau, s0=w[0] if s0 is None else s0)
    return s[(slice(None),) + (None,) * lep.ndim] * gain(lep, paved, alpha, b)[None]


def reasenberg_jones_rate(t_days: np.ndarray, mainshock_mag: float, min_mag: float = 5.0,
                          a: float = -1.67, b: float = 0.91, c: float = 0.05, p: float = 1.08) -> np.ndarray:
    """Expected aftershocks per day at or above min_mag, generic parameters (Reasenberg & Jones 1989).
    A standard statistical forecast, not a SWELL result. Use USGS's own forecast where one is published."""
    return 10.0 ** (a + b * (mainshock_mag - min_mag)) * (np.asarray(t_days, float) + c) ** (-p)
