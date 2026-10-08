# VBAS - Voice Biometric Attendance System

Streamlit attendance demo using frozen SpeechBrain ECAPA-TDNN embeddings. No fine-tuning is performed. Attendance uses cosine similarity against averaged enrollment embeddings; similarity is not a probability.

## Local run

Use Python 3.11 or 3.12 on Windows or Linux x86-64. The old bundled `venv` is not portable; create a new environment.

```powershell
python -m venv .deploy-venv
.\.deploy-venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml: set a unique administrator username and strong password.
.\.deploy-venv\Scripts\python -m streamlit run app.py
```

Run from this folder. Database/model paths are absolute internally, independent of the working directory. A missing SQLite database is created automatically. The existing local database is preserved; an existing active chairman is never overwritten by bootstrap secrets. New passwords must be 10-72 UTF-8 bytes. Old local passwords are accepted until explicitly changed; do not ship the old database.

Successful login opens the matching role dashboard immediately. Log in as chairman, add departments, sections, and semester numbers (1-8), create faculty/teachers, then enroll students through faculty. Add several independent WAV recordings per person (2-30 seconds each). The voice model loads only when processing recordings or verifying attendance; opening a dashboard does not download or initialize the model. First model loading can take time; public model downloads need internet access but no Hugging Face token.

## Free cloud deployment

1. Run `python scripts/package_deployment.py`. Extract `deploy-dist/VBAS-deploy.zip` and push its contents to a new GitHub repository root. The archive contains only a defined list of source/config/documentation files, never your database, recordings, caches, secrets, or virtual environments.
2. Create a free PostgreSQL database, for example Supabase. Copy its session-pooler connection URL; retain `sslmode=require`. URL-encode special characters in its password. Transaction-pooler URLs are not the documented configuration here.
3. Create an app at https://share.streamlit.io using that repository, `app.py` as entry point, and **Python 3.12** in Advanced settings.
4. Paste the example secrets into the deployment Secrets editor, replacing administrator credentials and adding `DATABASE_URL`. These must be top-level TOML keys. Never paste real values into GitHub.
5. Start the app. It creates empty tables and the initial chairman account. Log in and create reference data, accounts, and voice enrollments. Local records are not migrated automatically.
6. Test enrollment, microphone permissions, matching, duplicate attendance, suspension, and persistence after a reboot. HTTPS is supplied by Community Cloud.

Community Cloud is free but has resource limits and may sleep. CPU inference should be measured with realistic concurrent users. CPU inference uses two PyTorch threads by default; `TORCH_NUM_THREADS` can override this. Persistent cloud records require PostgreSQL: local SQLite files on Community Cloud are not durable. Supabase Free projects may pause after inactivity. A container alternative is included (`Dockerfile`, port 8501); it does not guarantee free hosting.

Official references:
- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/develop/concepts/connections/connecting-to-data
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/platform/free-project-pausing

## Configuration

Environment variables override `.streamlit/secrets.toml` and Streamlit Cloud secrets:

| Key | Meaning |
| --- | --- |
| ADMIN_USERNAME / ADMIN_PASSWORD | First-run chairman bootstrap only; does not reset existing accounts |
| DATABASE_URL | PostgreSQL connection URL; omit for local SQLite |
| ATTENDANCE_TIMEZONE | Defaults to Asia/Karachi |
| SPEAKER_VERIFICATION_THRESHOLD | Defaults to 0.5962; calibrate on independent recordings |

The database adapter supports SQLite and PostgreSQL with foreign keys, atomic enrollment, uniqueness of daily attendance, and account rechecks. Existing local schema is retained; startup adds missing tables/indexes. Back up the original database before any separate migration. Use an empty cloud database for a clean deployment.

## Verification

Chairman reference creation uses separate submit forms. Typing does not insert rows. A successful submit saves to the database, clears the form, refreshes the reference cache, and displays confirmation. Repeated or concurrent identical submissions use database uniqueness plus `ON CONFLICT DO NOTHING`, producing an already-exists notice rather than another row or a raw SQL error. Names have surrounding/repeated whitespace normalized; semester values remain restricted to 1–8. Reference creation rechecks active chairman authorization on the server.

Reference lists (departments, sections, semesters) use a bounded in-memory cache with a 60-second TTL. Chairman additions invalidate the affected list immediately. Cache keys isolate each database. Theme CSS is cached until its file modification time changes. Voice models use one shared resource cache. Account status, authorization, voice-profile activity, attendance reads, and attendance writes remain uncached so security and daily check-in decisions use current records. Cache contents are cleared when the app process restarts; free-host cold starts still take time.

```powershell
.\.deploy-venv\Scripts\python -m unittest discover -s tests -v
.\.deploy-venv\Scripts\python scripts/smoke_model.py
```

The smoke test loads the pretrained model and, if local cleaned recordings exist, checks one real recording. Add `--cold` to exercise first-start model downloading into a temporary directory. It does not train or publish audio. Run `python scripts/check_database.py` from the project folder to initialize and check the configured storage without printing credentials. Automated database tests use temporary SQLite databases. PostgreSQL needs a separate connection and persistence smoke test before going live.

## Limits and security

The redesigned interface shares one responsive visual system across the attendance hub and all four role workspaces. Animated voice graphics respect reduced-motion preferences. Set `UNIVERSITY_NAME` to personalize the campus brand. Voice check-in requires an active staff session, or a server-configured `KIOSK_ACCESS_CODE`; kiosk access expires after one hour. Account sessions expire after eight hours. No fine-tuning is performed.

Cloud database provisioning: project `mphrszecaswctcjpynqu` (VBAS Campus Intelligence), region `ap-south-1`, was created on the quoted $0/month plan. Its ten application tables were created and checked with row-level security enabled and access revoked from Supabase's `anon` and `authenticated` roles. This app uses a server-side PostgreSQL connection; do not put its database password in source code or browser JavaScript. The application connection and hosted deployment still require configuration and verification.

This is a supervised demonstration, not a replay-resistant biometric security system. Recorded or synthetic voices can still fool speaker matching. Do not use it for unsupervised high-stakes attendance until liveness/anti-spoofing and independent evaluation are added. The original 99.34% accuracy/EER claims have not been independently reproduced and are no longer presented as deployment guarantees.

Login failures are limited per username (five attempts per 15-minute window). This is a basic application limit; public deployments still need appropriate access controls and abuse monitoring. Dashboard sessions recheck active status and role on each rerun. Faculty enrollment is restricted to their own department. Stored voice embeddings and attendance are sensitive data: use private access where appropriate and maintain database backups.

Previously exposed credentials in the loose notes were removed, but their owners must revoke the Hugging Face token and change the exposed password. Removal from a file does not revoke a credential. Do not publish existing biometric data or the old database.

## Dependency compatibility

CPU-only PyTorch/TorchAudio 2.5.1 and Hugging Face Hub 0.28.1 are pinned for SpeechBrain 1.0.3. The previous TorchAudio 2.10 / Hub 1.x combination removed APIs called by this SpeechBrain version. One shared model loader is used across pages; inference is serialized to avoid concurrent mutations of shared inference state. Model weights and stored embedding dimensions remain unchanged.
