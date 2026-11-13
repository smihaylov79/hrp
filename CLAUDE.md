# Home Resource Planner (hrp) — context for Claude Code

Django 5.2 household-management app (shopping/expenses, income, budget, inventory, cooking, reports,
tasks, reading, entertainment, forum, weather, small "fastapps"). Student project being hardened.

## Environment
- Python 3.12, virtualenv in `.venv` (create with `setup_venv.bat`). Windows dev machine, PyCharm.
- Database: **MySQL** (must stay MySQL). Local DB holds a recent production backup.
- Settings come from `.env` via python-dotenv (SECRET_KEY, DEBUG, DB_*, API keys). Never print, commit or edit `.env`.
- Production: PythonAnywhere (`smihailov79.pythonanywhere.com`), static/media served via PA "Static files" mappings.
- Run: `.venv\Scripts\python manage.py runserver` · checks: `python manage.py check` · tests: `python manage.py test`

## Conventions
- UI language is Bulgarian; user-facing strings go through `{% trans %}` / `gettext`. Keep existing Bulgarian text.
- Frontend: Bootstrap 5.3 + `static/css/theme.css` design layer, Highcharts for charts. No Node build step.
- Every view that touches user data: `@login_required` / `LoginRequiredMixin` AND queryset scoped to the user
  or their household (`user.household`). Never `Model.objects.all()` for user-owned data.
- Currency conversion goes only through `reports/currency.py` (one place, rates loaded once per request).
- Prefer DB aggregation over pandas row loops; never run a query per DataFrame row.

## Guardrails
- No destructive DB operations (DROP, DELETE of data, migrations that remove models/columns) without explicit
  approval from the owner in the chat. The `finance` app's tables must stay in the DB until the owner says so.
- Work on a git branch, one commit per phase of `IMPROVEMENT_PLAN.md`.
- `.gitattributes` normalises line endings; don't mass-reformat files.
