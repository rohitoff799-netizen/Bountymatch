import json

from explainer import format_result
from hunter_profile import ask_user_profile
from scorer import score_program


def load_programs():
    with open("sample_programs.json", "r", encoding="utf-8") as file:
        return json.load(file)


def group_programs(scored_programs):
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

    exact_matches.sort(key=lambda item: item[1].get("total", 0), reverse=True)
    partial_matches.sort(key=lambda item: item[1].get("total", 0), reverse=True)
    fallback_matches.sort(key=lambda item: item[1].get("total", 0), reverse=True)

    return exact_matches, partial_matches, fallback_matches


def print_section(title, items, limit=3):
    if not items:
        return

    print(f"\n{title}")
    for program, breakdown in items[:limit]:
        print(format_result(program, breakdown))


def main():
    profile = ask_user_profile()
    programs = load_programs()

    scored_programs = []
    for program in programs:
        breakdown = score_program(program, profile)
        scored_programs.append((program, breakdown))

    exact_matches, partial_matches, fallback_matches = group_programs(scored_programs)

    print("\n=== Top Program Recommendations For You ===")

    print_section("🎯 Best Available Matches:", exact_matches)
    print_section("🟡 Close Matches:", partial_matches)
    print_section("💡 Fallback Options:", fallback_matches)


if __name__ == "__main__":
    main()