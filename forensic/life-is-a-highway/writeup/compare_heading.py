#!/usr/bin/env python3
"""
Compare the heading sources available on the CAN bus, to explain why the
steering-based path in decode_path.py drifts.

  0x025 STR1S01.SSA (+ SSAS fine angle) : steering wheel → bicycle model
  0x024 YGS1S03.YR                      : yaw-rate gyro
  0x0AA VSC1F01 rear wheel difference   : (VXRR - VXRL) / track

Prints the comparison and saves heading_compare.png.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import decode_path as DP

OUT_PNG = Path(__file__).parent / "heading_compare.png"
CACHE = Path(__file__).resolve().parent.parent / "scratch" / "heading_signals.npz"
ID_YAW = 0x024
DT = 0.02
STOPPED_MPS = 0.05


def decode():
    if CACHE.exists():
        return dict(np.load(CACHE))
    log = DP.ensure_log()
    db = DP.get_dbc()
    m = {i: db.get_message_by_frame_id(i) for i in (ID_YAW, DP.ID_STEER, DP.ID_WHEEL_SPEEDS)}
    yaw, steer, wheel = [], [], []
    print(f"Parsing {log} ...")
    for ts, can_id, data in DP.parse_log(log):
        if can_id not in m:
            continue
        try:
            d = m[can_id].decode(data, decode_choices=False)
        except Exception:
            continue
        if can_id == ID_YAW:
            yaw.append((ts, d["YR"]))
        elif can_id == DP.ID_STEER:
            steer.append((ts, d["SSA"], d["SSAS"]))
        else:
            wheel.append((ts, d["VXFL"], d["VXFR"], d["VXRL"], d["VXRR"]))
    yaw, steer, wheel = np.array(yaw), np.array(steer), np.array(wheel)

    t0 = wheel[0, 0]
    t = np.arange(0, wheel[-1, 0] - t0, DT)
    out = {
        "t": t,
        "v": np.interp(t, wheel[:, 0] - t0, wheel[:, 1:5].mean(1)) / 3.6,
        "v_rl": np.interp(t, wheel[:, 0] - t0, wheel[:, 3]) / 3.6,
        "v_rr": np.interp(t, wheel[:, 0] - t0, wheel[:, 4]) / 3.6,
        "ssa": np.interp(t, steer[:, 0] - t0, steer[:, 1]),
        "ssas": np.interp(t, steer[:, 0] - t0, steer[:, 2]),
        "yr": np.interp(t, yaw[:, 0] - t0, yaw[:, 1]),
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, **out)
    return out


if __name__ == "__main__":
    S = decode()
    t, v, yr = S["t"], S["v"], S["yr"]
    moving = v >= STOPPED_MPS

    def steer_rate(angle):   # deg/s from the bicycle model
        return np.rad2deg(v / DP.WHEELBASE_M * np.tan(np.deg2rad(angle / DP.STEERING_RATIO)))

    rate_ssa = steer_rate(S["ssa"])
    rate_fine = steer_rate(S["ssa"] + S["ssas"])
    rate_wheel = np.rad2deg((S["v_rr"] - S["v_rl"]) / DP.TRACK_WIDTH_M) * moving

    # 1. Gyro vs steering in real turns
    turns = (v > 5) & (np.abs(rate_fine) > 3) & (np.abs(rate_fine) < 30)
    slope, icpt = np.polyfit(rate_fine[turns], yr[turns], 1)
    corr = np.corrcoef(rate_fine[turns], yr[turns])[0, 1]
    print(f"Turns (v>5 m/s, n={turns.sum()}): gyro = {slope:.3f} × steering {icpt:+.3f} deg/s, r = {corr:.3f}")
    print(f"  → the bicycle model over-turns by {1/slope - 1:.0%} (understeer it does not model)")

    # 2. Straight-line bias on the highway
    hw = v > 20
    print(f"Highway (v>20 m/s, {hw.sum()*DT:.0f} s): mean steering yaw {rate_fine[hw].mean():+.3f} deg/s, "
          f"gyro {yr[hw].mean():+.3f} deg/s")
    print(f"  → steering drift of {(rate_fine[hw].mean() - yr[hw].mean()) * hw.sum() * DT:+.0f}° over the highway portion")
    print(f"Gyro while stopped: mean {yr[~moving].mean():+.3f} deg/s, std {yr[~moving].std():.3f} "
          f"(quantised at 0.244 deg/s)")

    # 3. Reversing: wheel speeds are unsigned, so steering integrates turns backwards when reversing
    early = t < 30
    print(f"First 30 s (leaving a parking spot): steering heading change "
          f"{np.sum(rate_fine[early]) * DT:+.0f}°, gyro {np.sum(yr[early] * moving[early]) * DT:+.0f}°")

    # Headings and paths
    sources = {
        "steering SSA (decode_path.py)": rate_ssa,
        "steering SSA+SSAS": rate_fine,
        "gyro YR": yr * moving,
        "rear wheel difference": rate_wheel,
    }
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle("Heading sources compared (each path starts at 0,0 heading east)")
    print("Total heading change / net displacement:")
    for name, rate in sources.items():
        h = np.cumsum(np.deg2rad(rate) * DT)
        x, y = np.cumsum(v * np.cos(h) * DT), np.cumsum(v * np.sin(h) * DT)
        print(f"  {name:<30} {np.rad2deg(h[-1]):+8.0f}°  {np.hypot(x[-1], y[-1])/1000:6.2f} km")
        ax1.plot(t, np.rad2deg(h), label=name)
        ax2.plot(x, y, label=name)
    ax1.set_xlabel("Time (s)"); ax1.set_ylabel("Integrated heading (deg)")
    ax1.grid(True, alpha=0.3); ax1.legend()
    ax2.set_xlabel("x (m)"); ax2.set_ylabel("y (m)"); ax2.set_aspect("equal")
    ax2.grid(True, alpha=0.3); ax2.legend()
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=120, bbox_inches="tight")
    print(f"Plot saved → {OUT_PNG}")
