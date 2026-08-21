import calendar
import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ResolutionCompatibility:
    compatible: bool
    confidence: float
    warnings: list[str]
    differences: list[str]
    level: str = "INCOMPATIBLE"
    core_compatible: bool = False
    fully_compatible: bool = False
    resolution_risk: str | None = None
    normalized_dates: tuple[date | None, date | None] = (None, None)


def _plain(value: str) -> str:
    return " ".join(value.lower().replace("’", "'").split())


def normalize_resolution_date(text: str) -> date | None:
    """Return one unambiguous contract date; never infer a missing year."""
    value = _plain(text)
    found: set[date] = set()
    for year, month, day in re.findall(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", value):
        try: found.add(date(int(year), int(month), int(day)))
        except ValueError: pass
    months = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    months.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
    month_pattern = "|".join(sorted(months, key=len, reverse=True))
    for month, day, year in re.findall(rf"\b({month_pattern})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", value):
        try: found.add(date(int(year), months[month], int(day)))
        except ValueError: pass
    return next(iter(found)) if len(found) == 1 else None


def _scope(text: str) -> dict[str, bool | None]:
    value = _plain(text)
    regulation = bool(re.search(r"\b(?:first\s+)?90\s+minutes\b|\bregulation(?:\s+time|\s+play)?\b", value))
    neg_prefix = r"(?:does\s+not\s+include|do\s+not\s+include|not\s+including|excluding|excludes?)"
    extra_excluded = bool(re.search(rf"{neg_prefix}[^.;()]{{0,35}}\bextra\s+time\b", value))
    penalties_excluded = bool(re.search(rf"{neg_prefix}[^.;()]{{0,55}}\bpenalt(?:y|ies)\b", value))
    extra_included = bool(re.search(r"\b(?:includes?|including)\s+(?:any\s+)?extra\s+time\b", value)) and not extra_excluded
    penalties_included = bool(re.search(r"\b(?:includes?|including)[^.;()]{0,35}\bpenalt(?:y|ies)\b", value)) and not penalties_excluded
    # An explicit regulation/first-90-minute scope excludes later phases even if
    # the prose does not repeat the exclusions.
    return {
        "regulation": regulation,
        "extra_time": False if extra_excluded or (regulation and not extra_included) else True if extra_included else None,
        "penalties": False if penalties_excluded or (regulation and not penalties_included) else True if penalties_included else None,
    }


def _edge_rules(text: str) -> dict[str, str | None]:
    value = _plain(text)
    cancelled = None
    if "cancel" in value:
        if re.search(r"cancel[^.]{0,100}resolve(?:s|d)?\s+(?:to\s+)?[\"']?yes", value): cancelled = "YES"
        elif re.search(r"cancel[^.]{0,100}resolve(?:s|d)?\s+(?:to\s+)?[\"']?no", value): cancelled = "NO"
        elif "void" in value or "refund" in value: cancelled = "VOID"
        else: cancelled = "MENTIONED_UNCLEAR"
    postponed = "REMAIN_OPEN" if re.search(r"postpon[^.]{0,100}remain\s+open", value) else "MENTIONED_UNCLEAR" if "postpon" in value else None
    abandoned = "MENTIONED_UNCLEAR" if "abandon" in value else None
    return {"cancelled": cancelled, "postponed": postponed, "abandoned": abandoned}


def resolution_compatibility(left: str, right: str) -> ResolutionCompatibility:
    a, b = _plain(left), _plain(right)
    sa, sb = _scope(a), _scope(b)
    differences: list[str] = []
    if sa["regulation"] != sb["regulation"] and (sa["regulation"] or sb["regulation"]): differences.append("规则范围冲突: regulation vs non-regulation")
    for label, key in (("extra time", "extra_time"), ("penalties", "penalties")):
        if sa[key] is not None and sb[key] is not None and sa[key] != sb[key]: differences.append(f"规则范围冲突: {label}")
    nums_a = re.findall(r"(?:over|above|below|under|超过|高于|低于)\s*\$?([0-9,.]+)", a)
    nums_b = re.findall(r"(?:over|above|below|under|超过|高于|低于)\s*\$?([0-9,.]+)", b)
    if nums_a and nums_b and nums_a[0].replace(",", "") != nums_b[0].replace(",", ""): differences.append(f"阈值不一致: {nums_a[0]} vs {nums_b[0]}")
    da, db = normalize_resolution_date(a), normalize_resolution_date(b)
    if da and db and da != db: differences.append(f"规则日期截止不一致: {da.isoformat()} vs {db.isoformat()}")
    core = not differences and sa["regulation"] and sb["regulation"] and sa["extra_time"] is False and sb["extra_time"] is False and sa["penalties"] is False and sb["penalties"] is False
    ea, eb = _edge_rules(a), _edge_rules(b)
    edge_complete = all(ea[k] is not None and eb[k] is not None and ea[k] == eb[k] for k in ea)
    full = bool(core and edge_complete)
    risk = None if full else "CANCELLATION_RULE_UNVERIFIED" if core else "CORE_RULE_MISMATCH"
    level = "FULLY_COMPATIBLE" if full else "CORE_COMPATIBLE" if core else "INCOMPATIBLE"
    warnings = ["⚠ " + x for x in differences]
    if core and not full: warnings.append("⚠ Cancellation/postponement/abandonment rules are not fully verified")
    return ResolutionCompatibility(core, .98 if full else .85 if core else .1, warnings, differences, level, bool(core), full, risk, (da, db))


def resolution_warnings(left: str, right: str) -> list[str]:
    return resolution_compatibility(left, right).warnings
