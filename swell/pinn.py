"""Physics-informed neural network for the clay twin. numpy only, so it runs wherever SWELL runs.

What it is
    A small network m(t, clay rating, paved fraction) -> ground level in mm, trained on two things at once:
      data loss     at the radar passes it is allowed to see:   m(t_k) - m(t_0)  should equal the artifact-corrected estimate
      physics loss  on every day, seen or not:                  m(t+1) - m(t)    should equal (G*w(t-tau) - m(t)) / T
    with G = alpha * clay * (1 - b * paved). alpha, b and T are trained together with the network, so the
    network also reports which physical constants it needs to explain the data (an inverse problem, after
    Raissi, Perdikaris & Karniadakis 2019). The residual is the same discrete daily step as swell/physics.py.

What it is for
    An ablation, reported whatever the outcome: held-out error of (a) no change, (b) the closed-form physics fit,
    (c) the same network with the physics loss switched off, (d) the physics-informed network.
    If (d) does not beat (c), the physics is not helping and SWELL says so.

What it is not
    Not the forecast engine (the fitted equations plus the filter are), not validated on real NISAR until a real
    site is run, and not a design tool.
"""
from __future__ import annotations

import numpy as np

from . import fit as F

HID = 24


def _init(rng):
    s = lambda a, b: rng.normal(0, 1 / np.sqrt(a), (a, b))
    return dict(W1=s(3, HID), b1=np.zeros(HID), W2=s(HID, HID), b2=np.zeros(HID), W3=s(HID, 1), b3=np.zeros(1))


def _fwd(p, X):
    h1 = np.tanh(X @ p["W1"] + p["b1"]); h2 = np.tanh(h1 @ p["W2"] + p["b2"])
    return (h2 @ p["W3"] + p["b3"])[:, 0], (X, h1, h2)


def _back(p, cache, dout):
    X, h1, h2 = cache
    d3 = dout[:, None]
    g = dict(W3=h2.T @ d3, b3=d3.sum(0))
    d2 = (d3 @ p["W3"].T) * (1 - h2 ** 2); g["W2"] = h1.T @ d2; g["b2"] = d2.sum(0)
    d1 = (d2 @ p["W2"].T) * (1 - h1 ** 2); g["W1"] = X.T @ d1; g["b1"] = d1.sum(0)
    return g


def _phys(raw):
    """raw -> (alpha > 0, 0 < b < 1, T > 1 day) and their derivatives with respect to raw."""
    sp = lambda x: np.logaddexp(0, x); sg = lambda x: 1 / (1 + np.exp(-x))
    return (sp(raw[0]), sg(raw[1]), 1 + sp(raw[2])), (sg(raw[0]), sg(raw[1]) * (1 - sg(raw[1])), sg(raw[2]))


def loss_and_grad(p, raw, batch, lam, scale):
    """batch: Xk, X0, y (data) and Xa, Xb, lep, pv, wlag (physics). Network output is in units of `scale` mm."""
    (alpha, b, T), (da, db, dT) = _phys(raw)
    mk, ck = _fwd(p, batch["Xk"]); m0, c0 = _fwd(p, batch["X0"])
    e = scale * (mk - m0) - batch["y"]
    Ld = float(np.mean(e ** 2)); de = 2 * e * scale / len(e)
    grads = _back(p, ck, de); g0 = _back(p, c0, -de)
    graw = np.zeros(3); Lp = 0.0
    if lam > 0:
        ma, ca = _fwd(p, batch["Xa"]); mb, cb = _fwd(p, batch["Xb"])
        G = alpha * batch["lep"] * (1 - b * batch["pv"]); A = scale * ma
        r = scale * (mb - ma) - (G * batch["wlag"] - A) / T
        Lp = float(np.mean(r ** 2)); dr = lam * 2 * r / len(r)
        ga = _back(p, ca, dr * scale * (-1 + 1 / T)); gb = _back(p, cb, dr * scale)
        for k in grads: grads[k] = grads[k] + ga[k] + gb[k]
        graw[0] = np.sum(dr * (-batch["lep"] * (1 - b * batch["pv"]) * batch["wlag"] / T)) * da
        graw[1] = np.sum(dr * (alpha * batch["lep"] * batch["pv"] * batch["wlag"] / T)) * db
        graw[2] = np.sum(dr * ((G * batch["wlag"] - A) / T ** 2)) * dT
    for k in grads: grads[k] = grads[k] + g0[k]
    return Ld + lam * Lp, grads, graw, Ld, Lp


def _train(site, fr, lam, steps, seed):
    rng = np.random.default_rng(seed)
    mk = F.masks(site)["clay"]; lep, pv = site["lep"][mk], site["paved"][mk]
    pd = np.asarray(site["pass_days"]); D = float(pd[-1]); w = np.asarray(site["w"]); tau = int(fr["par"]["tau"])
    lmax = float(lep.max()); feat = lambda t, c: np.stack([t / D, lep[c] / lmax, pv[c]], 1)
    Y = fr["mcorr"][:, mk]; tr = np.asarray(fr["train"]); scale = float(np.nanstd(Y[tr])) or 1.0
    pairs = [(k, c) for k in tr for c in np.flatnonzero(np.isfinite(Y[k]))]; pairs = np.array(pairs)
    p = _init(rng); raw = np.array([np.log(np.expm1(max(scale / max(lmax, 1e-6), .1))), 0.0, np.log(np.expm1(13.0))])
    theta = [p, raw]; m1 = [{k: 0 * v for k, v in p.items()}, 0 * raw]; m2 = [{k: 0 * v for k, v in p.items()}, 0 * raw]
    hist = []
    for it in range(1, steps + 1):
        s = pairs[rng.integers(0, len(pairs), 256)]; k, c = s[:, 0], s[:, 1]
        cc = rng.integers(0, len(lep), 512); t = rng.integers(0, int(D), 512).astype(float)
        batch = dict(Xk=feat(pd[k].astype(float), c), X0=feat(np.full(len(c), float(pd[0])), c), y=Y[k, c],
                     Xa=feat(t, cc), Xb=feat(t + 1, cc), lep=lep[cc], pv=pv[cc], wlag=w[np.maximum(t.astype(int) - tau, 0)])
        L, g, graw, Ld, Lp = loss_and_grad(p, raw, batch, lam, scale)
        lr = 3e-3 * (0.2 + 0.8 * (1 - it / steps))
        for obj, grad, a, v in ((p, g, m1[0], m2[0]),):
            for key in obj:
                a[key] = .9 * a[key] + .1 * grad[key]; v[key] = .999 * v[key] + .001 * grad[key] ** 2
                obj[key] -= lr * (a[key] / (1 - .9 ** it)) / (np.sqrt(v[key] / (1 - .999 ** it)) + 1e-8)
        m1[1] = .9 * m1[1] + .1 * graw; m2[1] = .999 * m2[1] + .001 * graw ** 2
        raw -= 3 * lr * (m1[1] / (1 - .9 ** it)) / (np.sqrt(m2[1] / (1 - .999 ** it)) + 1e-8)
        if it % max(1, steps // 20) == 0: hist.append([it, round(Ld, 3), round(Lp, 4)])

    def predict(k):
        c = np.arange(len(lep))
        return scale * (_fwd(p, feat(np.full(len(c), float(pd[k])), c))[0] - _fwd(p, feat(np.full(len(c), float(pd[0])), c))[0])
    te = np.asarray(fr["test"])
    err = np.concatenate([(predict(k) - Y[k])[np.isfinite(Y[k])] for k in te])
    (alpha, b, T), _ = _phys(raw)
    return dict(rmse=float(np.sqrt(np.mean(err ** 2))), alpha=float(alpha), b=float(b), T=float(T), history=hist)


def run(site: dict, fr: dict, steps: int = 4000, lam: float = 20.0, seed: int = 7) -> dict:
    mk = F.masks(site)["clay"]; pd = np.asarray(site["pass_days"]); te, tr = np.asarray(fr["test"]), np.asarray(fr["train"])
    Y = fr["mcorr"][:, mk]; phys = F.predict(site, fr["par"])[pd][:, mk]
    rm = lambda P: float(np.sqrt(np.nanmean(np.concatenate([(P[k] - Y[k])[np.isfinite(Y[k])] for k in te]) ** 2)))
    hold = {k: Y[tr[-1]] for k in te}
    nn, pinn = _train(site, fr, 0.0, steps, seed), _train(site, fr, lam, steps, seed)
    out = dict(method="discrete-residual physics-informed network, numpy, 3-24-24-1 tanh; alpha, b, T trained jointly; tau from the grid fit",
               steps=steps, physics_weight=lam, seed=seed, n_cells=int(mk.sum()), train_passes=tr.tolist(), heldout_passes=te.tolist(),
               heldout_rmse_mm=dict(no_change=rm(hold), physics_fit=rm({k: phys[k] for k in te}), network_only=nn["rmse"], physics_informed=pinn["rmse"]),
               discovered=dict(alpha=pinn["alpha"], b=pinn["b"], T=pinn["T"]),
               grid_fit=dict(alpha=fr["par"]["alpha"], b=fr["par"]["b"], T=fr["par"]["T"], tau=fr["par"]["tau"]),
               history=pinn["history"], source=site["source"])
    r = out["heldout_rmse_mm"]
    out["physics_helps"] = bool(r["physics_informed"] < r["network_only"])
    out["reading"] = ("On held-out passes the physics-informed network has lower error than the same network without physics."
                      if out["physics_helps"] else "On held-out passes the physics loss did not lower the error. Reported as found.")
    return out
