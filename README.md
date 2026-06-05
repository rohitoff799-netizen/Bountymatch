# Bountymatch

Bountymatch is a Python CLI tool that helps bug bounty hunters find programs that fit their preferences. It asks for your region, focus areas, bounty preference, program type, and ranking priority, then groups programs into exact, partial, and fallback matches before ranking them by score inside each group.

## What it does

Bountymatch is designed to solve a simple problem: most hunters do not want a random list of programs, they want a shortlist that matches how they actually hunt.

The current logic uses filters to decide match quality and weighted scoring to rank programs within each bucket, which makes the output easier to trust and understand.

### Current matching logic

- **Exact match**: the program satisfies the selected filters.
- **Partial match**: the program is close, such as a global program instead of an exact country match.
- **Fallback**: the program has at least one hard mismatch, such as the wrong region or no paid bounty when paid-only is selected.
- **Score**: used only to rank programs inside exact, partial, and fallback groups, not to decide the group itself.

## Features

- Interactive CLI profile flow.
- Personalized recommendations based on user preferences.
- Weighted scoring for freshness, competition, response quality, scope, bounty preference, and region.
- Clear reasoning output with strengths and tradeoffs for each program.
- Grouped results: exact, partial, and fallback matches.
- Display score capped to 0–100 for cleaner output while preserving the raw score for internal ranking.

## Project structure

```text
Bountymatch/
├── main.py
├── scorer.py
├── explainer.py
├── hunter_profile.py
├── sample_programs.json
├── README.md
└── requirements.txt
```

As the project grows, this structure will make it easier to add fetchers, cached data, and platform-specific normalization.

## How ranking works

Bountymatch separates **filter satisfaction** from **ranking strength**:

1. User filters determine whether a program is exact, partial, or fallback.
2. Weighted scoring then sorts programs inside those groups.
3. The output explains why each program appears where it does.

This keeps the recommendation system easier to reason about and debug.

## Getting started

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Bountymatch
```

### 2. Create a virtual environment

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

No external Python packages are required for the current CLI version.

The project currently uses only Python standard library modules, so this step is optional for now.

If you still want to keep the normal workflow:

```bash
pip install -r requirements.txt
```

### 4. Run the project

```bash
python main.py
```

## requirements.txt

For the current version, your `requirements.txt` can contain:

```txt
# No external dependencies required for the current CLI version.
# Uses only Python standard library modules.
```

## Sample flow

```text
[Step 1] Experience Level
[Step 2] Testing Focus Areas
[Step 3] Bounty Preference
[Step 4] Region / Country Preference
[Step 5] What matters most to you?
[Step 6] Program Type
```

After answering the prompts, Bountymatch prints the best available matches first, followed by close matches and fallback options.

## Data format

The program currently expects a JSON list of programs with fields like:

```json
{
  "name": "CRED",
  "platform": "HackerOne",
  "country": "India",
  "scope_types": ["web", "api"],
  "offers_bounty": true,
  "launched_days_ago": 55,
  "response_rate": 88,
  "awarded_reports": 35,
  "awarded_reporters": 12,
  "reports_received_90d": 74
}
```

## Current status

This version uses sample program data for development and testing.

The next major milestone is connecting real platform data through a separate fetch-and-normalize pipeline rather than mixing external-site logic directly into the CLI.

## Planned improvements

- Add `fetch_programs.py` for real platform data.
- Normalize data from multiple platforms into one shared schema.
- Store fetched results in a local `data/programs.json` cache.
- Add a web UI version of Bountymatch.
- Add tests for scoring and grouping behavior.

## Why this project matters

Bountymatch is meant to become more than a demo script. The goal is to build a practical target-selection tool for bug bounty hunters while also showing clean scoring logic, readable CLI output, and a project structure that can grow into real data integration.