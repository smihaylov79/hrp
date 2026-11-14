# HRP — deployment checklist (PythonAnywhere)

Everything that has to be done on the server when the `improvements` branch is deployed **once, at the end**.
Kept up to date after every phase of `IMPROVEMENT_PLAN.md`. Nothing here has been done on the server yet.

Status: covers **Phase 0 – Phase 6**. Last update: 13.11.2026.

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
- [ ] **`staticfiles/` is no longer in git (Phase 4).** The pull removes the collected static files from the
      server's working copy, so the site has **no CSS/JS until `collectstatic` is run** (§5). Do the pull,
      `pip install`, `migrate`, `createcachetable` and `collectstatic` in one go, then reload.
      (`.idea/` and `project_helpers.zip` also left the repo; nothing on the server needs them.)

---------------------------------------------------------------------------------------------------
## 2. Python packages (requirements)

`requirements.txt` changed in Phase 3 — the production virtualenv **must** be updated:

- [ ] `pip install -r requirements.txt` (inside the production virtualenv, before reloading the web app).
      This installs the new packages:
      **`pytesseract`** (the reading app imports it; without it the site does not start; the OCR feature also
      needs the `tesseract` binary and `TESSERACT_CMD` in `.env`) and
      **`openpyxl`** + `et_xmlfile` (Phase 5: Excel export of report tables; without it "Excel (XLSX)" gives an
      error, everything else works).
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
| `shopping.0020_user_date_index` (Phase 4) | Adds index (user, date) on purchases | No |
| `income.0003_user_date_index` (Phase 4) | Adds index (user, date_received) on incomes | No |

- [ ] `python manage.py migrate`
- [ ] `python manage.py makemigrations --check` must print "No changes detected".
- [ ] **`python manage.py createcachetable`** (Phase 4) — creates the table `hrp_cache` used by the shared cache
      (recipe catalogue, weather, utility prices). Safe to run more than once. Without it the cooking pages,
      the home page and the utility-bills page fail with "Table ... hrp_cache doesn't exist".
- Finance: **no migration**. Its 12 `finance_*` tables and its rows in `django_migrations` stay exactly as they are.

---------------------------------------------------------------------------------------------------
## 5. PythonAnywhere settings (Web tab)

- [ ] **Static files** mappings exist: URL `/static/` → `<project>/staticfiles`, URL `/media/` → the `MEDIA_ROOT` folder.
- [ ] `python manage.py collectstatic --noinput` — **required** on this deploy (see §1: `staticfiles/` left git).
- [ ] **Force HTTPS**: enabled (session and CSRF cookies are HTTPS-only when `DEBUG=False`).
- The new layout (Phase 6) loads its own stylesheet `static/css/theme.css` — it reaches the server only through
  `collectstatic`. Bootstrap 5.3.3, Bootstrap Icons 1.11.3 and the Inter font come from public CDNs
  (jsDelivr, Google Fonts) with pinned versions and integrity hashes; nothing to install.
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

- [ ] Log in; the home page is the new dashboard with the sidebar on the left; `/finance/` gives 404.
- [ ] Top bar: the dark-mode button switches the theme and the choice survives a reload; the language menu works;
      the search box finds one of your products.
- [ ] On a phone (or a narrow window) the sidebar is replaced by the menu button.
- [ ] Click through one page of every section (Пазаруване, Приходи, Бюджет, Наличности, Готвене, Задачи,
      Календар, Четене, Форум): each has a page title with its buttons on the right and no emoji icons;
      Бюджет → Проследяване and the weather forecast draw their charts.
- [ ] Switch the language to English: menu, home and Reports are in English.
- [ ] Reports → each of the six tabs opens (Обзор, Категории, Магазини, Цени и инфлация, Паричен поток,
      Бюджет) and the charts are drawn; the numbers are only your household's.
- [ ] Reports: change the period, the currency and the scope - the address bar changes and the tabs keep the
      choice; "Експорт" downloads a CSV and an Excel file that open correctly (Cyrillic text readable).
- [ ] An old bookmark such as `/reports/spending-history/` lands on the new Reports page.
- [ ] Add a small purchase in EUR — saving is immediate (no 1–2 s wait).
- [ ] Cooking → recipe list: your own name is in the navbar; log in as a second user and check theirs too.
- [ ] Pages have their styling (proves `collectstatic` ran) and recipe / book images load (media mapping).
- [ ] Inventory: change a quantity and save. Cooking → Favourites: create/rename/delete a group (CSRF check).
- [ ] Log out and open `/reports/price-changes/` — you are redirected to the login page.
- [ ] An error page shows the plain "Server Error (500)" text, not the yellow debug page (proves DEBUG is off).

---------------------------------------------------------------------------------------------------
## 9. Known caveats until the plan is finished

- **Deleting a user who has a finance portfolio fails** (MySQL still has the foreign key from
  `finance_userportfolio` to users). Stays until the finance tables are dropped in Phase 8 (GATE, with the owner).
- Database connections are now kept open for 280 s (`CONN_MAX_AGE`) with a health check; PythonAnywhere closes
  idle MySQL connections after 300 s, so no setting has to change there.
- The recipe catalogue is cached for up to 1 hour and refreshed automatically when a recipe, ingredient,
  recipe category or product is saved in the app or the admin. A change made directly in MySQL shows up after
  at most 1 hour (or immediately after `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`).
- Weather is cached 30 minutes per city; electricity / heating prices 24 hours.
- **Translations:** English is complete for the new layout, dashboard and Reports. Romanian and Greek only
  have the 31 older texts; everything new falls back to Bulgarian there until someone translates
  `locale/ro/…/django.po` and `locale/el/…/django.po` and runs `python manage.py compilemessages`
  (needs GNU gettext; Git Bash has it). The compiled `.mo` files are in git, so the server needs no extra step.
  Pages outside the shell, Home and Reports still have Bulgarian texts that were never marked for translation.
- **Reports are one hub now** (`/reports/` with six tabs). The addresses of the eight old report pages still
  work: they redirect to the matching tab and carry the period / currency over.
- **Personal inflation is calculated differently** (Phase 5): it is now a price index of a fixed basket
  (median unit price per month, first month = 100) instead of the change in the amount spent, so the
  percentages differ from the old page. The automatic basket only uses products bought in at least 3 months
  whose unit price stays within a factor of 3 (gifts, rent, trips and similar are left out).
- Charts: one library, Highcharts 11.4.8 from jsDelivr with an integrity hash (Chart.js and the second
  Highcharts copy are gone from the report pages).

---------------------------------------------------------------------------------------------------
## Change log of this file

| Phase | Added |
|---|---|
| 0 | Backups; `.env.example` |
| 1 | `DEBUG` parsing, secure cookies, Force HTTPS, static/media mappings, migration `reports.0004` |
| 2 | Migration `reports.0005`, `audit_rates`, `fetch_rates --backfill`, daily `fetch_rates` task |
| 3 (steps 1–3) | Finance unplugged (no migration), finance backups, user-deletion caveat |
| 3 (step 4) | `pip install -r requirements.txt` (pytesseract added, 14 unused packages removed) |
| 4 | `createcachetable`, index migrations `shopping.0020` + `income.0003`, `collectstatic` now mandatory (`staticfiles/` untracked), cache notes |
| 6 (part 1) | `theme.css` via `collectstatic`, CDN assets pinned with SRI, smoke-test steps for the new layout, translation note |
| 6 (part 2) | all remaining pages restyled (no server step beyond `collectstatic`); translation note updated |
| 5 | `pip install -r requirements.txt` now also installs `openpyxl`; `static/js/hrp-charts.js` via `collectstatic`; Reports hub smoke-test steps; note on the new inflation method and the redirects |
