# 📊 QuranHub Database Comparison & Structural Analysis

**Audit Date:** 2026-08-31 01:03:18  
**Reference Source:** [QuranHub Warsh Page-Images Data](https://raw.githubusercontent.com/QuranHub/quran-pages-images/main/ayat/warsh/data/quran.db)  

## 🔍 1. Database Nature & Purpose Comparison

| Feature | Local Database (`warsh.sqlite`) | QuranHub Reference (`quran.db`) |
| :--- | :--- | :--- |
| **Primary Purpose** | Full Quran text, Uthmani script, search, recitation & memorization | Visual bounding box coordinates for Warsh scanned page images |
| **Table Schema** | `aya (soraid, ayaid, text, uthmanitext, searchtext, joza, hezb)` | `ayas (aya_id, page, x, y)` |
| **Total Verses / Records** | **6,214** (Madani Warsh) | **6,236** (Coordinates across 604 pages) |
| **Page Coverage** | 114 Surahs | Pages 1 to 604 (604 pages total) |

---

## 📐 2. Structural & Numbering Systems Analysis

### A. Numbering Schemes in Quranic Narrations:
- **Madani Numbering (Warsh standard - 6,213 verses):**
  - Followed by our local `warsh.sqlite` database.
  - In Surah Al-Fatiha, Basmalah is an unnumbered header; Verse 1 begins with *'الحمد لله رب العالمين'* and Verse 6 is *'صراط الذين أنعمت عليهم'*.
- **Kufi Numbering (Hafs standard - 6,236 verses):**
  - Followed by our local `hafs.sqlite` and the index table in `QuranHub`.
  - In Surah Al-Fatiha, Basmalah is counted as Verse 1.

### B. Key Findings & Synergy:
- ✅ **QuranHub's `quran.db` contains image bounding box coordinates (page, x, y) for rendering highlights on Warsh page images.**
- ✅ **QuranHub indexes ayahs using a 6,236 global sequential key (1 to 6236) across 604 pages.**
- ✅ **Local `warsh.sqlite` stores full Uthmani text, diacritics, search text, hizb, and joza across 6,213 authentic Madani verses.**
- ✅ **Local `hafs.sqlite` contains 6,236 verses matching the exact count in QuranHub.**

---

## 📑 3. QuranHub Page Coordinate Distribution Sample (First 10 Pages)

| Page Number | Ayahs on Page (Coordinate Count) |
| :---: | :---: |
| Page 1 | 7 ayahs |
| Page 2 | 5 ayahs |
| Page 3 | 11 ayahs |
| Page 4 | 8 ayahs |
| Page 5 | 5 ayahs |
| Page 6 | 8 ayahs |
| Page 7 | 11 ayahs |
| Page 8 | 9 ayahs |
| Page 9 | 4 ayahs |
| Page 10 | 8 ayahs |

