# Mockups for Phase 5 / 6 (for approval — not wired to Django)

| File | What it shows |
|---|---|
| `base_layout.html` | New app shell: grouped sidebar, top bar (search, language, dark mode, user menu) and the home page as a dashboard |
| `reports_overview.html` | Reports hub → Overview: tabs, shared filter bar, KPI cards, charts, budget bars |
| `theme.css` | Draft of the design layer on top of Bootstrap 5.3 (becomes `static/css/theme.css`) |
| `shell.js` | Mockup-only helper that renders the shared sidebar / top bar |
| `standalone_*.html` | The same two pages with CSS and JS inlined, so a single file can be opened or sent |

Open them through a local server (`python -m http.server 8765 --directory mockups`) or just open a
`standalone_*.html` file in a browser. Monthly totals in the reports mockup are the household's real figures;
category split, budget and the home page numbers are sample data.
