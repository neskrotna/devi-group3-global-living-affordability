"""Conservative country matching shared by the preprocessing steps.

ISO names are matched exactly after trimming whitespace and ignoring case.
Source-specific aliases are explicit; there is no fuzzy matching. Kosovo uses
the practical, user-assigned code XK, not an officially assigned ISO code.

The cost-of-living source incorrectly uses ``Congo`` for cities in two countries.
Only its five known cities can resolve that ambiguous label. References:
https://data.un.org/legacy/en/iso/cd.html (Kinshasa and Lubumbashi)
https://www.un.org/en/spotlight-on-drcongo/background (Goma)
https://www.worldbank.org/ext/en/country/congo (Brazzaville and Pointe-Noire)
https://ec.europa.eu/eurostat/statistics-explained/SEPDF/cache/4904.pdf (Kosovo/XK)
"""

import pycountry


ISO_CODE_STATUS = "ISO 3166-1 alpha-2"
USER_ASSIGNED_CODE_STATUS = "user-assigned"

# Keep human-readable display names consistent across all three sources.
_DISPLAY_NAMES = {
    "BO": "Bolivia",
    "BN": "Brunei",
    "CD": "Democratic Republic of the Congo",
    "CG": "Republic of the Congo",
    "CZ": "Czechia",
    "FK": "Falkland Islands",
    "IR": "Iran",
    "KP": "North Korea",
    "KR": "South Korea",
    "LA": "Laos",
    "MD": "Moldova",
    "RU": "Russia",
    "SH": "Saint Helena",
    "SK": "Slovakia",
    "SX": "Sint Maarten",
    "SY": "Syria",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "TR": "Turkey",
    "VA": "Vatican City",
    "VE": "Venezuela",
    "VG": "British Virgin Islands",
    "VI": "U.S. Virgin Islands",
    "VN": "Vietnam",
}

# These labels occur in the committed CSVs but are not exact ISO names, or
# deliberately make a source convention explicit (e.g. OECD's "Korea").
_SOURCE_ALIASES = {
    "brunei": "BN",
    "cape verde": "CV",
    "curacao": "CW",
    "czech republic": "CZ",
    "falkland islands": "FK",
    "ivory coast": "CI",
    "korea": "KR",
    "reunion": "RE",
    "russia": "RU",
    "saint helena": "SH",
    "sint maarten": "SX",
    "slovak rep.": "SK",
    "swaziland": "SZ",
    "turkey": "TR",
    "uae": "AE",
    "vatican city": "VA",
}

_CONGO_CITY_CODES = {
    "kinshasa": "CD",
    "lubumbashi": "CD",
    "goma": "CD",
    "brazzaville": "CG",
    "pointe-noire": "CG",
}

_ISO_NAME_CODES = {
    getattr(country, field).casefold(): country.alpha_2
    for country in pycountry.countries
    for field in ("name", "official_name", "common_name")
    if hasattr(country, field)
}
_ISO_NAME_CODES.update({name.casefold(): code for code, name in _DISPLAY_NAMES.items()})


def normalize_country(name: str, city: str | None = None) -> tuple[str, str, str]:
    """Return ``(country, country_code, country_code_status)``.

    Unknown labels, blank values, and ambiguous ``Congo`` records raise
    ``ValueError`` so a new source spelling cannot silently create a bad join.
    City is used only for the five known ``Congo`` records. The returned display
    names also normalize successfully without city context.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Country must be a non-empty string, got {name!r}")
    key = name.strip().casefold()

    if key in {"kosovo", "kosovo (disputed territory)"}:
        return "Kosovo", "XK", USER_ASSIGNED_CODE_STATUS

    if key == "congo":
        city_key = city.strip().casefold() if isinstance(city, str) else ""
        code = _CONGO_CITY_CODES.get(city_key)
        if code is None:
            raise ValueError(
                f"Ambiguous country 'Congo' for city {city!r}; "
                "an explicit, verified city mapping is required"
            )
    else:
        code = _SOURCE_ALIASES.get(key) or _ISO_NAME_CODES.get(key)
        if code is None:
            raise ValueError(f"Unknown country {name!r}; add a verified explicit alias")

    country = pycountry.countries.get(alpha_2=code)
    display_name = _DISPLAY_NAMES.get(code) or getattr(country, "common_name", country.name)
    return display_name, code, ISO_CODE_STATUS
