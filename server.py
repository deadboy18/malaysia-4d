"""
Deadboy4D Analytics - Local Analysis Server
=============================================
Run:  python server.py
Open: http://localhost:8080
"""

import os, re, sys, json, time, threading, subprocess
from collections import Counter
from datetime import date

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_file

app = Flask(__name__, static_folder=".")

# -- Operator config -------------------------------------------------------
OPERATORS = {
    "sportstoto": {
        "name": "Sport Toto",
        "csv": "data/sportstoto_draws.csv",
        "scraper": "scraper_sportstoto.py",
        "color": "#CC0000",
        "min_year": 1992,
    },
    "magnum": {
        "name": "Magnum 4D",
        "csv": "data/magnum_draws.csv",
        "scraper": "scraper_magnum.py",
        "color": "#FFD700",
        "min_year": 1985,
    },
    "damacai": {
        "name": "Da Ma Cai",
        "csv": "data/damacai_draws.csv",
        "scraper": "scraper_damacai.py",
        "color": "#0066CC",
        "min_year": 2005,
    },
}

ALL_COLS = (
    ["prize_1", "prize_2", "prize_3"]
    + [f"special_{i}" for i in range(1, 11)]
    + [f"consol_{i}" for i in range(1, 11)]
)

# -- Analytics cache per operator ------------------------------------------
_caches = {}
_scrape = {"running": False, "log": [], "done": False, "error": None, "operator": None}


def load_and_compute(op_key):
    """Load CSV and precompute analytics for an operator. Cached by mtime."""
    op = OPERATORS.get(op_key)
    if not op or not os.path.exists(op["csv"]):
        return None
    mtime = os.path.getmtime(op["csv"])
    if op_key in _caches and _caches[op_key]["_mtime"] == mtime:
        return _caches[op_key]

    df = pd.read_csv(op["csv"], parse_dates=["date"])
    valid_cols = [c for c in ALL_COLS if c in df.columns]
    for col in valid_cols:
        df[col] = df[col].astype(str).str.zfill(4)

    freq = {}
    all_nums_flat = []
    for idx, row in df.iterrows():
        for col in valid_cols:
            n = row[col]
            if not (isinstance(n, str) and len(n) == 4 and n.isdigit()):
                continue
            all_nums_flat.append(n)
            if n not in freq:
                freq[n] = dict(total=0, p1=0, p2=0, p3=0, sp=0, co=0, last_idx=0)
            freq[n]["total"] += 1
            t = ("p1" if col == "prize_1" else "p2" if col == "prize_2"
                 else "p3" if col == "prize_3"
                 else "sp" if "special" in col else "co")
            freq[n][t] += 1
            freq[n]["last_idx"] = idx
    last_idx = len(df) - 1
    for n in freq:
        freq[n]["gap"] = last_idx - freq[n]["last_idx"]

    digit_positions = []
    for pos in range(4):
        cnt = Counter(int(n[pos]) for n in all_nums_flat)
        digit_positions.append([cnt.get(d, 0) for d in range(10)])

    def classify_pattern(n):
        d = list(n)
        if len(set(d)) == 1: return "quad"
        if d == sorted(d): return "ascending"
        if d == sorted(d, reverse=True): return "descending"
        if n == n[::-1]: return "palindrome"
        if len(set(d)) == 2: return "two_digit"
        if len(set(d)) == 3: return "three_digit"
        return "all_diff"

    pattern_1st = Counter()
    for n in df["prize_1"].astype(str).str.zfill(4):
        if len(n) == 4 and n.isdigit():
            pattern_1st[classify_pattern(n)] += 1
    pattern_all = Counter()
    for n in all_nums_flat:
        pattern_all[classify_pattern(n)] += 1

    df["weekday"] = df["date"].dt.day_name()
    weekday_freq = {}
    for day in ["Wednesday", "Saturday", "Sunday", "Tuesday", "Thursday", "Friday", "Monday"]:
        sub = df[df["weekday"] == day]
        if len(sub) == 0:
            continue
        nums = []
        for col in valid_cols:
            nums += sub[col].tolist()
        nums = [n for n in nums if isinstance(n, str) and len(n) == 4 and n.isdigit()]
        cnt = Counter(nums)
        weekday_freq[day] = {"draws": len(sub), "top10": [{"num": n, "count": c} for n, c in cnt.most_common(10)]}

    cache = {
        "_mtime": mtime, "df": df, "freq": freq,
        "digit_positions": digit_positions,
        "pattern_counts_1st": dict(pattern_1st),
        "pattern_counts_all": dict(pattern_all),
        "weekday_freq": weekday_freq,
        "total_numbers": len(all_nums_flat),
        "total_draws": len(df),
    }
    _caches[op_key] = cache
    return cache


# -- CORS ------------------------------------------------------------------
@app.after_request
def add_cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    return r


# -- Static ----------------------------------------------------------------
@app.route("/")
def index():
    return send_file("dashboard.html")


# -- Operators list --------------------------------------------------------
@app.route("/api/operators")
def operators():
    result = {}
    for key, op in OPERATORS.items():
        has_data = os.path.exists(op["csv"])
        draws = 0
        date_from = ""
        date_to = ""
        if has_data:
            try:
                df_tmp = pd.read_csv(op["csv"], usecols=["date"], parse_dates=["date"])
                draws = len(df_tmp)
                date_from = str(df_tmp["date"].min().date())
                date_to = str(df_tmp["date"].max().date())
            except:
                try:
                    draws = sum(1 for _ in open(op["csv"])) - 1
                except:
                    pass
        result[key] = {
            "name": op["name"], "color": op["color"],
            "has_data": has_data, "draws": draws,
            "min_year": op["min_year"],
            "date_from": date_from, "date_to": date_to,
        }
    return jsonify(result)


# -- Status ----------------------------------------------------------------
@app.route("/api/<op>/status")
def status(op):
    c = load_and_compute(op)
    if c is None:
        return jsonify({"loaded": False, "draws": 0, "message": "No data"})
    df = c["df"]
    return jsonify({
        "loaded": True,
        "draws": c["total_draws"],
        "numbers": c["total_numbers"],
        "unique": len(c["freq"]),
        "coverage": round(len(c["freq"]) / 100, 1),
        "date_from": str(df["date"].min().date()),
        "date_to": str(df["date"].max().date()),
        "draw_from": int(df["draw_seq"].min()),
        "draw_to": int(df["draw_seq"].max()),
        "expected": round(c["total_numbers"] / 10000, 2),
    })


# -- Frequency -------------------------------------------------------------
@app.route("/api/<op>/frequency")
def frequency(op):
    c = load_and_compute(op)
    if c is None:
        return jsonify({"error": "no data"}), 404
    tier = request.args.get("tier", "all")
    key = tier if tier in ("p1", "p2", "p3", "sp", "co", "total") else "total"
    rows = [
        {"num": n, "count": d[key], "total": d["total"],
         "p1": d["p1"], "p2": d["p2"], "p3": d["p3"],
         "sp": d["sp"], "co": d["co"], "gap": d["gap"]}
        for n, d in c["freq"].items() if d[key] > 0
    ]
    rows.sort(key=lambda x: -x["count"])
    total = c["total_numbers"]
    return jsonify({"top": rows[:50], "bottom": rows[-50:][::-1] if len(rows) > 50 else [], "total": total, "expected": round(total / 10000, 2), "unique": len(rows)})


# -- Digits ----------------------------------------------------------------
@app.route("/api/<op>/digits")
def digits(op):
    c = load_and_compute(op)
    if c is None:
        return jsonify({"error": "no data"}), 404
    return jsonify({"positions": c["digit_positions"]})


# -- Gaps ------------------------------------------------------------------
@app.route("/api/<op>/gaps")
def gaps(op):
    c = load_and_compute(op)
    if c is None:
        return jsonify({"error": "no data"}), 404
    rows = [{"num": n, **d} for n, d in c["freq"].items()]
    rows.sort(key=lambda x: -x["gap"])
    gap_vals = [r["gap"] for r in rows]
    return jsonify({
        "overdue": rows[:50], "gap_median": int(np.median(gap_vals)),
        "gap_mean": round(float(np.mean(gap_vals)), 1),
        "never_drawn": 10000 - len(rows),
        "overdue_100": sum(1 for g in gap_vals if g > 100),
        "overdue_50": sum(1 for g in gap_vals if g > 50),
    })


# -- Lookup ----------------------------------------------------------------
@app.route("/api/<op>/lookup")
def lookup(op):
    c = load_and_compute(op)
    if c is None:
        return jsonify({"error": "no data"}), 404
    num = request.args.get("num", "").zfill(4)
    if len(num) != 4 or not num.isdigit():
        return jsonify({"error": "invalid number"}), 400
    df = c["df"]
    valid_cols = [col for col in ALL_COLS if col in df.columns]
    appearances = []
    for _, row in df.iterrows():
        for col in valid_cols:
            if str(row[col]).zfill(4) == num:
                t = ("1st" if col == "prize_1" else "2nd" if col == "prize_2"
                     else "3rd" if col == "prize_3"
                     else "Special" if "special" in col else "Consolation")
                appearances.append({"draw_seq": int(row["draw_seq"]), "date": str(row["date"].date()), "tier": t})
    appearances.sort(key=lambda x: x["draw_seq"])
    stats = c["freq"].get(num, {"total": 0, "p1": 0, "p2": 0, "p3": 0, "sp": 0, "co": 0, "gap": None})
    return jsonify({
        "num": num, "found": len(appearances) > 0, "total": len(appearances),
        "tiers": {"p1": stats["p1"], "p2": stats["p2"], "p3": stats["p3"], "sp": stats["sp"], "co": stats["co"]},
        "gap": stats.get("gap"), "appearances": appearances[-30:],
    })


# -- Patterns --------------------------------------------------------------
@app.route("/api/<op>/patterns")
def patterns(op):
    c = load_and_compute(op)
    if c is None:
        return jsonify({"error": "no data"}), 404
    return jsonify({"all": c["pattern_counts_all"], "1st": c["pattern_counts_1st"], "weekdays": c["weekday_freq"]})


# -- Cross-operator comparison ---------------------------------------------
@app.route("/api/compare")
def compare():
    result = {}
    for key in OPERATORS:
        c = load_and_compute(key)
        if c is None:
            continue
        top20 = sorted(c["freq"].items(), key=lambda x: -x[1]["total"])[:20]
        result[key] = {
            "name": OPERATORS[key]["name"],
            "draws": c["total_draws"],
            "unique": len(c["freq"]),
            "top20": [{"num": n, "count": d["total"]} for n, d in top20],
            "never_drawn": 10000 - len(c["freq"]),
        }
    return jsonify(result)


# -- Export ----------------------------------------------------------------
@app.route("/api/<op>/export")
def export(op):
    csv_path = OPERATORS.get(op, {}).get("csv", "")
    if not os.path.exists(csv_path):
        return jsonify({"error": "no data"}), 404
    return send_file(csv_path, as_attachment=True, download_name=f"{op}_draws.csv")


# -- Scraper ---------------------------------------------------------------
@app.route("/api/scrape", methods=["POST"])
def scrape_start():
    global _scrape, _caches
    if _scrape["running"]:
        return jsonify({"error": "already running"}), 409
    body = request.get_json(force=True, silent=True) or {}
    op_key = body.get("operator", "sportstoto")
    from_y = body.get("from_year", date.today().year - 5)
    to_y = body.get("to_year", date.today().year)
    update = body.get("update", False)
    op = OPERATORS.get(op_key)
    if not op:
        return jsonify({"error": "unknown operator"}), 400
    _scrape = {"running": True, "log": [], "done": False, "error": None, "operator": op_key}

    def run():
        global _scrape, _caches
        try:
            scraper = op["scraper"]
            if not os.path.exists(scraper):
                _scrape["log"].append(f"[ERROR] Scraper not found: {scraper}")
                _scrape["log"].append("This operator's scraper is not yet available.")
                return
            cmd = [sys.executable, "-u", scraper]
            if update:
                cmd.append("--update")
            else:
                cmd += ["--from", str(from_y), "--to", str(to_y)]
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            for line in proc.stdout:
                _scrape["log"].append(line.rstrip())
            proc.wait()
            if op_key in _caches:
                del _caches[op_key]
        except Exception as e:
            _scrape["error"] = str(e)
        finally:
            _scrape["running"] = False
            _scrape["done"] = True

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started", "operator": op_key})


@app.route("/api/scrape/status")
def scrape_status():
    if _scrape["running"] and _scrape.get("operator") in _caches:
        del _caches[_scrape["operator"]]
    pct = 0
    current = ""
    for line in reversed(_scrape["log"]):
        if "[PROGRESS]" in line and pct == 0:
            m = re.search(r"(\d+)%", line)
            if m:
                pct = int(m.group(1))
            m2 = re.search(r"\| (\d{4}-\d{2})", line)
            if m2:
                current = m2.group(1)
            break
    draws_so_far = 0
    op_key = _scrape.get("operator", "sportstoto")
    csv_path = OPERATORS.get(op_key, {}).get("csv", "")
    if os.path.exists(csv_path):
        try:
            draws_so_far = sum(1 for _ in open(csv_path)) - 1
        except:
            pass
    return jsonify({
        "running": _scrape["running"], "done": _scrape["done"],
        "error": _scrape["error"], "operator": _scrape.get("operator"),
        "log": _scrape["log"][-100:], "progress_pct": pct,
        "current": current, "draws_so_far": max(draws_so_far, 0),
    })


# -- Run -------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("  Deadboy4D Analytics Server")
    print("  Open: http://localhost:8080")
    print("  Ctrl+C to stop")
    print("=" * 50)
    for key, op in OPERATORS.items():
        if os.path.exists(op["csv"]):
            print(f"  [{key}] Found data, preloading...")
            load_and_compute(key)
        else:
            print(f"  [{key}] No data yet")
    print("  Ready.")
    app.run(host="0.0.0.0", port=8080, debug=False)
