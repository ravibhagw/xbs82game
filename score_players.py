import json, os, math

STATS_DIR = os.path.expanduser("~/sandbox/xbs82/stats")

PROJ_FIELDS = [
    "goals", "assists", "points", "hits", "shots",
    "penaltyMinutes", "powerPlayGoals", "shortHandedGoals",
    "gameWinningGoals", "faceoffsTaken", "faceoffsWon",
    "saves", "shutouts", "minutes", "plusMinus",
]

def zscores(values):
    n = len(values)
    if n < 2:
        return [0.0] * n
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
    if std == 0:
        return [0.0] * n
    return [(v - mean) / std for v in values]

def zblend(rates, projs, w_rate=0.6, w_proj=0.4):
    zr = zscores(rates)
    zp = zscores(projs)
    return [w_rate * zr[i] + w_proj * zp[i] for i in range(len(rates))]

def score_from_z(z):
    return round(max(0.0, min(100.0, 72 + 28 * math.tanh(z * 0.5))), 1)

for season in range(23, 49):
    path = os.path.join(STATS_DIR, f"s{season}.json")
    with open(path) as f:
        data = json.load(f)

    players = []
    for team in data:
        for p in team["players"]:
            p["_teamId"] = team["teamId"]
            players.append(p)

    # Infer season length from max GP
    season_len = max(p["gamesPlayed"] for p in players)

    # Add projected stats (per player rate * 82)
    for p in players:
        gp = p["gamesPlayed"]
        rate = 82 / gp if gp > 0 else 0
        for field in PROJ_FIELDS:
            p[f"proj_{field}"] = round(p[field] * rate, 2)

    # Team-relative +/- per GP (skaters only)
    team_pm = {}
    team_pm_n = {}
    for p in players:
        if p["position"] in ("center", "wing", "defense") and p["gamesPlayed"] > 0:
            tid = p["_teamId"]
            team_pm[tid] = team_pm.get(tid, 0) + p["plusMinus"] / p["gamesPlayed"]
            team_pm_n[tid] = team_pm_n.get(tid, 0) + 1
    team_avg_pm = {tid: team_pm[tid] / team_pm_n[tid] for tid in team_pm}

    for pos in ("center", "wing", "defense", "goalie"):
        pp = [p for p in players if p["position"] == pos and p["gamesPlayed"] > 0]
        if not pp:
            continue

        gp_factors = [1.0 if p["gamesPlayed"] >= 20 else p["gamesPlayed"] / (p["gamesPlayed"] + 15) for p in pp]

        if pos == "center":
            pts_pg   = [p["points"] / p["gamesPlayed"] for p in pp]
            pts_proj = [p["proj_points"] for p in pp]
            fo_pct   = [p["faceoffsWon"] / p["faceoffsTaken"] if p["faceoffsTaken"] > 0 else 0.40 for p in pp]
            rel_pm   = [p["plusMinus"] / p["gamesPlayed"] - team_avg_pm.get(p["_teamId"], 0) for p in pp]
            rel_pm_p = [p["proj_plusMinus"] - team_avg_pm.get(p["_teamId"], 0) * 82 for p in pp]

            z_pts = zblend(pts_pg, pts_proj)
            z_fo  = zscores(fo_pct)
            z_pm  = zblend(rel_pm, rel_pm_p)

            raw = [0.45 * z_pts[i] + 0.35 * z_fo[i] + 0.20 * z_pm[i] for i in range(len(pp))]

        elif pos == "wing":
            pts_pg    = [p["points"] / p["gamesPlayed"] for p in pp]
            pts_proj  = [p["proj_points"] for p in pp]
            goals_pg  = [p["goals"] / p["gamesPlayed"] for p in pp]
            goals_proj= [p["proj_goals"] for p in pp]
            hits_pg   = [p["hits"] / p["gamesPlayed"] for p in pp]
            hits_proj = [p["proj_hits"] for p in pp]
            rel_pm    = [p["plusMinus"] / p["gamesPlayed"] - team_avg_pm.get(p["_teamId"], 0) for p in pp]
            rel_pm_p  = [p["proj_plusMinus"] - team_avg_pm.get(p["_teamId"], 0) * 82 for p in pp]

            z_pts   = zblend(pts_pg, pts_proj)
            z_goals = zblend(goals_pg, goals_proj)
            z_hits  = zblend(hits_pg, hits_proj)
            z_pm    = zblend(rel_pm, rel_pm_p)

            raw = [0.52 * z_pts[i] + 0.28 * z_goals[i] + 0.10 * z_pm[i] + 0.10 * z_hits[i] for i in range(len(pp))]

        elif pos == "defense":
            pts_pg    = [p["points"] / p["gamesPlayed"] for p in pp]
            pts_proj  = [p["proj_points"] for p in pp]
            hits_pg   = [p["hits"] / p["gamesPlayed"] for p in pp]
            hits_proj = [p["proj_hits"] for p in pp]
            rel_pm    = [p["plusMinus"] / p["gamesPlayed"] - team_avg_pm.get(p["_teamId"], 0) for p in pp]
            rel_pm_p  = [p["proj_plusMinus"] - team_avg_pm.get(p["_teamId"], 0) * 82 for p in pp]

            z_pts  = zblend(pts_pg, pts_proj)
            z_hits = zblend(hits_pg, hits_proj)
            z_pm   = zblend(rel_pm, rel_pm_p)

            dr_vals  = [p["defenseRating"] if p["defenseRating"] > 0 else None for p in pp]
            dr_valid = [v for v in dr_vals if v is not None]
            if dr_valid:
                dr_mean = sum(dr_valid) / len(dr_valid)
                dr_std  = math.sqrt(sum((v - dr_mean) ** 2 for v in dr_valid) / len(dr_valid)) or 1
                z_dr = [(v - dr_mean) / dr_std if v is not None else None for v in dr_vals]
            else:
                z_dr = [None] * len(pp)

            raw = []
            for i in range(len(pp)):
                if z_dr[i] is not None:
                    r = 0.42 * z_dr[i] + 0.28 * z_pts[i] + 0.15 * z_pm[i] + 0.15 * z_hits[i]
                else:
                    r = 0.28 * z_pts[i] + 0.36 * z_pm[i] + 0.36 * z_hits[i]
                raw.append(r)

        elif pos == "goalie":
            sv_pct  = [p["savePercentage"] for p in pp]
            neg_gaa = [-p["goalsAgainstAverage"] for p in pp]
            so_pg   = [p["shutouts"] / p["gamesPlayed"] for p in pp]
            so_proj = [p["proj_shutouts"] for p in pp]
            gp_vol  = [p["gamesPlayed"] / 60 for p in pp]

            z_sv  = zscores(sv_pct)
            z_gaa = zscores(neg_gaa)
            z_so  = zblend(so_pg, so_proj)
            z_vol = zscores(gp_vol)

            raw = [0.40 * z_sv[i] + 0.35 * z_gaa[i] + 0.15 * z_so[i] + 0.10 * z_vol[i] for i in range(len(pp))]

        penalized = [raw[i] * gp_factors[i] for i in range(len(pp))]
        final_z   = zscores(penalized)

        for i, p in enumerate(pp):
            p["score"] = score_from_z(final_z[i])

    # Role classification
    def percentile_rank(value, values):
        return sum(1 for v in values if v < value) / len(values)

    for pos in ("center", "wing", "defense"):
        pp = [p for p in players if p["position"] == pos and p["gamesPlayed"] > 0]
        if not pp:
            continue

        if pos in ("center", "wing"):
            hits_pg_vals = [p["hits"] / p["gamesPlayed"] for p in pp]
            pts_pg_vals  = [p["points"] / p["gamesPlayed"] for p in pp]

            for i, p in enumerate(pp):
                if p["points"] == 0:
                    p["role_calc"] = "Two-Way"
                    continue
                goals_ratio  = p["goals"] / p["points"]
                hits_pct     = percentile_rank(hits_pg_vals[i], hits_pg_vals)
                pts_pct      = percentile_rank(pts_pg_vals[i], pts_pg_vals)

                if hits_pct >= 0.75 and pts_pct < 0.50:
                    p["role_calc"] = "Power Forward"
                elif goals_ratio > 0.58:
                    p["role_calc"] = "Sniper"
                elif goals_ratio < 0.38:
                    p["role_calc"] = "Playmaker"
                else:
                    p["role_calc"] = "Two-Way"

        elif pos == "defense":
            pts_pg_vals  = [p["points"] / p["gamesPlayed"] for p in pp]
            hits_pg_vals = [p["hits"] / p["gamesPlayed"] for p in pp]

            for i, p in enumerate(pp):
                pts_pct  = percentile_rank(pts_pg_vals[i], pts_pg_vals)
                hits_pct = percentile_rank(hits_pg_vals[i], hits_pg_vals)

                if pts_pct >= 0.67:
                    p["role_calc"] = "Offensive"
                elif hits_pct >= 0.67 and pts_pct < 0.50:
                    p["role_calc"] = "Physical"
                else:
                    p["role_calc"] = "Two-Way"

    for p in players:
        if p["position"] == "goalie":
            p["role_calc"] = "Goalie"
        elif "role_calc" not in p:
            p["role_calc"] = "Two-Way"

    for team in data:
        for p in team["players"]:
            p.pop("_teamId", None)

    with open(path, "w") as f:
        json.dump(data, f)

print("Done — proj_* fields and scores written to all season files.")
