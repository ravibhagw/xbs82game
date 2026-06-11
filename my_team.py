#!/usr/bin/env python3
"""
Pick 6 players from the s48 roster and simulate an 82-game season.

Slots: g (goalie), c (center), w1 (wing), w2 (wing), d1 (defense), d2 (defense)
"""
import json, math, random, sys, os

STATS_FILE = os.path.join(os.path.dirname(__file__), "stats", "s48.json")
SCORE_CAP  = 120

SLOT_WEIGHTS = {"g": 0.22, "c": 0.20, "w1": 0.13, "w2": 0.13, "d1": 0.16, "d2": 0.16}
SLOT_POSITIONS = {"g": "goalie", "c": "center", "w1": "wing", "w2": "wing", "d1": "defense", "d2": "defense"}
SLOT_LABELS = {"g": "Goalie", "c": "Center", "w1": "Wing 1", "w2": "Wing 2", "d1": "Defense 1", "d2": "Defense 2"}


def load_players():
    with open(STATS_FILE) as f:
        data = json.load(f)
    players = [p for team in data for p in team["players"]]
    return sorted(players, key=lambda p: p["userName"].lower())


def find_player(name, players):
    """Case-insensitive substring match. Returns list of matches."""
    q = name.lower()
    return [p for p in players if q in p["userName"].lower()]


def list_by_position(players, position):
    pp = [p for p in players if p["position"] == position]
    return sorted(pp, key=lambda p: -p.get("score", 0))


def pick_player(slot, position, players, roster):
    taken = {p["userName"] for p in roster.values() if p}
    while True:
        print(f"\n── Slot: {SLOT_LABELS[slot]} ({position}) ──")
        query = input("  Search by name (or '?' to list all at position): ").strip()

        if query == "?":
            pp = list_by_position(players, position)
            for p in pp:
                flag = "  (taken)" if p["userName"] in taken else ""
                print(f"    {p['userName']:<30} score={p.get('score','?'):>5}  role={p.get('role_calc','?')}{flag}")
            continue

        matches = [p for p in find_player(query, players) if p["position"] == position]
        available = [p for p in matches if p["userName"] not in taken]

        if not matches:
            print(f"  No {position} found matching '{query}'. Try again.")
            continue
        if not available:
            print(f"  All matches are already on your roster. Try again.")
            continue
        if len(available) == 1:
            p = available[0]
            print(f"  → {p['userName']}  score={p.get('score','?')}  role={p.get('role_calc','?')}")
            confirm = input("  Add? [Y/n]: ").strip().lower()
            if confirm in ("", "y"):
                return p
        else:
            for i, p in enumerate(available):
                print(f"  [{i+1}] {p['userName']:<30} score={p.get('score','?'):>5}  role={p.get('role_calc','?')}")
            choice = input(f"  Pick 1-{len(available)} (or Enter to search again): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(available):
                return available[int(choice) - 1]


# ── Simulation (mirrors simulator.js logic) ──────────────────────────────────

def base_win_prob(roster):
    total = 0
    for slot, weight in SLOT_WEIGHTS.items():
        p = roster[slot]
        total += (min(p["score"], SCORE_CAP) / 100) * weight
    return min(total, 1.0)


def composition_modifier(roster):
    fwds = [roster["c"], roster["w1"], roster["w2"]]
    defs = [roster["d1"], roster["d2"]]
    fwd_roles = [p["role_calc"] for p in fwds]
    def_roles = [p["role_calc"] for p in defs]

    has_sniper     = "Sniper"       in fwd_roles
    has_playmaker  = "Playmaker"    in fwd_roles
    has_twoway_fwd = "Two-Way"      in fwd_roles
    has_power_fwd  = "Power Forward" in fwd_roles
    all_snipers    = all(r == "Sniper" for r in fwd_roles)
    no_playmaker   = not has_playmaker and not has_twoway_fwd

    has_offensive_d     = "Offensive" in def_roles
    has_non_offensive_d = any(r != "Offensive" for r in def_roles)
    both_offensive_d    = all(r == "Offensive" for r in def_roles)
    both_physical_d     = all(r == "Physical"  for r in def_roles)

    mod = 0
    if has_offensive_d and has_non_offensive_d: mod += 0.020
    if has_sniper and has_playmaker:             mod += 0.020
    if has_power_fwd and not both_physical_d:    mod += 0.010
    if all_snipers:                              mod -= 0.040
    if no_playmaker:                             mod -= 0.020
    if both_offensive_d:                         mod -= 0.030
    if both_physical_d and not has_power_fwd:    mod -= 0.015
    if has_power_fwd and both_physical_d:        mod -= 0.025
    return mod


def randn():
    u, v = 0, 0
    while u == 0: u = random.random()
    while v == 0: v = random.random()
    return math.sqrt(-2.0 * math.log(u)) * math.cos(2.0 * math.pi * v)


def simulate_season(roster, games=82, runs=500):
    base = base_win_prob(roster)
    mod  = composition_modifier(roster)
    win_prob = max(0, min(1, base + mod))

    all_wins = []
    for _ in range(runs):
        wins = sum(1 for _ in range(games) if random.random() < max(0, min(1, win_prob + randn() * 0.020)))
        all_wins.append(wins)

    avg_wins = sum(all_wins) / runs
    best  = max(all_wins)
    worst = min(all_wins)
    p10   = sorted(all_wins)[int(runs * 0.10)]
    p90   = sorted(all_wins)[int(runs * 0.90)]

    return {
        "win_probability": round(win_prob, 4),
        "base_win_prob":   round(base, 4),
        "composition_mod": round(mod, 4),
        "avg_wins":        round(avg_wins, 1),
        "avg_losses":      round(games - avg_wins, 1),
        "best":            best,
        "worst":           worst,
        "p10_wins":        p10,
        "p90_wins":        p90,
        "runs":            runs,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    players = load_players()
    print(f"\nLoaded {len(players)} players from s48.\n")
    print("Build your 6-player roster. Search by partial name, '?' to list all at position.\n")

    slots = ["g", "c", "w1", "w2", "d1", "d2"]
    roster = {s: None for s in slots}

    for slot in slots:
        pos = SLOT_POSITIONS[slot]
        roster[slot] = pick_player(slot, pos, players, roster)

    # Print roster summary
    print("\n" + "═" * 52)
    print("  YOUR ROSTER")
    print("═" * 52)
    for slot in slots:
        p = roster[slot]
        print(f"  {SLOT_LABELS[slot]:<12} {p['userName']:<28} score={p.get('score','?'):>5}  role={p.get('role_calc','?')}")

    print("\nSimulating 500 seasons...", end="", flush=True)
    results = simulate_season(roster)
    print(" done.\n")

    print("═" * 52)
    print("  SEASON PROJECTION  (82 games, 500 runs)")
    print("═" * 52)
    print(f"  Win probability per game : {results['win_probability']:.1%}")
    print(f"    Base probability       : {results['base_win_prob']:.1%}")
    print(f"    Composition modifier   : {results['composition_mod']:+.1%}")
    print(f"  Projected record         : {results['avg_wins']:.0f}W – {results['avg_losses']:.0f}L")
    print(f"  Range (10th–90th pct)   : {results['p10_wins']}W – {results['p90_wins']}W")
    print(f"  Best season              : {results['best']}W")
    print(f"  Worst season             : {results['worst']}W")
    print("═" * 52)

    # Composition notes
    mod = results["composition_mod"]
    if mod > 0:
        print(f"\n  Roster synergy: +{mod:.1%} bonus from good role balance.")
    elif mod < 0:
        print(f"\n  Roster warning: {mod:.1%} penalty from role imbalances.")
    else:
        print("\n  Roster is neutral (no composition bonus or penalty).")


if __name__ == "__main__":
    main()
