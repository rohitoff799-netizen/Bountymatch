import argparse
import json
import os

from explainer import format_result
from hunter_profile import ask_user_profile
from scorer import (
    score_program,
    resolve_crowd_value,
    resolve_payout_value,
    resolve_awarded_reporters,
)

REAL_DATA_FILE = os.path.join("data", "programs.json")
SAMPLE_DATA_FILE = "sample_programs.json"
RESULTS_FILE = "results.json"


def load_programs():
    if os.path.exists(REAL_DATA_FILE):
        data_file = REAL_DATA_FILE
        source_label = "cached dataset"
    else:
        data_file = SAMPLE_DATA_FILE
        source_label = "sample dataset"
        print("\nNo cached dataset found.")
        print("Using sample data instead.")
        print("Project maintainers can generate a fresh cache with fetch_programs.py.")

    with open(data_file, "r", encoding="utf-8") as file:
        programs = json.load(file)

    print(f"\nLoaded {len(programs)} programs from: {data_file} ({source_label})")
    return programs


def has_priority_evidence(program, priority):
    launched_days_ago = program.get("launched_days_ago")
    response_rate = program.get("response_rate")

    crowd_value = resolve_crowd_value(program)
    payout_value = resolve_payout_value(program)
    awarded_reporters = resolve_awarded_reporters(program)

    if priority == "freshness":
        return launched_days_ago is not None

    if priority == "low_competition":
        return crowd_value is not None or awarded_reporters is not None

    if priority == "response_quality":
        return response_rate is not None or payout_value is not None

    if priority == "balanced":
        signals = [
            launched_days_ago,
            response_rate,
            crowd_value,
            payout_value,
            awarded_reporters,
        ]
        return sum(value is not None for value in signals) >= 2

    return False


def is_hard_match(program, profile, breakdown):
    selected_focus = profile.get("focus_areas", [])
    preferred_country = str(profile.get("region", "any")).strip().lower()
    bounty_pref = profile.get("bounty_pref")
    selected_program_type = profile.get("program_type")

    program_scopes = program.get("scope_types", [])
    program_country = str(program.get("country", "global")).strip().lower()
    offers_bounty = bool(program.get("offers_bounty"))

    scope_ok = True
    if selected_focus:
        overlap = set(selected_focus) & set(program_scopes)
        scope_ok = bool(overlap)

    region_ok = (
        preferred_country == "any"
        or program_country == preferred_country
        or program_country == "global"
    )

    bounty_ok = True
    if bounty_pref == "paid_only":
        bounty_ok = offers_bounty

    program_type_ok = True
    if selected_program_type == "bounty":
        program_type_ok = offers_bounty
    elif selected_program_type == "vdp":
        program_type_ok = not offers_bounty

    match_quality = breakdown.get("match_quality", "fallback")
    return scope_ok and region_ok and bounty_ok and program_type_ok and match_quality != "fallback"


def sort_key(item, priority):
    program, breakdown = item

    evidence_present = has_priority_evidence(program, priority)
    data_confidence = breakdown.get("data_confidence", "high")
    total_score = breakdown.get("total", 0)
    match_quality = breakdown.get("match_quality", "fallback")

    confidence_rank = {
        "high": 2,
        "medium": 1,
        "low": 0,
    }.get(data_confidence, 0)

    match_rank = {
        "exact": 2,
        "partial": 1,
        "fallback": 0,
    }.get(match_quality, 0)

    if priority == "freshness":
        launched_days_ago = program.get("launched_days_ago")
        has_age = 1 if launched_days_ago is not None else 0
        freshness_rank = -launched_days_ago if launched_days_ago is not None else -999_999

        return (
            1 if evidence_present else 0,
            has_age,
            freshness_rank,
            confidence_rank,
            total_score,
            match_rank,
        )

    return (
        1 if evidence_present else 0,
        confidence_rank,
        total_score,
        match_rank,
    )


def group_programs(scored_programs, priority, profile):
    if priority == "freshness":
        eligible_matches = []
        ineligible_matches = []

        for item in scored_programs:
            program, breakdown = item
            if is_hard_match(program, profile, breakdown):
                eligible_matches.append(item)
            else:
                ineligible_matches.append(item)

        eligible_matches.sort(key=lambda item: sort_key(item, priority), reverse=True)
        ineligible_matches.sort(key=lambda item: sort_key(item, priority), reverse=True)

        return eligible_matches, ineligible_matches, []

    exact_matches = []
    partial_matches = []
    fallback_matches = []

    for program, breakdown in scored_programs:
        match_quality = breakdown.get("match_quality", "fallback")

        if match_quality == "exact":
            exact_matches.append((program, breakdown))
        elif match_quality == "partial":
            partial_matches.append((program, breakdown))
        else:
            fallback_matches.append((program, breakdown))

    exact_matches.sort(key=lambda item: sort_key(item, priority), reverse=True)
    partial_matches.sort(key=lambda item: sort_key(item, priority), reverse=True)
    fallback_matches.sort(key=lambda item: sort_key(item, priority), reverse=True)

    return exact_matches, partial_matches, fallback_matches


def print_low_confidence_warning(items, priority, limit=3):
    if not items:
        return

    top_items = items[:limit]
    low_conf_count = sum(
        1 for _, breakdown in top_items
        if breakdown.get("data_confidence", "high") == "low"
    )

    no_evidence_count = sum(
        1 for program, _ in top_items
        if not has_priority_evidence(program, priority)
    )

    if low_conf_count == len(top_items):
        print("\n⚠ Note: Top matches are based on limited platform metadata.")

    if no_evidence_count == len(top_items):
        if priority == "freshness":
            print("⚠ Freshness ranking is limited because launch-date data is missing for the top results.")
        elif priority == "low_competition":
            print("⚠ Competition ranking is limited because crowd/reporter data is missing for the top results.")
        elif priority == "response_quality":
            print("⚠ Response-quality ranking is limited because response or payout data is missing for the top results.")
        elif priority == "balanced":
            print("⚠ Balanced ranking is limited because too few scoring signals are available for the top results.")


def print_section(title, items, limit=3):
    if not items:
        return

    print(f"\n{title}")
    for program, breakdown in items[:limit]:
        print(format_result(program, breakdown))


def print_empty_message(exact_matches, partial_matches, fallback_matches):
    if exact_matches or partial_matches or fallback_matches:
        return

    print("\nNo programs could be ranked from the available dataset.")


def serialize_match_items(items, limit=None):
    selected_items = items if limit is None else items[:limit]
    output = []

    for program, breakdown in selected_items:
        output.append(
            {
                "program": program,
                "breakdown": breakdown,
            }
        )

    return output


def save_results(profile, exact_matches, partial_matches, fallback_matches, file_path=RESULTS_FILE):
    output = {
        "profile": profile,
        "exact_matches": serialize_match_items(exact_matches),
        "partial_matches": serialize_match_items(partial_matches),
        "fallback_matches": serialize_match_items(fallback_matches),
    }

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {file_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Bountymatch — Personalized bug bounty target finder"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save recommendations to results.json",
    )
    args = parser.parse_args()

    profile = ask_user_profile()
    programs = load_programs()
    priority = profile.get("priority", "balanced")

    scored_programs = []
    for program in programs:
        breakdown = score_program(program, profile)
        scored_programs.append((program, breakdown))

    exact_matches, partial_matches, fallback_matches = group_programs(
        scored_programs,
        priority,
        profile,
    )

    print("\n=== Top Program Recommendations For You ===")

    if priority == "freshness":
        print_low_confidence_warning(exact_matches, priority)
        print_section("🔥 Freshest Eligible Programs First:", exact_matches)
        print_section("🟡 Other Fresh Programs (hard mismatches):", partial_matches)
        print_empty_message(exact_matches, partial_matches, fallback_matches)
    else:
        print_low_confidence_warning(exact_matches, priority)
        print_section("🎯 Best Available Matches:", exact_matches)
        print_section("🟡 Close Matches:", partial_matches)
        print_section("💡 Fallback Options:", fallback_matches)
        print_empty_message(exact_matches, partial_matches, fallback_matches)

    if args.save:
        save_results(profile, exact_matches, partial_matches, fallback_matches)


if __name__ == "__main__":
    main()