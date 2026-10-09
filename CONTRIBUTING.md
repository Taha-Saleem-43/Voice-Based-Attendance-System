# Working on VBAS

`main` is the production branch consumed by Streamlit Community Cloud. Use a short-lived `feature/<name>` or `fix/<name>` branch for each cohesive change. Open a pull request into `main`, keep commits focused on one concern, and merge only after the App checks workflow passes. Do not commit deployment secrets, databases, recordings, model weights or environments. Avoid long-lived parallel production branches.

## Application structure

- `app.py`: public attendance hub and login routing.
- `pages/`: thin role entry points and workspace navigation.
- `ui/layout.py`: role guards, safe error boundaries and shared notices.
- `ui/workspace.py`: shared record tables, enrollment and voice-profile components.
- `ui/references.py`: academic reference forms and selectors.
- `backend/*_handler.py`, `management.py`, `directory.py`: explicit domain operations and queries.
- `backend/errors.py`: approved validation messages and safe support references.
- `static/theme.css`: shared responsive theme and input layout.
- `tests/`: database, authorization, UI, cache, export and package regressions.
- `.github/workflows/ci.yml`: dependency checks, parsing, regression tests and deployable source packaging.

## Local verification

Create and use a project-local `.deploy-venv`. Install dependencies only in that environment. On Windows run `.\.deploy-venv\Scripts\python -m unittest discover -s tests -v`; on Linux use `.deploy-venv/bin/python`. Never require production secrets or network model downloads for unit tests. Test new features with temporary databases and stub expensive model inference.

## Adding a feature

Keep authorization and mutations in backend services, use parameterized values, and add tests for failure and permission boundaries. Reuse workspace components for consistent labels, required-field hints, success notices and empty states. Preserve inputs on validation failure and reset forms after success. Keep Enter enabled for ordinary submit forms and disabled for destructive forms. Destructive operations need a named target and explicit confirmation. Do not delete referenced academic records or attendance history as a side effect of account suspension.

Never render raw exception strings, tracebacks, SQL, credentials, database host details or certificate payloads. Use `ValidationError` only for deliberately authored safe messages; unexpected errors go through `report_error` with a fixed operation name. Error references can be correlated with safe server diagnostics. CSV exports must neutralize spreadsheet formula prefixes.

The workflow currently uses Python 3.12. Branch protection is an account setting; this document and the workflow do not imply it has been enforced remotely.
