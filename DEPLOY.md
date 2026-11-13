# HRP — deployment checklist (PythonAnywhere)

Everything that has to be done on the server when the `improvements` branch is deployed **once, at the end**.
Kept up to date after every phase of `IMPROVEMENT_PLAN.md`. Nothing here has been done on the server yet.

Status: covers **Phase 0 – Phase 3**. Last update: 13.11.2026.

Paths below assume the project is in `~/hrp` and the virtualenv python is `~/.virtualenvs/hrp/bin/python`
— replace with the real paths from the PythonAnywhere **Web** tab.

---------------------------------------------------------------------------------------------------
## 0. Before touching anything

- [ ] **Database backup** (Bash console on PythonAnywhere):
      ```bash
      mysqldump -u smihailov79 -h smihailov79.mysql.pythonanywhere-services.com --no-tablespaces --single-transaction 'smihailov79$<db name>' > ~/backup_before_improvements_$(date +%Y%m%d).sql
      ```
- [ ] **Finance backup** (only if the finance data on the server differs from the local copy — see §6):
      the local backups already exist, see `backups/` in §6.
- [ ] Note the current commit so you can go back: `git rev-parse HEAD`.

---------------------------------------------------------------------------------------------------
## 1. Code

- [ ] `git fetch && git checkout improvements` (or merge `improvements` into `master` and pull).
- [ ] The `finance/` folder is still in the repo but the app is **unplugged** — do not delete it on the server.

---------------------------------------------------------------------------------------------------
## 2. Python packages (requirements)

`requirements.txt` changed in Phase 3 — the production virtualenv **must** be updated:

- [ ] `pip install -r requirements.txt` (inside the production virtualenv, before reloading the web app).
      This installs the one new package, **`pytesseract`** (the reading app imports it; without it the site
      does not start). The OCR feature also needs the `tesseract` binary and `TESSERACT_CMD` in `.env`.
- Removed from the file because nothing imports them: plotly, pyppeteer, requests-html, peewee, psycopg2,
  curl_cffi, fake-useragent, frozendict, multitasking, protobuf, contourpy, kiwisolver, fonttools, cycler.
  `pip install -r` does not uninstall them; they are harmless. Optional clean-up:
  `pip uninstall -y plotly pyppeteer requests-html peewee psycopg2 curl_cffi fake-useragent frozendict multitasking protobuf contourpy kiwisolver fonttools cycler`
- Still listed although only `finance/` uses them (kept until that folder is deleted): djangorestframework,
  django-multiselectfield (also still in `INSTALLED_APPS`), numpy, pytz.
- `yfinance` and `scikit-learn` were never in `requirements.txt`; the unplugged `finance/` code needs them, the
  site does not.

---------------------------------------------------------------------------------------------------
## 3. `.env` on the server

Key names are listed in `.env.example`.

- [ ] `DEBUG=False` — since Phase 1 this value is really honoured (before, any non-empty value meant ON).
      Do this **after** §5 "Static files" is confirmed, because with DEBUG off Django no longer serves `/media/`.
- [ ] `NGROK_URL` is no longer read by any page (finance unplugged). It can stay; nothing uses it.
- [ ] `API_EXCHANGE_RATES` is now optional: only a fallback for `fetch_rates` (primary source needs no key).

---------------------------------------------------------------------------------------------------
## 4. Database migrations

Run: `python manage.py migrate`

| Migration | What it does | Removes anything? |
|---|---|---|
| `reports.0004_basket_name_unique_per_owner` (Phase 1) | Inflation-basket name unique per user / per household instead of globally (index change) | No |
| `reports.0005_exchange_rate_keeps_given_date` (Phase 2) | `ExchangeRate.date_extracted` default = today instead of forced "now" | No |

- [ ] `python manage.py migrate`
- [ ] `python manage.py makemigrations --check` must print "No changes detected".
- Finance: **no migration**. Its 12 `finance_*` tables and its rows in `django_migrations` stay exactly as they are.

---------------------------------------------------------------------------------------------------
## 5. PythonAnywhere settings (Web tab)

- [ ] **Static files** mappings exist: URL `/static/` → `<project>/staticfiles`, URL `/media/` → the `MEDIA_ROOT` folder.
- [ ] `python manage.py collectstatic --noinput`
- [ ] **Force HTTPS**: enabled (session and CSRF cookies are HTTPS-only when `DEBUG=False`).
- [ ] **Reload** the web app (after everything else in this file).

---------------------------------------------------------------------------------------------------
## 6. One-off commands after migrating

- [ ] `python manage.py audit_rates` — lists purchases/incomes in a foreign currency without a usable rate.
- [ ] `python manage.py fetch_rates --backfill` — only if `audit_rates` listed something; then run `audit_rates` again.
      (Locally this added two EUR→USD rates: 2025-09-28 and 2025-10-26.)

Finance data backups made locally on 13.11.2026 (folder `backups/`, git-ignored, **not** on the server):

| File | Content |
|---|---|
| `backups/finance_tables_20261113_2233.sql` | `mysqldump` of the 12 `finance_*` tables (204.5 MB) |
| `backups/finance_backup_20261113_2233.json` | `manage.py dumpdata finance` — 988,911 objects (563.6 MB) |
| `backups/hrp_20261113_2154.sql` | full local database before any change (205.2 MB) |

- [ ] If the server's finance tables hold data that the local DB does not, take the same two backups **on the
      server before deploying** — `dumpdata finance` only works while the app is still installed
      (i.e. on the old code): `python manage.py dumpdata finance --indent 2 > ~/finance_backup.json`.

---------------------------------------------------------------------------------------------------
## 7. Scheduled tasks (Tasks tab)

| Task | When | Command |
|---|---|---|
| Exchange rates (Phase 2) | daily, e.g. 06:00 UTC | `~/.virtualenvs/hrp/bin/python ~/hrp/manage.py fetch_rates` |

- [ ] Create the task above. Purchases are no longer slowed down by rate downloads; without this task new
      foreign-currency purchases use the last stored rate.
- Note: `fetch_rates` calls `https://api.frankfurter.dev` (European Central Bank rates). On a **free**
      PythonAnywhere account outbound requests are limited to an allow-list — if the command fails there, set
      `API_EXCHANGE_RATES` (exchangerate.host key) as fallback or ask PythonAnywhere to allow the host.

---------------------------------------------------------------------------------------------------
## 8. Smoke test after reload

- [ ] Log in; home page loads; there is no "Пари" item in the navbar or on the home page; `/finance/` gives 404.
- [ ] Reports → each of the 7 reports opens; "Категории (таблица)" shows only your household's numbers.
- [ ] Add a small purchase in EUR — saving is immediate (no 1–2 s wait).
- [ ] Inventory: change a quantity and save. Cooking → Favourites: create/rename/delete a group (CSRF check).
- [ ] Log out and open `/reports/price-changes/` — you are redirected to the login page.
- [ ] An error page shows the plain "Server Error (500)" text, not the yellow debug page (proves DEBUG is off).

---------------------------------------------------------------------------------------------------
## 9. Known caveats until the plan is finished

- **Deleting a user who has a finance portfolio fails** (MySQL still has the foreign key from
  `finance_userportfolio` to users). Stays until the finance tables are dropped in Phase 8 (GATE, with the owner).
- The recipe list is no longer cached for 10 minutes (it leaked one user's page to others); the proper cache
  comes in Phase 4.
- `staticfiles/`, `.idea/` and `project_helpers.zip` are git-ignored but still tracked; untracking is planned
  together with the static-files setup in Phase 4 (after `git pull` run `collectstatic` — see §5).

---------------------------------------------------------------------------------------------------
## Change log of this file

| Phase | Added |
|---|---|
| 0 | Backups; `.env.example` |
| 1 | `DEBUG` parsing, secure cookies, Force HTTPS, static/media mappings, migration `reports.0004` |
| 2 | Migration `reports.0005`, `audit_rates`, `fetch_rates --backfill`, daily `fetch_rates` task |
| 3 (steps 1–3) | Finance unplugged (no migration), finance backups, user-deletion caveat |
| 3 (step 4) | `pip install -r requirements.txt` (pytesseract added, 14 unused packages removed) |
