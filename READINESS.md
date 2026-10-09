# University rollout assessment — 9 October 2026

**Decision: supervised pilot only. University-wide production approval is pending.**

The application supports independent role sessions and concurrency-safe daily attendance. The current free hosting deployment has not been tested with the university's actual peak traffic or biometric population. Neither unit tests nor a local database benchmark certify that hosting capacity.

## Evidence and changes

| Area | Evidence |
| --- | --- |
| Role isolation | Student reads are restricted to their account; teacher reads to assigned department/section; faculty directory and voice mutations to their department. Data services recheck current roles. |
| Data size | Synthetic local fixture: 20,000 students, 20,000 voice profiles, 600,000 attendance records; about 126 MB in SQLite including indexes. This is not a PostgreSQL size forecast. |
| Concurrent database use | 20 workers, 400 reads, zero read failures; p50 43 ms, p95 775 ms, max 1,095 ms on this machine. Authentication, browsers, network and real inference are excluded. |
| Atomic attendance | 20 concurrent attempts for one person produced one row. Twenty separate people were marked successfully. |
| Bounded reads | Keyset pagination, 100 displayed rows plus one continuation row. Search/date filtering executes in SQL. CSV export covers the displayed page. |
| Database connections | One per-process Psycopg pool, maximum four connections by default, maximum 32 waiting requests, 10-second acquisition timeout, database statement and lock timeouts. Replicas each need their own connection budget. |
| Voice verification | Production UI requires an enrolled username and checks that account's samples. It does not scan the full university gallery. Up to ten samples per account; legacy galleries over the safety limit are rejected. |
| Voice overload | One active model inference, at most two waiting, bounded wait; overload returns a retry message. This avoids unbounded queues but does not increase CPU throughput. |
| Audit trail | Account enrollment/status, academic reference mutations and voice enrollment/removal store actor, operation, target identifier and time. No passwords, names, recordings or vectors are copied into the audit log. |
| Remote database | Healthy at audit time; one account, zero attendance records, zero voice samples. Public API grants absent. All eleven application tables including audit events have RLS. Eight unindexed foreign-key findings were resolved; remaining performance notices are unused indexes on the almost-empty database. |
| CI | Regression tests plus a disposable PostgreSQL 17 service exercise transactions, pooling, scoped reads and concurrent writes. See the feature pull request for the actual run result. |

Reproduce the synthetic test inside the project environment:

```powershell
.\.deploy-venv\Scripts\python scripts/load_test.py --students 20000 --days 30 --workers 20 --requests 400 --output load-test-result.json
```

The script creates and removes a temporary local database. It never uses deployment secrets or connects to production. CI PostgreSQL tests require localhost and the disposable `vbas_test` database and cannot be pointed at the Supabase project.

## Gates before collecting university-wide data

1. **Define the requirement:** population, simultaneous dashboard users, check-in stations and peak arrivals/minute. Current attendance is once per person per day; courses, timetable sessions, multiple daily class attendance, corrections, leave and historical cohort changes are not modeled. A per-course requirement needs a separate schema/workflow change.
2. **Validate the host:** stage realistic browser sessions and audio requests on equivalent infrastructure. Record p95 login/page/voice latency, throughput, errors, CPU/RAM, pool wait times and restart recovery. The local benchmark gives no hosted concurrent-user guarantee. Community Cloud has shared CPU/RAM limits and sleeps after inactivity; it is not an autoscaling inference service.
3. **Provide durable operations:** automated encrypted off-site backups with a verified restore, monitoring/alerts, documented retention and archive policy, and a recovery owner. Free Supabase requires users to arrange backups; database quotas must be monitored as attendance grows. Do not rely on CSV page exports as backups.
4. **Secure account operations:** rotate credentials previously posted in chat, use an application database role with least privilege instead of the owner account, provide secure password reset/account recovery, and integrate university SSO/MFA where required. Existing weak account passwords are not silently changed by this release. The audit trail currently records administrative mutations, not a complete security event stream.
5. **Validate biometrics:** test independent genuine and impostor recordings, false accept/reject rates, noise, devices and peak latency. Staff supervision remains required. Replay/synthetic-voice detection is absent. Username-based verification reduces gallery size; it does not solve spoofing or establish accuracy.
6. **Approve academic and privacy workflows:** obtain the institution's consent/retention requirements and a non-biometric attendance alternative; rehearse enrollment, suspension, deletion, exports and recovery with authorized staff. Bulk roster import, student promotion/profile correction, attendance correction and course/session attendance remain future work.

For larger scale, retain Postgres but separate web sessions from a bounded inference worker service, add a persistent job queue and monitor it, size compute for measured arrivals, and load-test the complete system. Horizontal replicas require coordinated rate limits and session routing; the current Streamlit session state and per-process queues do not implement that distributed architecture.

## Current hosting references

- [Streamlit Community Cloud resources and hibernation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- [Supabase plan quotas](https://supabase.com/docs/guides/platform/billing-on-supabase)
- [Supabase backup guidance](https://supabase.com/docs/guides/platform/backups)
- [Supabase database advisor findings](https://supabase.com/docs/guides/database/database-linter)
- [Psycopg connection pooling](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
