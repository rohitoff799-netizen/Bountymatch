import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone, timedelta

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "programs.json")

SOURCES = {
    "HackerOne": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/hackerone_data.json",
    "Bugcrowd": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/bugcrowd_data.json",
    "Intigriti": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/intigriti_data.json",
}

ORDERED_SCOPES = ["web", "api", "mobile", "ios", "android", "network", "source_code"]

COUNTRY_HINTS = {
    "india": "india",
    "indian": "india",
    "singapore": "singapore",
    "usa": "usa",
    "united states": "usa",
    "us ": "usa",
    "u.s.": "usa",
    "uk": "uk",
    "united kingdom": "uk",
    "england": "uk",
    "ireland": "ireland",
    "roi": "ireland",
    "taiwan": "taiwan",
    "japan": "japan",
    "germany": "germany",
    "france": "france",
    "canada": "canada",
    "australia": "australia",
    "new zealand": "new_zealand",
    "indonesia": "indonesia",
    "malaysia": "malaysia",
    "philippines": "philippines",
    "vietnam": "vietnam",
    "thailand": "thailand",
    "uae": "uae",
    "united arab emirates": "uae",
    "saudi": "saudi_arabia",
    "netherlands": "netherlands",
    "spain": "spain",
    "italy": "italy",
    "sweden": "sweden",
    "norway": "norway",
    "denmark": "denmark",
    "finland": "finland",
    "global": "global",
    "worldwide": "global",
}

DATE_FIELD_CANDIDATES = [
    "launched_at",
    "launch_date",
    "launched_date",
    "started_accepting_at",
    "created_at",
    "published_at",
    "opened_at",
    "start_date",
]

REPORT_FIELD_CANDIDATES = [
    "awarded_reports",
    "resolved_report_count",
    "report_count",
    "reports_count",
]

REPORTER_FIELD_CANDIDATES = [
    "awarded_reporters",
    "reporter_count",
    "researcher_count",
    "unique_reporters",
]

RECENT_REPORT_FIELD_CANDIDATES = [
    "reports_received_90d",
    "reports_last_90_days",
    "recent_reports_count",
    "last_90_days_reports_count",
]

H1_USERNAME = os.environ.get("H1_USERNAME", "").strip()
H1_API_TOKEN = os.environ.get("H1_API_TOKEN", "").strip()
H1_API_BASE_URL = os.environ.get("H1_API_BASE_URL", "https://api.hackerone.com/v1").rstrip("/")
H1_API_DELAY_SECONDS = float(os.environ.get("H1_API_DELAY_SECONDS", "0.4") or 0.4)

H1_RESPONSE_RATE_FIELDS = [
    "response_efficiency_percentage",
    "triaged_response_percentage",
]

H1_AVG_RESPONSE_DAYS_FIELDS = [
    "average_time_to_triage",
    "average_days_to_first_response",
    "avg_response_days",
    "average_bounty_time",
    "average_time_to_bounty",
]

H1_AVERAGE_PAYOUT_FIELDS = [
    "mean_bounty_paid_in_last_90_days",
    "average_bounty_paid_in_last_90_days",
    "average_payout",
]

H1_MAX_PAYOUT_FIELDS = [
    "maximum_bounty",
    "max_bounty",
    "max_payout",
]


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def clean_url(url):
    url = clean_text(url)
    markdown_match = re.match(r"^\[(.*?)\]\((https?://[^)]+)\)$", url)
    if markdown_match:
        return markdown_match.group(2).strip()
    return url


def slugify_name(name):
    value = clean_text(name).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def to_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = clean_text(value)
    if not text:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None

    try:
        return int(float(match.group(0)))
    except ValueError:
        return None


def pick_first_int(data, keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        if key in data:
            parsed = to_int(data.get(key))
            if parsed is not None:
                return parsed
    return None


def parse_date(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000.0
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except Exception:
            return None

    text = clean_text(value)
    if not text:
        return None

    candidates = [
        text,
        text.replace("Z", "+00:00"),
    ]

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass

    return None


def derive_launched_days_ago(program):
    for field in DATE_FIELD_CANDIDATES:
        if field in program:
            dt = parse_date(program.get(field))
            if dt is not None:
                now = datetime.now(timezone.utc)
                delta_days = (now - dt).days
                if delta_days >= 0:
                    return delta_days
    return None


def average_from_min_max(min_value, max_value):
    if min_value is None and max_value is None:
        return None
    if min_value is not None and max_value is not None:
        return int((min_value + max_value) / 2)
    return min_value if min_value is not None else max_value


def infer_country(*texts):
    combined = " ".join(clean_text(t).lower() for t in texts if t)

    for hint, country in COUNTRY_HINTS.items():
        if hint in combined:
            return country

    return "global"


def infer_scope_types_from_targets(targets):
    scope_types = set()

    for target in targets or []:
        raw_type = clean_text(
            target.get("asset_type")
            or target.get("type")
            or target.get("name")
            or target.get("category")
        ).lower()

        raw_value = clean_text(
            target.get("asset_identifier")
            or target.get("target")
            or target.get("endpoint")
            or target.get("uri")
            or target.get("name")
        ).lower()

        blob = f"{raw_type} {raw_value}"

        if "api" in blob or "/v1" in blob or "/v2" in blob or "graphql" in blob:
            scope_types.add("api")

        if "android" in blob or "play.google.com" in blob or ".apk" in blob:
            scope_types.update(["android", "mobile"])

        if "ios" in blob or "apple" in blob or "apps.apple.com" in blob or ".ipa" in blob:
            scope_types.update(["ios", "mobile"])

        if "mobile" in blob:
            scope_types.add("mobile")

        if "source" in blob or "github" in blob or "gitlab" in blob or "repository" in blob:
            scope_types.add("source_code")

        if "ip" in blob or "network" in blob or "cidr" in blob or "port" in blob:
            scope_types.add("network")

        if (
            "url" in blob
            or "website" in blob
            or "web" in blob
            or raw_value.startswith("http")
            or "." in raw_value
        ):
            scope_types.add("web")

    if not scope_types:
        scope_types.add("web")

    return [item for item in ORDERED_SCOPES if item in scope_types]


def normalize_scopes(scope_types):
    normalized = set()
    for scope in scope_types or []:
        value = clean_text(scope).lower()
        if value in ORDERED_SCOPES:
            normalized.add(value)
    if not normalized:
        normalized.add("web")
    return [item for item in ORDERED_SCOPES if item in normalized]


def base_program_record(name, platform, url, scope_types, country, offers_bounty):
    return {
        "id": f"{platform.lower()}::{slugify_name(name)}",
        "name": clean_text(name),
        "platform": platform,
        "country": country or "global",
        "scope_types": normalize_scopes(scope_types),
        "offers_bounty": bool(offers_bounty),
        "launched_days_ago": None,
        "response_rate": None,
        "avg_response_days": None,
        "awarded_reports": None,
        "awarded_reporters": None,
        "reports_received_90d": None,
        "average_payout": None,
        "max_payout": None,
        "public_reports_90d": None,
        "public_awarded_reports": None,
        "public_average_payout": None,
        "public_severity_breakdown": None,
        "url": clean_url(url),
        "data_sources": [platform],
    }


def enrich_common_metadata(record, raw_program):
    if record["launched_days_ago"] is None:
        record["launched_days_ago"] = derive_launched_days_ago(raw_program)

    if record["awarded_reports"] is None:
        record["awarded_reports"] = pick_first_int(raw_program, REPORT_FIELD_CANDIDATES)

    if record["awarded_reporters"] is None:
        record["awarded_reporters"] = pick_first_int(raw_program, REPORTER_FIELD_CANDIDATES)

    if record["reports_received_90d"] is None:
        record["reports_received_90d"] = pick_first_int(raw_program, RECENT_REPORT_FIELD_CANDIDATES)

    if record["avg_response_days"] is None:
        record["avg_response_days"] = pick_first_int(
            raw_program,
            ["avg_response_days", "average_time_to_triage", "average_days_to_first_response"],
        )

    return record


def normalize_hackerone(program):
    targets = program.get("targets", {}).get("in_scope", [])
    name = program.get("name", "Unknown Program")
    handle = program.get("handle", "")
    website = program.get("website", "")
    url = program.get("url", "")
    state = clean_text(program.get("submission_state") or program.get("state")).lower()

    record = base_program_record(
        name=name,
        platform="HackerOne",
        url=url,
        scope_types=infer_scope_types_from_targets(targets),
        country=infer_country(name, handle, website, url),
        offers_bounty=program.get("offers_bounties", False),
    )

    response_rate = to_int(
        program.get("response_efficiency_percentage")
        or program.get("triaged_response_percentage")
    )
    if response_rate is not None:
        record["response_rate"] = response_rate

    record["awarded_reports"] = pick_first_int(program, REPORT_FIELD_CANDIDATES)
    record["awarded_reporters"] = pick_first_int(program, REPORTER_FIELD_CANDIDATES)
    record["reports_received_90d"] = pick_first_int(program, RECENT_REPORT_FIELD_CANDIDATES)
    record["avg_response_days"] = pick_first_int(
        program,
        ["avg_response_days", "average_bounty_time", "average_time_to_bounty"],
    )

    if not record["offers_bounty"] and state == "public_mode":
        record["offers_bounty"] = False

    return enrich_common_metadata(record, program)


def normalize_bugcrowd(program):
    targets = program.get("targets", {}).get("in_scope", [])
    name = program.get("name", "Unknown Program")
    url = program.get("url", "")
    max_payout = to_int(program.get("max_payout"))
    min_payout = to_int(program.get("min_payout"))
    avg_payout = to_int(program.get("average_payout"))

    record = base_program_record(
        name=name,
        platform="Bugcrowd",
        url=url,
        scope_types=infer_scope_types_from_targets(targets),
        country=infer_country(name, url),
        offers_bounty=bool(max_payout and max_payout > 0),
    )

    record["max_payout"] = max_payout
    record["average_payout"] = avg_payout if avg_payout is not None else average_from_min_max(min_payout, max_payout)
    record["response_rate"] = pick_first_int(program, ["response_rate", "accepting_submissions_percentage"])

    record["awarded_reports"] = pick_first_int(program, REPORT_FIELD_CANDIDATES)
    record["awarded_reporters"] = pick_first_int(program, REPORTER_FIELD_CANDIDATES)
    record["reports_received_90d"] = pick_first_int(program, RECENT_REPORT_FIELD_CANDIDATES)
    record["avg_response_days"] = pick_first_int(program, ["avg_response_days"])

    return enrich_common_metadata(record, program)


def normalize_intigriti(program):
    targets = program.get("targets", {}).get("in_scope", [])
    name = program.get("name", "Unknown Program")
    handle = program.get("handle", "")
    company_handle = program.get("company_handle", "")
    url = program.get("url", "")

    max_bounty = program.get("max_bounty", {}) or {}
    min_bounty = program.get("min_bounty", {}) or {}

    max_value = to_int(max_bounty.get("value"))
    min_value = to_int(min_bounty.get("value"))

    record = base_program_record(
        name=name,
        platform="Intigriti",
        url=url,
        scope_types=infer_scope_types_from_targets(targets),
        country=infer_country(name, handle, company_handle, url),
        offers_bounty=bool(max_value and max_value > 0),
    )

    record["max_payout"] = max_value
    record["average_payout"] = average_from_min_max(min_value, max_value)
    record["response_rate"] = pick_first_int(program, ["response_rate"])

    record["awarded_reports"] = pick_first_int(program, REPORT_FIELD_CANDIDATES)
    record["awarded_reporters"] = pick_first_int(program, REPORTER_FIELD_CANDIDATES)
    record["reports_received_90d"] = pick_first_int(program, RECENT_REPORT_FIELD_CANDIDATES)
    record["avg_response_days"] = pick_first_int(program, ["avg_response_days"])

    return enrich_common_metadata(record, program)


def dedupe_key(program):
    return slugify_name(program["name"])


def richer_value(old_value, new_value, field_name=None):
    if new_value in (None, "", "global"):
        return old_value

    if old_value in (None, "", "global"):
        return new_value

    if field_name == "platform":
        return old_value

    if isinstance(old_value, list) and isinstance(new_value, list):
        merged = set(old_value) | set(new_value)
        return [item for item in ORDERED_SCOPES if item in merged]

    if field_name in {
        "max_payout",
        "average_payout",
        "awarded_reports",
        "awarded_reporters",
        "reports_received_90d",
        "public_reports_90d",
        "public_awarded_reports",
        "public_average_payout",
    }:
        return max(old_value, new_value)

    if field_name == "launched_days_ago":
        return min(old_value, new_value)

    if field_name == "response_rate":
        return max(old_value, new_value)

    if field_name == "avg_response_days":
        return min(old_value, new_value)

    if field_name == "url":
        return old_value if len(clean_text(old_value)) >= len(clean_text(new_value)) else new_value

    return old_value


def merge_records(existing, incoming):
    merged = dict(existing)

    merge_fields = [
        "country",
        "launched_days_ago",
        "response_rate",
        "avg_response_days",
        "awarded_reports",
        "awarded_reporters",
        "reports_received_90d",
        "average_payout",
        "max_payout",
        "public_reports_90d",
        "public_awarded_reports",
        "public_average_payout",
        "url",
    ]

    for field in merge_fields:
        merged[field] = richer_value(merged.get(field), incoming.get(field), field)

    if not merged.get("public_severity_breakdown") and incoming.get("public_severity_breakdown"):
        merged["public_severity_breakdown"] = incoming.get("public_severity_breakdown")

    merged["offers_bounty"] = merged.get("offers_bounty", False) or incoming.get("offers_bounty", False)

    merged_scopes = set(merged.get("scope_types", [])) | set(incoming.get("scope_types", []))
    merged["scope_types"] = [item for item in ORDERED_SCOPES if item in merged_scopes]

    merged_sources = set(merged.get("data_sources", [])) | set(incoming.get("data_sources", []))
    merged["data_sources"] = sorted(merged_sources)

    if merged.get("platform") != incoming.get("platform"):
        platforms = []
        for value in [merged.get("platform"), incoming.get("platform")]:
            for part in clean_text(value).split(" + "):
                if part and part not in platforms:
                    platforms.append(part)
        merged["platform"] = " + ".join(platforms)

    return merged


def get_nested(data, path):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def pick_first_nested_int(data, candidate_paths):
    for path in candidate_paths:
        value = get_nested(data, path)
        parsed = to_int(value)
        if parsed is not None:
            return parsed
    return None


def build_h1_auth_header():
    raw = f"{H1_USERNAME}:{H1_API_TOKEN}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")
    return {"Authorization": f"Basic {encoded}"}


def h1_credentials_available():
    return bool(H1_USERNAME and H1_API_TOKEN)


def fetch_h1_program_payload(handle):
    if not h1_credentials_available():
        return None

    safe_handle = urllib.parse.quote(clean_text(handle))
    if not safe_handle:
        return None

    url = f"{H1_API_BASE_URL}/hackers/programs/{safe_handle}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Bountymatch/1.0",
            **build_h1_auth_header(),
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_h1_hacktivity_page(query_string, page_number=1, page_size=100):
    if not h1_credentials_available():
        return None

    params = urllib.parse.urlencode(
        {
            "queryString": query_string,
            "sortField": "latest_disclosable_activity_at",
            "sortDirection": "DESC",
            "page[number]": page_number,
            "page[size]": page_size,
        }
    )

    url = f"{H1_API_BASE_URL}/hackers/hacktivity?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Bountymatch/1.0",
            **build_h1_auth_header(),
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_h1_attributes(payload):
    if not isinstance(payload, dict):
        return {}

    attributes = get_nested(payload, ["data", "attributes"])
    if isinstance(attributes, dict):
        return attributes

    if isinstance(payload.get("attributes"), dict):
        return payload["attributes"]

    return payload


def derive_h1_handle(record):
    url = clean_url(record.get("url"))
    if not url:
        return None

    match = re.search(r"hackerone\.com/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)

    return None


def parse_hacktivity_amount(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        nested_amount = value.get("amount")
        if nested_amount is not None:
            parsed = to_int(nested_amount)
            if parsed is not None:
                return float(parsed)
        return None

    parsed = to_int(value)
    if parsed is not None:
        return float(parsed)

    return None


def parse_best_activity_date(attrs):
    for field in ["disclosed_at", "latest_disclosable_activity_at", "submitted_at"]:
        raw = attrs.get(field)
        if not raw:
            continue
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            continue
    return None


def calculate_hacktivity_metrics(items, cutoff_dt, expected_handle):
    expected_handle = clean_text(expected_handle).lower()
    public_reports = []
    severity_breakdown = {}

    for item in items:
        attrs = item.get("attributes", {}) or {}

        raw_blob = json.dumps(item).lower()
        if expected_handle and expected_handle not in raw_blob:
            continue

        activity_dt = parse_best_activity_date(attrs)
        if activity_dt is None or activity_dt < cutoff_dt:
            continue

        if attrs.get("disclosed") is True and attrs.get("disclosed_at"):
            public_reports.append(attrs)
            severity = clean_text(attrs.get("severity_rating")).lower() or "unknown"
            severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1

    awarded = []
    payouts = []

    for report in public_reports:
        parsed_amount = parse_hacktivity_amount(report.get("total_awarded_amount"))
        if parsed_amount is not None and parsed_amount > 0:
            awarded.append(report)
            payouts.append(parsed_amount)

    return {
        "public_reports_90d": len(public_reports),
        "public_awarded_reports": len(awarded),
        "public_average_payout": round(sum(payouts) / len(payouts), 2) if payouts else None,
        "public_severity_breakdown": severity_breakdown or None,
    }


def get_h1_hacktivity_metrics(handle, days_back=90, max_pages=20):
    if not h1_credentials_available():
        return {}

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    query_string = f'"{handle}"'
    collected_items = []
    stop_early = False

    for page_number in range(1, max_pages + 1):
        try:
            payload = fetch_h1_hacktivity_page(
                query_string,
                page_number=page_number,
                page_size=100,
            )
        except Exception:
            break

        if not isinstance(payload, dict):
            break

        items = payload.get("data", []) or []
        if not items:
            break

        for item in items:
            attrs = item.get("attributes", {}) or {}
            activity_dt = parse_best_activity_date(attrs)

            if activity_dt and activity_dt < cutoff_dt:
                stop_early = True
                break

            collected_items.append(item)

        if stop_early or len(items) < 100:
            break

        time.sleep(H1_API_DELAY_SECONDS)

    return calculate_hacktivity_metrics(collected_items, cutoff_dt, handle)


def enrich_hackerone_record(record):
    if not h1_credentials_available():
        return record, False, "missing_credentials"

    if "HackerOne" not in clean_text(record.get("platform")):
        return record, False, "not_hackerone"

    handle = derive_h1_handle(record)
    if not handle:
        return record, False, "missing_handle"

    try:
        payload = fetch_h1_program_payload(handle)
        attrs = extract_h1_attributes(payload)

        if not isinstance(attrs, dict):
            return record, False, "invalid_payload"

        enriched = dict(record)

        response_rate = pick_first_int(attrs, H1_RESPONSE_RATE_FIELDS)
        if response_rate is not None:
            enriched["response_rate"] = richer_value(enriched.get("response_rate"), response_rate, "response_rate")

        avg_response_days = pick_first_int(attrs, H1_AVG_RESPONSE_DAYS_FIELDS)
        if avg_response_days is not None:
            enriched["avg_response_days"] = richer_value(enriched.get("avg_response_days"), avg_response_days, "avg_response_days")

        awarded_reports = pick_first_int(attrs, REPORT_FIELD_CANDIDATES)
        if awarded_reports is not None:
            enriched["awarded_reports"] = richer_value(enriched.get("awarded_reports"), awarded_reports, "awarded_reports")

        awarded_reporters = pick_first_int(attrs, REPORTER_FIELD_CANDIDATES)
        if awarded_reporters is not None:
            enriched["awarded_reporters"] = richer_value(enriched.get("awarded_reporters"), awarded_reporters, "awarded_reporters")

        reports_received_90d = pick_first_int(attrs, RECENT_REPORT_FIELD_CANDIDATES)
        if reports_received_90d is not None:
            enriched["reports_received_90d"] = richer_value(enriched.get("reports_received_90d"), reports_received_90d, "reports_received_90d")

        average_payout = pick_first_int(attrs, H1_AVERAGE_PAYOUT_FIELDS)
        if average_payout is None:
            average_payout = pick_first_nested_int(
                attrs,
                [
                    ["mean_bounty_paid_in_last_90_days", "amount"],
                    ["average_bounty_paid_in_last_90_days", "amount"],
                    ["average_payout", "amount"],
                ],
            )
        if average_payout is not None:
            enriched["average_payout"] = richer_value(enriched.get("average_payout"), average_payout, "average_payout")

        max_payout = pick_first_int(attrs, H1_MAX_PAYOUT_FIELDS)
        if max_payout is None:
            max_payout = pick_first_nested_int(
                attrs,
                [
                    ["maximum_bounty", "amount"],
                    ["max_bounty", "amount"],
                    ["max_payout", "amount"],
                ],
            )
        if max_payout is not None:
            enriched["max_payout"] = richer_value(enriched.get("max_payout"), max_payout, "max_payout")

        if enriched.get("launched_days_ago") is None:
            enriched["launched_days_ago"] = derive_launched_days_ago(attrs)

        offers_bounty_value = attrs.get("offers_bounties")
        if isinstance(offers_bounty_value, bool):
            enriched["offers_bounty"] = enriched.get("offers_bounty", False) or offers_bounty_value

        hacktivity_metrics = get_h1_hacktivity_metrics(handle, days_back=90)
        for key, value in hacktivity_metrics.items():
            if value is not None:
                enriched[key] = value

        return enriched, True, None

    except Exception as error:
        return record, False, str(error)


def enrich_merged_hackerone_programs(programs):
    if not h1_credentials_available():
        print("HackerOne enrichment skipped (missing H1_USERNAME or H1_API_TOKEN).")
        return programs

    h1_programs = [p for p in programs if "HackerOne" in clean_text(p.get("platform"))]
    total = len(h1_programs)

    print(f"\nEnriching merged HackerOne programs via HackerOne API... ({total} programs)")
    print(" - Program API: response rate, payouts, launch age")
    print(" - Hacktivity API: public/disclosed-only 90d metrics")

    enriched_programs = []
    success_count = 0
    fail_count = 0
    skipped_count = 0
    processed_h1 = 0

    for program in programs:
        if "HackerOne" not in clean_text(program.get("platform")):
            enriched_programs.append(program)
            continue

        processed_h1 += 1

        enriched, changed, reason = enrich_hackerone_record(program)
        enriched_programs.append(enriched)

        if changed:
            success_count += 1
        else:
            if reason in {"missing_credentials", "not_hackerone", "missing_handle"}:
                skipped_count += 1
            else:
                fail_count += 1
                print(f" - [{processed_h1}/{total}] HackerOne enrich failed for {program.get('name', 'Unknown Program')}: {reason}")

        if processed_h1 % 25 == 0 or processed_h1 == total:
            print(f"   progress: {processed_h1}/{total} processed, {success_count} updated, {fail_count} failed")

        time.sleep(H1_API_DELAY_SECONDS)

    print(f"HackerOne enrichment complete: {success_count} updated, {skipped_count} skipped, {fail_count} failed.")
    return enriched_programs


def fetch_and_normalize_all():
    records = []

    normalizers = {
        "HackerOne": normalize_hackerone,
        "Bugcrowd": normalize_bugcrowd,
        "Intigriti": normalize_intigriti,
    }

    for platform, url in SOURCES.items():
        print(f" Fetching {platform}...", end=" ", flush=True)

        try:
            data = fetch_json(url)
            normalizer = normalizers[platform]
            normalized = [normalizer(item) for item in data]
            records.extend(normalized)
            print(f"✓ ({len(normalized)} programs)")
        except Exception as error:
            print(f"✗ Failed: {error}")

    print(f"\nFetched and normalized {len(records)} total records.")
    return records


def merge_all(records):
    merged = {}

    for record in records:
        key = dedupe_key(record)
        if key not in merged:
            merged[key] = record
        else:
            merged[key] = merge_records(merged[key], record)

    return list(merged.values())


def save_programs(programs):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(programs, file, indent=2, ensure_ascii=False)


def print_summary(programs):
    by_source = defaultdict(int)
    bounty_count = 0
    metadata_coverage = defaultdict(int)

    tracked_fields = [
        "launched_days_ago",
        "response_rate",
        "awarded_reports",
        "awarded_reporters",
        "reports_received_90d",
        "average_payout",
        "max_payout",
        "avg_response_days",
        "public_reports_90d",
        "public_awarded_reports",
        "public_average_payout",
        "public_severity_breakdown",
    ]

    for program in programs:
        for source in program.get("data_sources", []):
            by_source[source] += 1

        if program.get("offers_bounty"):
            bounty_count += 1

        for field in tracked_fields:
            if program.get(field) is not None:
                metadata_coverage[field] += 1

    print(f"Saved {len(programs)} merged programs to {OUTPUT_FILE}")
    print(f"Programs offering bounty: {bounty_count}")
    print("Source coverage:")
    for source, count in sorted(by_source.items()):
        print(f" - {source}: {count}")

    print("Metadata coverage:")
    for field in tracked_fields:
        print(f" - {field}: {metadata_coverage[field]}")


def main():
    try:
        records = fetch_and_normalize_all()
        merged_programs = merge_all(records)
        merged_programs = enrich_merged_hackerone_programs(merged_programs)
        save_programs(merged_programs)
        print_summary(merged_programs)
    except Exception as error:
        print(f"Failed to fetch programs: {error}")


if __name__ == "__main__":
    main()