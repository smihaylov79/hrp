/* Mockup only: renders the shared sidebar + top bar so both mockup pages stay identical.
   In the real app this markup lives in templates/base.html (Django template, {% trans %} strings). */
(function () {
  const active = document.body.dataset.active;
  const groups = [
    ['', [['home', 'bi-house', 'Начало', 'base_layout.html']]],
    ['Пари', [['shopping', 'bi-bag', 'Пазаруване'], ['income', 'bi-wallet2', 'Приходи'],
              ['budget', 'bi-piggy-bank', 'Бюджет'], ['reports', 'bi-bar-chart-line', 'Отчети', 'reports_overview.html']]],
    ['Дом', [['inventory', 'bi-box-seam', 'Наличности'], ['cooking', 'bi-egg-fried', 'Готвене'],
             ['tasks', 'bi-check2-square', 'Задачи', null, '3']]],
    ['Свободно време', [['reading', 'bi-book', 'Четене'], ['fun', 'bi-controller', 'Забавление'],
                        ['forum', 'bi-chat-dots', 'Форум']]],
    ['Приложения', [['change', 'bi-calculator', 'Калкулатор за ресто']]],
  ];
  const nav = groups.map(([title, items]) =>
    (title ? `<div class="hrp-nav-group">${title}</div>` : '') +
    items.map(([key, icon, label, href, badge]) =>
      `<a href="${href || '#'}" class="${key === active ? 'active' : ''}"><i class="bi ${icon}"></i>${label}` +
      (badge ? `<span class="badge rounded-pill text-bg-primary">${badge}</span>` : '') + `</a>`).join('')
  ).join('');
  const brand = `<a class="hrp-brand" href="base_layout.html"><span class="hrp-brand-mark"><i class="bi bi-house-heart"></i></span>Home Resource Planner</a>`;

  document.getElementById('sidebar').innerHTML = brand + `<nav class="hrp-nav">${nav}</nav>`;
  document.getElementById('offcanvas-body').innerHTML = `<nav class="hrp-nav">${nav}</nav>`;
  document.getElementById('topbar').innerHTML = `
    <button class="hrp-icon-btn d-lg-none" data-bs-toggle="offcanvas" data-bs-target="#navOffcanvas" aria-label="Меню"><i class="bi bi-list"></i></button>
    <div class="hrp-search"><i class="bi bi-search"></i>
      <input class="form-control" type="search" placeholder="Търси продукт, рецепта, покупка…" aria-label="Търсене"></div>
    <div class="ms-auto d-flex align-items-center gap-2">
      <div class="dropdown">
        <button class="hrp-icon-btn" data-bs-toggle="dropdown" aria-label="Език"><i class="bi bi-translate"></i></button>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><a class="dropdown-item active" href="#">Български</a></li><li><a class="dropdown-item" href="#">English</a></li>
          <li><a class="dropdown-item" href="#">Română</a></li><li><a class="dropdown-item" href="#">Ελληνικά</a></li>
        </ul>
      </div>
      <button class="hrp-icon-btn" id="themeToggle" aria-label="Тъмен режим"><i class="bi bi-moon-stars"></i></button>
      <div class="dropdown">
        <button class="btn d-flex align-items-center gap-2 p-0 border-0" data-bs-toggle="dropdown">
          <span class="hrp-avatar">СМ</span><span class="d-none d-md-inline fw-semibold">Стоян</span><i class="bi bi-chevron-down small"></i>
        </button>
        <ul class="dropdown-menu dropdown-menu-end">
          <li><a class="dropdown-item" href="#"><i class="bi bi-person me-2"></i>Профил</a></li>
          <li><a class="dropdown-item" href="#"><i class="bi bi-people me-2"></i>Домакинство</a></li>
          <li><hr class="dropdown-divider"></li>
          <li><a class="dropdown-item" href="#"><i class="bi bi-box-arrow-right me-2"></i>Изход</a></li>
        </ul>
      </div>
    </div>`;

  const root = document.documentElement;
  const saved = (() => { try { return localStorage.getItem('hrp-theme'); } catch (e) { return null; } })();
  const setTheme = (theme) => {
    root.setAttribute('data-bs-theme', theme);
    document.querySelector('#themeToggle i').className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    document.dispatchEvent(new CustomEvent('hrp-theme', { detail: theme }));
  };
  setTheme(saved || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('hrp-theme', next); } catch (e) { /* private mode */ }
    setTheme(next);
  });
})();
