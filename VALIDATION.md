# Deployment preparation validation

Validated on Windows with Python 3.12.8 and the new isolated `.deploy-venv` environment.

- Clean dependency installation: successful; `pip check` reported no broken requirements.
- Regression suite: **29 tests passed**. Covers database initialization, foreign keys, transactional rollback, enrollment scope, login cooldown, suspended accounts, daily/concurrent attendance, timezone dates, embedding persistence/validation, audio validation/resampling, role dashboards, login navigation, semester insertion, model-failure recovery, package exclusions, and supervised check-in authorization/idempotency.
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
