"""Reinforcement learning for one concrete decision: in what order should a crew treat zones when it can do one per radar cycle?

Environment  the fitted clay twin. Each zone has its own gain (clay, paving) and wetness state. Rain for the next 60 days is
             unknown, so each episode draws it by block-bootstrapping the site's own rain record.
Action       every 12 days, pick one untreated zone to moisture-stabilise (barrier, controlled watering, drainage that holds
             moisture steady). Assumed effect: wetness swings there, up or down, are cut by `cut` from the day of treatment.
             Why not simply "less wetting"? In the twin, drying already-swollen clay moves the ground as much as wetting dry
             clay does, so one-way drying raised exposure above doing nothing. Steady moisture is what lowers movement.
Reward       minus the exposure: cells x millimetres of movement beyond `thr` mm from today's level, summed over days.
Learner      Q-learning with a linear value function over five readable zone features (numpy only).
Report       mean exposure on held-out rain sequences for: no action, random order, largest movement first, largest clay gain
             first, and the learned policy. If the learned policy does not beat the best simple rule, SWELL says so.

A planning aid inside a model. It is not evidence that drainage works at this site, and not a work order.
"""
from __future__ import annotations

import numpy as np

from . import fit as F
from . import stakeholders as SH

FEATURES = ["bias", "zone size x clay gain", "movement so far", "wetness now", "movement still to come", "cycles left"]


def _zones(site, fr):
    p = fr["par"]; ok = F.masks(site)["ok"] & ~site["ref"].astype(bool)
    gain = p["alpha"] * site["lep"] * (1 - p["b"] * site["paved"]); out = []
    for z in SH.zones(site):
        ii, jj = map(np.array, zip(*z["cells"])); good = ok[ii, jj]
        if good.sum() >= 5:
            out.append((z["name"], float(gain[ii, jj][good].mean()), int(good.sum())))
    return out


class Env:
    def __init__(self, site, fr, cut=0.5, thr=3.0, periods=5, step=12):
        p = fr["par"]; self.T, self.tau = float(p["T"]), int(p["tau"]); self.cut, self.thr, self.P, self.step = cut, thr, periods, step
        z = _zones(site, fr); self.names = [a for a, _, _ in z]; self.g = np.array([b for _, b, _ in z]); self.n = np.array([c for _, _, c in z], float)
        self.rain = np.asarray(site["rain"], float); w = np.asarray(site["w"], float)
        m = self.g * w[0]
        for t in range(len(w)):
            m = m + (self.g * w[max(t - self.tau, 0)] - m) / self.T
        self.m0 = m; a = 0.0
        for r in self.rain: a = 0.9 * a + r
        self.A0 = a; self.hist0 = np.tile(w[-(self.tau + 1):][:, None], (1, len(self.g)))
        self.scale = float((self.g * self.n).max()) or 1.0

    def sample_rain(self, rng):
        days = self.P * self.step; out = []
        while len(out) < days:
            s = rng.integers(0, max(1, len(self.rain) - 10)); out.extend(self.rain[s:s + 10])
        return np.array(out[:days])

    def reset(self, rain):
        self.r = rain; self.t = 0; self.k = 0; self.m = self.m0.copy(); self.A = np.full(len(self.g), self.A0)
        self.hist = self.hist0.copy(); self.treated = np.zeros(len(self.g), bool); self.Aref = self.A.copy(); return self

    def wet(self):
        a = np.where(self.treated, self.Aref + (1 - self.cut) * (self.A - self.Aref), self.A)
        return a / (a + 40.0)

    def features(self):
        w = self.wet()
        return np.stack([np.ones_like(self.g), self.g * self.n / self.scale, np.abs(self.m - self.m0) / 10.0, w,
                         (self.g * w - self.m) / 10.0, np.full_like(self.g, (self.P - self.k) / self.P)], 1)

    def act(self, a):
        if a is not None: self.treated[a] = True; self.Aref[a] = self.A[a]
        cost = 0.0
        for _ in range(self.step):
            self.A = 0.9 * self.A + self.r[self.t]
            self.hist = np.vstack([self.hist[1:], self.wet()])
            self.m = self.m + (self.g * self.hist[0] - self.m) / self.T
            cost += float(np.sum(self.n * np.maximum(np.abs(self.m - self.m0) - self.thr, 0.0))); self.t += 1
        self.k += 1
        return -cost / 1000.0, self.k >= self.P


def _policy(name, env, theta, rng):
    free = np.flatnonzero(~env.treated)
    if name == "no action" or not len(free): return None
    if name == "random order": return int(rng.choice(free))
    if name == "largest movement first": return int(free[np.argmax(np.abs(env.m - env.m0)[free])])
    if name == "largest clay gain first": return int(free[np.argmax((env.g * env.n)[free])])
    return int(free[np.argmax(env.features()[free] @ theta)])


def run(site: dict, fr: dict, episodes: int = 1200, eval_n: int = 150, seed: int = 11, cut: float = 0.5, thr: float = 3.0) -> dict:
    rng = np.random.default_rng(seed); env = Env(site, fr, cut, thr)
    if len(env.g) < 6:
        return dict(skipped="fewer than 6 resolved zones")
    theta = np.zeros(len(FEATURES)); gamma, lr = 0.95, 0.02
    for ep in range(episodes):
        env.reset(env.sample_rain(rng)); eps = max(0.03, 0.4 * (1 - ep / (0.7 * episodes))); done = False
        while not done:
            free = np.flatnonzero(~env.treated); phi_all = env.features()
            a = int(rng.choice(free)) if rng.random() < eps else int(free[np.argmax(phi_all[free] @ theta)])
            phi = phi_all[a]; r, done = env.act(a)
            nxt = 0.0 if done else float(np.max(env.features()[~env.treated] @ theta))
            theta += lr * np.clip(r + gamma * nxt - phi @ theta, -5, 5) * phi
    rains = [env.sample_rain(np.random.default_rng(10_000 + k)) for k in range(eval_n)]; scores = {}
    for name in ("no action", "random order", "largest movement first", "largest clay gain first", "learned policy"):
        tot = []; prng = np.random.default_rng(5)
        for rain in rains:
            env.reset(rain); done = False; s = 0.0
            while not done:
                r, done = env.act(_policy(name, env, theta, prng)); s -= r
            tot.append(s)
        scores[name] = float(np.mean(tot))
    env.reset(np.full(env.P * env.step, float(env.rain.mean()))); order = []
    for _ in range(env.P):
        a = _policy("learned policy", env, theta, rng); order.append(env.names[a]); env.act(a)
    rules = {k: v for k, v in scores.items() if k not in ("learned policy", "no action")}; best = min(rules, key=rules.get)
    gain = (rules[best] - scores["learned policy"]) / rules[best] if rules[best] > 0 else 0.0
    return dict(method="Q-learning, linear value function over 5 zone features, block-bootstrapped rain from this site's record",
                assumption=f"moisture-stabilising a zone cuts its wetness swings by {cut:.0%}; one zone per 12-day cycle, 5 cycles; exposure = cells x mm beyond {thr:g} mm from today",
                episodes=episodes, heldout_sequences=eval_n, zones=len(env.g), exposure=scores, best_simple_rule=best,
                learned_vs_best_rule=float(gain), learned_beats_rules=bool(gain > 0.01), suggested_order=order,
                weights=dict(zip(FEATURES, [float(x) for x in theta])), source=site["source"],
                reading=(f"The learned policy lowers model exposure by {gain:.0%} against the best simple rule ({best})." if gain > 0.01 else
                         f"The learned policy does not beat the best simple rule ({best}). The simple rule is enough here. Reported as found."))
