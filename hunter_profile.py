def ask_user_profile():
    print("\n" + "="*50)
    print("   BOUNTYMATCH — Personalized Target Finder")
    print("="*50)

    print("\n[Step 1] Experience Level")
    print("  1. Complete beginner (just started learning)")
    print("  2. Beginner (know basics, tried a few programs)")
    print("  3. Intermediate (found bugs before, some reports)")
    print("  4. Advanced (regular hunter, multiple valid reports)")
    print("  5. Expert (top-ranked, consistent earner)")
    exp_choice = input("\nEnter number (1-5): ").strip()
    experience_map = {
        "1": "complete_beginner",
        "2": "beginner",
        "3": "intermediate",
        "4": "advanced",
        "5": "expert"
    }
    experience = experience_map.get(exp_choice, "beginner")

    print("\n[Step 2] Testing Focus Areas")
    print("  Leave blank and press Enter to skip (means ANY)")
    print("  Options: web, api, mobile, ios, android, network, source_code")
    focus_input = input("  Your focus areas (comma separated, or press Enter to skip): ").strip().lower()
    if focus_input == "":
        focus_areas = []  # empty means any
    else:
        focus_areas = [f.strip() for f in focus_input.split(",")]

    print("\n[Step 3] Bounty Preference")
    print("  1. Paid bounties only")
    print("  2. VDP (no money) is okay too")
    print("  3. No preference")
    bounty_choice = input("Enter number (1-3): ").strip()
    bounty_map = {"1": "paid_only", "2": "vdp_ok", "3": "any"}
    bounty_pref = bounty_map.get(bounty_choice, "any")

    print("\n[Step 4] Region / Country Preference")
    print("  Examples: india, singapore, global, usa")
    print("  Press Enter to skip (means ANY country)")
    region = input("  Preferred country or Enter to skip: ").strip().lower()
    if region == "":
        region = "any"

    print("\n[Step 5] What matters most to you?")
    print("  1. I want the freshest/newest programs")
    print("  2. I want programs with least competition")
    print("  3. I want programs with best response/payout")
    print("  4. Balanced — mix of everything")
    priority_choice = input("Enter number (1-4): ").strip()
    priority_map = {
        "1": "freshness",
        "2": "low_competition",
        "3": "response_quality",
        "4": "balanced"
    }
    priority = priority_map.get(priority_choice, "balanced")

    print("\n[Step 6] Program Type")
    print("  1. Bug Bounty (paid)")
    print("  2. VDP only")
    print("  3. Both")
    type_choice = input("Enter number (1-3): ").strip()
    type_map = {"1": "bounty", "2": "vdp", "3": "both"}
    program_type = type_map.get(type_choice, "both")

    profile = {
        "experience": experience,
        "focus_areas": focus_areas,
        "bounty_pref": bounty_pref,
        "region": region,
        "priority": priority,
        "program_type": program_type
    }

    print("\n--- Your Profile Summary ---")
    print(f"  Experience   : {experience}")
    print(f"  Focus Areas  : {focus_areas if focus_areas else 'Any'}")
    print(f"  Bounty Pref  : {bounty_pref}")
    print(f"  Region       : {region}")
    print(f"  Priority     : {priority}")
    print(f"  Program Type : {program_type}")
    print("----------------------------\n")

    return profile