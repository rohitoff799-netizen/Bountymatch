def get_crowd_label(program):
    reports_received_90d = program.get("reports_received_90d")
    awarded_reports = program.get("awarded_reports", "N/A")

    if reports_received_90d is not None:
        if reports_received_90d <= 100:
            return f"Low ({reports_received_90d} reports received in last 90 days)"
        if reports_received_90d <= 300:
            return f"Moderate ({reports_received_90d} reports received in last 90 days)"
        return f"High ({reports_received_90d} reports received in last 90 days)"

    if awarded_reports == "N/A":
        return "Unknown"

    if awarded_reports <= 50:
        return f"Low ({awarded_reports} awarded reports)"
    if awarded_reports <= 200:
        return f"Moderate ({awarded_reports} awarded reports)"
    return f"High ({awarded_reports} awarded reports)"


def get_verdict(match_quality):
    if match_quality == "exact":
        return "✅ Best available match"
    if match_quality == "partial":
        return "🟡 Close match"
    return "❌ Fallback option"


def format_result(program, breakdown):
    lines = []

    raw_score = breakdown.get("total", 0)
    display_score = min(max(raw_score, 0), 100)

    name = program.get("name", "Unknown Program")
    platform = program.get("platform", "Unknown Platform")
    country = program.get("country", "Unknown")
    match_quality = breakdown.get("match_quality", "fallback")
    awarded_reports = program.get("awarded_reports", "N/A")
    awarded_reporters = program.get("awarded_reporters", "N/A")
    reports_received_90d = program.get("reports_received_90d")

    crowd_label = get_crowd_label(program)
    verdict = get_verdict(match_quality)

    lines.append("\n" + "=" * 52)
    lines.append(f"  Program       : {name} ({platform})")
    lines.append(f"  Country       : {country}")
    lines.append(f"  Score         : {display_score} / 100")
    lines.append(f"  Match Quality : {match_quality}")
    lines.append(f"  Awarded Reports     : {awarded_reports}")
    lines.append(f"  Awarded Reporters   : {awarded_reporters}")

    if reports_received_90d is not None:
        lines.append(f"  Reports Received 90d: {reports_received_90d}")
    else:
        lines.append("  Reports Received 90d: N/A")

    lines.append(f"  Crowd Level         : {crowd_label}")
    lines.append(f"  Verdict       : {verdict}")
    lines.append("")

    reasons_for = breakdown.get("reasons_for", [])
    reasons_against = breakdown.get("reasons_against", [])

    if reasons_for:
        lines.append("  Why it may be good for you:")
        for reason in reasons_for:
            lines.append(f"    + {reason}")

    if reasons_against:
        lines.append("")
        lines.append("  Risks / tradeoffs:")
        for reason in reasons_against:
            lines.append(f"    - {reason}")

    lines.append("=" * 52)
    return "\n".join(lines)