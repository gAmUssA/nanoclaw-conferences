#!/usr/bin/env python3
"""Geo gate for CFP candidates (check-cfps Step 6, jbaruch/nanoclaw-conferences#91).

CFPs count only in markets Port will pay to send Baruch to. The policy is
operator data in `cfp-geo-policy.json`: `allowed_countries`, `aliases`
(alternate spellings to a canonical allowed name) and per-slug
`exceptions`. This script applies it before every tier, the
javaconferences.org auto-approve included.

A candidate's country comes from, in order: its `country` field, the
last comma part of `location`, then `city` as `City (Country)` or
`City, …, Country`. A value names a country only when it is an allowed
country, an alias, or a name in `COUNTRY_NAMES`; anything else (a bare
city, a US state code, `?`) leaves the country unresolved. Verdicts:

- `allowed`: the country is allowed, or the slug is in `exceptions`.
- `excluded`: a recognized country outside the policy. The caller
  dismisses it with `bot_notes` set to `reason`, which starts with
  `Auto-dismissed: Geo:`.
- `unresolved`: no country could be read, or the event is online-only.
  The caller passes it on to the topic filter; it is never geo-dismissed.

Input  (stdin): a JSON array of candidates, each an object with `slug`
                 and optional `country`, `location`, `city`, `is_online`
                 (extra fields ignored).
Args:   --policy <path>  cfp-geo-policy.json.
Output (stdout): a JSON array parallel to the input, each
                 `{"slug", "verdict", "country", "reason"}`; `country` is
                 the canonical name or null.

Exit 0 on success; 1 when the policy is missing, unreadable or malformed;
2 on bad stdin (not a JSON array, a non-object, a missing `slug`, or a
location field that is not a string).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Country names as they appear in CFP metadata, beyond the policy's own
# allowed list and aliases. Only a name here can geo-dismiss: an
# unrecognized value is unresolved and goes to the topic filter.
COUNTRY_NAMES = frozenset(
    {
        "Afghanistan",
        "Albania",
        "Algeria",
        "Andorra",
        "Angola",
        "Argentina",
        "Armenia",
        "Australia",
        "Austria",
        "Azerbaijan",
        "Bahamas",
        "Bahrain",
        "Bangladesh",
        "Barbados",
        "Belarus",
        "Belgium",
        "Belize",
        "Benin",
        "Bhutan",
        "Bolivia",
        "Bosnia and Herzegovina",
        "Botswana",
        "Brazil",
        "Brunei",
        "Bulgaria",
        "Burkina Faso",
        "Burundi",
        "Cambodia",
        "Cameroon",
        "Canada",
        "Cape Verde",
        "Central African Republic",
        "Chad",
        "Chile",
        "China",
        "Colombia",
        "Comoros",
        "Congo",
        "Costa Rica",
        "Croatia",
        "Cuba",
        "Cyprus",
        "Czechia",
        "Democratic Republic of the Congo",
        "Denmark",
        "Djibouti",
        "Dominica",
        "Dominican Republic",
        "Ecuador",
        "Egypt",
        "El Salvador",
        "Equatorial Guinea",
        "Eritrea",
        "Estonia",
        "Eswatini",
        "Ethiopia",
        "Fiji",
        "Finland",
        "France",
        "Gabon",
        "Gambia",
        "Georgia",
        "Germany",
        "Ghana",
        "Greece",
        "Grenada",
        "Guatemala",
        "Guinea",
        "Guinea-Bissau",
        "Guyana",
        "Haiti",
        "Honduras",
        "Hong Kong",
        "Hungary",
        "Iceland",
        "India",
        "Indonesia",
        "Iran",
        "Iraq",
        "Ireland",
        "Israel",
        "Italy",
        "Ivory Coast",
        "Côte d'Ivoire",
        "Jamaica",
        "Japan",
        "Jordan",
        "Kazakhstan",
        "Kenya",
        "Kosovo",
        "Kuwait",
        "Kyrgyzstan",
        "Laos",
        "Latvia",
        "Lebanon",
        "Lesotho",
        "Liberia",
        "Libya",
        "Liechtenstein",
        "Lithuania",
        "Luxembourg",
        "Macau",
        "Madagascar",
        "Malawi",
        "Malaysia",
        "Maldives",
        "Mali",
        "Malta",
        "Mauritania",
        "Mauritius",
        "Mexico",
        "Moldova",
        "Monaco",
        "Mongolia",
        "Montenegro",
        "Morocco",
        "Mozambique",
        "Myanmar",
        "Namibia",
        "Nepal",
        "Netherlands",
        "New Zealand",
        "Nicaragua",
        "Niger",
        "Nigeria",
        "North Korea",
        "North Macedonia",
        "Norway",
        "Oman",
        "Pakistan",
        "Palestine",
        "Panama",
        "Papua New Guinea",
        "Paraguay",
        "Peru",
        "Philippines",
        "Poland",
        "Portugal",
        "Puerto Rico",
        "Qatar",
        "Romania",
        "Russia",
        "Rwanda",
        "Saudi Arabia",
        "Senegal",
        "Serbia",
        "Seychelles",
        "Sierra Leone",
        "Singapore",
        "Slovakia",
        "Slovenia",
        "Somalia",
        "South Africa",
        "South Korea",
        "South Sudan",
        "Spain",
        "Sri Lanka",
        "Sudan",
        "Suriname",
        "Sweden",
        "Switzerland",
        "Syria",
        "Taiwan",
        "Tajikistan",
        "Tanzania",
        "Thailand",
        "Togo",
        "Trinidad and Tobago",
        "Tunisia",
        "Turkey",
        "Türkiye",
        "Turkmenistan",
        "Uganda",
        "Ukraine",
        "United Arab Emirates",
        "United Kingdom",
        "United States",
        "Uruguay",
        "Uzbekistan",
        "Venezuela",
        "Vietnam",
        "Yemen",
        "Zambia",
        "Zimbabwe",
    }
)

_PARENS = re.compile(r"\(([^()]+)\)\s*$")


def _key(value: str) -> str:
    """Case- and accent-insensitive comparison key."""
    decomposed = unicodedata.normalize("NFKD", value.strip())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


class Policy:
    """The operator's travel policy, keyed for lookup."""

    def __init__(self, raw: object):
        if not isinstance(raw, dict):
            raise ValueError("policy must be a JSON object")
        allowed = raw.get("allowed_countries")
        aliases = raw.get("aliases", {})
        exceptions = raw.get("exceptions", {})
        if not isinstance(allowed, list) or not all(isinstance(c, str) for c in allowed):
            raise ValueError("allowed_countries must be an array of strings")
        if not isinstance(aliases, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()
        ):
            raise ValueError("aliases must map strings to strings")
        if not isinstance(exceptions, dict):
            raise ValueError("exceptions must be an object keyed by slug")
        self.allowed = {_key(c): c for c in allowed}
        self.aliases = {_key(k): v for k, v in aliases.items()}
        self.exceptions = exceptions
        self.known = {_key(c): c for c in COUNTRY_NAMES} | self.allowed

    def country(self, value: str) -> str | None:
        """The canonical country `value` names, or None when it names none."""
        key = _key(value)
        if key in self.aliases:
            return self.aliases[key]
        return self.known.get(key)


def resolve_country(candidate: dict, policy: Policy) -> str | None:
    """The candidate's country, from `country`, then `location`, then `city`."""
    country = candidate.get("country")
    if country:
        named = policy.country(country)
        if named:
            return named
    location = candidate.get("location")
    if location:
        named = policy.country(location.rsplit(",", 1)[-1])
        if named:
            return named
    city = candidate.get("city")
    if city:
        inner = _PARENS.search(city)
        if inner:
            named = policy.country(inner.group(1))
            if named:
                return named
        named = policy.country(_PARENS.sub("", city).rsplit(",", 1)[-1])
        if named:
            return named
    return None


def verdict(candidate: dict, policy: Policy) -> dict:
    slug = candidate["slug"]
    if slug in policy.exceptions:
        return {
            "slug": slug,
            "verdict": "allowed",
            "country": None,
            "reason": "Geo: policy exception",
        }
    if candidate.get("is_online") is True:
        return {
            "slug": slug,
            "verdict": "unresolved",
            "country": None,
            "reason": "online event: no travel to judge",
        }
    country = resolve_country(candidate, policy)
    if country is None:
        return {
            "slug": slug,
            "verdict": "unresolved",
            "country": None,
            "reason": "country not resolved",
        }
    if _key(country) in policy.allowed:
        return {"slug": slug, "verdict": "allowed", "country": country, "reason": f"Geo: {country}"}
    return {
        "slug": slug,
        "verdict": "excluded",
        "country": country,
        "reason": (
            f"Auto-dismissed: Geo: {country} is outside the travel policy (cfp-geo-policy.json)"
        ),
    }


def _validate(records: object) -> list[dict]:
    if not isinstance(records, list):
        raise ValueError("stdin must be a JSON array of candidates")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"candidate {index} is not an object")
        if not isinstance(record.get("slug"), str) or not record["slug"]:
            raise ValueError(f"candidate {index} has no slug")
        for field in ("country", "location", "city"):
            value = record.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"candidate {record['slug']}: {field} must be a string")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Geo gate for CFP candidates (check-cfps Step 6).")
    parser.add_argument("--policy", required=True)
    args = parser.parse_args(argv)
    try:
        policy = Policy(json.loads(Path(args.policy).read_text(encoding="utf-8")))
    # RecursionError: deeply nested JSON exhausts the decoder's stack.
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        print(
            f"geo-gate: cannot use the travel policy at {args.policy} ({exc}); "
            "fix cfp-geo-policy.json, then rerun. No candidate was geo-gated.",
            file=sys.stderr,
        )
        return 1
    try:
        records = _validate(json.load(sys.stdin))
    except (json.JSONDecodeError, ValueError, RecursionError) as exc:
        print(
            f"geo-gate: bad candidate input ({exc}); pass a JSON array of objects with a slug",
            file=sys.stderr,
        )
        return 2
    json.dump([verdict(r, policy) for r in records], sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
