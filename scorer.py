def count_present(*values):
    return sum(value is not None for value in values)


def resolve_crowd_value(program):
    """
    Best available crowd signal, in priority order:
    1. reports_received_90d (from platform API, rare)
    2. public_reports_90d (from Hacktivity API, most common)
    3. awarded_reports (from platform API, rare)
    4. public_awarded_reports (from Hacktivity API, fallback)
    """
    return (
        program.get("reports_received_90d")
        or program.get("public_reports_90d")
        or program.get("awarded_reports")
        or program.get("public_awarded_reports")
    )


def resolve_payout_value(program):
    """
    Best available payout signal, in priority order:
    1. max_payout (from Bugcrowd/Intigriti)
    2. average_payout (from Intigriti min/max average)
    3. public_average_payout (from Hacktivity disclosed reports)
    """
    return (
        program.get("max_payout")
        or program.get("average_payout")
        or program.get("public_average_payout")
    )


def resolve_awarded_reporters(program):
    """
    Best available reporter pool signal.
    awarded_reporters is rarely populated from arkadiyt data,
    but kept for forward compatibility if H1 API exposes it later.
    """
    return program.get("awarded_reporters")


def score_program(program, profile):
    score = 0
    reasons = []
    risks = []
    neutral_notes = []

    selected_focus = profile.get("focus_areas", [])
    program_scopes = program.get("scope_types", [])

    preferred_country = str(profile.get("region", "any")).strip().lower()
    program_country = str(program.get("country", "global")).strip().lower()

    bounty_pref = profile.get("bounty_pref")
    priority = profile.get("priority")
    selected_program_type = profile.get("program_type")
    experience = profile.get("experience", "beginner")

    crowd_tolerance = {
        "complete_beginner": 20,
        "beginner": 50,
        "intermediate": 150,
        "advanced": 300,
        "expert": 99999,
    }
    max_crowd = crowd_tolerance.get(experience, 50)

    exact_scope_match = False
    partial_scope_match = False
    region_match = False
    bounty_match = False
    program_type_match = False

    # --- Scope matching ---
    if not selected_focus:
        score += 15
        reasons.append("No focus area selected — open to any scope")
        exact_scope_match = True
    else:
        overlap = set(selected_focus) & set(program_scopes)
        if overlap:
            if set(selected_focus).issubset(set(program_scopes)):
                score += 20
                reasons.append(f"Full scope match: {', '.join(sorted(overlap))}")
                exact_scope_match = True
            else:
                score += 10
                reasons.append(f"Partial scope match: {', '.join(sorted(overlap))}")
                partial_scope_match = True
        else:
            risks.append("Does not match your selected testing focus")

    # --- Region matching ---
    if preferred_country == "any":
        score += 10
        reasons.append("No region restriction selected")
        region_match = True
    else:
        if program_country == preferred_country:
            score += 15
            reasons.append(f"Exact region match: {program_country}")
            region_match = True
        elif program_country == "global":
            score += 10
            reasons.append("Global program — accessible in your region")
            region_match = True
        else:
            risks.append(f"Outside your preferred region ({program_country})")

    # --- Bounty preference ---
    if bounty_pref == "paid_only":
        if program.get("offers_bounty"):
            score += 20
            reasons.append("Offers paid bounties (exact match)")
            bounty_match = True
        else:
            risks.append("No bounty payout")
    elif bounty_pref == "vdp_ok":
        if program.get("offers_bounty"):
            score += 15
            reasons.append("Paid program accepted")
        else:
            score += 10
            reasons.append("VDP accepted by your preference")
        bounty_match = True
    else:
        score += 10
        reasons.append("No bounty preference restriction")
        bounty_match = True

    # --- Program type ---
    if selected_program_type == "bounty":
        if program.get("offers_bounty"):
            score += 10
            reasons.append("Matches selected program type: bug bounty")
            program_type_match = True
        else:
            risks.append("Not a paid bug bounty program")
    elif selected_program_type == "vdp":
        if not program.get("offers_bounty"):
            score += 10
            reasons.append("Matches selected program type: VDP")
            program_type_match = True
        else:
            risks.append("Not a VDP-only program")
    else:
        score += 5
        reasons.append("Open to both bounty and VDP programs")
        program_type_match = True

    launched_days_ago = program.get("launched_days_ago")
    response_rate = program.get("response_rate")
    avg_response_days = program.get("avg_response_days")

    crowd_value = resolve_crowd_value(program)

    payout_value = resolve_payout_value(program)
    max_payout = program.get("max_payout")
    average_payout = program.get("average_payout") or program.get("public_average_payout")

    awarded_reporters = resolve_awarded_reporters(program)

    severity_breakdown = program.get("public_severity_breakdown") or {}
    has_critical = severity_breakdown.get("critical", 0) > 0
    has_high = severity_breakdown.get("high", 0) > 0

    # --- Priority-based scoring ---
    if priority == "freshness":
        if launched_days_ago is not None:
            if launched_days_ago <= 30:
                score += 30
                reasons.append(f"Very fresh program ({launched_days_ago} days old)")
            elif launched_days_ago <= 90:
                score += 22
                reasons.append(f"Fresh program ({launched_days_ago} days old)")
            elif launched_days_ago <= 180:
                score += 12
                reasons.append(f"Relatively fresh program ({launched_days_ago} days old)")
            elif launched_days_ago <= 365:
                score += 2
                neutral_notes.append(f"Not very new ({launched_days_ago} days old)")
            elif launched_days_ago <= 730:
                score -= 10
                risks.append(f"Old for a freshness-first search ({launched_days_ago} days old)")
            else:
                score -= 25
                risks.append(
                    f"Too old for a freshness-first search ({launched_days_ago} days old)"
                )
        else:
            score -= 12
            risks.append("Missing launch-date data for freshness ranking")

        if crowd_value is not None:
            if crowd_value <= max_crowd:
                score += 2
                reasons.append(
                    f"Competition suits your level ({crowd_value} public reports in 90d)"
                )
            elif crowd_value > max_crowd * 2:
                score -= 3
                risks.append(
                    f"Crowded for your experience ({crowd_value} public reports in 90d)"
                )
            else:
                neutral_notes.append(
                    f"Competition moderate for your level ({crowd_value} public reports in 90d)"
                )
        else:
            neutral_notes.append("Competition data unavailable")

        freshness_signal_count = count_present(launched_days_ago, crowd_value)
        if freshness_signal_count == 0:
            score -= 8
            risks.append("Too little freshness data to rank confidently")

    elif priority == "low_competition":
        if crowd_value is not None:
            if crowd_value <= max_crowd:
                score += 20
                reasons.append(
                    f"Competition suits your level ({crowd_value} public reports in 90d)"
                )
            elif crowd_value <= max_crowd * 2:
                score += 8
                neutral_notes.append(
                    f"Competition manageable but slightly high ({crowd_value} public reports in 90d)"
                )
            else:
                score -= 10
                risks.append(
                    f"Too crowded for your experience ({crowd_value} public reports in 90d)"
                )
        else:
            score -= 8
            neutral_notes.append("Competition data unavailable")

        if awarded_reporters is not None:
            if awarded_reporters <= 25:
                score += 5
                reasons.append(f"Smaller active hunter pool ({awarded_reporters} reporters)")
            elif awarded_reporters >= 150:
                score -= 3
                risks.append(f"Large active hunter pool ({awarded_reporters} reporters)")
        else:
            neutral_notes.append("Reporter-count data unavailable")

        competition_signal_count = count_present(crowd_value, awarded_reporters)
        if competition_signal_count == 0:
            score -= 15
            risks.append("Too little competition data to rank confidently")
        elif competition_signal_count == 1:
            score -= 6
            neutral_notes.append("Limited competition data available")

    elif priority == "response_quality":
        if response_rate is not None:
            if response_rate >= 95:
                score += 20
                reasons.append(f"Excellent response rate ({response_rate}%)")
            elif response_rate >= 90:
                score += 15
                reasons.append(f"Strong response rate ({response_rate}%)")
            elif response_rate >= 70:
                score += 8
                reasons.append(f"Decent response rate ({response_rate}%)")
            else:
                risks.append(f"Weak response rate ({response_rate}%)")
        else:
            score -= 10
            neutral_notes.append("Response-rate data unavailable")

        if avg_response_days is not None:
            if avg_response_days <= 3:
                score += 5
                reasons.append(f"Very fast triage ({avg_response_days} day avg response)")
            elif avg_response_days <= 7:
                score += 3
                reasons.append(f"Fast triage ({avg_response_days} day avg response)")
            elif avg_response_days >= 30:
                score -= 3
                risks.append(f"Slow triage ({avg_response_days} day avg response)")

        if max_payout is not None:
            if max_payout >= 5000:
                score += 10
                reasons.append(f"High max payout (${max_payout:,})")
            elif max_payout >= 1000:
                score += 5
                reasons.append(f"Reasonable max payout (${max_payout:,})")
        elif average_payout is not None:
            if average_payout >= 500:
                score += 5
                reasons.append(f"Solid average payout (${average_payout:,})")
            elif average_payout < 100:
                score -= 2
                risks.append(f"Low average payout (${average_payout:,})")
        else:
            score -= 4
            neutral_notes.append("Payout data unavailable")

        response_signal_count = count_present(response_rate, payout_value)
        if response_signal_count == 0:
            score -= 15
            risks.append("Too little response-quality data to rank confidently")
        elif response_signal_count == 1 and response_rate is None:
            score -= 8
            risks.append("Missing response-rate data for response-quality ranking")
        elif response_signal_count == 1:
            score -= 5
            neutral_notes.append("Limited response-quality data available")

    else:  # balanced
        if launched_days_ago is not None:
            if launched_days_ago <= 90:
                score += 8
                reasons.append(f"Fresh program ({launched_days_ago} days old)")
            elif launched_days_ago <= 180:
                score += 4
                reasons.append(f"Relatively fresh program ({launched_days_ago} days old)")
            else:
                neutral_notes.append(f"Older program ({launched_days_ago} days old)")
        else:
            neutral_notes.append("Freshness data unavailable")

        if response_rate is not None:
            if response_rate >= 90:
                score += 8
                reasons.append(f"Strong response rate ({response_rate}%)")
            elif response_rate >= 70:
                score += 4
                reasons.append(f"Decent response rate ({response_rate}%)")
            else:
                risks.append(f"Weak response rate ({response_rate}%)")
        else:
            neutral_notes.append("Response-rate data unavailable")

        if crowd_value is not None:
            if crowd_value <= max_crowd:
                score += 8
                reasons.append(
                    f"Competition suits your level ({crowd_value} public reports in 90d)"
                )
            elif crowd_value > max_crowd * 2:
                score -= 5
                risks.append(
                    f"Crowded for your experience ({crowd_value} public reports in 90d)"
                )
            else:
                neutral_notes.append(
                    f"Competition moderate for your level ({crowd_value} public reports in 90d)"
                )
        else:
            neutral_notes.append("Competition data unavailable")

        if max_payout is not None:
            if max_payout >= 5000:
                score += 6
                reasons.append(f"High max payout (${max_payout:,})")
            elif max_payout >= 1000:
                score += 3
                reasons.append(f"Reasonable max payout (${max_payout:,})")
        elif average_payout is not None and average_payout >= 250:
            score += 3
            reasons.append(f"Solid payout floor (${average_payout:,})")
        else:
            neutral_notes.append("Payout data unavailable")

        balanced_signal_count = count_present(
            launched_days_ago,
            response_rate,
            crowd_value,
            payout_value,
        )

        if balanced_signal_count <= 1:
            score -= 15
            risks.append("Too little program data to rank confidently")
        elif balanced_signal_count == 2:
            score -= 8
            neutral_notes.append("Limited program data available")
        elif balanced_signal_count == 3:
            score -= 3

    # --- Severity bonus (from Hacktivity public data) ---
    if has_critical and priority in ("low_competition", "balanced"):
        score += 3
        neutral_notes.append("Critical-severity bugs confirmed publicly in this program")
    elif has_high and priority in ("low_competition", "balanced"):
        score += 1
        neutral_notes.append("High-severity bugs confirmed publicly in this program")

    # --- Data confidence ---
    overall_signal_count = count_present(
        launched_days_ago,
        response_rate,
        crowd_value,
        payout_value,
        awarded_reporters,
    )

    data_confidence = "high"
    if overall_signal_count <= 1:
        data_confidence = "low"
    elif overall_signal_count <= 3:
        data_confidence = "medium"

    # --- Match quality ---
    scope_ok = exact_scope_match or partial_scope_match
    hard_match_count = sum([scope_ok, region_match, bounty_match, program_type_match])

    if scope_ok and region_match and bounty_match and program_type_match:
        match_quality = "exact"
    elif hard_match_count >= 2:
        match_quality = "partial"
    else:
        match_quality = "fallback"

    return {
        "total": max(0, min(score, 100)),
        "match_quality": match_quality,
        "data_confidence": data_confidence,
        "reasons": reasons,
        "risks": risks,
        "neutral_notes": neutral_notes,
    }