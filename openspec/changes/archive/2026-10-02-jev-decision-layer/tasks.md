## 1. Decision aid

- [x] 1.1 Add the Choice, Score, and Noul client, parser, and no-key heuristic in `src/lib/jev`, and the inspection-service call in `backend/app/jev.py`
- [x] 1.2 Run the aid after `policy.check`, log both gates when `JEV_DUAL_RUN=1`, and let `JEV_PRIMARY=1` set the gate only above the confidence floor without clearing an open panel
- [x] 1.3 Show the decision aid and calibrated confidence in the UI, labeled as an aid
- [x] 1.4 Document the key, env vars, and cost in the README
- [x] 1.5 Cover response parsing and the fallback heuristics with unit tests
