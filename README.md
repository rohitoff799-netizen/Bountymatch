# Bountymatch

Bountymatch is a Python CLI tool that helps bug bounty hunters find programs that match how they actually hunt.

Instead of showing a random list of programs, Bountymatch asks about your experience, focus areas, bounty preference, region, ranking priority, and program type, then recommends programs using a mix of match quality and scoring signals.

## What it does

Bountymatch separates **match quality** from **ranking strength**:

- **Exact match**: the program satisfies the user’s hard requirements.
- **Partial match**: the program is close, but misses part of the ideal fit.
- **Fallback**: the program has stronger mismatches and is shown only when needed.
- **Score**: used to rank programs after match quality is determined.

This makes recommendations easier to trust. A high score does not automatically override a poor fit, and a good fit is not confused with strong metadata alone.

## Features

- Interactive CLI profile flow.
- Match-quality aware recommendations.
- Ranking based on freshness, competition, response quality, or a balanced strategy.
- Freshness mode that prioritizes the newest valid programs first.
- Separate handling for hard mismatches in freshness mode.
- Experience-aware competition scoring.
- Better handling of incomplete metadata through confidence-aware ranking.
- Human-readable recommendation output with strengths, risks, tradeoffs, and verdicts.
- Optional JSON export with `--save`.
- Separate maintainer pipeline for rebuilding and enriching the dataset.

## Project structure

```text
Bountymatch/
├── main.py
├── fetch_programs.py
├── scorer.py
├── explainer.py
├── hunter_profile.py
├── sample_programs.json
├── data/
│   └── programs.json
├── README.md
└── requirements.txt
```

## Installation

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

```bash
pip install -r requirements.txt
```

Current dependency:

```txt
colorama>=0.4.6
```

## Usage

### Run the recommender

```bash
python main.py
```

Bountymatch will use:

- `data/programs.json` if a cached dataset exists
- `sample_programs.json` if no cached dataset is available

### Save recommendations to JSON

```bash
python main.py --save
```

This writes output to:

```text
results.json
```

## CLI flow

The recommender asks for:

1. Experience level
2. Testing focus areas
3. Bounty preference
4. Region / country preference
5. Ranking priority
6. Program type

After that, Bountymatch prints recommendations based on your chosen ranking mode.

## How ranking works

Bountymatch supports four ranking priorities:

- **Freshness**: prefers newly launched programs, with crowd-awareness as a secondary signal.
- **Low competition**: prefers programs with lower recent/public report activity and, when available, smaller active reporter pools.
- **Response quality**: prefers stronger response rates, faster response/triage times, and better payout signals.
- **Balanced**: combines freshness, competition, response quality, and payout into a mixed recommendation.

The scorer also tracks **data confidence**, so weakly populated programs are ranked more carefully.

## Match quality vs score

Bountymatch does **not** rely only on numeric score.

A recommendation is judged using two layers:

1. **Match quality**: whether the program fits the hunter’s selected focus, region, bounty preference, and program type.
2. **Score**: how strong the program looks inside that fit level, based on your selected priority and available metadata.

This helps avoid misleading situations where a high-scoring program still violates the user’s hard preferences.

## Freshness mode behavior

Freshness mode is slightly different from the other ranking modes.

Instead of showing only the normal exact/partial/fallback grouping, it separates results into:

- **Freshest Eligible Programs First**: programs that satisfy hard constraints and are sorted by freshness.
- **Other Fresh Programs (hard mismatches)**: newer programs that may still be interesting, but do not satisfy key constraints such as paid-only or selected program type.

This makes freshness mode more practical for real hunting. You still discover new programs quickly, but invalid targets do not pollute the primary recommendation list.

## Output style

Each recommendation includes:

- program name and platform,
- country,
- score,
- match quality,
- data confidence,
- crowd signal and crowd source,
- payout and response metrics,
- public severity summary when available,
- strengths,
- risks and tradeoffs,
- verdict label.

## Data sources and enrichment

The maintainer pipeline fetches and normalizes public program data from:

- HackerOne
- Bugcrowd
- Intigriti

It can also optionally enrich merged HackerOne records using:

- HackerOne program API metadata
- HackerOne Hacktivity public/disclosed report signals

That enrichment improves fields such as:

- `response_rate`
- `avg_response_days`
- `reports_received_90d`
- `public_reports_90d`
- `public_awarded_reports`
- `public_average_payout`
- `public_severity_breakdown`

These enriched fields help the scorer and explainer give more realistic recommendations.

## Example normalized program fields

```json
{
  "name": "CRED",
  "platform": "HackerOne",
  "country": "india",
  "scope_types": ["web", "api"],
  "offers_bounty": true,
  "launched_days_ago": 55,
  "response_rate": 88,
  "avg_response_days": 3,
  "awarded_reports": 35,
  "awarded_reporters": 12,
  "reports_received_90d": 74,
  "average_payout": 250,
  "max_payout": 5000,
  "public_reports_90d": 19,
  "public_awarded_reports": 11,
  "public_average_payout": 420,
  "public_severity_breakdown": {
    "high": 2,
    "medium": 7,
    "low": 10
  },
  "url": "https://hackerone.com/example"
}
```

## For users

If you only want recommendations, you do **not** need API credentials.

Typical user workflow:

```bash
python main.py
```

That is enough if the repository already contains `data/programs.json`, or if you are okay using the bundled sample dataset.

## For maintainers

This section is for the project owner or anyone rebuilding the dataset.

### Rebuild the cached dataset

```bash
python fetch_programs.py
```

This creates or updates:

```text
data/programs.json
```

### Optional HackerOne enrichment

`fetch_programs.py` can optionally enrich merged HackerOne programs with additional metadata from the HackerOne API and Hacktivity.

This is a **maintainer-only** workflow.

Regular users do not need HackerOne credentials and do not need to run this step.

If a maintainer wants to run enrichment locally, the script reads these environment variables:

- `H1_USERNAME`
- `H1_API_TOKEN`

**Windows**

```bash
set H1_USERNAME=your_hackerone_username
set H1_API_TOKEN=your_hackerone_token
python fetch_programs.py
```

**macOS / Linux**

```bash
H1_USERNAME=your_hackerone_username H1_API_TOKEN=your_hackerone_token python fetch_programs.py
```

If these variables are not set, the fetch still works, but HackerOne enrichment is skipped.

### Why the fetch pipeline is separate

The recommendation CLI is designed for normal users.

The fetch pipeline is separate because it:

- depends on external platform data,
- may use authenticated enrichment,
- rebuilds the shared cached dataset,
- is better suited to maintainers than day-to-day users.

This keeps the CLI simple and avoids forcing end users to manage external credentials.

## Current status

Bountymatch now has two clear layers:

- a **user CLI** for personalized recommendations,
- a **maintainer fetch/enrichment pipeline** for improving dataset quality.

That split makes the project easier to use, easier to maintain, and easier to extend later into automation or a web product.

## Suggested next improvements

- Add unit tests for scoring and grouping behavior.
- Add schema validation for normalized records.
- Add a small `--top N` flag for output control.
- Add optional non-interactive CLI arguments.
- Add automated cache refresh workflows.
- Improve zero-value handling in signal resolver helpers.
- Add a web UI in the future.

## Why this project matters

Bountymatch is more than a simple demo script.

It is a recommendation engine for bug bounty target selection, with explicit tradeoffs, explainable ranking, and a structure that can grow into a more serious tool.