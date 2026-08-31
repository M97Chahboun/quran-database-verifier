# 📖 Quran Database Verifier & Multi-Qira'at Suite
### أداة التحقق والمطابقة واستخراج قواعد بيانات القراءات القرآنية (SQLite)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite3-green.svg)](https://www.sqlite.org/)
[![Qira'at](https://img.shields.io/badge/Qira'at%20Count-8%20Riwayat-purple.svg)]()
[![Hafs Alignment](https://img.shields.io/badge/Hafs%20Alignment-100.00%25-brightgreen.svg)]()
[![Warsh Alignment](https://img.shields.io/badge/Warsh%20Alignment-100.00%25-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An open-source audit, verification, extraction, and multi-source consensus benchmark toolkit providing **pristine, 100% audited SQLite databases** for the **8 major Quranic recitations (القراءات والروايات القرآنية)** with authentic Uthmanic text directly from the **King Fahd Glorious Quran Printing Complex (مجمع الملك فهد لطباعة المصحف الشريف بالمدينة المنورة)**.

---

## 🌟 Available Qira'at & Riwayat Databases

All databases are structured with identical schema (`aya`, `sora`, `ayatafseer`), complete with Tashkeel, clean Imla'i search text, Surah metadata, and Bismillah headers:

| # | Riwayah (الرواية) | Reader (القارئ) | Database File | Total Ayahs | Counting Method (العدّ) | Status |
| :-: | :--- | :--- | :--- | :---: | :---: | :---: |
| 1 | **حفص عن عاصم** | عاصم بن أبي النَّجود الكوفي | [`databases/hafs.sqlite`](databases/hafs.sqlite) | **6,236** | الكوفي | 🏆 **100.00% Exact Match** |
| 2 | **ورش عن نافع** | نافع بن عبد الرحمن المدني | [`databases/warsh.sqlite`](databases/warsh.sqlite) | **6,214** | المدني الأخير | 🏆 **100.00% Exact Match** |
| 3 | **قالون عن نافع** | نافع بن عبد الرحمن المدني | [`databases/qaloon.sqlite`](databases/qaloon.sqlite) | **6,214** | المدني الأخير | ✅ Extracted & Verified |
| 4 | **شعبة عن عاصم** | عاصم بن أبي النَّجود الكوفي | [`databases/shubah.sqlite`](databases/shubah.sqlite) | **6,236** | الكوفي | ✅ Extracted & Verified |
| 5 | **الدوري عن أبي عمرو** | أبو عمرو بن العلاء البصري | [`databases/duri.sqlite`](databases/duri.sqlite) | **6,218** | المدني الأول / البصري | ✅ Extracted & Verified |
| 6 | **السوسي عن أبي عمرو** | أبو عمرو بن العلاء البصري | [`databases/susi.sqlite`](databases/susi.sqlite) | **6,217** | البصري | ✅ Extracted & Verified |
| 7 | **البزي عن ابن كثير** | عبد الله بن كثير المكي | [`databases/bazzi.sqlite`](databases/bazzi.sqlite) | **6,221** | المكي | ✅ Extracted & Verified |
| 8 | **قنبل عن ابن كثير** | عبد الله بن كثير المكي | [`databases/qunbul.sqlite`](databases/qunbul.sqlite) | **6,221** | المكي | ✅ Extracted & Verified |

---

## 📊 Benchmark & Certification Summary

Audited against the official King Fahd Complex (KFGQPC) digital datasets:

| Mushaf | Recitation Standard | Total Ayahs | Character Match | Normalized Match | Critical Errors | Harakat Errors |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`hafs.sqlite`** | حفص عن عاصم (Kufi Standard) | **6,236** | **6,236 (100.00%)** | **6,236 (100.00%)** | **0** | **0** |
| **`warsh.sqlite`** | ورش عن نافع (Madani Standard) | **6,214** | **6,214 (100.00%)** | **6,214 (100.00%)** | **0** | **0** |

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/M97Chahboun/quran-database-verifier.git
cd quran-database-verifier
```

### 2. Extract / Re-generate All Qira'at Databases
```bash
# Extract and build all 8 SQLite databases automatically:
python3 scripts/extract_all_qiraat.py

# Extract a specific recitation (e.g. qaloon, duri, bazzi):
python3 scripts/extract_all_qiraat.py --qiraa qaloon
```

### 3. Run Verification Suite
```bash
# Verify Hafs & Warsh against King Fahd Complex API:
python3 scripts/verify_quran_databases.py --db all --format all
```

### 4. Run Multi-Source Benchmark
```bash
# Cross-benchmark against King Fahd Complex, Quran.com API v4, and AlQuran Cloud:
python3 scripts/benchmark_quran_sources.py
```

---

## 🗄️ Database Schema

All generated SQLite databases use the standardized schema:

```sql
-- 1. Ayahs table (Includes Tashkeel, Search text, and Rub'/Hizb/Juz)
CREATE TABLE aya (
    soraid      INTEGER NOT NULL, -- Surah number (1 to 114)
    ayaid       INTEGER NOT NULL, -- Verse number (1 to N; 0 for Bismillah headers)
    quarter     INTEGER,          -- Rub' (Quarter of Hizb, 1 to 240)
    hezb        INTEGER,          -- Hizb (1 to 60)
    joza        INTEGER,          -- Juz' / Para (1 to 30)
    text        TEXT,             -- Full Uthmanic Arabic text with Tashkeel
    uthmanitext TEXT,             -- Synchronized Uthmanic script
    searchtext  TEXT,             -- Clean Imla'i search text without diacritics
    page        INTEGER,          -- Physical Mushaf page (1 to 604)
    PRIMARY KEY (soraid, ayaid)
);

-- 2. Surah table
CREATE TABLE sora (
    soraid       INTEGER NOT NULL PRIMARY KEY, -- Surah number (1 to 114)
    name         TEXT,                         -- Arabic name (e.g. الفاتحة)
    name_english TEXT,                         -- English name (e.g. Surat Al-Fatiha)
    place        INTEGER                       -- 1 = Makki, 2 = Madani
);

-- 3. Ayah Tafseer table
CREATE TABLE ayatafseer (
    soraid  INTEGER NOT NULL,
    ayaid   INTEGER NOT NULL,
    tafseer TEXT,
    PRIMARY KEY (soraid, ayaid)
);
```

---

## 📂 Repository Structure

```
quran-database-verifier/
├── README.md                          # Comprehensive documentation
├── LICENSE                            # MIT License
├── requirements.txt                   # Dependency manifest (Standard Lib only)
├── databases/
│   ├── hafs.sqlite                    # حفص عن عاصم (6,236 Ayahs - 100% Certified)
│   ├── warsh.sqlite                   # ورش عن نافع (6,214 Ayahs - 100% Certified)
│   ├── qaloon.sqlite                  # قالون عن نافع (6,214 Ayahs)
│   ├── shubah.sqlite                  # شعبة عن عاصم (6,236 Ayahs)
│   ├── duri.sqlite                    # الدوري عن أبي عمرو (6,218 Ayahs)
│   ├── susi.sqlite                    # السوسي عن أبي عمرو (6,217 Ayahs)
│   ├── bazzi.sqlite                   # البزي عن ابن كثير (6,221 Ayahs)
│   ├── qunbul.sqlite                  # قنبل عن ابن كثير (6,221 Ayahs)
│   └── fix_quran_discrepancies.sql    # Transactional SQL migration
├── scripts/
│   ├── extract_all_qiraat.py          # Multi-Qira'at extraction & generation engine
│   ├── verify_quran_databases.py      # Core CLI verification engine
│   ├── benchmark_quran_sources.py     # Multi-source consensus benchmark tool
│   └── compare_with_quranhub.py       # QuranHub 604-page layout comparator
└── reports/
    ├── quran_diff_viewer.html         # Standalone visual diff viewer (HTML/CSS)
    ├── quran_alignment_report.md      # Full Markdown audit report
    └── quran_benchmark_consensus_report.md # Multi-source consensus report
```

---

## 🌐 Ground Truth References

- **King Fahd Glorious Quran Printing Complex (KFGQPC / مجمع الملك فهد)**: [qurancomplex.gov.sa](https://qurancomplex.gov.sa/)
- **Quranpedia REST API**: [api.quranpedia.net](https://api.quranpedia.net)
- **Quran.com API v4 (Quran Foundation)**: [api.quran.com](https://api.quran.com)
- **AlQuran Cloud (Islamic Network)**: [alquran.cloud](https://alquran.cloud)
- **QuranHub Project**: [github.com/QuranHub](https://github.com/QuranHub)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
