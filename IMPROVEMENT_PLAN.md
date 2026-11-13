# HRP — Improvement Plan (audit of 13.11.2026)

Work through the phases in order. Each phase = one branch commit, `python manage.py check` and tests green,
and a short manual click-through before the next phase. Phases marked **GATE** need the owner's OK first.

---------------------------------------------------------------------------------------------------
## Phase 0 — Safety net
- [ ] `git checkout -b improvements`. Add `.gitattributes` (`* text=auto`, `*.bat text eol=crlf`) and commit:
      220 files currently show as modified only because of CRLF/LF line endings (no real content change).
- [ ] Fresh MySQL backup (`mysqldump`) before any migration.
- [ ] Add `.env.example` (keys only, no values). Extend `.gitignore`: `staticfiles/`, `.idea/`, `*.zip`.
- [ ] Add tests for: currency conversion, per-user data isolation of every report, inventory/budget ownership.
      (All `tests.py` files are currently empty.)

---------------------------------------------------------------------------------------------------
## Phase 1 — Security & data isolation (do first: real data of other users is exposed)
| Where | Problem | Fix |
|---|---|---|
| `hrp/settings.py` `DEBUG = os.getenv('DEBUG')` | Any non-empty string is truthy → `DEBUG=False` in .env still means **DEBUG ON** (error pages leak settings; Django keeps every SQL query in memory → slower). | `DEBUG = os.getenv("DEBUG", "False").lower() in ("1","true","yes")`. Add `CSRF_TRUSTED_ORIGINS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER` for prod. |
| `reports/views.py` `by_category_table` | No login; loads **all users'** ShoppingProducts. Also the cause of wrong category numbers. | `@login_required`, scope to user/household, filter dates in SQL (see Phase 2). |
| `reports/views.py` `price_changes` | No login; `UserInflationBasket.objects.all()` / `HouseholdInflationBasket.objects.all()` → every user sees every basket. | Filter by user / household. |
| `create_inflation_basket`, `edit_inflation_basket` | Product pickers list `InventoryProduct.objects.all()` (all users). `save_inflation_basket` has no login. | Scope + `@login_required`, `get_object_or_404(..., user=...)` for product ids. |
| `reports.models.UserInflationBasket.name` (and household) | `unique=True` globally → two users can't both have a basket "Храна". | `UniqueConstraint(fields=["user","name"])` (migration). |
| `forum/views.py` `edit_request_thread` | Anonymous users can approve/reject thread requests. | `@login_required` + `user.is_staff` check. |
| `inventory/views.py` `update_inventory`, `user_category_settings` | No login; `bulk_update_inventory` updates rows by id with **no owner filter** (IDOR). | `@login_required`; filter `id__in=…, user=user` / `household=household`. |
| `budget/views.py` propose_budget finalize | `Budget.objects.get(pk=budget_id)` with no owner check → can wipe someone else's budget items. | `get_object_or_404(Budget, pk=…, household=… / creator=…)`. |
| `income_spendings_comparison`, `shopping.add_product`, `reading.*_ajax`, `upload_note_image`, `save_extracted_comment` | Missing `@login_required` (some crash for anonymous, some allow writes). | Add decorator. |
| `cooking/views.py` 5× `@csrf_exempt` | CSRF disabled on state-changing AJAX. | Remove; send `X-CSRFToken` header from JS. |
| `weather/views.py` | `http://` with API key in URL, no timeout. | `https`, `timeout=5`. |

---------------------------------------------------------------------------------------------------
## Phase 2 — Currency conversion (why some categories are wrong)
### Bugs found
1. **`by_category_table` mixes all users** (Phase 1) → category totals are everyone's spending, not yours.
2. **Missing rate silently becomes 1.0** (`reports/utils.py convert_amount`: `float(rate or 1.0)`). There is no
   inverse lookup and no cross-rate via EUR (unlike `fastapps/change_calculator/services.py`, which has both).
   Any purchase whose pair (e.g. `USD→EUR`) isn't in `ExchangeRate` is counted 1:1 → wrong totals in exactly the
   categories that contain those purchases.
3. **`ExchangeRate.date_extracted` is `auto_now_add=True`** → the `date_extracted=date` passed in
   `shopping/helpers.get_exchange_rate` is ignored; every row gets *today*. The lookup by shopping date never
   matches for past dates, then `create()` hits `unique_together` → IntegrityError → swallowed as
   "Unable to fetch exchange rate". Result: rates for back-dated purchases are often never stored.
4. `exchangerate.host` now needs an API key; if it fails, USD pairs never exist (→ bug 2).
5. BGN↔EUR uses `0.51129` (rounded) one way and `1.95583` the other; should be the exact peg from one constant.
6. `by_product_statistics`: lowest/highest price are picked by the **unconverted** `price` column, then the
   converted value is shown → wrong product when currencies are mixed (BGN before 2026, EUR after).
7. Rows with no category/main category are dropped by `groupby` (NaN) → category sum < grand total.
8. `price_changes` hard-codes `'BGN'`; `income` conversion has a separate implementation with the same flaws.
9. Performance: one DB query **per DataFrame row** (`df.apply(convert_amount)`) — thousands of queries per report.

### Fix
- New `reports/currency.py`:
  - `BGN_PER_EUR = Decimal("1.95583")` (fixed peg, no API).
  - `get_rate(base, target, on_date=None)`: same → 1; BGN/EUR via peg; direct → inverse → cross via EUR;
    pick the rate on or before `on_date` (else latest). Raise `MissingRate` — **never** default to 1.
  - `rates_for(target, currencies)` loads all needed rates in one query; `convert_df(df, target)` vectorised
    via `df["shopping__currency"].map(rates)`; collect missing pairs and show a warning banner on the report.
- `ExchangeRate.date_extracted`: `DateField(default=date.today)` (no DB schema change beyond AlterField).
- Remove `time.sleep(1)` and the per-currency API loop from the shopping save request; fetch rates in a daily
  scheduled task on PythonAnywhere (`manage.py fetch_rates`) instead.
- `fillna("Без категория")` for category columns; sort min/max by converted price.
- Decide (owner): convert with **latest** rate (current behaviour) or **rate on purchase date** (more correct for USD).
- Data check after deploy: management command `audit_rates` listing currency pairs used in shopping/income with no rate.

---------------------------------------------------------------------------------------------------
## Phase 3 — Remove the finance app without harming the DB  (**GATE** before step 4)
Finance is isolated: nothing outside `finance/` imports it. Its only outside link is FKs to `users_customuser`
(`UserPortfolio.user`). Removing an app from `INSTALLED_APPS` does **not** drop its tables — Django just stops
managing them.
1. Backup: `python manage.py dumpdata finance --indent 2 > finance_backup.json` **and** `mysqldump <db> $(finance_* tables)`.
2. Copy `finance/` (with `migrations/`) to the new project. If the new project uses the same MySQL DB, run
   `migrate finance --fake` there; if a new DB, load the dump.
3. In hrp: remove `'finance'` from `PROJECT_APPS`, `finance.context_processors.fastapi_url` from TEMPLATES,
   `path('finance/', …)` from urls, the "Пари" nav item in `templates/base.html` and the card in `templates/home.html`.
   Do NOT create a migration that deletes finance models. Delete the `finance/` folder.
4. Prune requirements no longer used (verify each with grep): plotly, pyppeteer, requests-html, peewee,
   psycopg2, curl_cffi, fake-useragent, frozendict, multitasking, protobuf, matplotlib leftovers
   (contourpy, kiwisolver, fonttools, cycler), djangorestframework (only finance uses it). **Add** `pytesseract` (used by reading, missing).
5. Caveat until cleanup: MySQL keeps the FK constraint from `finance_userportfolio` to users → deleting a user who
   has a portfolio will fail. Do the cleanup below soon after the new project is confirmed working.
6. **Later DB cleanup (with owner):** drop `finance_*` tables in FK order, `DELETE FROM django_migrations WHERE app='finance'`,
   then `python manage.py remove_stale_contenttypes` (also removes the finance permissions).

---------------------------------------------------------------------------------------------------
## Phase 4 — Speed on PythonAnywhere
Biggest wins first:
1. **`finance.context_processors.fastapi_url` does an HTTP call to ngrok on every page render, with no timeout.**
   When ngrok is offline every page waits for the connection to fail. Removed in Phase 3.
2. **Fix DEBUG** (Phase 1) — DEBUG on stores every query in memory.
3. **Cooking `@cache_page(60*10)` on `recipe_list`** — this is why you saw someone else's name: the decorator caches the
   response *before* `SessionMiddleware` adds `Vary: Cookie`, so one user's page (navbar, inventory-based
   cost/availability) is served to everyone for 10 min. Remove it. Instead:
   - configure `CACHES` with `DatabaseCache` (shared by all PA workers; run `createcachetable`);
   - cache only **user-independent** data (recipe list + ingredients, categories) under a key invalidated by
     `post_save/post_delete` on Recipe/RecipeIngredient; compute per-user cost/availability fresh (cheap: 1 query).
   - N+1: `{item.product.id: …}` over inventory triggers one query per item → use `item.product_id` /
     `.values_list("product_id","quantity","average_price")`. `cooking_home`: add `select_related("category")`.
   - Images: `loading="lazy"`, `width/height`, generate thumbnails (Pillow) instead of full-size photos.
   - Paginate or lazy-render the recipe list if it grows.
4. Weather on the home page: external call each load → cache 30 min per location, `timeout=5`.
5. `utility_bills`: 3 external calls (one scrapes toplo.bg without timeout; URL hard-codes `year=2026`) → cache daily, timeouts.
6. Reports: replace per-row conversion (Phase 2); call `by_product_statistics`, `monthly_weekly_spending`,
   `calculate_price_changes`, `monthly_compare_chart` once each (now called 2–3× each). Aggregate in SQL first
   (`values(...).annotate(Sum)` grouped by currency) and convert the aggregates.
7. DB: `CONN_MAX_AGE = 280`, `CONN_HEALTH_CHECKS = True` (PA MySQL drops idle connections at 300 s); add
   `Index(fields=["user","date"])` on `Shopping`, `Index(fields=["user","date_received"])` on `Income`.
8. Context processors: `forum.get_categories` queries on every page and its `categories` key collides with cooking/
   shopping context — rename to `forum_categories` and only use in forum templates.
9. `MIDDLEWARE`: move `LocaleMiddleware` between `SessionMiddleware` and `CommonMiddleware` (Django requirement).
10. PA: static/media via "Static files" mappings, `collectstatic` on deploy; `static()` in urls only when DEBUG.
11. Measure locally with `django-debug-toolbar` (dev only) — target < 15 queries per page.

---------------------------------------------------------------------------------------------------
## Phase 5 — Reports redesign (proposal)
Current: 8 separate pages with overlapping filters, mixed chart libs (Highcharts from two CDNs + Chart.js),
backup template `sp_hist_backup.html`, and inconsistent defaults (BGN in some, EUR in others).
Proposed structure — one **Reports hub** with a shared filter bar (period presets: this month / last month /
3 / 6 / 12 months / YTD / custom; currency default **EUR**; scope: household / personal / external) kept in the URL:
1. **Overview** — KPI cards: spent this period, Δ vs previous period, Δ vs same period last year, avg/day,
   income, net, savings rate; mini sparklines; top 5 categories; budget usage bars.
2. **Categories** — drill-down main → sub → product (click a bar), plus the YoY table (current
   `by_category_table`) for any month, with "Без категория" visible.
3. **Shops** — spend share, price comparison per product across shops (cheapest highlighted), basket cost per shop.
4. **Prices & personal inflation** — fix the method: today's inflation uses **monthly total spending**, which
   measures how much you bought, not prices. Use a basket index: fixed quantities × median **unit price** per month
   (Laspeyres), base month = 100. Product price-history chart stays here.
5. **Cash flow** — income vs spending, net and cumulative balance, savings rate per month.
6. **Budget vs actual** — reuse budget data; variance per main category.
- Export CSV/XLSX for every table; empty states instead of crashes; a "rates missing" warning when applicable.
- One chart library: Highcharts (already used most; free for personal/non-commercial use), one pinned version
  loaded in `base.html` block, with a theme matching the design tokens.

---------------------------------------------------------------------------------------------------
## Phase 6 — Modern styling
**Recommendation: keep Bootstrap 5.3, add a custom design layer — don't switch to fully custom CSS or Tailwind.**
- ~70 templates (after finance removal) already use Bootstrap classes; rewriting all for custom CSS is weeks of work for the same result.
- Tailwind needs a Node build step — awkward on PythonAnywhere.
- Bootstrap 5.3 is themeable via CSS variables and has built-in dark mode (`data-bs-theme`). `static/css/styles.css`
  is currently **empty**, which is why the site looks like default Bootstrap.
Plan:
- `static/css/theme.css`: brand palette, `--bs-*` overrides, radius 14px, soft layered shadows, font
  **Inter** or **Manrope** (both have Cyrillic), tabular numbers for money.
- Layout: left sidebar (collapsible, offcanvas on mobile) with grouped nav —
  *Пари* (Пазаруване, Приходи, Бюджет, Отчети) · *Дом* (Наличности, Готвене, Задачи) · *Свободно време*
  (Четене, Забавление, Форум) · *Приложения*; top bar with search, language, dark-mode toggle, user menu.
- Bootstrap Icons instead of emojis; reusable includes: page header, KPI card, empty state, filter bar, toast messages.
- Home page as a dashboard: tasks today, events, weather, month-to-date spending vs budget, "ready to cook" recipes.
- Pin CDN versions with SRI hashes (or self-host in `static/vendor/`).
- Do it incrementally: base.html + theme first, then page by page (home → reports → shopping → cooking → rest).

---------------------------------------------------------------------------------------------------
## Phase 7 — Logic fixes across sections
- `date.replace(year=…)` in SpendingsView / IncomeView crashes on 29 Feb → `relativedelta(years=offset)`.
- `SpendingsView`: when there is no data `df` is None but `df.groupby` runs → 500 error. Guard early.
- ConsumptionSummary "fast" filter uses `30*months` days → `relativedelta(months=…)`; unhandled bad date strings → use a form.
- `save_shopping_products`: `get_or_create(..., category=product.category)` creates a **duplicate inventory row**
  when a product's category changes → look up by (owner, product) only, then update category.
- `load_prefill_data`: last price only from the user's own purchases (not household), 2 queries per item → one query.
- `Shopping.total_amount/total_discount`: Python loops per row → `annotate(Sum)` in list views.
- `utility_bills` tries `BGN→BGN` rates (no `base == target` skip).
- `Recipe.check_availability` / `calculate_cost` model methods: N+1, duplicates logic in views → one service function.
- Remove dead code: `reports.utils.get_category_totals` (also unscoped & unconverted), duplicate
  `get_same_month_previous_years`, `income_analysis` function view (replaced by `IncomeView`), commented wagtail code,
  `sp_hist_backup.html`, `project_helpers.zip`.
- `HomeView` for anonymous users sets lists where counts are expected; `datetime.now()` → `timezone.now()` (USE_TZ=True).
- Forms/validation instead of raw `request.POST[...]` (KeyError → 500) in inflation basket views.

---------------------------------------------------------------------------------------------------
## Phase 8 — DB cleanup (**GATE**, with owner)
Finance tables (Phase 3 step 6), `remove_stale_contenttypes`, orphan check queries (inventory rows without owner,
exchange rates duplicates), `OPTIMIZE TABLE` on big tables.
