-- ========================================================
-- AUTOMATED QURAN DATABASE FIX MIGRATION
-- Generated At: 2026-08-25 22:14:39
-- Audited against Quranpedia REST API (King Fahd Complex)
-- ========================================================

-- ========================================================
-- FIXES FOR HAFS DATABASE (hafs.sqlite)
-- ========================================================
BEGIN TRANSACTION;

-- 1. Fix Surah At-Tawbah 9:1 (Remove concatenated surah title header)
UPDATE aya
SET text = 'بَرَآءَةٞ مِّنَ ٱللَّهِ وَرَسُولِهِۦٓ إِلَى ٱلَّذِينَ عَٰهَدتُّم مِّنَ ٱلۡمُشۡرِكِينَ',
    uthmanitext = 'بَرَآءَةٞ مِّنَ ٱللَّهِ وَرَسُولِهِۦٓ إِلَى ٱلَّذِينَ عَٰهَدتُّم مِّنَ ٱلۡمُشۡرِكِينَ'
WHERE soraid = 9 AND ayaid = 1;

COMMIT;

-- ========================================================
-- FIXES FOR WARSH DATABASE (warsh.sqlite)
-- ========================================================
BEGIN TRANSACTION;

COMMIT;
