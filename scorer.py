def get_weights(profile):
    priority = profile.get("priority", "balanced")

    weight_map = {
        "freshness": {
            "freshness": 30,
            "competition": 15,
            "response": 15,
            "scope": 15,
            "bounty": 15,
            "region": 10,
        },
        "low_competition": {
            "freshness": 15,
            "competition": 30,
            "response": 15,
            "scope": 15,
            "bounty": 15,
            "region": 10,
        },
        "response_quality": {
            "freshness": 10,
            "competition": 15,
            "response": 30,
            "scope": 20,
            "bounty": 15,
            "region": 10,
        },
        "balanced": {
            "freshness": 20,
            "competition": 20,
            "response": 15,
            "scope": 15,
            "bounty": 20,
            "region": 10,
        },
    }

    return weight_map.get(priority, weight_map["balanced"])


def get_crowd_metrics(program):
    reports_90d = program.get("reports_received_90d")
    awarded_reports = program.get("awarded_reports", 0)

    if reports_90d is not None:
        return {
            "source": "reports_received_90d",
            "value": reports_90d,
        }

    return {
        "source": "awarded_reports",
        "value": awarded_reports,
    }


def score_program(program, profile):
    try:
        weights = get_weights(profile)
        score = 0
        reasons_for = []
        reasons_against = []

        region_pref = profile.get("region", "any").lower()
        focus_areas = [area.lower() for area in profile.get("focus_areas", [])]
        bounty_pref = profile.get("bounty_pref", "any")
        program_type = profile.get("program_type", "both")

        program_country = program.get("country", "global").lower()
        scope = [item.lower() for item in program.get("scope_types", [])]
        offers_bounty = program.get("offers_bounty", False)
        launched_days_ago = program.get("launched_days_ago", 9999)
        response_rate = program.get("response_rate", 0)

        hard_mismatch = False
        partial_filter = False

        if region_pref != "any":
            if program_country == region_pref:
                score += weights["region"] + 20
                reasons_for.append(f"Exact region match ({program.get('country', 'Unknown')})")
            elif program_country == "global":
                score += int(weights["region"] * 0.5)
                reasons_for.append("Global program — accessible in your region")
                partial_filter = True
            else:
                score -= 25
                reasons_against.append(
                    f"Outside your preferred region ({program.get('country', 'Unknown')})"
                )
                hard_mismatch = True
        else:
            score += int(weights["region"] * 0.5)

        if not focus_areas:
            score += weights["scope"]
            reasons_for.append("Scope accepted (no focus filter applied — showing all)")
        else:
            matched_focus = [area for area in focus_areas if area in scope]

            if len(matched_focus) == len(focus_areas):
                score += weights["scope"] + 10
                reasons_for.append(f"Full scope match: {', '.join(matched_focus)}")
            elif matched_focus:
                score += int(weights["scope"] * 0.5)
                reasons_for.append(f"Partial scope match: {', '.join(matched_focus)}")
                missing_focus = [area for area in focus_areas if area not in scope]
                reasons_against.append(f"Scope missing: {', '.join(missing_focus)}")
                partial_filter = True
            else:
                score -= 20
                reasons_against.append(
                    f"Scope does not match your focus ({', '.join(focus_areas)})"
                )
                hard_mismatch = True

        if bounty_pref == "paid_only":
            if offers_bounty:
                score += weights["bounty"] + 10
                reasons_for.append("Offers paid bounties (exact match)")
            else:
                score -= 20
                reasons_against.append("VDP only — no paid bounties (you want paid programs)")
                hard_mismatch = True
        elif bounty_pref == "vdp_ok":
            score += weights["bounty"]
            reasons_for.append("Bounty preference satisfied")
        else:
            score += int(weights["bounty"] * 0.5)

        if program_type == "bounty":
            if offers_bounty:
                reasons_for.append("Matches selected program type: bug bounty")
            else:
                score -= 15
                reasons_against.append("Program type mismatch — you wanted bug bounty only")
                hard_mismatch = True
        elif program_type == "vdp":
            if not offers_bounty:
                reasons_for.append("Matches selected program type: VDP")
            else:
                score -= 15
                reasons_against.append("Program type mismatch — you wanted VDP only")
                hard_mismatch = True

        if launched_days_ago <= 60:
            score += weights["freshness"]
            reasons_for.append(f"Newer program (launched {launched_days_ago} days ago)")
        elif launched_days_ago <= 365:
            score += int(weights["freshness"] * 0.5)
            reasons_for.append(
                f"Moderately fresh (launched {launched_days_ago} days ago)"
            )
        else:
            score -= 5
            reasons_against.append(f"Older program (launched {launched_days_ago} days ago)")

        crowd = get_crowd_metrics(program)
        crowd_value = crowd["value"]
        crowd_source = crowd["source"]

        if crowd_source == "reports_received_90d":
            if crowd_value <= 100:
                score += weights["competition"]
                reasons_for.append(
                    f"Low crowd — only {crowd_value} reports received in last 90 days"
                )
            elif crowd_value <= 300:
                score += int(weights["competition"] * 0.5)
                reasons_for.append(
                    f"Moderate crowd — {crowd_value} reports received in last 90 days"
                )
            else:
                score -= 10
                reasons_against.append(
                    f"High crowd — {crowd_value} reports received in last 90 days"
                )
        else:
            if crowd_value <= 50:
                score += weights["competition"]
                reasons_for.append(
                    f"Low competition — only {crowd_value} awarded reports"
                )
            elif crowd_value <= 200:
                score += int(weights["competition"] * 0.5)
                reasons_for.append(
                    f"Moderate competition — {crowd_value} awarded reports"
                )
            else:
                score -= 10
                reasons_against.append(
                    f"High competition — {crowd_value} awarded reports"
                )

        if response_rate >= 90:
            score += weights["response"]
            reasons_for.append(f"Strong response rate ({response_rate}%)")
        elif response_rate >= 75:
            score += int(weights["response"] * 0.6)
            reasons_for.append(f"Decent response rate ({response_rate}%)")
        else:
            score -= 5
            reasons_against.append(f"Weak response rate ({response_rate}%)")

        if hard_mismatch:
            match_quality = "fallback"
            tier = 3
        elif partial_filter:
            match_quality = "partial"
            tier = 2
        else:
            match_quality = "exact"
            tier = 1

        return {
            "total": score,
            "tier": tier,
            "match_quality": match_quality,
            "reasons_for": reasons_for,
            "reasons_against": reasons_against,
        }

    except Exception as error:
        return {
            "total": 0,
            "tier": 3,
            "match_quality": "fallback",
            "reasons_for": [],
            "reasons_against": [f"Scoring error: {str(error)}"],
        }