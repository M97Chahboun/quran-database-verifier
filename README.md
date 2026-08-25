# 📖 Quran Database Verifier & Benchmark Suite
### أداة التحقق والمطابقة والتدقيق لقواعد بيانات القرآن الكريم (حفص وورش)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite3-green.svg)](https://www.sqlite.org/)
[![Hafs Alignment](https://img.shields.io/badge/Hafs%20Alignment-100.00%25-brightgreen.svg)]()
[![Warsh Alignment](https://img.shields.io/badge/Warsh%20Alignment-99.49%25-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An open-source audit, verification, and multi-source consensus benchmark toolkit designed to ensure **100% precision, authenticity, and zero-defect correctness** in digital Quran SQLite databases for both **Hafs (حفص عن عاصم)** and **Warsh (ورش عن نافع - طريق الأزرق)**.

---

## 🌟 Overview & Mission

Digital Quran applications and research projects require absolute accuracy. Small typos, missing diacritics, shifted verse numbering, or incorrect headers can easily compromise user experience and scholarly trust.

This project provides:
1. **Pristine, 100% Audited SQLite Databases** for Hafs and Warsh.
2. **Automated Verification Engine**: Character-level comparison against official KFGQPC (مجمع الملك فهد) digital sources.
3. **Multi-Source Consensus Benchmark**: Cross-verification across **KFGQPC**, **Quran.com API v4**, **AlQuran Cloud**, and **QuranHub**.
4. **Interactive Visual HTML Diff Viewer**: Side-by-side verse comparisons with color-coded insertion, deletion, and diacritic discrepancy highlights.
5. **Automated SQL Fix Generator**: Generates safe transactional SQL migration scripts to fix discovered defects.

---

## 📊 Benchmark & Certification Summary

Audited against 4 independent global authorities:

| Mushaf | Recitation Standard | Total Ayahs | KFGQPC Alignment | Critical Text Errors | Verse Count Mismatches | Internal DB Issues |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`hafs.sqlite`** | حفص عن عاصم (Kufi Standard) | **6,236** | **100.00%** (6,236 / 6,236) | **0** | **0** | **0** |
| **`warsh.sqlite`** | ورش عن نافع (Madani Standard) | **6,214** | **99.49%** (6,182 / 6,214) | **0** | **0** | **0** |

> **Note on Warsh:** The 0.51% variation in Warsh consists solely of decorative Waqf mark choices (`ۖ`) and font glyph representations (e.g. sequential tanween `ٗ` vs `ً`). All words, consonants, vowels, and verse counts are **100% authentic**.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/M97Chahboun/quran-database-verifier.git
cd quran-database-verifier
```

### 2. Run Full Database Verification
```bash
# Verify both Hafs and Warsh databases and generate all reports:
python3 scripts/verify_quran_databases.py --db all --format all

# Run verification for a single recitation:
python3 scripts/verify_quran_databases.py --db hafs --format html
```

### 3. Run Multi-Source Consensus Benchmark
```bash
# Cross-benchmark against King Fahd Complex, Quran.com API v4, and AlQuran Cloud:
python3 scripts/benchmark_quran_sources.py
```

### 4. Compare with QuranHub Scanned Page Reference
```bash
# Verify 604-page visual coordinate mapping for Warsh:
python3 scripts/compare_with_quranhub.py
```

---

## 📂 Repository Structure

```
quran-database-verifier/
├── README.md                          # Comprehensive documentation
├── LICENSE                            # MIT License
├── requirements.txt                   # Dependency manifest (Standard Lib only)
├── databases/
│   ├── hafs.sqlite                    # Pristine 100% verified Hafs SQLite database
│   ├── warsh.sqlite                   # Pristine 100% verified Warsh SQLite database
│   └── fix_quran_discrepancies.sql    # Transactional SQL migration fix script
├── scripts/
│   ├── verify_quran_databases.py      # Core CLI verification engine
│   ├── benchmark_quran_sources.py     # Multi-source consensus benchmark tool
│   └── compare_with_quranhub.py       # QuranHub 604-page layout comparator
└── reports/
    ├── quran_diff_viewer.html         # Standalone visual diff viewer (HTML/CSS)
    ├── quran_alignment_report.md      # Full Markdown audit report
    ├── quran_benchmark_consensus_report.md # Multi-source consensus report
    └── quranhub_comparison_report.md  # QuranHub comparison report
```

---

## 🗄️ Database Schema

Both `hafs.sqlite` and `warsh.sqlite` follow the standard SQLite schema for Quran applications:

```sql
CREATE TABLE aya (
    soraid      INTEGER NOT NULL, -- Surah number (1 to 114)
    ayaid       INTEGER NOT NULL, -- Verse number within the Surah (1 to N)
    quarter     INTEGER,          -- Rub' (Quarter of Hizb, 1 to 240)
    hezb        INTEGER,          -- Hizb (1 to 60)
    joza        INTEGER,          -- Juz' / Para (1 to 30)
    text        TEXT,             -- Full Uthmanic Arabic text with Tashkeel
    uthmanitext TEXT,             -- Synchronized Uthmanic script
    searchtext  TEXT,             -- Clean Imla'i search text without diacritics
    ayatafseer  TEXT,             -- Ayah tafseer / commentary
    page        INTEGER,          -- Physical Mushaf page (1 to 604)
    PRIMARY KEY (soraid, ayaid)
);
```

---

## 🔬 Key Issues Audited and Solved

1. **Surah 9:1 (At-Tawbah) Header Fix (`hafs.sqlite`)**:
   - Removed prepended Surah title `سُورَةُ التَّوۡبَةِ ` from verse 1.
2. **Surah 67 (Al-Mulk) Authentic Verse Count (`warsh.sqlite`)**:
   - Split verse 9 into verses 9 and 10 to conform to the **31-ayah Madani Warsh standard**.
3. **Surah 16:123 (An-Nahl) Precision Audit (`warsh.sqlite`)**:
   - Validated that local database correctly retains **128 verses** (resolving upstream API 127-verse merge).
4. **Harakat & Position Indices**:
   - Every discrepancy reports the exact character index and descriptive Arabic diacritic name (`فتحة (Fatha)`, `ضمة (Damma)`, `كسرة (Kasra)`, `سكون (Sukun)`, `تطويل (Tatweel)`, etc.).
5. **Internal Column Consistency**:
   - Ensured 100% synchronization between `text` and `uthmanitext`.

---

## 🌐 Ground Truth References

- **King Fahd Glorious Quran Printing Complex (KFGQPC / مجمع الملك فهد)**: [qurancomplex.gov.sa](https://qurancomplex.gov.sa/)
- **Quranpedia REST API**: [api.quranpedia.net](https://api.quranpedia.net)
- **Quran.com API v4 (Quran Foundation)**: [api.quran.com](https://api.quran.com)
- **AlQuran Cloud (Islamic Network)**: [alquran.cloud](https://alquran.cloud)
- **QuranHub Project**: [github.com/QuranHub](https://github.com/QuranHub)

---

## 🤝 Contributing

Contributions, additional benchmark sources, and suggestions are warmly welcome!
Please feel free to open an **Issue** or submit a **Pull Request**.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
