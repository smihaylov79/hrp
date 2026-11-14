# HRP — deployment runbook (PythonAnywhere)

One deployment of the `improvements` branch (all phases of `IMPROVEMENT_PLAN.md`, 0 – 8).
Every step below was run on the local copy of the database on 14.11.2026. **Nothing has been done on the server.**

Do the steps **in this order**, in one sitting, in a PythonAnywhere **Bash console**. A step that prints an error
means **stop** — do not continue with the next one. Steps 5 and 9 are the only ones that cannot be undone
without the backups from steps 1 and 5.

Replace in the commands below (the real values are on the PythonAnywhere **Web** and **Databases** tabs):

| Placeholder | Meaning | Example |
|---|---|---|
| `~/hrp` | project folder (where `manage.py` is) | `/home/smihailov79/hrp` |
| `python` | the python of the site's virtualenv | `~/.virtualenvs/hrp/bin/python` |
| `DBUSER`, `DBHOST`, `DBNAME` | values of `DB_USER`, `DB_HOST`, `DB_NAME` in the server's `.env` | `smihailov79`, `smihailov79.mysql.pythonanywhere-services.com`, `smihailov79$hrp` |

---------------------------------------------------------------------------------------------------
## 1. Full database backup — STOP if it fails

```bash
cd ~/hrp
git rev-parse HEAD > ~/hrp_commit_before_deploy.txt
mysqldump -u DBUSER -h DBHOST -p --no-tablespaces --single-transaction 'DBNAME' > ~/hrp_full_before_deploy.sql
tail -c 200 ~/hrp_full_before_deploy.sql
```

- [ ] The last line printed must contain `-- Dump completed`. If not, stop.
- [ ] Download `hrp_full_before_deploy.sql` to your computer (Files tab). It contains the finance tables too.

---------------------------------------------------------------------------------------------------
## 2. Code

```bash
cd ~/hrp
git fetch
git checkout improvements        # or merge improvements into master and pull master
```

- The `finance/` folder disappears with this checkout (it was deleted from the repository). A complete copy is
  on your PC in `C:\Claude_projects\finance_export\finance\`.
- `staticfiles/` is no longer in git, so the pull removes the collected static files: the site has **no CSS
  until step 11**. Do not reload the web app before the end.

---------------------------------------------------------------------------------------------------
## 3. Python packages

```bash
python -m pip install -r requirements.txt
python manage.py check
```

- [ ] `check` must print "no issues".
- New packages: **`pytesseract`** (the reading app imports it; without it the site does not start) and
  **`openpyxl`** + `et_xmlfile` (Excel export of report tables).
- `requirements.txt` now lists only what the site imports and what those packages need: 24 lines instead of 62.
  `requirements.in` holds the 12 top-level packages it is generated from.
- Optional clean-up of packages that are no longer used (pip does not remove them by itself; harmless if left):
  ```bash
  python -m pip uninstall -y aiohappyeyeballs aiohttp aiosignal appdirs attrs bs4 cffi colorama contourpy cssselect \
    curl_cffi cycler django-multiselectfield djangorestframework fake-useragent feedparser fonttools frozendict \
    frozenlist importlib_metadata kiwisolver lxml multidict multitasking narwhals parse peewee platformdirs plotly \
    propcache protobuf psycopg2 pycparser pyee pyparsing pyppeteer pyquery requests-html sgmllib3k tqdm w3lib \
    websockets yarl zipp yfinance scikit-learn
  python -m pip check
  ```

---------------------------------------------------------------------------------------------------
## 4. `.env` on the server

Key names are in `.env.example`.

- [ ] `DEBUG=False` — since Phase 1 this value is really honoured (before, any non-empty value meant ON).
- [ ] `NGROK_URL` can be deleted (nothing reads it any more).
- [ ] `API_EXCHANGE_RATES` is optional now: only a fallback for `fetch_rates`.
- [ ] `TESSERACT_CMD` — path of the `tesseract` program, only needed for the OCR feature in Reading.

---------------------------------------------------------------------------------------------------
## 5. Finance data: dump the production tables FIRST — STOP if it fails

The production finance data is newer than the local copy, so this dump is the one to keep.

```bash
python manage.py dump_finance_tables --output ~/finance_tables_prod.sql
```

- [ ] It must end with `Dumped 12 tables, … rows to …`. The command checks that the file ends with
      "Dump completed", that every finance table is in it and that no table changed during the dump; on any
      problem it prints an error and exits with a non-zero status. **If it reports an error: stop here. Do not
      run step 9.** (Steps 6–8 and 10–14 can still be done; the finance tables simply stay.)
- [ ] It also writes `~/finance_tables_prod.sql.counts.json` (row count per table). Step 9 needs both files.
- [ ] **Download both files to your PC now** (Files tab) and put them in `C:\Claude_projects\finance_export\`
      (they replace the older local dump there).
- [ ] Recommended — prove the dump restores. Create an empty database in the **Databases** tab, e.g.
      `DBUSER$finance_check`, then:
      ```bash
      python manage.py verify_finance_dump --dump-file ~/finance_tables_prod.sql --database 'DBUSER$finance_check'
      ```
      It loads the dump into that database and compares the row count of every table with the live tables. It must
      end with `The dump restores correctly`. Delete the `finance_check` database afterwards in the Databases tab.

---------------------------------------------------------------------------------------------------
## 6. Data cleanup (duplicate inventory rows, unused exchange rates)

```bash
python manage.py cleanup_data --dry-run     # shows what would change, changes nothing
python manage.py cleanup_data
python manage.py cleanup_data               # second run must print "Nothing to clean up."
```

- Merges inventory rows that exist twice for the same household (or user) and product: the older row is kept,
  quantities and amounts are added up, inflation-basket items are re-pointed. Locally: 4 products
  (Семена, Нахут - консерва, 3-1, Нахут - зърна).
- Deletes exchange-rate rows that are never read (same currency, BGN ↔ EUR). Locally: 446 of 761. Report totals
  do not change (checked locally to the cent).
- Run it **before** step 7: the migration `inventory.0012` adds a rule "one row per owner and product" and would
  otherwise do the same merge itself, without a dry run.

---------------------------------------------------------------------------------------------------
## 7. Database migrations

```bash
python manage.py migrate
python manage.py makemigrations --check     # must print "No changes detected"
```

| Migration | What it does | Removes anything? |
|---|---|---|
| `reports.0004_basket_name_unique_per_owner` | Inflation-basket name unique per user / household instead of globally | No |
| `reports.0005_exchange_rate_keeps_given_date` | A rate keeps the date it is given | No |
| `shopping.0020_user_date_index` | Index (user, date) on purchases | No |
| `income.0003_user_date_index` | Index (user, date_received) on incomes | No |
| `taskmanager.0004_task_due_date_local_today` | New task is due today in Sofia time | No |
| `inventory.0012_one_row_per_owner_and_product` | One inventory row per owner and product (merges duplicates first — none left after step 6) | No |

No migration touches the finance tables.

---------------------------------------------------------------------------------------------------
## 8. Cache table

```bash
python manage.py createcachetable
```

- Creates `hrp_cache` (recipe catalogue, weather, utility prices). Safe to repeat. Without it the home page, the
  cooking pages and the utility-bills page fail.

---------------------------------------------------------------------------------------------------
## 9. Drop the finance tables — only after step 5 succeeded and the dump is on your PC

```bash
python manage.py drop_finance_tables --dump-file ~/finance_tables_prod.sql --dry-run
python manage.py drop_finance_tables --dump-file ~/finance_tables_prod.sql --optimize
python manage.py drop_finance_tables --dump-file ~/finance_tables_prod.sql      # must print "Nothing to do"
```

The command refuses to run unless the dump file is complete, contains every finance table and its recorded row
counts equal the live tables (so a dump made earlier than the last change is rejected — make a new one). Then it:

1. drops the 12 `finance_*` tables,
2. deletes the finance rows from `django_migrations`,
3. runs `remove_stale_contenttypes --include-stale-apps` (the finance content types and their permissions),
4. runs `OPTIMIZE TABLE` on the remaining tables.

Locally this took 7 seconds and the database went from 205 MB to 5 MB.
After this step a user who had a finance portfolio can be deleted again (the old foreign key is gone).

---------------------------------------------------------------------------------------------------
## 10. Exchange rates

```bash
python manage.py audit_rates
python manage.py fetch_rates --backfill     # only if audit_rates listed something; then audit_rates again
```

---------------------------------------------------------------------------------------------------
## 11. Static files

```bash
python manage.py collectstatic --noinput
```

- [ ] **Web** tab → Static files: URL `/static/` → `<project>/staticfiles`, URL `/media/` → the `MEDIA_ROOT` folder.
      With `DEBUG=False` Django no longer serves `/media/` itself.
- The new design is `static/css/theme.css` and `static/js/hrp-charts.js`; Bootstrap 5.3.3, Bootstrap Icons,
  Highcharts 11.4.8 and the Inter font come from public CDNs with pinned versions and integrity hashes.

---------------------------------------------------------------------------------------------------
## 12. Scheduled task (Tasks tab)

| Task | When | Command |
|---|---|---|
| Exchange rates | daily, e.g. 06:00 UTC | `~/.virtualenvs/hrp/bin/python ~/hrp/manage.py fetch_rates` |

- Purchases are no longer slowed down by rate downloads; without this task new foreign-currency purchases use the
  last stored rate.
- `fetch_rates` calls `https://api.frankfurter.dev` (European Central Bank rates, no key). On a **free**
  PythonAnywhere account outbound requests are limited to an allow-list — if the command fails there, set
  `API_EXCHANGE_RATES` (exchangerate.host key) as fallback or ask PythonAnywhere to allow the host.

---------------------------------------------------------------------------------------------------
## 13. Web tab

- [ ] **Force HTTPS**: enabled (session and CSRF cookies are HTTPS-only when `DEBUG=False`).
- [ ] **Reload** the web app.

---------------------------------------------------------------------------------------------------
## 14. Smoke test after reload

- [ ] Log in; the home page is the dashboard with the sidebar on the left; `/finance/` gives 404.
- [ ] Top bar: the dark-mode button switches the theme and the choice survives a reload; the language menu works;
      the search box finds one of your products.
- [ ] On a phone (or a narrow window) the sidebar is replaced by the menu button.
- [ ] Reports → each of the six tabs opens and the charts are drawn; the numbers are only your household's.
      Change the period, currency and scope — the address changes and the tabs keep the choice; "Експорт"
      downloads a CSV and an Excel file that open correctly.
- [ ] An old bookmark such as `/reports/spending-history/` lands on the new Reports page.
- [ ] Add a small purchase in EUR of a product you already have: saving is immediate, the product's row in
      Inventory grows and no second row appears.
- [ ] Inventory: change a quantity and save. "Генерирай списък" asks for confirmation, then opens the new list.
- [ ] Cooking → recipe list shows your own name in the top bar; Favourites: create, rename and delete a menu.
- [ ] Бюджет → Проследяване and the weather forecast draw their charts.
- [ ] Log out and open `/reports/prices/` — you are redirected to the login page.
- [ ] A non-existing address shows the plain "Not Found" page, not the yellow debug page (DEBUG is off).

---------------------------------------------------------------------------------------------------
## If something goes wrong

- Before step 9 everything can be undone: `git checkout $(cat ~/hrp_commit_before_deploy.txt)`, reinstall the old
  requirements, reload. The migrations of step 7 only add indexes and rules; the old code runs with them.
- To restore the whole database: `mysql -u DBUSER -h DBHOST -p 'DBNAME' < ~/hrp_full_before_deploy.sql`.
- To restore only the finance tables: `mysql -u DBUSER -h DBHOST -p 'DBNAME' < ~/finance_tables_prod.sql`.

---------------------------------------------------------------------------------------------------
## What changes for the users (worth knowing before you deploy)

- **Reports are one hub** (`/reports/`, six tabs). The eight old report addresses redirect to the matching tab.
- **Personal inflation is calculated differently**: a price index of a fixed basket (median unit price per month,
  first month = 100) instead of the change in the amount spent, so the percentages differ from the old page.
  The automatic basket only uses products bought in at least 3 months whose unit price stays within a factor of 3.
- **Foreign-currency amounts use the rate of the purchase date**; BGN ↔ EUR always uses 1.95583.
- **Actions that change data are buttons (POST)**: generate shopping list, cook recipe, recipe / menu shopping
  list, add product. A hand-typed address for them answers "405".
- **Messages** ("Списъкът … е генериран" and similar) are now shown, as toasts; they were never displayed before.
- **Languages:** English is complete for the menu, home and Reports. Romanian and Greek keep their 31 older
  texts and show Bulgarian for the rest until it is decided which languages are maintained. Most other pages
  contain Bulgarian text that was never marked for translation.
- The recipe catalogue is cached for up to 1 hour and refreshed when a recipe, ingredient, category or product is
  saved in the site or the admin; weather is cached 30 minutes per city, electricity / heating prices 24 hours.
- Database connections stay open for 280 s (PythonAnywhere closes idle ones after 300 s) — nothing to configure.

---------------------------------------------------------------------------------------------------
## Local run of this runbook (14.11.2026) — for reference

| Step | Result on the local database |
|---|---|
| Full backup | `backups/hrp_before_phase8_20261114_0926.sql` — 205.6 MB, 68 tables, complete |
| Finance folder export | `C:\Claude_projects\finance_export\finance\` — 50 files incl. 17 migration files, identical to the repository |
| Finance dump | `backups/finance_tables_final_20261114_0932.sql` — 12 tables, 988,911 rows; copy in `finance_export\` |
| Restore check | loaded into scratch database `hrp_finance_verify`: row counts and `CHECKSUM TABLE` identical for all 12 tables; scratch database dropped |
| `cleanup_data` | 4 duplicate groups merged, 446 of 761 rate rows deleted; second run: nothing to clean |
| `drop_finance_tables --optimize` | 12 tables dropped, 16 migration rows and 12 content types removed, 56 tables optimised; 205 MB → 5 MB |
| Site check | fresh virtualenv from `requirements.txt`: `check` clean, 158 tests pass, 67 URLs load for a user and a visitor; report totals unchanged (EUR 81,558.63 spending / 89,006.60 income) |
