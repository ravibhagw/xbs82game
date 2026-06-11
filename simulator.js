const SCORE_CAP = 120;

// Slot weights — goalie and center touch every play
const SLOT_WEIGHTS = {
    g:  0.22,
    c:  0.20,
    w1: 0.13,
    w2: 0.13,
    d1: 0.16,
    d2: 0.16,
};

// Map slot keys to position names for validation
const SLOT_POSITIONS = {
    g:  "goalie",
    c:  "center",
    w1: "wing",
    w2: "wing",
    d1: "defense",
    d2: "defense",
};

function baseWinProbability(roster) {
    let total = 0;
    for (const [slot, weight] of Object.entries(SLOT_WEIGHTS)) {
        const p = roster[slot];
        if (!p) return 0; // incomplete roster
        // Normalize by 100 so scores above 100 contribute above baseline.
        // A 120-rated player gives 1.2x their slot weight — generational talent matters.
        total += (Math.min(p.score, SCORE_CAP) / 100) * weight;
    }
    return Math.min(total, 1.0);
}

function compositionModifier(roster) {
    const roles = {
        forwards: [roster.c, roster.w1, roster.w2].filter(Boolean),
        defense:  [roster.d1, roster.d2].filter(Boolean),
    };

    const fwdRoles   = roles.forwards.map(p => p.role_calc);
    const defRoles   = roles.defense.map(p => p.role_calc);

    const hasSniper       = fwdRoles.includes("Sniper");
    const hasPlaymaker    = fwdRoles.includes("Playmaker");
    const hasTwoWayFwd    = fwdRoles.includes("Two-Way");
    const hasPowerFwd     = fwdRoles.includes("Power Forward");
    const allSnipers      = fwdRoles.every(r => r === "Sniper");
    const noPlaymaker     = !hasPlaymaker && !hasTwoWayFwd;

    const hasOffensiveD   = defRoles.includes("Offensive");
    const hasNonOffensiveD = defRoles.some(r => r !== "Offensive");
    const bothOffensiveD  = defRoles.every(r => r === "Offensive");
    const bothPhysicalD   = defRoles.every(r => r === "Physical");

    let modifier = 0;

    // Rewards
    if (hasOffensiveD && hasNonOffensiveD)  modifier += 0.020; // ideal D pairing
    if (hasSniper && hasPlaymaker)           modifier += 0.020; // dynamic forward combo
    if (hasPowerFwd && !bothPhysicalD)       modifier += 0.010; // PF reduces need for physical D

    // Penalties
    if (allSnipers)                          modifier -= 0.040; // no puck movement
    if (noPlaymaker)                         modifier -= 0.020; // nobody to set up plays
    if (bothOffensiveD)                      modifier -= 0.030; // defensive vulnerability
    if (bothPhysicalD && !hasPowerFwd)       modifier -= 0.015; // no offensive punch from D
    if (hasPowerFwd && bothPhysicalD)        modifier -= 0.025; // too much muscle, not enough skill

    // Bad-player drag: escalating penalty for each player below the league p25 threshold.
    // 1 bad player: -2%, 2: -6%, 3: -12%, 4+: -20% total.
    const DRAG_THRESHOLD = 63;
    const DRAG_STEPS = [0.020, 0.040, 0.060, 0.080];
    const allSlotPlayers = Object.values(roster).filter(Boolean);
    const badCount = allSlotPlayers.filter(p => p.score < DRAG_THRESHOLD).length;
    for (let i = 0; i < badCount; i++) {
        modifier -= DRAG_STEPS[Math.min(i, DRAG_STEPS.length - 1)];
    }

    return modifier;
}

function simulateSeason(roster, games = 82) {
    const base     = baseWinProbability(roster);
    const modifier = compositionModifier(roster);
    const winProb  = Math.max(0, Math.min(1, base + modifier));

    // Per-game variance using Box-Muller normal distribution
    function randn() {
        let u = 0, v = 0;
        while (u === 0) u = Math.random();
        while (v === 0) v = Math.random();
        return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    }

    // Game-level noise: ~2% std dev so good teams can lose on a bad night
    const GAME_NOISE_STD = 0.020;

    let wins = 0;
    const gameLog = [];

    for (let g = 1; g <= games; g++) {
        const noise      = randn() * GAME_NOISE_STD;
        const gameProb   = Math.max(0, Math.min(1, winProb + noise));
        const won        = Math.random() < gameProb;
        if (won) wins++;
        gameLog.push({ game: g, won, winProb: +gameProb.toFixed(4) });
    }

    return {
        wins,
        losses: games - wins,
        record: `${wins}-${games - wins}`,
        winProbability: +winProb.toFixed(4),
        baseWinProbability: +base.toFixed(4),
        compositionModifier: +modifier.toFixed(4),
        perfect: wins === games,
        gameLog,
    };
}

function validateRoster(roster) {
    const errors = [];
    for (const [slot, expectedPos] of Object.entries(SLOT_POSITIONS)) {
        const p = roster[slot];
        if (!p) {
            errors.push(`Missing player in slot: ${slot}`);
        } else if (p.position !== expectedPos) {
            errors.push(`Slot ${slot} expects ${expectedPos}, got ${p.position} (${p.userName})`);
        }
    }
    return errors;
}

function projectWins(roster) {
    const errors = validateRoster(roster);
    if (errors.length) {
        return { error: errors };
    }
    return simulateSeason(roster);
}
