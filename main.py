"""GTA VI launch-day Twitch CCU forecaster — comparable-launch log-ratio quantiles.

Strategy:
  1. Align each comparable launch's hourly Twitch curve to its own release (unlock/day_start).
  2. Build a launch-day "shape" in log space: r(h) = ln(viewers_h) - ln(viewers_1), h = 1..24.
  3. Kernel-weight comparables by similarity to our launch (hour-1 size, platform, franchise).
  4. Weighted-mean center curve; scale to our known hour-1 print p1.
  5. Quantiles = center * exp(z_tau * sigma(h)) with sigma from the comparable residual spread.

Robust: any exception falls back to the persistence baseline so output is ALWAYS valid.
Deterministic: sorted iteration, no randomness.
"""
import json, math, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
SIGMA = 0.15  # persistence fallback sigma

# ---- tuning knobs ----
SIZE_KERNEL = 2.2
MIN_SHAPE_SIGMA = 0.06 # floor on the per-hour residual spread
SHAPE_SIGMA_SCALE = 0.8
SPREAD_DAMP = 0.5
HORIZON_GROWTH = 0.0   # extra spread per sqrt hour (0 = flat)


def parse_iso(ts):
    """Parse '2022-02-25T00:00:00Z' -> epoch seconds."""
    from datetime import datetime, timezone
    t = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(t).timestamp()


def hour_index(from_ts, anchor_ts):
    """Integer hour offset of from_ts from anchor_ts (release hour = 0)."""
    return int(round((parse_iso(from_ts) - anchor_ts) / 3600.0))


def comparable_shape(comp):
    """Return {rel_hour(1..24): viewers} for a comparable's release day, anchored on its unlock.

    Anchors on `unlock` if it is a timestamp, else day_start. rel_hour 1 = [anchor, anchor+1h).
    """
    anchor = comp.get("unlock")
    # unlock may be a long prose string, not a timestamp; fall back to day_start
    anchor_ts = None
    if isinstance(anchor, str) and len(anchor) >= 10 and anchor[4] == "-":
        try:
            anchor_ts = parse_iso(anchor[:19] + ("Z" if anchor.endswith("Z") else ""))
        except Exception:
            anchor_ts = None
    if anchor_ts is None:
        anchor_ts = parse_iso(comp["day_start"].replace("Z", "+00:00").replace("+00:00", "Z") if False else comp["day_start"])
    curve = {}
    for pt in comp.get("hourly", []):
        try:
            rh = hour_index(pt["from"], anchor_ts) + 1  # release hour -> 1
        except Exception:
            continue
        if 1 <= rh <= 24:
            v = pt.get("viewers")
            if isinstance(v, (int, float)) and v > 0:
                curve[rh] = v
    return curve if 1 in curve else None


def launch_hour1(comp):
    c = comparable_shape(comp)
    return c[1] if c else None


def platform_family(platforms):
    p = (platforms or "").lower()
    has_pc = "pc" in p
    has_console = any(k in p for k in ("ps4", "ps5", "xbox", "switch", "console"))
    if has_pc and has_console:
        return "both"
    if has_pc:
        return "pc"
    if has_console:
        return "console"
    return "both"


def build_center_and_sigma(p1, comps, our_platform):
    """Return (center[h] for h=2..24 as log-ratio from h1, sigma[h])."""
    # gather shapes
    shapes = []
    for c in comps:
        curve = comparable_shape(c)
        if not curve:
            continue
        c1 = curve[1]
        if c1 <= 0:
            continue
        # similarity weight: size (hour-1) kernel + platform match
        w = math.exp(-((math.log(p1) - math.log(c1)) ** 2) / (2 * SIZE_KERNEL ** 2))
        fam = platform_family(c.get("platforms"))
        if fam == our_platform:
            w *= 1.5
        elif fam == "both" or our_platform == "both":
            w *= 1.15
        # franchise bonus: GTA / Rockstar-adjacent not really present; skip
        # keep only hours that are monotonically usable; require h1..h? present enough
        # build log-ratio shape r(h) = ln(v_h) - ln(v_1) for hours present
        shape = {}
        for h, v in curve.items():
            shape[h] = math.log(v) - math.log(c1)
        shapes.append((w, shape))
    # compute weighted center & residual spread per hour
    center = {}
    sigma = {}
    for h in range(2, 25):
        num = 0.0; den = 0.0; vals = []
        for w, shape in shapes:
            if h in shape:
                num += w * shape[h]; den += w; vals.append((w, shape[h]))
        if den == 0:
            continue
        mu = num / den
        # weighted variance
        var = 0.0; wsum = 0.0
        for w, v in vals:
            var += w * (v - mu) ** 2; wsum += w
        var = var / wsum if wsum else 0.0
        center[h] = mu
        sigma[h] = max(MIN_SHAPE_SIGMA, SHAPE_SIGMA_SCALE * math.sqrt(var))
    return center, sigma


def persistence_qs(p1, h):
    return [p1 * math.exp(z * SIGMA * math.sqrt(h - 1)) for z in Z]


def forecast_case(case):
    known = next((k for k in case["known"] if k["hour"] == 1), None)
    if known is None:
        raise ValueError("no hour-1 print")
    p1 = max(1.0, float(known["viewers"]))
    try:
        comps = case.get("comparables") or []
        our_platform = "console"  # GTA VI is console (PS5/Xbox) per brief
        center, sigma = build_center_and_sigma(p1, comps, our_platform)
        if not center:
            raise ValueError("no usable comparables")
        # blend center with persistence to hedge: weight center more at short horizon
        rows = []
        for row in case["forecast"]:
            h = row["hour"]
            if h in center:
                ratio = math.exp(center[h])  # center is already ln(v_h)-ln(v_1)
                med = p1 * ratio
                # widen spread modestly with horizon
                sig = max(MIN_SHAPE_SIGMA, (sigma.get(h, MIN_SHAPE_SIGMA) * SPREAD_DAMP)) + HORIZON_GROWTH * math.sqrt(h - 1)
                qs = [med * math.exp(z * sig) for z in Z]
            else:
                qs = persistence_qs(p1, h)
            rows.append((h, qs))
        return rows
    except Exception:
        # fallback: persistence
        return [(row["hour"], persistence_qs(p1, row["hour"])) for row in case["forecast"]]


def round_q(x):
    # keep 2 decimals, ensure positive
    v = max(1e-9, x)
    return round(v, 2)


def persistence_rows_from_case(case):
    """Persistence fallback rows, tolerating a missing/odd case structure."""
    p1 = 1
    try:
        known = next((k for k in case["known"] if k["hour"] == 1), None)
        if known is not None:
            p1 = max(1, int(known["viewers"]))
    except Exception:
        p1 = 1
    rows = []
    try:
        frows = case["forecast"]
    except Exception:
        frows = [{"hour": h} for h in range(2, 25)]
    for r in frows:
        rows.append((r["hour"], persistence_qs(p1, r["hour"])))
    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        # A malformed/empty case must never crash the run: fall back to persistence.
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(case, dict):
                raise ValueError("case is not an object")
            try:
                rows = forecast_case(case)
            except Exception:
                rows = persistence_rows_from_case(case)
        except Exception:
            rows = [(h, persistence_qs(1, h)) for h in range(2, 25)]
        # enforce non-decreasing + bounds
        out_hours = []
        for h, qs in rows:
            qs = [round_q(q) for q in qs]
            for i in range(4):
                if qs[i] > qs[i + 1]:
                    qs[i + 1] = qs[i]
            out_hours.append({"hour": h, "q": qs})
        # sort by hour for determinism
        out_hours.sort(key=lambda r: r["hour"])
        payload = {"hours": out_hours}
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
