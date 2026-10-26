#!/usr/bin/env python3
"""
Snap the drive onto real roads while allowing for accumulated heading error.

locate_start.py treats the dead-reckoned path as rigid and only solves one
rotation. That breaks down because heading error builds up over the trip:

  - Steering-based heading (decode_path.py) is very sensitive to bias. A 0.1°
    steering-wheel offset adds ~80° of drift over 20 minutes of highway driving,
    and the bicycle model ignores understeer (it over-turns by ~38% vs the gyro).
    It also can't tell forward from reverse, because wheel speeds are unsigned.
  - The yaw-rate gyro (0x024 YGS1S03.YR) measures rotation directly, including
    reversing. Its only real unknown is a small constant bias.

This script:

  1. Decodes wheel speeds (0x0AA) and gyro yaw rate (0x024) from the log.
  2. For each candidate gyro bias, integrates heading and distance.
  3. Walks the path BACKWARD from the known end point in 1 km segments. A beam
     search picks a heading correction for each segment so the path lies on
     OSM roads. Corrections between segments are limited to ±4°, so the
     shape still has to agree with the driving data; it can't jump to an
     arbitrary road.
  4. Picks the bias whose snapped path fits roads best, then checks it with an
     independent test: do the car's full stops land on real traffic signals?

The result is a ranked estimate, not proof. Only submitting it confirms it.
"""

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

import decode_path as DP
import locate_start as LS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUT_PNG = Path(__file__).parent / "snap_path.png"
SIGNAL_CACHE = Path(__file__).resolve().parent.parent / "scratch" / "snap_signals.npz"

ID_YAW = 0x024            # YGS1S03: YR yaw rate, 0.244 deg/s per bit
DT = 0.02                 # integration step (s)
STOPPED_MPS = 0.05        # below this the car is stationary: no heading change

BIAS_SWEEP = np.round(np.arange(-0.060, 0.0601, 0.005), 3)   # deg/s
FIT_TIE = 0.005           # fits within this of the best count as equally good
SEG_M = 1000.0            # path is snapped in segments of this length
STEP_M = 20.0             # resample spacing along the path
MAX_TURN_DEG = 4.0        # max heading correction change between segments
TURN_STEP_DEG = 0.5
CORR_PENALTY = 0.01       # score penalty per degree of correction change
BEAM = 60
CELL_M = 10.0
# Graded road fit: (distance to road in m, score)
ROAD_LEVELS = ((80, 0.1), (50, 0.3), (30, 0.6), (15, 1.0))
SIGNAL_HIT_M = 100.0


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------
def decode_signals():
    """Return (t, wheel speed m/s, yaw rate deg/s) on a common DT timeline."""
    if SIGNAL_CACHE.exists():
        c = np.load(SIGNAL_CACHE)
        return c["t"], c["v"], c["yr"]

    log = DP.ensure_log()
    db = DP.get_dbc()
    m_wheel = db.get_message_by_frame_id(DP.ID_WHEEL_SPEEDS)
    m_yaw = db.get_message_by_frame_id(ID_YAW)

    wheel, yaw = [], []
    print(f"Parsing {log} ...")
    for ts, can_id, data in DP.parse_log(log):
        try:
            if can_id == DP.ID_WHEEL_SPEEDS:
                d = m_wheel.decode(data, decode_choices=False)
                wheel.append((ts, (d["VXFL"] + d["VXFR"] + d["VXRL"] + d["VXRR"]) / 4))
            elif can_id == ID_YAW:
                yaw.append((ts, m_yaw.decode(data, decode_choices=False)["YR"]))
        except Exception:
            continue
    wheel, yaw = np.array(wheel), np.array(yaw)

    t0 = wheel[0, 0]
    t = np.arange(0, min(wheel[-1, 0], yaw[-1, 0]) - t0, DT)
    v = np.interp(t, wheel[:, 0] - t0, wheel[:, 1]) / 3.6
    yr = np.interp(t, yaw[:, 0] - t0, yaw[:, 1])
    SIGNAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(SIGNAL_CACHE, t=t, v=v, yr=yr)
    return t, v, yr


def gyro_heading(v, yr, bias):
    moving = v >= STOPPED_MPS
    return np.cumsum(np.deg2rad(yr - bias) * DT * moving)


# ---------------------------------------------------------------------------
# Road fit field
# ---------------------------------------------------------------------------
class RoadField:
    """Raster of graded closeness-to-road scores around the end point."""

    def __init__(self, roads_local, radius_m):
        self.r = radius_m
        self.n = int(2 * radius_m / CELL_M) + 1
        raw = np.zeros((self.n, self.n), dtype=bool)
        for e, n in roads_local:
            s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(e), np.diff(n)))])
            si = np.arange(0, s[-1] + CELL_M / 2, CELL_M / 2)
            self._mark(raw, np.interp(si, s, e), np.interp(si, s, n))
        self.field = np.zeros(raw.shape, dtype=np.float32)
        for dist, val in ROAD_LEVELS:
            self.field[LS.RoadGrid._dilate(raw, int(round(dist / CELL_M)))] = val

    def _idx(self, e, n):
        i = np.floor((e + self.r) / CELL_M).astype(int)
        j = np.floor((n + self.r) / CELL_M).astype(int)
        return i, j, (i >= 0) & (i < self.n) & (j >= 0) & (j < self.n)

    def _mark(self, grid, e, n):
        i, j, ok = self._idx(e, n)
        grid[j[ok], i[ok]] = True

    def __call__(self, e, n):
        i, j, ok = self._idx(e, n)
        s = np.zeros(len(e))
        s[ok] = self.field[j[ok], i[ok]]
        return s


# ---------------------------------------------------------------------------
# Snap: beam search over per-segment heading corrections, walking from the end
# ---------------------------------------------------------------------------
class Snapper:
    def __init__(self, v, field):
        self.field = field
        self.s_end = np.cumsum((v * DT)[::-1])          # distance from end, reversed time
        self.si = np.arange(0, self.s_end[-1], STEP_M)  # sample distances from end
        self.seg = (self.si // SEG_M).astype(int)
        self.nseg = self.seg.max() + 1
        self.deltas = np.deg2rad(np.arange(-MAX_TURN_DEG, MAX_TURN_DEG + 1e-9, TURN_STEP_DEG))

    def _walk(self, e0, n0, h):
        # walking backward in time: step opposite to the direction of travel
        return e0 - np.cumsum(STEP_M * np.cos(h)), n0 - np.cumsum(STEP_M * np.sin(h))

    def run(self, heading):
        h = np.interp(self.si, self.s_end, heading[::-1])
        # (score, correction, e, n, corrections so far); first segment tries every rotation
        beam = [(0.0, th, 0.0, 0.0, []) for th in np.deg2rad(np.arange(0, 360, 1.0))]
        for k in range(self.nseg):
            hk = h[self.seg == k]
            cand = []
            for score, corr, e0, n0, hist in beam:
                for d in (self.deltas if k else [0.0]):
                    c = corr + d
                    e, n = self._walk(e0, n0, hk + c)
                    s = score + self.field(e, n).mean() - CORR_PENALTY * abs(math.degrees(d))
                    cand.append((s, c, e[-1], n[-1], hist + [c]))
            cand.sort(key=lambda r: -r[0])
            beam = []
            for c in cand:   # keep distinct states only
                if all(math.hypot(c[2] - b[2], c[3] - b[3]) > 30 or abs(c[1] - b[1]) > 0.004
                       for b in beam):
                    beam.append(c)
                if len(beam) == BEAM:
                    break
        best = beam[0]
        e, n = self.path(h, best[4])
        return best[0] / self.nseg, np.rad2deg(best[4]), e, n

    def path(self, h, corr):
        es, ns, e0, n0 = [], [], 0.0, 0.0
        for k in range(self.nseg):
            e, n = self._walk(e0, n0, h[self.seg == k] + corr[k])
            es.append(e); ns.append(n); e0, n0 = e[-1], n[-1]
        return np.concatenate(es), np.concatenate(ns)

    def position_at_time(self, t, ts, e, n):
        """Snapped position at time t (path samples are indexed by distance from end)."""
        d = np.interp(t, ts, self.s_end[::-1])
        return np.interp(d, self.si + STEP_M, e), np.interp(d, self.si + STEP_M, n)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def plot(sweep, best, e, n, roads_local, sig, stop_pts):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8), gridspec_kw={"width_ratios": [1, 1.4]})
    fig.suptitle("Life is a Highway: drift-corrected road snapping")

    b = [r[0] for r in sweep]
    ax1.plot(b, [r[1] for r in sweep], "ko-", markersize=4)
    ax1.axvline(best[0], color="r", linestyle="--", label=f"best bias {best[0]:+.3f} deg/s")
    ax1.set_xlabel("Gyro bias (deg/s)")
    ax1.set_ylabel("Road fit (mean per km, 1 = on road)")
    ax1.set_title("Road fit vs gyro bias")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    pad = 1500
    lo_e, hi_e, lo_n, hi_n = e.min() - pad, e.max() + pad, n.min() - pad, n.max() + pad
    segs = [np.column_stack(r) for r in roads_local
            if (r[0].max() > lo_e) & (r[0].min() < hi_e) & (r[1].max() > lo_n) & (r[1].min() < hi_n)]
    ax2.add_collection(LineCollection(segs, colors="0.8", linewidths=0.5))
    se, sn = sig
    m = (se > lo_e) & (se < hi_e) & (sn > lo_n) & (sn < hi_n)
    ax2.scatter(se[m], sn[m], s=3, c="tab:orange", label="OSM signals / stop signs")
    ax2.plot(e, n, "b-", linewidth=1.5, label="Snapped path")
    pe, pn = stop_pts
    ax2.scatter(pe, pn, s=50, facecolors="none", edgecolors="r", linewidths=1.5, label="Full stops")
    ax2.plot(e[-1], n[-1], "go", markersize=10, markeredgecolor="k", label="Start (estimated)")
    ax2.plot(0, 0, "rs", markersize=9, label="End (given)")
    ax2.set_xlim(lo_e, hi_e)
    ax2.set_ylim(lo_n, hi_n)
    ax2.set_aspect("equal")
    ax2.set_xlabel("East of end point (m)")
    ax2.set_ylabel("North of end point (m)")
    ax2.set_title(f"Snapped path, bias {best[0]:+.3f} deg/s")
    ax2.legend(loc="best", fontsize=8)

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"Plot saved → {OUT_PNG}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    t, v, yr = decode_signals()
    driven = np.sum(v * DT)
    print(f"  Duration           : {t[-1]:.0f} s")
    print(f"  Distance driven    : {driven/1000:.2f} km")
    print(f"  Gyro mean, stopped : {yr[v < STOPPED_MPS].mean():+.3f} deg/s "
          f"(not trusted: 0.244 deg/s quantisation with little noise to dither)")

    # The start can be at most the driven distance from the end, in any direction
    radius = math.ceil((driven + 500) / 1000) * 1000
    print(f"Fetching OSM data within {radius/1000:.0f} km of the end point ...")
    signals, roads = LS.fetch_osm(radius, tiles=6)
    roads_local = [LS.to_local(r[:, 0], r[:, 1]) for r in roads]
    sig_local = LS.to_local(signals[:, 0], signals[:, 1])
    print(f"  Signals/stop signs : {len(signals)}")
    print(f"  Road ways          : {len(roads)}")

    print("Rasterising roads ...")
    field = RoadField(roads_local, radius)
    snapper = Snapper(v, field)

    print(f"Snapping for {len(BIAS_SWEEP)} gyro biases ...")
    print(f"  {'bias':>7} {'fit':>6} {'corr span':>9}  start")
    sweep = []
    for bias in BIAS_SWEEP:
        fit, corr, e, n = snapper.run(gyro_heading(v, yr, bias))
        lat, lon = LS.to_latlon(e[-1], n[-1])
        sweep.append((bias, fit, corr, e, n))
        print(f"  {bias:+7.3f} {fit:6.3f} {corr.max()-corr.min():8.1f}°  {lat:.5f}, {lon:.5f}", flush=True)

    # Among equally good fits, prefer the bias needing the least heading
    # correction: that path agrees most with the raw driving data.
    top = max(r[1] for r in sweep)
    best = min((r for r in sweep if r[1] >= top - FIT_TIE), key=lambda r: np.ptp(r[2]))
    bias, fit, corr, e, n = best

    # Independent check: stops were not used in the fit
    stops = LS.extract_stops(t, np.zeros_like(v), np.zeros_like(v), v * 2.23694)
    print()
    print(f"Stop check at bias {bias:+.3f} (stops were not used to fit):")
    pe, pn, hits = [], [], 0
    for t0, t1, _, _ in stops:
        x, y = snapper.position_at_time((t0 + t1) / 2, t, e, n)
        d = np.hypot(sig_local[0] - x, sig_local[1] - y).min()
        hits += d <= SIGNAL_HIT_M
        lat, lon = LS.to_latlon(x, y)
        pe.append(x); pn.append(y)
        print(f"  t={t0:7.1f}-{t1:7.1f}s  {t1-t0:5.1f}s  {lat:.5f}, {lon:.5f}  "
              f"nearest signal {d:5.0f} m  {'HIT ' if d <= SIGNAL_HIT_M else 'miss'}")
    print(f"  {hits}/{len(stops)} stops within {SIGNAL_HIT_M:.0f} m of a signal or stop sign")

    # How stable is the start across biases that fit well?
    good = [r for r in sweep if r[1] >= top - 0.05]
    starts = np.array([[r[3][-1], r[4][-1]] for r in good])
    spread = np.hypot(*(starts - starts.mean(0)).T).max()

    lat, lon = LS.to_latlon(e[-1], n[-1])
    print()
    print(f"Road fit           : {fit:.3f} (1 = every sample on a road)")
    print(f"Heading correction : {corr.min():.1f}° to {corr.max():.1f}° across {snapper.nseg} segments")
    print(f"Start spread       : {spread:.0f} m across {len(good)} biases within 0.05 of the best fit")
    print(f"Most likely start  : {lat:.5f}, {lon:.5f}")
    print(f"                     {LS.reverse_geocode(lat, lon)}")
    print("(Ranked estimate only; confirm by submitting the coordinate.)")

    plot([(r[0], r[1]) for r in sweep], best, e, n, roads_local, sig_local, (pe, pn))
