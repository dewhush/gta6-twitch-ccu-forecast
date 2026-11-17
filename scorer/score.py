"""Local scorer reproducing make.fun gta6-twitch-ccu-forecast-01's official metric exactly.

Metric: mean pinball loss on the log scale over hours 2-24 x levels [0.05,0.25,0.5,0.75,0.95].
  d = ln(y) - ln(q); pinball = 2*max(tau*d, (tau-1)*d); y floored at 1.
Lower is better. A case whose output is invalid scores as if every quantile equalled hour-1's print.

Usage: python3 scorer/score.py [out_dir] [--truth-dir scorer/]
"""
import json, math, os, sys, glob

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
SIGMA = 0.15

def pinball(tau, y, q):
    y = max(1.0, y); q = max(1e-12, q)
    d = math.log(y) - math.log(q)
    return 2.0 * max(tau * d, (tau - 1) * d)

def parse_out(path):
    """Return list of 23 (hour, [q05..q95]) rows, or None if invalid."""
    try:
        obj = json.loads(open(path, encoding="utf-8").read())
    except Exception:
        return None
    if not isinstance(obj, dict) or set(obj.keys()) != {"hours"}:
        return None
    rows = obj["hours"]
    if not isinstance(rows, list) or len(rows) != 23:
        return None
    out = []
    for r in rows:
        if not isinstance(r, dict) or set(r.keys()) != {"hour", "q"}:
            return None
        h = r["hour"]; q = r["q"]
        if not isinstance(h, int) or not isinstance(q, list) or len(q) != 5:
            return None
        for v in q:
            if not isinstance(v, (int, float)) or math.isnan(v) or v <= 0 or v > 1e9:
                return None
        # non-decreasing
        if any(q[i] > q[i+1] + 1e-9 for i in range(4)):
            return None
        out.append((h, q))
    return out

def case_loss(case, rows):
    """Mean pinball over hours 2..24 that have truth, x levels."""
    known = next((k for k in case["known"] if k["hour"] == 1), None)
    p1 = max(1, known["viewers"]) if known else 1
    truth = rows_truth if False else None  # placeholder
    return None

def persistence_quantiles(p1, h):
    return [p1 * math.exp(z * SIGMA * math.sqrt(h - 1)) for z in Z]

def score_case(case, truth, rows):
    """rows: parsed output list [(hour,[q..])] or None (invalid). Returns loss."""
    known = next((k for k in case["known"] if k["hour"] == 1), None)
    p1 = max(1, known["viewers"]) if known else 1
    qmap = {}
    if rows is not None:
        for h, q in rows:
            qmap[h] = q
    tot = 0.0; n = 0
    for h in range(2, 25):
        if h not in truth:
            continue
        y = truth[h]
        if rows is None:
            qs = [p1] * 5  # invalid: every quantile = hour-1 print
        else:
            qs = qmap.get(h)
            if qs is None:
                qs = [p1] * 5
        for tau, q in zip(LEVELS, qs):
            tot += pinball(tau, y, q); n += 1
    return (tot / n) if n else float("nan")

def baseline_loss(case, truth):
    known = next((k for k in case["known"] if k["hour"] == 1), None)
    p1 = max(1, known["viewers"]) if known else 1
    tot = 0.0; n = 0
    for h in range(2, 25):
        if h not in truth:
            continue
        qs = persistence_quantiles(p1, h)
        for tau, q in zip(LEVELS, qs):
            tot += pinball(tau, truth[h], q); n += 1
    return (tot / n) if n else float("nan")

def main():
    out_dir = "out"
    truth_dir = "scorer"
    args = [a for a in sys.argv[1:]]
    if args and not args[0].startswith("--"):
        out_dir = args.pop(0)
    if "--truth-dir" in args:
        i = args.index("--truth-dir"); truth_dir = args[i+1]
    # load truth
    truths = {}
    for p in glob.glob(os.path.join(truth_dir, "truth_p*.json")):
        cid = os.path.basename(p)[len("truth_"):-len(".json")]
        truths[cid] = {int(k): v for k, v in json.load(open(p)).items()}
    if not truths:
        print("No truth files found in", truth_dir); sys.exit(1)
    # load cases
    cases = {}
    for cid in truths:
        cp = os.path.join("input", cid + ".in")
        if os.path.exists(cp):
            cases[cid] = json.loads(open(cp, encoding="utf-8").read())
    results = []
    for cid in sorted(truths):
        if cid not in cases:
            continue
        op = os.path.join(out_dir, cid + ".out")
        rows = parse_out(op) if os.path.exists(op) else None
        ours = score_case(cases[cid], truths[cid], rows)
        base = baseline_loss(cases[cid], truths[cid])
        results.append((cid, ours, base, rows is not None))
    print(f"{'case':<6}{'ours':>10}{'baseline':>11}{'valid':>8}")
    o = []; b = []
    for cid, ours, base, valid in results:
        print(f"{cid:<6}{ours:>10.4f}{base:>11.4f}{'yes' if valid else 'NO':>8}")
        o.append(ours); b.append(base)
    if o:
        mo = sum(o)/len(o); mb = sum(b)/len(b)
        print(f"{'MEAN':<6}{mo:>10.4f}{mb:>11.4f}")
        print(f"\nbeat baseline? {'YES' if mo < mb else 'NO'}  (delta {mo-mb:+.4f})")

if __name__ == "__main__":
    main()
