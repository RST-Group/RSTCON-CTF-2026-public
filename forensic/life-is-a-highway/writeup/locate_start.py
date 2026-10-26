#!/usr/bin/env python3
"""
Estimate where the trip started by solving the unknown heading rotation of the
dead-reckoned path produced by decode_path.py.

decode_path.py integrates heading from steering input only, so path_data.csv is
in a local frame with an arbitrary orientation. The trip's END is known, which
fixes translation, and the wheel speeds fix scale. That leaves one unknown: the
rotation θ from local x/y to East/North.

For every candidate θ the path is rotated, anchored on the known end point, and
scored against OpenStreetMap data (via Overpass):

  - Road score: how much of the driven path lies on a real road.
  - Stop score: how close each full stop lands to a real traffic signal or stop sign.

Both scores are weighted toward the end of the trip, because dead-reckoning
heading error grows with distance from the anchor. The best-scoring rotations
are printed with their implied start coordinates. This ranks candidates; it does
not prove one. The only confirmation is submitting a coordinate.
"""

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CSV_FILE = Path(__file__).parent / "path_data.csv"
OUT_PNG  = Path(__file__).parent / "locate_start.png"
CACHE_DIR = Path(__file__).resolve().parent.parent / "scratch" / "osm_cache"

END_LAT, END_LON = 38.9166896, -77.2210292   # given in the challenge

OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT    = "rstcon-ctf-writeup/1.0"

# Roads to match against. Residential/service streets are left out to keep the
# Overpass download manageable; the parts of the trip on them simply won't score.
ROAD_CLASSES = "motorway|trunk|primary|secondary|tertiary|unclassified"

STOP_SPEED_MPH  = 1.0     # below this the car counts as stopped
MIN_STOP_S      = 1.5     # ignore stops shorter than this
SAMPLE_SPACING_M = 50.0   # path is resampled by arc length for road scoring
CELL_M          = 10.0    # road raster resolution
ROAD_NEAR_M     = 20.0    # full credit if a path sample is within this of a road
ROAD_FAR_M      = 50.0    # half credit within this
STOP_FALLOFF_M  = 100.0   # stop credit drops linearly to 0 at this distance
DRIFT_SCALE_M   = 5000.0  # weight = 1 / (1 + dist_from_end / DRIFT_SCALE_M)
ROAD_WEIGHT     = 0.5     # combined = ROAD_WEIGHT*road + (1-ROAD_WEIGHT)*stop

COARSE_STEP_DEG = 0.5
FINE_STEP_DEG   = 0.05
N_CANDIDATES    = 3       # distinct peaks to refine and report
MIN_PEAK_SEP_DEG = 10.0

# Local equirectangular projection centred on the end point
M_PER_DEG_LAT = 111320.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(END_LAT))


def to_local(lat, lon):
    return (np.asarray(lon) - END_LON) * M_PER_DEG_LON, (np.asarray(lat) - END_LAT) * M_PER_DEG_LAT


def to_latlon(e, n):
    return END_LAT + n / M_PER_DEG_LAT, END_LON + e / M_PER_DEG_LON


# ---------------------------------------------------------------------------
# Load path and extract features
# ---------------------------------------------------------------------------
def load_path(path: Path):
    d = np.genfromtxt(path, delimiter=",", names=True)
    return d["time_s"], d["x_m"], d["y_m"], d["speed_mph"]


def extract_stops(t, x, y, speed):
    """Return [(t_start, t_end, x_mean, y_mean)] for sustained full stops.

    Stops touching the very start or end of the log are dropped: those are the
    car idling where it was parked, not a traffic control.
    """
    stopped = speed < STOP_SPEED_MPH
    edges = np.diff(stopped.astype(int))
    starts = list(np.where(edges == 1)[0] + 1)
    ends   = list(np.where(edges == -1)[0] + 1)
    if stopped[0]:
        starts.insert(0, 0)
    if stopped[-1]:
        ends.append(len(t))

    stops = []
    for s, e in zip(starts, ends):
        if s == 0 or e == len(t):
            continue
        if t[e - 1] - t[s] < MIN_STOP_S:
            continue
        stops.append((t[s], t[e - 1], x[s:e].mean(), y[s:e].mean()))
    return stops


def resample_by_arclength(x, y, spacing):
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0], np.cumsum(seg)])
    si = np.arange(0, s[-1], spacing)
    return np.interp(si, s, x), np.interp(si, s, y), s[-1] - si   # last: dist to end


def dist_to_end_at(x, y, px, py):
    """Arc-length distance to trip end for arbitrary points on the path."""
    seg = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0], np.cumsum(seg)])
    idx = [int(np.argmin(np.hypot(x - a, y - b))) for a, b in zip(px, py)]
    return s[-1] - s[idx]


# ---------------------------------------------------------------------------
# OpenStreetMap data
# ---------------------------------------------------------------------------
def overpass(query: str, name: str, retries: int = 5):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{name}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    req = urllib.request.Request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": USER_AGENT},
    )
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as exc:
            # 429/504 are the public server being busy; back off and retry
            if exc.code not in (429, 502, 503, 504) or attempt == retries:
                raise
            wait = 15 * attempt
            print(f"    {name}: HTTP {exc.code}, retrying in {wait}s ...")
            time.sleep(wait)
    cache.write_text(json.dumps(data))
    return data


def fetch_osm(radius_m, tiles=4):
    """Fetch signals/stop signs and road geometry around the end point.

    The area is split into tiles x tiles queries so each one stays small enough
    for the public Overpass server. Results are cached per tile.
    """
    dlat = radius_m / M_PER_DEG_LAT
    dlon = radius_m / M_PER_DEG_LON
    lats = np.linspace(END_LAT - dlat, END_LAT + dlat, tiles + 1)
    lons = np.linspace(END_LON - dlon, END_LON + dlon, tiles + 1)

    signals = {}
    roads = {}
    for a in range(tiles):
        for b in range(tiles):
            bbox = f"{lats[a]:.5f},{lons[b]:.5f},{lats[a+1]:.5f},{lons[b+1]:.5f}"
            name = f"r{int(radius_m)}_t{a}{b}"
            print(f"  Tile {a*tiles + b + 1}/{tiles*tiles} ...", end="\r", flush=True)

            sig = overpass(
                f'[out:json][timeout:180];node[highway~"^(traffic_signals|stop)$"]({bbox});out;',
                f"signals_{name}",
            )
            for el in sig["elements"]:
                signals[el["id"]] = (el["lat"], el["lon"])

            rd = overpass(
                f'[out:json][timeout:180];way[highway~"^({ROAD_CLASSES})(_link)?$"]({bbox});out skel geom;',
                f"roads_{name}",
            )
            for el in rd["elements"]:
                if "geometry" in el:
                    roads[el["id"]] = np.array([[p["lat"], p["lon"]] for p in el["geometry"]])
    print()
    return np.array(list(signals.values())), list(roads.values())


# ---------------------------------------------------------------------------
# Road raster (no scipy: rasterise, then dilate with array shifts)
# ---------------------------------------------------------------------------
class RoadGrid:
    def __init__(self, roads_local, radius_m):
        self.r = radius_m
        self.n = int(2 * radius_m / CELL_M) + 1
        grid = np.zeros((self.n, self.n), dtype=bool)
        for e, n in roads_local:
            seg_len = np.hypot(np.diff(e), np.diff(n))
            s = np.concatenate([[0], np.cumsum(seg_len)])
            si = np.arange(0, s[-1] + CELL_M / 2, CELL_M / 2)
            i, j = self._idx(np.interp(si, s, e), np.interp(si, s, n))
            ok = (i >= 0) & (i < self.n) & (j >= 0) & (j < self.n)
            grid[j[ok], i[ok]] = True
        self.near = self._dilate(grid, int(round(ROAD_NEAR_M / CELL_M)))
        self.far  = self._dilate(grid, int(round(ROAD_FAR_M / CELL_M)))

    def _idx(self, e, n):
        return (np.floor((e + self.r) / CELL_M).astype(int),
                np.floor((n + self.r) / CELL_M).astype(int))

    @staticmethod
    def _dilate(grid, r):
        out = grid.copy()
        for axis in (0, 1):
            acc = out.copy()
            for k in range(1, r + 1):
                acc |= np.roll(out, k, axis=axis)
                acc |= np.roll(out, -k, axis=axis)
            out = acc
        return out

    def score(self, e, n):
        i, j = self._idx(e, n)
        ok = (i >= 0) & (i < self.n) & (j >= 0) & (j < self.n)
        s = np.zeros(len(e))
        s[ok] = np.where(self.near[j[ok], i[ok]], 1.0,
                         np.where(self.far[j[ok], i[ok]], 0.5, 0.0))
        return s


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def rotate_anchor(x, y, theta_deg, x_end, y_end):
    """Rotate local x/y by θ (CCW) and translate so the trip end sits at (0, 0)."""
    th = math.radians(theta_deg)
    c, s = math.cos(th), math.sin(th)
    dx, dy = x - x_end, y - y_end
    return dx * c - dy * s, dx * s + dy * c


class Scorer:
    def __init__(self, samples, stops, stops_dist_to_end, grid, signals_local, x_end, y_end):
        self.sx, self.sy, sd = samples
        self.sw = 1.0 / (1.0 + sd / DRIFT_SCALE_M)
        self.px = np.array([s[2] for s in stops])
        self.py = np.array([s[3] for s in stops])
        self.pw = 1.0 / (1.0 + stops_dist_to_end / DRIFT_SCALE_M)
        self.grid = grid
        self.sig_e, self.sig_n = signals_local
        self.x_end, self.y_end = x_end, y_end

    def stop_distances(self, theta):
        e, n = rotate_anchor(self.px, self.py, theta, self.x_end, self.y_end)
        d = np.hypot(e[:, None] - self.sig_e[None, :], n[:, None] - self.sig_n[None, :])
        return d.min(axis=1)

    def __call__(self, theta):
        e, n = rotate_anchor(self.sx, self.sy, theta, self.x_end, self.y_end)
        road = np.sum(self.sw * self.grid.score(e, n)) / self.sw.sum()
        d = self.stop_distances(theta)
        stop = np.sum(self.pw * np.clip(1 - d / STOP_FALLOFF_M, 0, 1)) / self.pw.sum()
        return ROAD_WEIGHT * road + (1 - ROAD_WEIGHT) * stop, road, stop


def find_peaks(thetas, scores, k, min_sep):
    order = np.argsort(scores)[::-1]
    peaks = []
    for i in order:
        th = thetas[i]
        if all(abs((th - p + 180) % 360 - 180) >= min_sep for p in peaks):
            peaks.append(th)
        if len(peaks) == k:
            break
    return peaks


def reverse_geocode(lat, lon):
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "json", "zoom": 14})
    req = urllib.request.Request(f"{NOMINATIM_URL}?{q}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("display_name", "?")
    except Exception as exc:
        return f"(geocode failed: {exc})"
    finally:
        time.sleep(1.1)   # Nominatim usage policy: max 1 request/second


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
CANDIDATE_COLORS = ["tab:blue", "tab:green", "tab:purple", "tab:brown", "tab:pink"]


def plot(coarse_t, coarse_s, results, x, y, x_end, y_end, roads_local, signals_local, stops):
    """Score curve plus every ranked candidate drawn on the map."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle("Life is a Highway: rotation search")
    colors = [CANDIDATE_COLORS[k % len(CANDIDATE_COLORS)] for k in range(len(results))]

    ax1.plot(coarse_t, coarse_s, "k-", linewidth=0.8)
    for k, (r, c) in enumerate(zip(results, colors), 1):
        ax1.axvline(r[0], color=c, linestyle="--", label=f"#{k}  θ = {r[0]:.2f}°  score {r[1]:.3f}")
    ax1.set_xlabel("Rotation θ (deg, local frame → East/North, CCW)")
    ax1.set_ylabel("Combined score")
    ax1.set_title("Score vs rotation")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    stop_x = np.array([s[2] for s in stops])
    stop_y = np.array([s[3] for s in stops])
    paths = [rotate_anchor(x, y, r[0], x_end, y_end) for r in results]

    pad = 2000
    lo_e = min(e.min() for e, _ in paths) - pad
    hi_e = max(e.max() for e, _ in paths) + pad
    lo_n = min(n.min() for _, n in paths) - pad
    hi_n = max(n.max() for _, n in paths) + pad
    segs = [np.column_stack(r) for r in roads_local
            if (r[0].max() > lo_e) & (r[0].min() < hi_e) & (r[1].max() > lo_n) & (r[1].min() < hi_n)]
    ax2.add_collection(LineCollection(segs, colors="0.8", linewidths=0.4))
    se, sn = signals_local
    m = (se > lo_e) & (se < hi_e) & (sn > lo_n) & (sn < hi_n)
    ax2.scatter(se[m], sn[m], s=2, c="tab:orange", alpha=0.5, label="OSM signals / stop signs")

    # Every rotation puts the start somewhere on this circle
    net = math.hypot(x[0] - x_end, y[0] - y_end)
    a = np.linspace(0, 2 * np.pi, 361)
    ax2.plot(net * np.cos(a), net * np.sin(a), "k:", linewidth=0.8, label=f"{net/1000:.1f} km start circle")

    # Higher zorder for better ranks keeps #1 drawn on top
    for k in range(len(results)):
        th = results[k][0]
        e, n = paths[k]
        c = colors[k]
        best = k == 0
        z = 10 - k
        ax2.plot(e, n, "-", color=c, linewidth=1.6 if best else 1.0, alpha=1.0 if best else 0.8,
                 label=f"#{k+1} path, θ = {th:.2f}°", zorder=z)
        pe, pn = rotate_anchor(stop_x, stop_y, th, x_end, y_end)
        ax2.scatter(pe, pn, s=30, facecolors="none", edgecolors=c, zorder=z)
        ax2.plot(e[0], n[0], "o", color=c, markersize=10, markeredgecolor="k", zorder=z)
        ax2.annotate(f"#{k+1}", (e[0], n[0]), xytext=(6, 6), textcoords="offset points",
                     fontsize=10, fontweight="bold", color=c, zorder=z)
    ax2.plot(0, 0, "rs", markersize=9, label="End (given)", zorder=20)
    ax2.scatter([], [], s=30, facecolors="none", edgecolors="k", label="Full stops")

    ax2.set_xlim(lo_e, hi_e)
    ax2.set_ylim(lo_n, hi_n)
    ax2.set_aspect("equal")
    ax2.set_xlabel("East of end point (m)")
    ax2.set_ylabel("North of end point (m)")
    ax2.set_title(f"Top {len(results)} candidate rotations (circles = estimated starts)")
    ax2.legend(loc="best", fontsize=8)

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"Plot saved → {OUT_PNG}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not CSV_FILE.exists():
        sys.exit(f"{CSV_FILE} not found; run decode_path.py first")

    print(f"Loading {CSV_FILE} ...")
    t, x, y, speed = load_path(CSV_FILE)
    x_end, y_end = x[-1], y[-1]
    net = math.hypot(x_end - x[0], y_end - y[0])
    print(f"  Net displacement   : {net/1000:.2f} km  (start lies on this circle around the end)")

    stops = extract_stops(t, x, y, speed)
    stops_dist_to_end = dist_to_end_at(x, y, [s[2] for s in stops], [s[3] for s in stops])
    print(f"  Full stops         : {len(stops)}")

    samples = resample_by_arclength(x, y, SAMPLE_SPACING_M)
    print(f"  Path samples       : {len(samples[0])} every {SAMPLE_SPACING_M:.0f} m")

    # Every rotation keeps the path within its own extent of the end point
    radius = max(np.hypot(x - x_end, y - y_end)) + 1500
    print(f"Fetching OSM data within {radius/1000:.1f} km of the end point ...")
    signals, roads = fetch_osm(radius)
    print(f"  Signals/stop signs : {len(signals)}")
    print(f"  Road ways          : {len(roads)}")

    signals_local = to_local(signals[:, 0], signals[:, 1])
    roads_local = [to_local(r[:, 0], r[:, 1]) for r in roads]

    print("Rasterising roads ...")
    grid = RoadGrid(roads_local, radius)
    scorer = Scorer(samples, stops, stops_dist_to_end, grid, signals_local, x_end, y_end)

    print("Coarse rotation sweep ...")
    coarse_t = np.arange(0, 360, COARSE_STEP_DEG)
    coarse = np.array([scorer(th) for th in coarse_t])
    peaks = find_peaks(coarse_t, coarse[:, 0], N_CANDIDATES, MIN_PEAK_SEP_DEG)

    print("Refining peaks ...")
    results = []
    for p in peaks:
        fine_t = np.arange(p - 2 * COARSE_STEP_DEG, p + 2 * COARSE_STEP_DEG, FINE_STEP_DEG) % 360
        fine = np.array([scorer(th) for th in fine_t])
        i = int(np.argmax(fine[:, 0]))
        th = fine_t[i]
        e0, n0 = rotate_anchor(x[0], y[0], th, x_end, y_end)
        lat, lon = to_latlon(e0, n0)
        results.append((th, *fine[i], lat, lon))
    results.sort(key=lambda r: -r[1])

    print()
    print(f"{'rank':>4} {'θ (deg)':>8} {'combined':>9} {'road':>6} {'stop':>6}  {'start lat, lon':<24} place")
    for k, (th, comb, road, stop, lat, lon) in enumerate(results, 1):
        place = reverse_geocode(lat, lon)
        print(f"{k:>4} {th:>8.2f} {comb:>9.3f} {road:>6.3f} {stop:>6.3f}  {lat:.5f}, {lon:.5f}    {place}")

    best = results[0][0]
    print()
    print(f"Stop matches at best θ = {best:.2f}°:")
    d = scorer.stop_distances(best)
    for k, (s, dist) in enumerate(zip(stops, d)):
        e, n = rotate_anchor(np.array([s[2]]), np.array([s[3]]), best, x_end, y_end)
        lat, lon = to_latlon(e[0], n[0])
        flag = "HIT " if dist <= STOP_FALLOFF_M else "miss"
        print(f"  #{k:<2} t={s[0]:7.1f}-{s[1]:7.1f}s  {s[1]-s[0]:5.1f}s  "
              f"{lat:.5f}, {lon:.5f}  nearest signal {dist:6.0f} m  {flag}")

    print()
    print(f"Most likely start: {results[0][4]:.5f}, {results[0][5]:.5f}")
    print("(Ranked estimate only; confirm by submitting the coordinate.)")

    plot(coarse_t, coarse[:, 0], results, x, y, x_end, y_end, roads_local, signals_local, stops)
