from colorama import Fore, Style, init

init(autoreset=True)


def format_value(value, fallback="Unknown"):
    if value is None:
        return fallback
    if isinstance(value, str) and not value.strip():
        return fallback
    return value


def format_money(value, fallback="Unknown"):
    if value is None:
        return fallback
    try:
        return f"${int(value):,}"
    except (TypeError, ValueError):
        return fallback


def resolve_crowd_display(program):
    reports_received_90d = program.get("reports_received_90d")
    public_reports_90d = program.get("public_reports_90d")
    awarded_reports = program.get("awarded_reports")
    public_awarded_reports = program.get("public_awarded_reports")

    if reports_received_90d is not None:
        return reports_received_90d, "Platform reports (90d)"
    if public_reports_90d is not None:
        return public_reports_90d, "Public Hacktivity reports (90d)"
    if awarded_reports is not None:
        return awarded_reports, "Platform awarded reports"
    if public_awarded_reports is not None:
        return public_awarded_reports, "Public Hacktivity awarded reports"
    return None, "No crowd data"


def crowd_label(crowd_value, source_label="reports"):
    if crowd_value is None:
        return "Unknown"
    if crowd_value < 20:
        return f"Low ({crowd_value} via {source_label})"
    if crowd_value < 100:
        return f"Medium ({crowd_value} via {source_label})"
    return f"High ({crowd_value} via {source_label})"


def verdict_label(match_quality, data_confidence="high"):
    if match_quality == "fallback":
        return Fore.RED + "❌ Fallback option" + Style.RESET_ALL

    if data_confidence == "low":
        if match_quality == "exact":
            return Fore.LIGHTYELLOW_EX + "🟠 Low-confidence match" + Style.RESET_ALL
        return Fore.LIGHTYELLOW_EX + "🟠 Low-confidence option" + Style.RESET_ALL

    if data_confidence == "medium":
        if match_quality == "exact":
            return Fore.YELLOW + "🟡 Promising but incomplete" + Style.RESET_ALL
        return Fore.YELLOW + "🟡 Close match" + Style.RESET_ALL

    if match_quality == "exact":
        return Fore.GREEN + "🟢 Strong match" + Style.RESET_ALL

    return Fore.YELLOW + "🟡 Close match" + Style.RESET_ALL


def format_list(items, empty_message="None"):
    if not items:
        return f" - {empty_message}"
    return "\n".join(f" + {item}" for item in items)


def format_risks(items, neutral_notes=None):
    lines = []

    if items:
        lines.extend(f" - {item}" for item in items)
    else:
        lines.append(" - No major tradeoffs identified")

    if neutral_notes:
        lines.extend(f" • {note}" for note in neutral_notes)

    return "\n".join(lines)


def normalize_url(url):
    if not url:
        return None

    url = str(url).strip()

    if "](" in url and url.startswith("[") and url.endswith(")"):
        parts = url.split("](", 1)
        if len(parts) == 2:
            extracted = parts[1][:-1].strip()
            if extracted.startswith("http://") or extracted.startswith("https://"):
                return extracted

    return url


def format_severity_breakdown(severity_breakdown):
    if not severity_breakdown:
        return "Unknown"

    ordered = ["critical", "high", "medium", "low", "none", "unknown"]
    parts = []

    for key in ordered:
        value = severity_breakdown.get(key)
        if value:
            parts.append(f"{key}:{value}")

    return ", ".join(parts) if parts else "Unknown"


def format_result(program, breakdown):
    awarded_reporters = program.get("awarded_reporters")
    response_rate = program.get("response_rate")
    launched_days_ago = program.get("launched_days_ago")
    avg_response_days = program.get("avg_response_days")
    max_payout = program.get("max_payout")
    average_payout = program.get("average_payout")
    public_average_payout = program.get("public_average_payout")
    public_severity_breakdown = program.get("public_severity_breakdown")
    url = normalize_url(program.get("url"))

    crowd_value, crowd_source = resolve_crowd_display(program)

    match_quality = breakdown.get("match_quality", "fallback")
    data_confidence = breakdown.get("data_confidence", "high")

    lines = [
        "\n====================================================",
        f" Program : {format_value(program.get('name'))} ({format_value(program.get('platform'))})",
        f" Country : {format_value(program.get('country'))}",
        f" Score : {breakdown.get('total', 0)} / 100",
        f" Match Quality : {format_value(match_quality)}",
        f" Data Confidence : {format_value(data_confidence)}",
        f" Crowd Signal : {format_value(crowd_value)}",
        f" Crowd Source : {crowd_source}",
        f" Crowd Level : {crowd_label(crowd_value, crowd_source.lower())}",
        f" Awarded Reporters : {format_value(awarded_reporters)}",
        f" Response Rate : {format_value(f'{response_rate}%' if response_rate is not None else None)}",
        f" Avg Response Days : {format_value(avg_response_days)}",
        f" Launched Days Ago : {format_value(launched_days_ago)}",
        f" Max Payout : {format_money(max_payout)}",
        f" Average Payout : {format_money(average_payout)}",
        f" Public Avg Payout : {format_money(public_average_payout)}",
        f" Public Severity : {format_severity_breakdown(public_severity_breakdown)}",
        f" Verdict : {verdict_label(match_quality, data_confidence)}",
    ]

    if url:
        lines.append(f" URL : {url}")

    lines.extend(
        [
            "",
            " Why it may be good for you:",
            format_list(
                breakdown.get("reasons", []),
                empty_message="No strong positive reasons recorded",
            ),
            "",
            " Risks / tradeoffs:",
            format_risks(
                breakdown.get("risks", []),
                breakdown.get("neutral_notes", []),
            ),
            "====================================================",
        ]
    )

    return "\n".join(lines)