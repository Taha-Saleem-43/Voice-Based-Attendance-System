# Deployment preparation validation

## Scale audit — 9 October 2026

Final local suite: **58 passed, 4 skipped** (62 discovered, 69.23 seconds). The four skipped cases require the disposable PostgreSQL CI service. Dependency compatibility and source compilation passed. The updated real model loaded in 4.71 seconds and produced a finite normalized 192-dimensional real-recording embedding in 9.63 seconds; parameters remain frozen.

Synthetic local benchmark: 20,000 students, 20,000 voice profiles, 600,000 attendance rows, 20 concurrent workers, 400 reads, zero failures. Read p50 43 ms, p95 775 ms, maximum 1,095 ms. Twenty duplicate writes produced one row and twenty independent writes succeeded. Browser, network, bcrypt and inference are excluded; this is not a hosted capacity certification.

Remote Supabase audit: healthy, initially one account/no voice or attendance data, no public API table grants. Additive indexes and the protected audit table were applied and verified. Missing foreign-key index notices were resolved; unused-index notices remain on the almost-empty database. See `READINESS.md`: university-wide production approval remains pending, with concrete acceptance gates.

## Workspace overhaul — 9 October 2026

The final regression run passed **49 tests in 70.89 seconds**, using the project `.deploy-venv`. Temporary-database tests required sandbox permission on Windows. Source compilation passed. Tests cover all role sections without model initialization, safe error messages and logs, confirmations, stale account-state updates, scoped voice removal, retained invalid form inputs, CSV formula handling, and lightweight backend imports. The real-recording model smoke test passed: a finite normalized 192-dimensional embedding, frozen parameters, 6.88-second load and 14.45-second inference. Timings are local observations.

GitHub Actions configuration now checks dependencies, compiles sources, runs tests, and packages an explicit source allowlist. A configured workflow is not evidence of a successful remote run; check the feature pull request for its actual result.

Validated on Windows with Python 3.12.8 and the new isolated `.deploy-venv` environment.

- Clean dependency installation: successful; `pip check` reported no broken requirements.
- Regression suite: **34 tests passed**. Covers database initialization, foreign keys, transactional rollback, enrollment scope, login cooldown, suspended accounts, daily/concurrent attendance, timezone dates, embedding persistence/validation, audio validation/resampling, role dashboards, login destinations for all four roles, semester insertion, model-failure recovery, package exclusions, and supervised check-in authorization/idempotency. Dashboard tests also assert that the voice model is not loaded on page entry. Streamlit AppTest does not support this legacy multi-page switch directly, so navigation calls are asserted and destination pages are exercised separately.
- Local pretrained model: loaded successfully; real cleaned recording produced a finite normalized 192-dimensional embedding. All model parameters remain frozen. Model load: 3.71 seconds; embedding: 6.25 seconds on this machine.
- First-start model retrieval into an empty temporary model directory: successful; real recording inference passed. Model retrieval/load: 56.87 seconds; embedding: 6.02 seconds. The Hugging Face client may reuse its global cache. These are local timings, not cloud performance guarantees.
- Source/TOML parsing: passed.
- Deployment archive: source-only allowlist; excludes the old database, voice samples (including assets), actual secrets, caches, model weights, environments, and runtime logs.

## Still required before going live

1. Revoke the token and change the password previously exposed in loose notes. Local removal does not revoke them.
2. Configure the app's private PostgreSQL connection and Streamlit deployment secrets using the example file. A fresh Supabase project `mphrszecaswctcjpynqu` is provisioned; its ten tables and row-level security were verified remotely. Existing local data is not migrated automatically.
3. Verify the application's PostgreSQL connectivity and record persistence after a deployment restart. Schema provisioning is verified, but the Python application has not yet been connected to the remote database.
4. Test microphone permissions in a real browser over HTTPS and measure memory/latency on the chosen free host. The Dockerfile is supplied but a Linux container build was not run on this machine.

The redesigned homepage was visually checked at desktop size and a 390px mobile viewport with no horizontal overflow. CSS animation honors reduced-motion preferences. Supervised check-in adds staff authorization, kiosk expiry, and account session expiry; recognition runs only after authorization and active-profile checks.

The app remains a supervised demo. Anti-spoof/liveness detection and independent accuracy/threshold evaluation are not implemented by this deployment work. No fine-tuning was performed. Source publication and database provisioning do not constitute a running hosted deployment.

Reference cache checks passed: repeated reads execute one query, cached results return independent copies, separate databases cannot share results, and invalidation exposes new records immediately. The chairman form test verifies invalidation after adding a semester. No measured cloud speedup is claimed.

Reference-form update verification: the expanded 37-test suite passed 36 checks and encountered one 20-second faculty page startup timeout. All seven page tests passed on rerun (22.81 seconds total), including the chairman success/duplicate notices and immediate cache invalidation. New backend tests passed for simultaneous department submissions (one row only), repeated semester submission, invalid inputs, and rejection of non-chairman writes.
