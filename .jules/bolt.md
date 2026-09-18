## 2026-09-18 - Heavy Dependency CLI Bottlenecks
**Learning:** Initializing heavy libraries like `google.generativeai` and `textstat` globally causes massive CLI startup delays (~1.3s overhead).
**Action:** Always lazy-load heavy modules directly inside the functions where they are used to keep CLI execution lightning fast.
