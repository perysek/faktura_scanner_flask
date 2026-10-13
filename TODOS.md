# TODOS

## App settings

- [ ] **Absence-conflict timing offsets as app settings.** "Zatwierdź mimo to" in the absence
  conflict-resolution modal parks unresolved visits in `absence_conflict_pending` with
  `valid_for = visit start − 48 h`; at that moment the scheduler auto-cancels the visit and the
  queued `absence_cancellation` SMS goes out. The 48 h is hardcoded as
  `AUTO_CANCEL_OFFSET_HOURS` in `services/absence_conflict_deferral_service.py`. Make the
  auto-cancel offset AND the conflict-SMS send-time offset customizable parameters in a future
  app-settings panel / db table. (Recorded 2026-10-13.)
