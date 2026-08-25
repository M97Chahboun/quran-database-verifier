#!/usr/bin/env python3
"""
Quran Database Verification & Alignment Tool
===========================================
Audits local SQLite Quran databases (hafs.sqlite, warsh.sqlite) against
the official Quranpedia REST API (https://api.quranpedia.net).

Features:
- Multi-tier verification: Structure, Strict Match, Normalized, Harakat, Waqf, Internal Consistency.
- Granular discrepancy classification (Critical, Harakat, Orthographic, Waqf, Structural).
- Visual side-by-side character level diffing.
- Multi-format reporting (Console, Markdown, JSON, Interactive HTML Diff Viewer).
- Automated SQL migration fix generation.
"""

import argparse
import difflib
import html
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configuration & Constants
API_BASE_URL = "https://api.quranpedia.net/v1"
MUSHAF_IDS = {
    "hafs": 2,   # King Fahd Complex - Text Version (Uthmani)
    "warsh": 4,  # King Fahd Complex - Warsh
}

WAQF_CHARS: Set[str] = {"ۖ", "ۗ", "ۘ", "ۙ", "ۚ", "ۜ", "ۛ", "۞", "۩"}
ZERO_WIDTH_CHARS_PATTERN = re.compile(r"[\u200b-\u200f\ufeff\u061c]")
TATWEEL_CHAR = "\u0640"
HARAKAT_PATTERN = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D4-\u08FF]")

# ANSI Color codes for terminal
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class DiffItem:
    sora_id: int
    sora_name: str
    aya_id: int
    severity: str  # CRITICAL, HARAKAT, ORTHOGRAPHIC, WAQF, STRUCTURAL
    category_desc: str
    db_text: str
    api_text: str
    db_diff_highlight: str
    api_diff_highlight: str
    details: List[str] = field(default_factory=list)


@dataclass
class InternalDbIssue:
    sora_id: int
    aya_id: int
    issue_type: str
    details: str
    sql_fix: Optional[str] = None


@dataclass
class MushafAuditResult:
    flavor: str
    db_path: str
    mushaf_id: int
    total_db_ayahs: int
    total_api_ayahs: int
    total_surahs: int
    exact_matches: int
    normalized_matches: int
    tatweel_only_diffs: int
    nfkd_only_diffs: int
    waqf_only_diffs: int
    critical_diffs: int
    harakat_diffs: int
    orthographic_diffs: int
    structural_diffs: int
    internal_issues: List[InternalDbIssue] = field(default_factory=list)
    discrepancies: List[DiffItem] = field(default_factory=list)
    surah_count_mismatches: List[Tuple[int, str, int, int]] = field(default_factory=list)


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_tatweel(text: str) -> str:
    return clean_whitespace(text.replace(TATWEEL_CHAR, ""))


def clean_zero_width(text: str) -> str:
    return ZERO_WIDTH_CHARS_PATTERN.sub("", text)


def clean_waqf(text: str) -> str:
    return "".join(c for c in text if c not in WAQF_CHARS)


def clean_harakat(text: str) -> str:
    return HARAKAT_PATTERN.sub("", text)


def normalize_nfkd(text: str) -> str:
    return unicodedata.normalize("NFKD", text)


def normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fetch_api_mushaf(mushaf_id: int, cache_dir: Path, force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch full mushaf data from Quranpedia API with local caching."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"mushaf_{mushaf_id}.json"

    if cache_file.exists() and not force_refresh:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    url = f"{API_BASE_URL}/mushafs/{mushaf_id}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "TathbeetQuranVerifier/1.0", "Accept": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data
    except Exception as e:
        # If full mushaf fails, fallback to fetching surah by surah
        print(f"{Colors.YELLOW}Warning: Full mushaf fetch failed ({e}). Attempting surah-by-surah fetch...{Colors.RESET}")
        surahs_data = []
        for s in range(1, 115):
            surah_url = f"{API_BASE_URL}/mushafs/{mushaf_id}/{s}"
            s_req = urllib.request.Request(surah_url, headers={"User-Agent": "TathbeetQuranVerifier/1.0"})
            with urllib.request.urlopen(s_req, timeout=15) as s_resp:
                ayahs = json.loads(s_resp.read().decode("utf-8"))
                surahs_data.append({"id": s, "ayahs": ayahs})
            time.sleep(0.05)
        fallback_data = {"id": mushaf_id, "surahs": surahs_data}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(fallback_data, f, ensure_ascii=False, indent=2)
        return fallback_data


ARABIC_CHAR_NAMES = {
    "\u064E": "فتحة (Fatha)",
    "\u064F": "ضمة (Damma)",
    "\u0650": "كسرة (Kasra)",
    "\u0651": "شدة (Shaddah)",
    "\u0652": "سكون (Sukun)",
    "\u064B": "تنوين فتح (Fathatan)",
    "\u064C": "تنوين ضم (Dammatan)",
    "\u064D": "تنوين كسر (Kasratan)",
    "\u0653": "علامة مد (Maddah)",
    "\u0654": "همزة علوية (Hamza Above)",
    "\u0655": "همزة سفلية (Hamza Below)",
    "\u0640": "تطويل / كشيدة (Tatweel)",
    "\u0670": "ألف خنجرية صغيرة (Small Alif)",
    "\u0656": "تنوين كسر متتابع (Sequential Kasratan)",
    "\u0657": "تنوين فتح متتابع (Sequential Fathatan)",
    "\u065E": "تنوين ضم متتابع (Sequential Dammatan)",
    "\u06E1": "سكون قرآني (Quranic Sukun)",
    "\u06E2": "ميم إقلاب صغيرة (Small Meem)",
    "\u06E5": "واو صلة صغرى (Small Waw)",
    "\u06E6": "ياء صلة صغرى (Small Yaa)",
    "\u06EC": "نقطة إمالة (Imala Dot)",
    "\u06EA": "نقطة تقليل / تسهيل (Tashil Dot)",
    "\u06D6": "علامة وقف صلى (Waqf Salla)",
    "\u06D7": "علامة وقف قلى (Waqf Qala)",
    "\u06D8": "علامة وقف لازم (Waqf Lazim)",
    "\u06D9": "علامة وقف لا (Waqf Mamnoo)",
    "\u06DA": "علامة وقف جائز (Waqf Jaiz)",
    "\u06DB": "علامة تعانق الوقف (Waqf Tanazuq)",
    "\u06DC": "علامة سكتة (Saktah)",
    "\u06DF": "صفر مستدير (Rounded Zero)",
    "\u06E0": "صفر مستطيل (Rectangular Zero)",
    " ": "مسافة (Space)",
    "۞": "علامة الحزب / الربع (Hizb Rub')",
    "۩": "علامة السجدة (Sajdah)",
}


def format_char_desc(text: str) -> str:
    """Format character sequence into clean, human-readable Arabic and English names."""
    if not text:
        return ""
    if text in ARABIC_CHAR_NAMES:
        return ARABIC_CHAR_NAMES[text]
    if len(text) == 1:
        c = text[0]
        if c in ARABIC_CHAR_NAMES:
            return ARABIC_CHAR_NAMES[c]
        if ord(c) < 32 or ord(c) in range(0x200B, 0x2010) or ord(c) == 0xFEFF:
            return f"رمز خاص (Special Char U+{ord(c):04X})"
        return f"حرف '{c}'"
    if text.strip() == "":
        return f"{len(text)} مسافات (Spaces)"
    return f"'{text}'"


def generate_char_diff_highlights(s1: str, s2: str) -> Tuple[str, str, List[str]]:
    """Generate HTML inline character diff highlights and human-readable descriptions."""
    matcher = difflib.SequenceMatcher(None, s1, s2)
    s1_parts = []
    s2_parts = []
    details = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        sub1 = s1[i1:i2]
        sub2 = s2[j1:j2]
        if tag == "equal":
            s1_parts.append(html.escape(sub1))
            s2_parts.append(html.escape(sub2))
        elif tag == "delete":
            s1_parts.append(f'<del class="diff-del">{html.escape(sub1)}</del>')
            details.append(f"Extra in DB at index {i1}: {format_char_desc(sub1)}")
        elif tag == "insert":
            s2_parts.append(f'<ins class="diff-ins">{html.escape(sub2)}</ins>')
            details.append(f"Missing from DB at index {i1}: {format_char_desc(sub2)}")
        elif tag == "replace":
            s1_parts.append(f'<del class="diff-del">{html.escape(sub1)}</del>')
            s2_parts.append(f'<ins class="diff-ins">{html.escape(sub2)}</ins>')
            details.append(f"Mismatch at index {i1}: DB has {format_char_desc(sub1)} vs API has {format_char_desc(sub2)}")

    return "".join(s1_parts), "".join(s2_parts), details


def classify_discrepancy(db_text: str, api_text: str, is_surah_header: bool = False) -> Tuple[str, str]:
    """
    Classifies the severity and category of a discrepancy:
    - CRITICAL: Word differences, added/missing letters or headers.
    - HARAKAT: Pure diacritic / vowel differences (fatha, damma, kasra, sukun, tanween).
    - ORTHOGRAPHIC: Tatweel (kashida), Unicode NFKD normalization, hamza style variations.
    - WAQF: Waqf mark differences.
    """
    if is_surah_header or "سورة" in db_text or "سُورَةُ" in db_text:
        return "CRITICAL", "Surah Header erroneously prepended to Ayah text"

    # Strip tatweel and zero-width
    db_no_tat = clean_zero_width(clean_tatweel(db_text))
    api_no_tat = clean_zero_width(clean_tatweel(api_text))

    if db_no_tat == api_no_tat:
        return "ORTHOGRAPHIC", "Kashida / Tatweel (ـ) count difference only"

    if normalize_nfkd(db_no_tat) == normalize_nfkd(api_no_tat):
        return "ORTHOGRAPHIC", "Unicode combining mark order / canonical equivalence (NFKD)"

    # Check without waqf marks
    db_no_waqf = normalize_nfkd(clean_waqf(db_no_tat))
    api_no_waqf = normalize_nfkd(clean_waqf(api_no_tat))

    if db_no_waqf == api_no_waqf:
        return "WAQF", "Waqf / pause symbol difference (ۖ ۗ ۚ ۛ ۜ)"

    # Check bare consonant skeleton (Rasm)
    db_rasm = normalize_nfc(clean_harakat(db_no_tat))
    api_rasm = normalize_nfc(clean_harakat(api_no_tat))

    # Normalize subtle hamza representations on yeh/teeth
    # In Warsh/Hafs, floating hamza above yeh vs yeh with hamza:
    norm_hamza = lambda t: t.replace("ئ", "ئ").replace("ىٔ", "ئ").replace("ء", "").replace("ٔ", "")
    if norm_hamza(db_rasm) == norm_hamza(api_rasm):
        # The consonants match! It's a Harakat or Hamza orthography difference
        # Check if bare consonants without hamza match
        if db_rasm == api_rasm:
            return "HARAKAT", "Diacritic / Tashkeel / Harakat difference"
        else:
            return "ORTHOGRAPHIC", "Hamza on Nabrah / Yeh orthographic representation"

    # If consonants differ significantly
    return "CRITICAL", "Consonant / Word / Letter text difference"


def audit_mushaf_database(
    flavor: str,
    db_path: Path,
    mushaf_id: int,
    cache_dir: Path,
    target_surah: Optional[int] = None,
    force_refresh: bool = False
) -> MushafAuditResult:
    """Performs a comprehensive multi-tier audit of a SQLite Quran database against the API."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # 1. Fetch API data
    api_mushaf = fetch_api_mushaf(mushaf_id, cache_dir, force_refresh)
    api_ayahs: Dict[Tuple[int, int], str] = {}
    api_surah_names: Dict[int, str] = {}
    api_surah_counts: Dict[int, int] = {}

    for s in api_mushaf.get("surahs", []):
        sid = int(s["id"])
        api_surah_names[sid] = s.get("name", f"Surah {sid}")
        ayah_list = s.get("ayahs", [])

        # Handle known API defect: Surah 16 (An-Nahl) in Warsh (mushaf 4)
        # In some API endpoints/responses, verses 123 & 124 are merged into one entry with inline marker '١٢٣'
        # Database correctly has 128 verses. We normalize the API dataset to separate them.
        if mushaf_id == 4 and sid == 16 and len(ayah_list) == 127:
            normalized_ayah_list = []
            for a in ayah_list:
                num = int(a["number"])
                text = a.get("text", "")
                if num < 123:
                    normalized_ayah_list.append(a)
                elif num == 123 and ("١٢٣" in text or "إِنَّمَا جُعِلَ" in text):
                    parts = re.split(r'ۖ?١٢٣\s*', text)
                    if len(parts) >= 2:
                        normalized_ayah_list.append({"number": 123, "text": parts[0].strip() + ("ۖ" if not parts[0].strip().endswith("ۖ") else "")})
                        normalized_ayah_list.append({"number": 124, "text": parts[1].strip()})
                    else:
                        normalized_ayah_list.append(a)
                else:
                    a_copy = dict(a)
                    a_copy["number"] = num + 1
                    normalized_ayah_list.append(a_copy)
            ayah_list = normalized_ayah_list

        api_surah_counts[sid] = len(ayah_list)
        for a in ayah_list:
            aid = int(a["number"])
            text = a.get("text", "")
            # Clean zero-width BOM if present in API
            text = clean_zero_width(text)
            api_ayahs[(sid, aid)] = text

    # 2. Query Local Database
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Get Surah names from local DB
    cur.execute("SELECT soraid, name FROM sora ORDER BY soraid")
    db_surah_names = {r[0]: r[1] for r in cur.fetchall()}

    # Internal checks
    internal_issues: List[InternalDbIssue] = []

    # Check for text != uthmanitext
    cur.execute("SELECT soraid, ayaid, text, uthmanitext FROM aya WHERE text != uthmanitext")
    for soraid, ayaid, txt, utxt in cur.fetchall():
        escaped_txt = txt.replace("'", "''")
        internal_issues.append(
            InternalDbIssue(
                sora_id=soraid,
                aya_id=ayaid,
                issue_type="TEXT_UTHMANITEXT_MISMATCH",
                details=f"text ({txt}) != uthmanitext ({utxt})",
                sql_fix=f"UPDATE aya SET uthmanitext = '{escaped_txt}' WHERE soraid = {soraid} AND ayaid = {ayaid};"
            )
        )

    # Check for empty or NULL texts
    cur.execute("SELECT soraid, ayaid FROM aya WHERE text IS NULL OR text = '' OR uthmanitext IS NULL")
    for soraid, ayaid in cur.fetchall():
        internal_issues.append(
            InternalDbIssue(
                sora_id=soraid,
                aya_id=ayaid,
                issue_type="NULL_OR_EMPTY_TEXT",
                details=f"Ayah {soraid}:{ayaid} has NULL or empty text"
            )
        )

    # Fetch ayahs to audit
    if target_surah:
        cur.execute("SELECT soraid, ayaid, text, uthmanitext FROM aya WHERE ayaid > 0 AND soraid = ? ORDER BY soraid, ayaid", (target_surah,))
    else:
        cur.execute("SELECT soraid, ayaid, text, uthmanitext FROM aya WHERE ayaid > 0 ORDER BY soraid, ayaid")
    db_rows = cur.fetchall()

    # Surah count mismatches
    surah_count_mismatches: List[Tuple[int, str, int, int]] = []
    for sid in range(1, 115):
        if target_surah and sid != target_surah:
            continue
        cur.execute("SELECT COUNT(*) FROM aya WHERE soraid = ? AND ayaid > 0", (sid,))
        db_cnt = cur.fetchone()[0]
        api_cnt = api_surah_counts.get(sid, 0)
        if db_cnt != api_cnt:
            s_name = db_surah_names.get(sid, f"سورة {sid}")
            surah_count_mismatches.append((sid, s_name, db_cnt, api_cnt))

    conn.close()

    # 3. Ayah-by-Ayah Multi-Tier Comparison
    exact_matches = 0
    normalized_matches = 0
    tatweel_only_diffs = 0
    nfkd_only_diffs = 0
    waqf_only_diffs = 0
    critical_diffs = 0
    harakat_diffs = 0
    orthographic_diffs = 0
    structural_diffs = len(surah_count_mismatches)
    discrepancies: List[DiffItem] = []

    for soraid, ayaid, db_text, uthmanitext in db_rows:
        api_text = api_ayahs.get((soraid, ayaid))
        sora_name = db_surah_names.get(soraid, f"سورة {soraid}")

        if api_text is None:
            # Missing in API (e.g. verse numbering offset)
            diff_item = DiffItem(
                sora_id=soraid,
                sora_name=sora_name,
                aya_id=ayaid,
                severity="STRUCTURAL",
                category_desc="Ayah missing in API (verse division difference)",
                db_text=db_text,
                api_text="[NOT FOUND IN API AT THIS AYAH NUMBER]",
                db_diff_highlight=html.escape(db_text),
                api_diff_highlight="<em>(None)</em>",
                details=["This ayah number does not exist in the API dataset for this Surah."]
            )
            discrepancies.append(diff_item)
            critical_diffs += 1
            continue

        if db_text == api_text:
            exact_matches += 1
            normalized_matches += 1
            continue

        # Check Tatweel only
        if clean_tatweel(db_text) == clean_tatweel(api_text):
            tatweel_only_diffs += 1
            normalized_matches += 1
            sev, cat = classify_discrepancy(db_text, api_text)
            orthographic_diffs += 1
        # Check NFKD normalization + Tatweel
        elif normalize_nfkd(clean_tatweel(db_text)) == normalize_nfkd(clean_tatweel(api_text)):
            nfkd_only_diffs += 1
            normalized_matches += 1
            sev, cat = classify_discrepancy(db_text, api_text)
            orthographic_diffs += 1
        # Check Waqf only
        elif normalize_nfkd(clean_waqf(clean_tatweel(db_text))) == normalize_nfkd(clean_waqf(clean_tatweel(api_text))):
            waqf_only_diffs += 1
            normalized_matches += 1
            sev, cat = classify_discrepancy(db_text, api_text)
            waqf_only_diffs += 1
        else:
            # Substantive discrepancy
            is_surah_header = (soraid == 9 and ayaid == 1 and "التَّوۡبَةِ" in db_text)
            sev, cat = classify_discrepancy(db_text, api_text, is_surah_header=is_surah_header)
            if sev == "CRITICAL":
                critical_diffs += 1
            elif sev == "HARAKAT":
                harakat_diffs += 1
            elif sev == "ORTHOGRAPHIC":
                orthographic_diffs += 1
            elif sev == "WAQF":
                waqf_only_diffs += 1

        db_hl, api_hl, details = generate_char_diff_highlights(db_text, api_text)
        diff_item = DiffItem(
            sora_id=soraid,
            sora_name=sora_name,
            aya_id=ayaid,
            severity=sev,
            category_desc=cat,
            db_text=db_text,
            api_text=api_text,
            db_diff_highlight=db_hl,
            api_diff_highlight=api_hl,
            details=details
        )
        discrepancies.append(diff_item)

    return MushafAuditResult(
        flavor=flavor,
        db_path=str(db_path),
        mushaf_id=mushaf_id,
        total_db_ayahs=len(db_rows),
        total_api_ayahs=len(api_ayahs),
        total_surahs=114 if not target_surah else 1,
        exact_matches=exact_matches,
        normalized_matches=normalized_matches,
        tatweel_only_diffs=tatweel_only_diffs,
        nfkd_only_diffs=nfkd_only_diffs,
        waqf_only_diffs=waqf_only_diffs,
        critical_diffs=critical_diffs,
        harakat_diffs=harakat_diffs,
        orthographic_diffs=orthographic_diffs,
        structural_diffs=structural_diffs,
        internal_issues=internal_issues,
        discrepancies=discrepancies,
        surah_count_mismatches=surah_count_mismatches
    )


# ----------------------------------------------------------------------
# Reports Generators (Console, Markdown, JSON, HTML, SQL)
# ----------------------------------------------------------------------

def print_console_summary(results: List[MushafAuditResult]) -> None:
    """Print an aesthetic, colored terminal summary."""
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.CYAN}       QURAN DATABASE VERIFICATION & AUDIT SUMMARY{Colors.RESET}")
    print(f"       Audited against Quranpedia API (api.quranpedia.net)")
    print("=" * 80)

    for res in results:
        exact_pct = (res.exact_matches / res.total_db_ayahs * 100) if res.total_db_ayahs else 0
        norm_pct = (res.normalized_matches / res.total_db_ayahs * 100) if res.total_db_ayahs else 0

        print(f"\n{Colors.BOLD}► Mushaf: {res.flavor.upper()} ({Path(res.db_path).name}){Colors.RESET}")
        print(f"  • Total DB Ayahs       : {res.total_db_ayahs:,}")
        print(f"  • Total API Ayahs      : {res.total_api_ayahs:,}")
        print(f"  • Exact Character Match: {Colors.GREEN if exact_pct > 95 else Colors.YELLOW}{res.exact_matches:,} ({exact_pct:.2f}%){Colors.RESET}")
        print(f"  • Normalized Match     : {Colors.GREEN}{res.normalized_matches:,} ({norm_pct:.2f}%){Colors.RESET}")
        print(f"  --------------------------------------------------")
        print(f"  • {Colors.RED if res.critical_diffs else Colors.GREEN}Critical Text Errors : {res.critical_diffs}{Colors.RESET}")
        print(f"  • {Colors.YELLOW if res.harakat_diffs else Colors.GREEN}Harakat/Vowel Diffs  : {res.harakat_diffs}{Colors.RESET}")
        print(f"  • Orthographic Diffs   : {res.orthographic_diffs} (Tatweel: {res.tatweel_only_diffs}, NFKD: {res.nfkd_only_diffs})")
        print(f"  • Waqf Symbol Diffs    : {res.waqf_only_diffs}")
        print(f"  • Verse Count Mismatches: {Colors.YELLOW if res.surah_count_mismatches else Colors.GREEN}{len(res.surah_count_mismatches)}{Colors.RESET}")
        print(f"  • Internal DB Issues   : {Colors.YELLOW if res.internal_issues else Colors.GREEN}{len(res.internal_issues)}{Colors.RESET}")

        if res.surah_count_mismatches:
            print(f"\n  {Colors.YELLOW}Surahs with Verse Count Differences:{Colors.RESET}")
            for sid, sname, db_c, api_c in res.surah_count_mismatches:
                print(f"    - Surah {sid} ({sname}): DB has {db_c} ayahs vs API has {api_c} ayahs (Δ {api_c - db_c:+d})")

        critical_items = [d for d in res.discrepancies if d.severity == "CRITICAL"]
        if critical_items:
            print(f"\n  {Colors.RED}{Colors.BOLD}Critical Discrepancies Details ({len(critical_items)}):{Colors.RESET}")
            for d in critical_items[:10]:
                print(f"    {Colors.RED}[{d.sora_id}:{d.aya_id}] {d.sora_name} - {d.category_desc}{Colors.RESET}")
                print(f"      DB : {d.db_text}")
                print(f"      API: {d.api_text}")

    print("\n" + "=" * 80 + "\n")


def generate_markdown_report(results: List[MushafAuditResult], output_file: Path) -> None:
    """Generate a comprehensive GitHub-flavored Markdown report."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# 📖 Quran Database Verification & Alignment Report\n")
    lines.append(f"**Audit Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Data Source:** [Quranpedia REST API](https://api.quranpedia.net)  \n")

    lines.append("## 📊 Executive Summary\n")
    lines.append("| Mushaf | Total Ayahs | Exact Match | Normalized Match | Critical Errors | Harakat Diffs | Orthographic | Waqf Diffs |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for res in results:
        exact_pct = (res.exact_matches / res.total_db_ayahs * 100) if res.total_db_ayahs else 0
        norm_pct = (res.normalized_matches / res.total_db_ayahs * 100) if res.total_db_ayahs else 0
        crit_badge = f"🔴 **{res.critical_diffs}**" if res.critical_diffs else "🟢 0"
        lines.append(
            f"| **{res.flavor.capitalize()}** (`{Path(res.db_path).name}`) | {res.total_db_ayahs:,} | "
            f"{res.exact_matches:,} ({exact_pct:.2f}%) | {res.normalized_matches:,} ({norm_pct:.2f}%) | "
            f"{crit_badge} | {res.harakat_diffs} | {res.orthographic_diffs} | {res.waqf_only_diffs} |"
        )
    lines.append("\n---\n")

    for res in results:
        lines.append(f"## 🔍 Detailed Analysis: {res.flavor.upper()} Mushaf\n")

        if res.internal_issues:
            lines.append("### ⚠️ Internal Database Consistency Issues\n")
            lines.append("| Surah | Ayah | Issue Type | Details |")
            lines.append("| :---: | :---: | :--- | :--- |")
            for issue in res.internal_issues:
                lines.append(f"| {issue.sora_id} | {issue.aya_id} | `{issue.issue_type}` | {issue.details} |")
            lines.append("\n")

        if res.surah_count_mismatches:
            lines.append("### 🔢 Verse Count / Division Differences\n")
            lines.append("| Surah # | Surah Name | Local DB Count | Quranpedia API Count | Difference |")
            lines.append("| :---: | :--- | :---: | :---: | :---: |")
            for sid, sname, db_c, api_c in res.surah_count_mismatches:
                lines.append(f"| {sid} | {sname} | {db_c} | {api_c} | {api_c - db_c:+d} |")
            lines.append("\n")

        critical_items = [d for d in res.discrepancies if d.severity == "CRITICAL"]
        if critical_items:
            lines.append("### 🚨 Critical Discrepancies Requiring Fix\n")
            for d in critical_items:
                lines.append(f"#### 📍 Surah {d.sora_id}:{d.aya_id} ({d.sora_name}) - `{d.category_desc}`\n")
                lines.append(f"- **Local DB:** `{d.db_text}`")
                lines.append(f"- **API Reference:** `{d.api_text}`")
                if d.details:
                    lines.append(f"- **Discrepancy Details:** {'; '.join(d.details)}")
                lines.append("")

        harakat_items = [d for d in res.discrepancies if d.severity == "HARAKAT"]
        if harakat_items:
            lines.append(f"### 🔤 Diacritic & Harakat Differences ({len(harakat_items)})\n")
            lines.append("<details><summary>Click to expand all Harakat differences</summary>\n\n")
            lines.append("| Surah | Ayah | Name | Local DB | Quranpedia API | Notes |")
            lines.append("| :---: | :---: | :--- | :--- | :--- | :--- |")
            for d in harakat_items:
                lines.append(f"| {d.sora_id} | {d.aya_id} | {d.sora_name} | `{d.db_text}` | `{d.api_text}` | {'; '.join(d.details[:2])} |")
            lines.append("\n</details>\n")

        lines.append("\n---\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Generated Markdown report: {output_file}")


def generate_json_report(results: List[MushafAuditResult], output_file: Path) -> None:
    """Export complete audit results as structured JSON."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "source_api": API_BASE_URL,
        "mushafs": [asdict(r) for r in results]
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Generated JSON report: {output_file}")


def generate_html_diff_viewer(results: List[MushafAuditResult], output_file: Path) -> None:
    """Generate an interactive, state-of-the-art HTML side-by-side diff viewer with filters."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    json_payload = json.dumps([asdict(r) for r in results], ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مقارنة وتدقيق نصوص المصحف الشريف | Tathbeet Quran Audit</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Amiri+Quran&family=Cairo:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #090d16;
            --bg-card: #111827;
            --bg-card-hover: #1f293d;
            --border: #1e293b;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.2);
            --green: #10b981;
            --green-bg: rgba(16, 185, 129, 0.15);
            --red: #ef4444;
            --red-bg: rgba(239, 68, 68, 0.2);
            --yellow: #f59e0b;
            --yellow-bg: rgba(245, 158, 11, 0.15);
            --purple: #a855f7;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Cairo', system-ui, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding-bottom: 4rem;
        }}

        .container {{
            max-width: 1280px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}

        /* Header */
        header {{
            text-align: center;
            margin-bottom: 2.5rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
            position: relative;
        }}
        header h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}
        header p {{
            color: var(--text-muted);
            font-size: 1rem;
        }}

        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2.5rem;
        }}
        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 1rem;
            padding: 1.25rem;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            transition: transform 0.2s, border-color 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            margin: 0.25rem 0;
        }}
        .stat-label {{
            color: var(--text-muted);
            font-size: 0.875rem;
            font-weight: 600;
        }}

        /* Filter Controls */
        .controls {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 1rem;
            padding: 1.25rem;
            margin-bottom: 2rem;
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: center;
            justify-content: space-between;
        }}
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        select, input {{
            background: #0d1117;
            border: 1px solid var(--border);
            color: var(--text);
            padding: 0.6rem 1rem;
            border-radius: 0.5rem;
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
        }}
        select:focus, input:focus {{
            border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }}

        /* Diff Cards */
        .diff-list {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }}
        .diff-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 1rem;
            overflow: hidden;
            transition: border-color 0.2s;
        }}
        .diff-card:hover {{
            border-color: #334155;
        }}
        .diff-card.critical {{ border-left: 4px solid var(--red); border-right: 4px solid var(--red); }}
        .diff-card.harakat {{ border-left: 4px solid var(--yellow); border-right: 4px solid var(--yellow); }}
        .diff-card.orthographic {{ border-left: 4px solid var(--accent); border-right: 4px solid var(--accent); }}
        .diff-card.waqf {{ border-left: 4px solid var(--purple); border-right: 4px solid var(--purple); }}

        .card-header {{
            padding: 1rem 1.25rem;
            background: rgba(255,255,255,0.02);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        .card-title {{
            font-weight: 700;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .badge {{
            font-size: 0.75rem;
            padding: 0.25rem 0.6rem;
            border-radius: 9999px;
            font-weight: 700;
            letter-spacing: 0.025em;
        }}
        .badge-critical {{ background: var(--red-bg); color: var(--red); }}
        .badge-harakat {{ background: var(--yellow-bg); color: var(--yellow); }}
        .badge-orthographic {{ background: var(--accent-glow); color: var(--accent); }}
        .badge-waqf {{ background: rgba(168, 85, 247, 0.2); color: var(--purple); }}
        .badge-flavor {{ background: #1e293b; color: #cbd5e1; }}

        .card-body {{
            padding: 1.25rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.25rem;
        }}
        @media (max-width: 768px) {{
            .card-body {{ grid-template-columns: 1fr; }}
        }}
        .diff-box {{
            background: #0a0e17;
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            padding: 1rem;
        }}
        .diff-box-title {{
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }}
        .quran-text {{
            font-family: 'Amiri Quran', serif;
            font-size: 1.5rem;
            line-height: 2.2;
            word-spacing: 4px;
        }}
        .diff-del {{
            background-color: rgba(239, 68, 68, 0.35);
            color: #fca5a5;
            text-decoration: none;
            padding: 0.1rem 0.25rem;
            border-radius: 0.25rem;
            border-bottom: 2px solid var(--red);
        }}
        .diff-ins {{
            background-color: rgba(16, 185, 129, 0.35);
            color: #6ee7b7;
            text-decoration: none;
            padding: 0.1rem 0.25rem;
            border-radius: 0.25rem;
            border-bottom: 2px solid var(--green);
        }}

        .card-footer {{
            padding: 0.75rem 1.25rem;
            background: rgba(0,0,0,0.2);
            border-top: 1px solid var(--border);
            font-size: 0.85rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>تدقيق ومطابقة قواعد بيانات القرآن الكريم</h1>
            <p>مقارنة شاملة مع مرجعية مجمع الملك فهد عبر منصة Quranpedia API (حفص وورش)</p>
        </header>

        <div class="stats-grid" id="statsGrid">
            <!-- Populated by JS -->
        </div>

        <div class="controls">
            <div class="filter-group">
                <label>الرواية:</label>
                <select id="flavorFilter" onchange="renderDiffs()">
                    <option value="all">الكل (حفص وورش)</option>
                    <option value="hafs">مصحف حفص</option>
                    <option value="warsh">مصحف ورش</option>
                </select>
            </div>
            <div class="filter-group">
                <label>مستوى الاختلاف:</label>
                <select id="severityFilter" onchange="renderDiffs()">
                    <option value="all">جميع المستويات</option>
                    <option value="CRITICAL">🔴 حرج (أخطاء نصية / زيادة أو نقص)</option>
                    <option value="HARAKAT">🟡 حركات وتشكيل</option>
                    <option value="ORTHOGRAPHIC">🔵 رسم / كشيدة / همزات</option>
                    <option value="WAQF">🟣 علامات وقف</option>
                </select>
            </div>
            <div class="filter-group">
                <input type="text" id="searchInput" placeholder="بحث برقم السورة، الآية، أو النص..." oninput="renderDiffs()">
            </div>
        </div>

        <div class="diff-list" id="diffList">
            <!-- Populated by JS -->
        </div>
    </div>

    <script>
        const auditData = {json_payload};

        function initStats() {{
            const grid = document.getElementById('statsGrid');
            let totalAyahs = 0;
            let exactMatches = 0;
            let criticalDiffs = 0;
            let harakatDiffs = 0;

            auditData.forEach(r => {{
                totalAyahs += r.total_db_ayahs;
                exactMatches += r.exact_matches;
                criticalDiffs += r.critical_diffs;
                harakatDiffs += r.harakat_diffs;
            }});

            const exactPct = (exactMatches / totalAyahs * 100).toFixed(2);

            grid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">إجمالي الآيات المفحوصة</div>
                    <div class="stat-value" style="color: var(--accent);">${{totalAyahs.toLocaleString()}}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">تطابق تام (Exact Match)</div>
                    <div class="stat-value" style="color: var(--green);">${{exactPct}}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">أخطاء حرجة (Critical Fixes)</div>
                    <div class="stat-value" style="color: var(--red);">${{criticalDiffs}}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">فروق حركات وتشكيل</div>
                    <div class="stat-value" style="color: var(--yellow);">${{harakatDiffs}}</div>
                </div>
            `;
        }}

        function renderDiffs() {{
            const flavor = document.getElementById('flavorFilter').value;
            const severity = document.getElementById('severityFilter').value;
            const search = document.getElementById('searchInput').value.trim().toLowerCase();
            const list = document.getElementById('diffList');

            let allDiffs = [];
            auditData.forEach(m => {{
                if (flavor !== 'all' && m.flavor !== flavor) return;
                m.discrepancies.forEach(d => {{
                    allDiffs.push({{ ...d, flavor: m.flavor }});
                }});
            }});

            const filtered = allDiffs.filter(d => {{
                if (severity !== 'all' && d.severity !== severity) return false;
                if (search) {{
                    const matchSurah = d.sora_id.toString().includes(search);
                    const matchAyah = d.aya_id.toString().includes(search);
                    const matchName = d.sora_name.toLowerCase().includes(search);
                    const matchText = d.db_text.includes(search) || d.api_text.includes(search);
                    if (!matchSurah && !matchAyah && !matchName && !matchText) return false;
                }}
                return true;
            }});

            if (filtered.length === 0) {{
                list.innerHTML = `
                    <div style="text-align: center; padding: 3rem; background: var(--bg-card); border-radius: 1rem; color: var(--green);">
                        <h3>✨ لا توجد فروق تطابق هذا الفلتر!</h3>
                    </div>
                `;
                return;
            }}

            list.innerHTML = filtered.map(d => `
                <div class="diff-card ${{d.severity.toLowerCase()}}">
                    <div class="card-header">
                        <div class="card-title">
                            <span>سورة ${{d.sora_name}} (${{d.sora_id}} : ${{d.aya_id}})</span>
                            <span class="badge badge-${{d.severity.toLowerCase()}}">${{d.severity}}</span>
                            <span class="badge badge-flavor">${{d.flavor.toUpperCase()}}</span>
                        </div>
                        <div style="font-size: 0.85rem; color: var(--text-muted);">${{d.category_desc}}</div>
                    </div>
                    <div class="card-body">
                        <div class="diff-box">
                            <div class="diff-box-title">قاعدة البيانات المحلية (Local Database)</div>
                            <div class="quran-text">${{d.db_diff_highlight}}</div>
                        </div>
                        <div class="diff-box">
                            <div class="diff-box-title">مرجعية Quranpedia API (King Fahd Complex)</div>
                            <div class="quran-text">${{d.api_diff_highlight}}</div>
                        </div>
                    </div>
                    ${{d.details && d.details.length > 0 ? `
                        <div class="card-footer">
                            🔍 تفاصيل الاختلاف: ${{d.details.join(' | ')}}
                        </div>
                    ` : ''}}
                </div>
            `).join('');
        }}

        initStats();
        renderDiffs();
    </script>
</body>
</html>
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Generated HTML Visual Diff Viewer: {output_file}")


def generate_sql_fix_script(results: List[MushafAuditResult], output_file: Path) -> None:
    """Generate transactional SQL fix script to patch verified database bugs."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("-- ========================================================")
    lines.append("-- AUTOMATED QURAN DATABASE FIX MIGRATION")
    lines.append(f"-- Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("-- Audited against Quranpedia REST API (King Fahd Complex)")
    lines.append("-- ========================================================\n")

    for res in results:
        lines.append(f"-- ========================================================")
        lines.append(f"-- FIXES FOR {res.flavor.upper()} DATABASE ({Path(res.db_path).name})")
        lines.append(f"-- ========================================================")
        lines.append("BEGIN TRANSACTION;\n")

        # 1. Fix Surah 9:1 Header concatanation bug in Hafs
        if res.flavor == "hafs":
            lines.append("-- 1. Fix Surah At-Tawbah 9:1 (Remove concatenated surah title header)")
            lines.append("UPDATE aya")
            lines.append("SET text = 'بَرَآءَةٞ مِّنَ ٱللَّهِ وَرَسُولِهِۦٓ إِلَى ٱلَّذِينَ عَٰهَدتُّم مِّنَ ٱلۡمُشۡرِكِينَ',")
            lines.append("    uthmanitext = 'بَرَآءَةٞ مِّنَ ٱللَّهِ وَرَسُولِهِۦٓ إِلَى ٱلَّذِينَ عَٰهَدتُّم مِّنَ ٱلۡمُشۡرِكِينَ'")
            lines.append("WHERE soraid = 9 AND ayaid = 1;\n")

        # 2. Internal consistency fixes (e.g. text != uthmanitext)
        if res.internal_issues:
            lines.append("-- 2. Fix internal text vs uthmanitext inconsistencies")
            for issue in res.internal_issues:
                if issue.sql_fix:
                    lines.append(issue.sql_fix)
            lines.append("")

        lines.append("COMMIT;\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ Generated SQL Fix Migration: {output_file}")


# ----------------------------------------------------------------------
# Main CLI Entry Point
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verify and audit local Quran SQLite databases against Quranpedia API."
    )
    parser.add_argument(
        "--db",
        choices=["hafs", "warsh", "all"],
        default="all",
        help="Specify which database to audit (default: all)"
    )
    parser.add_argument(
        "--surah",
        type=int,
        default=None,
        help="Audit only a specific Surah number (1-114)"
    )
    parser.add_argument(
        "--format",
        choices=["console", "md", "json", "html", "all"],
        default="all",
        help="Output report formats (default: all)"
    )
    parser.add_argument(
        "--generate-sql",
        action="store_true",
        default=True,
        help="Generate SQL fix migration script (default: True)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force fresh download from Quranpedia API instead of using cache"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save generated reports (default: quran_challenge/reports)"
    )

    args = parser.parse_args()

    # Paths resolution
    base_dir = Path(__file__).resolve().parent.parent
    db_dir = base_dir / "databases"
    cache_dir = db_dir / ".cache"
    reports_dir = Path(args.output_dir) if args.output_dir else base_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    flavors_to_audit = ["hafs", "warsh"] if args.db == "all" else [args.db]
    results: List[MushafAuditResult] = []

    print(f"{Colors.BOLD}{Colors.CYAN}🚀 Starting Quran Database Verification Suite...{Colors.RESET}")
    print(f"📁 Database directory : {db_dir}")
    print(f"🌐 Remote API source  : {API_BASE_URL}")
    print(f"📑 Output directory   : {reports_dir}\n")

    for flavor in flavors_to_audit:
        db_file = db_dir / f"{flavor}.sqlite"
        mushaf_id = MUSHAF_IDS[flavor]
        print(f"⏳ Auditing {flavor.upper()} (mushaf_id: {mushaf_id}) from {db_file.name}...")

        try:
            res = audit_mushaf_database(
                flavor=flavor,
                db_path=db_file,
                mushaf_id=mushaf_id,
                cache_dir=cache_dir,
                target_surah=args.surah,
                force_refresh=args.no_cache
            )
            results.append(res)
        except Exception as e:
            print(f"{Colors.RED}❌ Error auditing {flavor}: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()

    # Generate Reports
    if args.format in ["console", "all"]:
        print_console_summary(results)

    if args.format in ["md", "all"]:
        md_path = reports_dir / "quran_alignment_report.md"
        generate_markdown_report(results, md_path)

    if args.format in ["json", "all"]:
        json_path = reports_dir / "quran_alignment_report.json"
        generate_json_report(results, json_path)

    if args.format in ["html", "all"]:
        html_path = reports_dir / "quran_diff_viewer.html"
        generate_html_diff_viewer(results, html_path)

    if args.generate_sql:
        sql_path = db_dir / "fix_quran_discrepancies.sql"
        generate_sql_fix_script(results, sql_path)

    print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 Verification audit completed successfully!{Colors.RESET}\n")


if __name__ == "__main__":
    main()
