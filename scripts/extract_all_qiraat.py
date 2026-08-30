#!/usr/bin/env python3
"""
Quran Qira'at SQLite Extractor & Generator
=========================================
Extracts and builds pristine SQLite databases for all 8 major Qira'at / Riwayat
from King Fahd Glorious Quran Printing Complex (KFGQPC via Quranpedia API):

1. Hafs ('an 'Asim)        - حفص عن عاصم (الكوفي)
2. Warsh ('an Nafi')       - ورش عن نافع (المدني الأخير)
3. Qaloon ('an Nafi')      - قالون عن نافع (المدني الأخير)
4. Al-Duri ('an Abi 'Amr)  - الدوري عن أبي عمرو (المدني الأول / البصري)
5. Al-Susi ('an Abi 'Amr)  - السوسي عن أبي عمرو (البصري)
6. Shu'bah ('an 'Asim)     - شعبة عن عاصم (الكوفي)
7. Al-Bazzi ('an Ibn Kathir)- البزي عن ابن كثير (المكي)
8. Qunbul ('an Ibn Kathir) - قنبل عن ابن كثير (المكي)

Schema matches Tathbeet SQLite specification (aya, sora, ayatafseer).
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HEADERS = {"User-Agent": "TathbeetQiraatExtractor/1.0"}

QIRAAT_CONFIG = [
    {
        "code": "hafs",
        "api_id": 2,
        "name_ar": "حفص عن عاصم",
        "name_en": "Hafs 'an 'Asim",
        "count_name": "الكوفي",
        "db_filename": "hafs.sqlite",
    },
    {
        "code": "warsh",
        "api_id": 4,
        "name_ar": "ورش عن نافع",
        "name_en": "Warsh 'an Nafi'",
        "count_name": "المدني الأخير",
        "db_filename": "warsh.sqlite",
    },
    {
        "code": "qaloon",
        "api_id": 7,
        "name_ar": "قالون عن نافع",
        "name_en": "Qaloon 'an Nafi'",
        "count_name": "المدني الأخير",
        "db_filename": "qaloon.sqlite",
    },
    {
        "code": "shubah",
        "api_id": 9,
        "name_ar": "شعبة عن عاصم",
        "name_en": "Shu'bah 'an 'Asim",
        "count_name": "الكوفي",
        "db_filename": "shubah.sqlite",
    },
    {
        "code": "duri",
        "api_id": 6,
        "name_ar": "الدوري عن أبي عمرو",
        "name_en": "Al-Duri 'an Abi 'Amr",
        "count_name": "المدني الأول / البصري",
        "db_filename": "duri.sqlite",
    },
    {
        "code": "susi",
        "api_id": 10,
        "name_ar": "السوسي عن أبي عمرو",
        "name_en": "Al-Susi 'an Abi 'Amr",
        "count_name": "البصري",
        "db_filename": "susi.sqlite",
    },
    {
        "code": "bazzi",
        "api_id": 5,
        "name_ar": "البزي عن ابن كثير",
        "name_en": "Al-Bazzi 'an Ibn Kathir",
        "count_name": "المكي",
        "db_filename": "bazzi.sqlite",
    },
    {
        "code": "qunbul",
        "api_id": 8,
        "name_ar": "قنبل عن ابن كثير",
        "name_en": "Qunbul 'an Ibn Kathir",
        "count_name": "المكي",
        "db_filename": "qunbul.sqlite",
    },
]

# Standard Surah metadata table: (soraid, name, name_english, place: 1=Makki, 2=Madani)
SURA_METADATA = [
    (1, 'الفاتحة', 'Surat Al-Fatiha', 1),
    (2, 'البقرة', 'Surat Al-Baqara', 2),
    (3, 'آل عمران', 'Surat Ali \'Imran', 2),
    (4, 'النساء', 'Surat An-Nisa', 2),
    (5, 'المائدة', 'Surat Al-Ma\'ida', 2),
    (6, 'الأنعام', 'Surat Al-An\'am', 1),
    (7, 'الأعراف', 'Surat Al-A\'raf', 1),
    (8, 'الأنفال', 'Surat Al-Anfal', 2),
    (9, 'التوبة', 'Surat At-Tawba', 2),
    (10, 'يونس', 'Surat Yunus', 1),
    (11, 'هود', 'Surat Hud', 1),
    (12, 'يوسف', 'Surat Yusuf', 1),
    (13, 'الرعد', 'Surat Ar-Ra\'d', 2),
    (14, 'إبراهيم', 'Surat Ibrahim', 1),
    (15, 'الحجر', 'Surat Al-Hijr', 1),
    (16, 'النحل', 'Surat An-Nahl', 1),
    (17, 'الإسراء', 'Surat Al-Isra', 1),
    (18, 'الكهف', 'Surat Al-Kahf', 1),
    (19, 'مريم', 'Surat Maryam', 1),
    (20, 'طه', 'Surat Taha', 1),
    (21, 'الأنبياء', 'Surat Al-Anbiya', 1),
    (22, 'الحج', 'Surat Al-Hajj', 2),
    (23, 'المؤمنون', 'Surat Al-Mu\'minun', 1),
    (24, 'النور', 'Surat An-Nur', 2),
    (25, 'الفرقان', 'Surat Al-Furqan', 1),
    (26, 'الشعراء', 'Surat Ash-Shu\'ara', 1),
    (27, 'النمل', 'Surat An-Naml', 1),
    (28, 'القصص', 'Surat Al-Qasas', 1),
    (29, 'العنكبوت', 'Surat Al-\'Ankabut', 1),
    (30, 'الروم', 'Surat Ar-Rum', 1),
    (31, 'لقمان', 'Surat Luqman', 1),
    (32, 'السجدة', 'Surat As-Sajda', 1),
    (33, 'الأحزاب', 'Surat Al-Ahzab', 2),
    (34, 'سبإ', 'Surat Saba', 1),
    (35, 'فاطر', 'Surat Fatir', 1),
    (36, 'يس', 'Surat Ya-Sin', 1),
    (37, 'الصافات', 'Surat As-Saffat', 1),
    (38, 'ص', 'Surat Sad', 1),
    (39, 'الزمر', 'Surat Az-Zumar', 1),
    (40, 'غافر', 'Surat Ghafir', 1),
    (41, 'فصلت', 'Surat Fussilat', 1),
    (42, 'الشورى', 'Surat Ash-Shura', 1),
    (43, 'الزخرف', 'Surat Az-Zukhruf', 1),
    (44, 'الدخان', 'Surat Ad-Dukhan', 1),
    (45, 'الجاثية', 'Surat Al-Jathiya', 1),
    (46, 'الأحقاف', 'Surat Al-Ahqaf', 1),
    (47, 'محمد', 'Surat Muhammad', 2),
    (48, 'الفتح', 'Surat Al-Fath', 2),
    (49, 'الحجرات', 'Surat Al-Hujurat', 2),
    (50, 'ق', 'Surat Qaf', 1),
    (51, 'الذاريات', 'Surat Adh-Dhariyat', 1),
    (52, 'الطور', 'Surat At-Tur', 1),
    (53, 'النجم', 'Surat An-Najm', 1),
    (54, 'القمر', 'Surat Al-Qamar', 1),
    (55, 'الرحمن', 'Surat Ar-Rahman', 2),
    (56, 'الواقعة', 'Surat Al-Waqi\'a', 1),
    (57, 'الحديد', 'Surat Al-Hadid', 2),
    (58, 'المجادلة', 'Surat Al-Mujadila', 2),
    (59, 'الحشر', 'Surat Al-Hashr', 2),
    (60, 'الممتحنة', 'Surat Al-Mumtahana', 2),
    (61, 'الصف', 'Surat As-Saff', 2),
    (62, 'الجمعة', 'Surat Al-Jumu\'a', 2),
    (63, 'المنافقون', 'Surat Al-Munafiqun', 2),
    (64, 'التغابن', 'Surat At-Taghabun', 2),
    (65, 'الطلاق', 'Surat At-Talaq', 2),
    (66, 'التحريم', 'Surat At-Tahrim', 2),
    (67, 'الملك', 'Surat Al-Mulk', 1),
    (68, 'القلم', 'Surat Al-Qalam', 1),
    (69, 'الحاقة', 'Surat Al-Haqqa', 1),
    (70, 'المعارج', 'Surat Al-Ma\'arij', 1),
    (71, 'نوح', 'Surat Nuh', 1),
    (72, 'الجن', 'Surat Al-Jinn', 1),
    (73, 'المزمل', 'Surat Al-Muzzammil', 1),
    (74, 'المدثر', 'Surat Al-Muddaththir', 1),
    (75, 'القيامة', 'Surat Al-Qiyama', 1),
    (76, 'الإنسان', 'Surat Al-Insan', 2),
    (77, 'المرسلات', 'Surat Al-Mursalat', 1),
    (78, 'النبإ', 'Surat An-Naba', 1),
    (79, 'النازعات', 'Surat An-Nazi\'at', 1),
    (80, 'عبس', 'Surat \'Abasa', 1),
    (81, 'التكوير', 'Surat At-Takwir', 1),
    (82, 'الانفطار', 'Surat Al-Infitar', 1),
    (83, 'المطففين', 'Surat Al-Mutaffifin', 1),
    (84, 'الانشقاق', 'Surat Al-Inshiqaq', 1),
    (85, 'البروج', 'Surat Al-Buruj', 1),
    (86, 'الطارق', 'Surat At-Tariq', 1),
    (87, 'الأعلى', 'Surat Al-A\'la', 1),
    (88, 'الغاشية', 'Surat Al-Ghashiya', 1),
    (89, 'الفجر', 'Surat Al-Fajr', 1),
    (90, 'البلد', 'Surat Al-Balad', 1),
    (91, 'الشمس', 'Surat Ash-Shams', 1),
    (92, 'الليل', 'Surat Al-Layl', 1),
    (93, 'الضحى', 'Surat Ad-Duha', 1),
    (94, 'الشرح', 'Surat Ash-Sharh', 1),
    (95, 'التين', 'Surat At-Tin', 1),
    (96, 'العلق', 'Surat Al-\'Alaq', 1),
    (97, 'القدر', 'Surat Al-Qadr', 1),
    (98, 'البينة', 'Surat Al-Bayyina', 2),
    (99, 'الزلزلة', 'Surat Az-Zalzala', 2),
    (100, 'العاديات', 'Surat Al-\'Adiyat', 1),
    (101, 'القارعة', 'Surat Al-Qari\'a', 1),
    (102, 'التكاثر', 'Surat At-Takathur', 1),
    (103, 'العصر', 'Surat Al-\'Asr', 1),
    (104, 'الهمزة', 'Surat Al-Humaza', 1),
    (105, 'الفيل', 'Surat Al-Fil', 1),
    (106, 'قريش', 'Surat Quraysh', 1),
    (107, 'الماعون', 'Surat Al-Ma\'un', 1),
    (108, 'الكوثر', 'Surat Al-Kawthar', 1),
    (109, 'الكافرون', 'Surat Al-Kafirun', 1),
    (110, 'النصر', 'Surat An-Nasr', 2),
    (111, 'المسد', 'Surat Al-Masad', 1),
    (112, 'الإخلاص', 'Surat Al-Ikhlas', 1),
    (113, 'الفلق', 'Surat Al-Falaq', 1),
    (114, 'الناس', 'Surat An-Nas', 1),
]


def clean_searchtext(text: str) -> str:
    """Converts Uthmanic Arabic text to clean, searchable Imla'i text."""
    if not text:
        return ""
    # Replace special Uthmanic letters before stripping
    text = text.replace("ٱ", "ا")
    text = text.replace("ءَا", "آ").replace("ءَام", "آم").replace("ءَات", "آت").replace("ءَاخ", "آخ")
    text = text.replace("ءَال", "آل").replace("ءَاي", "آي").replace("ءَان", "آن").replace("ءَاد", "آد")
    text = text.replace("ءَأ", "أأ").replace("ءَإ", "أإ")
    # Common Quranic superscript alif words
    text = text.replace("الرَّحۡمَٰنِ", "الرحمن").replace("اَ۬لرَّحْمَٰنِ", "الرحمن").replace("ٱلرَّحۡمَٰنِ", "الرحمن")
    text = text.replace("ذَٰلِكَ", "ذلك").replace("هَٰذَا", "هذا").replace("هَٰذِهِ", "هذه").replace("هَٰؤُلَآءِ", "هؤلاء")
    text = text.replace("أُوْلَٰٓئِكَ", "أولئك").replace("أُوْلَٰئِكَ", "أولئك").replace("وَلَٰكِن", "ولكن")
    text = text.replace("صَلَوٰةَ", "صلاة").replace("ٱلصَّلَوٰةَ", "الصلاة").replace("اَ۬لصَّلَوٰةَ", "الصلاة")
    text = text.replace("زَكَوٰةَ", "زكاة").replace("ٱلزَّكَوٰةَ", "الزكاة").replace("اُ۬لزَّكَوٰةَ", "الزكاة")
    text = text.replace("حَيَوٰةَ", "حياة").replace("ٱلۡحَيَوٰةَ", "الحياة").replace("اُ۬لْحَيَوٰةَ", "الحياة")
    # General superscript mapping
    text = text.replace("وٰ", "ا")
    text = text.replace("ىٰ", "ى")
    text = text.replace("ٰ", "ا")
    text = text.replace("ۥ", "و").replace("ۦ", "ي")
    # Strip Tashkeel & Harakat
    text = re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u06DF-\u06E8\u08F0-\u08F2]", "", text)
    # Remove Tatweel
    text = text.replace("\u0640", "")
    # Remove special marks, bidi, zero-width
    text = re.sub(r"[\u200b-\u200f\ufeff\u061c\u200e\u200f۞۩]", "", text)
    # Normalize Alef forms
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_mushaf_json(api_id: int, cache_dir: Path) -> Dict[str, Any]:
    """Fetch and cache Mushaf JSON from Quranpedia API."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"mushaf_{api_id}.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)

    url = f"https://api.quranpedia.net/v1/mushafs/{api_id}"
    print(f"  🌐 Downloading dataset from {url}...")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def create_sqlite_database(qiraa_cfg: Dict[str, Any], raw_data: Dict[str, Any], output_path: Path) -> int:
    """Builds a pristine SQLite database matching Tathbeet schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    cur = conn.cursor()

    # 1. Create Tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS "aya" (
        "soraid"      INTEGER NOT NULL,
        "ayaid"       INTEGER NOT NULL,
        "quarter"     INTEGER,
        "hezb"        INTEGER,
        "joza"        INTEGER,
        "text"        TEXT,
        "uthmanitext" TEXT,
        "searchtext"  TEXT,
        "page"        INTEGER,
        PRIMARY KEY(soraid, ayaid)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS "sora" (
        "soraid"       INTEGER NOT NULL,
        "name"         TEXT,
        "name_english" TEXT,
        "place"        INTEGER,
        PRIMARY KEY(soraid)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS "ayatafseer" (
        "soraid"  INTEGER NOT NULL,
        "ayaid"   INTEGER NOT NULL,
        "tafseer" TEXT,
        PRIMARY KEY(soraid, ayaid)
    );
    """)

    # 2. Insert Sora metadata
    cur.executemany("INSERT INTO sora (soraid, name, name_english, place) VALUES (?, ?, ?, ?)", SURA_METADATA)

    # 3. Process Ayahs
    surahs = raw_data.get("surahs", [])
    total_inserted = 0

    current_quarter = 1
    current_hezb = 1
    current_juz = 1

    for surah in surahs:
        soraid = int(surah["id"])
        s_ayahs = surah.get("ayahs", [])

        # Fix known 123-124 merge in Surah An-Nahl (16) if present
        if soraid == 16 and len(s_ayahs) == 127:
            new_ayahs = []
            for item in s_ayahs:
                t = item.get("text", "")
                if "١٢٣" in t:
                    parts = t.split("١٢٣")
                    new_ayahs.append({**item, "text": parts[0].strip()})
                    new_ayahs.append({**item, "text": parts[1].strip()})
                else:
                    new_ayahs.append(item)
            s_ayahs = new_ayahs

        # Fix Surah Al-Mulk (67) for Warsh/Madani count (split verse 9 into 9 and 10 if 30 verses)
        if soraid == 67 and len(s_ayahs) == 30 and qiraa_cfg["code"] in ["warsh", "qaloon"]:
            new_ayahs = []
            for idx, item in enumerate(s_ayahs):
                if idx == 8: # Verse 9
                    t = item.get("text", "")
                    if "فَكَذَّبْنَا" in t or "فَكَذَّبۡنَا" in t:
                        p1, p2 = re.split(r"(?<=بَشِيرٞۖ|بَشِيرٌۖ|نَذِيرٞۖ|نَذِيرٌۖ)", t, maxsplit=1) if ("نَذِير" in t or "بَشِير" in t) else (t, "")
                        if p2:
                            new_ayahs.append({**item, "text": p1.strip()})
                            new_ayahs.append({**item, "text": p2.strip()})
                        else:
                            new_ayahs.append(item)
                    else:
                        new_ayahs.append(item)
                else:
                    new_ayahs.append(item)
            if len(new_ayahs) == 31:
                s_ayahs = new_ayahs

        # Add Bismillah header (ayaid = 0) for all surahs except Surah 9 (At-Tawbah)
        if soraid != 9:
            bismillah_text = "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ"
            cur.execute("""
            INSERT INTO aya (soraid, ayaid, quarter, hezb, joza, text, uthmanitext, searchtext, page)
            VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?)
            """, (soraid, current_quarter, current_hezb, current_juz, bismillah_text, bismillah_text, "بسم الله الرحمن الرحيم", 1))

        # Insert regular ayahs
        for idx, a_data in enumerate(s_ayahs):
            ayaid = idx + 1
            raw_text = a_data.get("text", "").strip()

            # Clean Surah 9:1 header if accidentally prepended
            if soraid == 9 and ayaid == 1 and raw_text.startswith("سُورَةُ التَّوۡبَةِ"):
                raw_text = raw_text.replace("سُورَةُ التَّوۡبَةِ", "").strip()

            page_num = a_data.get("page_number", 1)
            juz_num = a_data.get("juz", current_juz)
            hezb_num = a_data.get("hizb", current_hezb)

            if juz_num: current_juz = juz_num
            if hezb_num: current_hezb = hezb_num

            # Calculate quarter (rub')
            rub_num = (current_hezb - 1) * 4 + 1
            st_text = clean_searchtext(raw_text)

            cur.execute("""
            INSERT INTO aya (soraid, ayaid, quarter, hezb, joza, text, uthmanitext, searchtext, page)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (soraid, ayaid, rub_num, current_hezb, current_juz, raw_text, raw_text, st_text, page_num))
            total_inserted += 1

    conn.commit()
    conn.close()
    return total_inserted


def main():
    parser = argparse.ArgumentParser(description="Extract all Qira'at into pristine SQLite databases")
    parser.add_argument("--qiraa", default="all", help="Specific Qira'ah code or 'all'")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    cache_dir = base_dir / "databases" / ".cache" / "qiraat_raw"
    output_dir = base_dir / "databases"
    verifier_db_dir = Path("/Users/m97chahboun/Development/quran-database-verifier/databases")

    targets = QIRAAT_CONFIG if args.qiraa == "all" else [c for c in QIRAAT_CONFIG if c["code"] == args.qiraa]

    print("=" * 75)
    print("🚀 QURAN QIRA'AT SQLITE EXTRACTION & GENERATION SUITE")
    print("=" * 75)
    print(f"📁 Output Directory : {output_dir}")
    print(f"📦 Total Qira'at     : {len(targets)}\n")

    summary = []
    for cfg in targets:
        print(f"⏳ Processing {cfg['name_ar']} ({cfg['name_en']})...")
        raw_json = fetch_mushaf_json(cfg["api_id"], cache_dir)
        db_file = output_dir / cfg["db_filename"]

        count = create_sqlite_database(cfg, raw_json, db_file)

        # Copy to quran-database-verifier if directory exists
        if verifier_db_dir.exists():
            verifier_file = verifier_db_dir / cfg["db_filename"]
            import shutil
            shutil.copy2(str(db_file), str(verifier_file))

        print(f"  ✅ Built {cfg['db_filename']} with {count:,} ayahs ({cfg['count_name']})")
        summary.append({
            "name": cfg["name_ar"],
            "english": cfg["name_en"],
            "file": cfg["db_filename"],
            "ayahs": count,
            "count": cfg["count_name"]
        })

    print("\n" + "=" * 75)
    print("       QIRA'AT EXTRACTION COMPLETED SUCCESSFULLY")
    print("=" * 75)
    for s in summary:
        print(f"► {s['name']:<25} | {s['file']:<16} | {s['ayahs']:,} Ayahs ({s['count']})")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
