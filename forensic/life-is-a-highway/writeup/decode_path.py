#!/usr/bin/env python3
"""
Decode vehicle speed and steering wheel angle from a Toyota candump log,
then reconstruct the driven path using a bicycle kinematic model.

DBC source: https://github.com/commaai/opendbc (toyota_2017_ref_pt.dbc)
  - 0x0AA (170) VSC1F01: VXFL/VXFR/VXRL/VXRR wheel speeds, factor 0.01 offset -67.67 km/h
  - 0x025 (37)  STR1S01: SSA steering sensor angle, factor 1.5 deg
  - 0x0B4 (180) VSC1S03: SP1 vehicle speed, factor 0.01 km/h
"""

import gzip
import re
import shutil
import sys
import urllib.request
from pathlib import Path

import cantools
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOG_FILE = Path(__file__).parent / "candump-2026-08-22_185046.log"
LOG_GZ   = Path(__file__).resolve().parent.parent / "dist" / "candump-2026-08-22_185046.log.gz"
DBC_URL = "https://raw.githubusercontent.com/commaai/opendbc/master/opendbc/dbc/toyota_2017_ref_pt.dbc"
SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"
DBC_CACHE = SCRATCH_DIR / "toyota_2017_ref_pt.dbc"
DBC_FIXED = SCRATCH_DIR / "toyota_2017_ref_pt_fixed.dbc"

# 2016 Toyota Corolla parameters
WHEELBASE_M = 2.700       # metres
STEERING_RATIO = 15.5     # steering wheel deg → front wheel deg
TRACK_WIDTH_M = 1.524     # metres (used for speed averaging)

# CAN IDs of interest (decimal)
ID_WHEEL_SPEEDS = 0x0AA   # 170
ID_STEER        = 0x025   # 37
ID_SPEED        = 0x0B4   # 180

# ---------------------------------------------------------------------------
# Unpack the challenge log
# ---------------------------------------------------------------------------
def ensure_log() -> Path:
    """Decompress the distributed candump log next to this script if needed."""
    if not LOG_FILE.exists():
        print(f"Unpacking {LOG_GZ} ...")
        with gzip.open(LOG_GZ, "rb") as src, open(LOG_FILE, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return LOG_FILE


# ---------------------------------------------------------------------------
# Fetch DBC
# ---------------------------------------------------------------------------
def get_dbc() -> cantools.database.Database:
    SCRATCH_DIR.mkdir(exist_ok=True)
    if not DBC_FIXED.exists():
        if not DBC_CACHE.exists():
            print(f"Downloading DBC from {DBC_URL} ...")
            urllib.request.urlretrieve(DBC_URL, DBC_CACHE)
        _patch_dbc(DBC_CACHE, DBC_FIXED)
    db = cantools.database.load_file(str(DBC_FIXED), strict=False)
    return db


def _patch_dbc(src: Path, dst: Path):
    """Remove messages with out-of-range frame IDs (Toyota proprietary extended frames)."""
    import re
    content = src.read_text()
    blocks = re.split(r'(?=^BO_ )', content, flags=re.MULTILINE)
    good = []
    for blk in blocks:
        m = re.match(r'^BO_ (\d+)', blk)
        if m and int(m.group(1)) > 0x1FFFFFFF:
            continue
        good.append(blk)
    dst.write_text("".join(good))
    print(f"  Patched DBC: removed {len(blocks) - len(good)} out-of-range messages")


# ---------------------------------------------------------------------------
# Parse candump log
# ---------------------------------------------------------------------------
LINE_RE = re.compile(
    r'^\((\d+\.\d+)\)\s+\w+\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]+)'
)

def parse_log(path: Path):
    """Yield (timestamp_s, can_id_int, data_bytes) for every frame."""
    with open(path) as fh:
        for line in fh:
            m = LINE_RE.match(line.strip())
            if m:
                ts = float(m.group(1))
                can_id = int(m.group(2), 16)
                data = bytes.fromhex(m.group(3))
                yield ts, can_id, data


# ---------------------------------------------------------------------------
# Decode signals
# ---------------------------------------------------------------------------
def decode_signals(db: cantools.database.Database, log_path: Path):
    """
    Returns three sorted lists:
      wheel_speeds : [(ts, vFL, vFR, vRL, vRR)]  km/h
      steers       : [(ts, angle_deg)]            steering wheel degrees
      speeds       : [(ts, speed_kph)]            km/h
    """
    wheel_speeds = []
    steers = []
    speeds = []

    msgs = {
        ID_WHEEL_SPEEDS: db.get_message_by_frame_id(ID_WHEEL_SPEEDS),
        ID_STEER:        db.get_message_by_frame_id(ID_STEER),
        ID_SPEED:        db.get_message_by_frame_id(ID_SPEED),
    }

    for ts, can_id, data in parse_log(log_path):
        if can_id not in msgs:
            continue
        try:
            decoded = msgs[can_id].decode(data, decode_choices=False)
        except Exception:
            continue

        if can_id == ID_WHEEL_SPEEDS:
            vfl = decoded.get("VXFL", 0.0)
            vfr = decoded.get("VXFR", 0.0)
            vrl = decoded.get("VXRL", 0.0)
            vrr = decoded.get("VXRR", 0.0)
            wheel_speeds.append((ts, vfl, vfr, vrl, vrr))

        elif can_id == ID_STEER:
            angle = decoded.get("SSA", 0.0)
            steers.append((ts, float(angle)))

        elif can_id == ID_SPEED:
            spd = decoded.get("SP1", 0.0)
            speeds.append((ts, float(spd)))

    return wheel_speeds, steers, speeds


# ---------------------------------------------------------------------------
# Dead-reckoning path integration (bicycle model)
# ---------------------------------------------------------------------------
def compute_path(wheel_speeds, steers, speeds):
    """
    Fuse wheel speeds + steering angle with a kinematic bicycle model.

    State: [x (m), y (m), heading (rad)]
    Speed source: average of all four wheel speeds (km/h → m/s)
    Steering: SSA (steering wheel deg) / STEERING_RATIO → front wheel angle

    NOTE: heading is initialised to 0 at t=0 and only integrated from
    relative steering input — there is no compass/GPS/magnetometer signal
    in this CAN log to anchor it to true north. x/y are therefore a
    LOCAL, ARBITRARILY-ORIENTED planar frame (heading=0 == whatever
    direction the vehicle was pointed at the first sample), not true
    East/North, until independently calibrated (e.g. by map-matching
    against a known start or end point).
    """
    # Build unified timeline at ~10 ms resolution
    if not wheel_speeds or not steers:
        print("ERROR: insufficient data")
        sys.exit(1)

    t0 = min(wheel_speeds[0][0], steers[0][0])

    # Build lookup arrays
    ws_t  = np.array([r[0] for r in wheel_speeds])
    ws_v  = np.array([(r[1]+r[2]+r[3]+r[4])/4 for r in wheel_speeds]) / 3.6  # m/s
    st_t  = np.array([r[0] for r in steers])
    st_a  = np.array([r[1] for r in steers])  # steering wheel deg

    # Normalise time
    ws_t -= t0
    st_t -= t0

    # Common timeline: every 0.02 s from start to end
    t_end = min(ws_t[-1], st_t[-1])
    ts = np.arange(0, t_end, 0.02)

    v_interp     = np.interp(ts, ws_t, ws_v)
    steer_interp = np.interp(ts, st_t, st_a)

    # Integrate
    x, y, heading = 0.0, 0.0, 0.0
    xs, ys, headings = [x], [y], [heading]

    for i in range(1, len(ts)):
        dt = ts[i] - ts[i-1]
        v  = v_interp[i]
        sw = steer_interp[i]
        delta = np.deg2rad(sw / STEERING_RATIO)  # front wheel angle

        # Bicycle model
        heading  += (v / WHEELBASE_M) * np.tan(delta) * dt
        x        += v * np.cos(heading) * dt
        y        += v * np.sin(heading) * dt

        xs.append(x)
        ys.append(y)
        headings.append(heading)

    return ts, np.array(xs), np.array(ys), np.array(headings), v_interp, steer_interp


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def plot_results(ts, xs, ys, headings, v_interp, steer_interp, steers, speeds):
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("2016 Toyota Corolla — Reconstructed Drive Path", fontsize=14)

    KMH_TO_MPH = 0.621371

    # --- Path (coloured by speed) ---
    ax = axes[0, 0]
    sc = ax.scatter(xs, ys, c=v_interp * 3.6 * KMH_TO_MPH, cmap="plasma", s=1, linewidths=0)
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label("Speed (mph)")
    ax.plot(xs[0], ys[0], "go", markersize=8, label="Start")
    ax.plot(xs[-1], ys[-1], "rs", markersize=8, label="End")
    ax.set_xlabel("Local X (m) — arbitrary heading=0 axis, NOT true East")
    ax.set_ylabel("Local Y (m) — arbitrary heading=0 axis, NOT true North")
    ax.set_title("Driven Path (coloured by speed) — uncalibrated local frame")
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Speed over time ---
    ax = axes[0, 1]
    if speeds:
        sp_t0 = speeds[0][0]
        sp_ts = np.array([r[0] - sp_t0 for r in speeds])
        sp_vs = np.array([r[1] for r in speeds]) * KMH_TO_MPH
        ax.plot(sp_ts, sp_vs, "b-", linewidth=0.8, label="SP1 (VSC1S03)")
    ax.plot(ts, v_interp * 3.6 * KMH_TO_MPH, "r--", linewidth=0.8, alpha=0.7, label="Wheel avg (0xAA)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Speed (mph)")
    ax.set_title("Vehicle Speed")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Steering angle over time ---
    ax = axes[1, 0]
    st_t0 = steers[0][0]
    st_ts = np.array([r[0] - st_t0 for r in steers])
    st_as = np.array([r[1] for r in steers])
    ax.plot(st_ts, st_as, "g-", linewidth=0.8)
    ax.axhline(0, color="k", linewidth=0.5)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Steering Wheel Angle (deg)")
    ax.set_title("Steering Angle (SSA, positive = left)")
    ax.grid(True, alpha=0.3)

    # --- Heading over time ---
    ax = axes[1, 1]
    ax.plot(ts, np.rad2deg(headings), "m-", linewidth=0.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Relative Heading (deg, arbitrary 0-ref)")
    ax.set_title("Vehicle Heading (relative to arbitrary start orientation, NOT compass bearing)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out = Path(__file__).parent / "path_reconstruction.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Plot saved → {out}")
    plt.show()


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
def export_csv(ts, xs, ys, headings, v_interp, steer_interp):
    out = Path(__file__).parent / "path_data.csv"
    with open(out, "w") as fh:
        fh.write("time_s,x_m,y_m,heading_deg,speed_mph,steer_wheel_deg\n")
        for i in range(len(ts)):
            fh.write(
                f"{ts[i]:.3f},{xs[i]:.3f},{ys[i]:.3f},"
                f"{np.rad2deg(headings[i]):.3f},"
                f"{v_interp[i]*3.6*0.621371:.3f},{steer_interp[i]:.3f}\n"
            )
    print(f"CSV saved  → {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ensure_log()
    print("Loading DBC ...")
    db = get_dbc()

    print(f"Parsing {LOG_FILE} ...")
    wheel_speeds, steers, speeds = decode_signals(db, LOG_FILE)
    print(f"  Wheel speed frames : {len(wheel_speeds)}")
    print(f"  Steering frames    : {len(steers)}")
    print(f"  Speed frames       : {len(speeds)}")

    if wheel_speeds:
        avg_spd = np.mean([(r[1]+r[2]+r[3]+r[4])/4 for r in wheel_speeds])
        max_spd = max((r[1]+r[2]+r[3]+r[4])/4 for r in wheel_speeds)
        print(f"  Avg wheel speed    : {avg_spd * 0.621371:.1f} mph")
        print(f"  Max wheel speed    : {max_spd * 0.621371:.1f} mph")
    if steers:
        angles = [r[1] for r in steers]
        print(f"  Steer range        : {min(angles):.1f} … {max(angles):.1f} deg")

    print("Computing path ...")
    ts, xs, ys, headings, v_interp, steer_interp = compute_path(wheel_speeds, steers, speeds)

    total_dist = np.sum(np.sqrt(np.diff(xs)**2 + np.diff(ys)**2))
    duration   = ts[-1]
    print(f"  Duration           : {duration:.1f} s")
    print(f"  Distance travelled : {total_dist/1000:.2f} km")
    print(f"  Net displacement   : {np.hypot(xs[-1], ys[-1]):.1f} m")

    export_csv(ts, xs, ys, headings, v_interp, steer_interp)
    plot_results(ts, xs, ys, headings, v_interp, steer_interp, steers, speeds)
