/* Shared chart helpers for HRP (Highcharts, one pinned version loaded by the page).
 *
 * Colours come from the CSS variables in theme.css, so a chart follows the light / dark theme:
 * every chart registered here is redrawn when the theme toggle fires the "hrp-theme" event.
 *
 * Rules built in: 2px lines, no markers except the labelled end point, hairline grid, one y-axis,
 * a legend for two or more series, text in the text colours (never in a series colour), shared tooltip.
 */
(function () {
  'use strict';
  var registry = [];

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function palette() {
    return {
      text: css('--hrp-text'), text2: css('--hrp-text-2'), grid: css('--grid'), surface: css('--hrp-surface'),
      series: [css('--series-1'), css('--series-2')], font: css('--hrp-font')
    };
  }

  function base(c, options) {
    var manySeries = options.series.length > 1;
    return {
      chart: { type: options.type, backgroundColor: 'transparent', spacingRight: options.endLabels ? 70 : 10,
               style: { fontFamily: c.font }, animation: false },
      title: { text: null }, credits: { enabled: false },
      xAxis: Object.assign({ lineColor: c.grid, tickLength: 0, crosshair: { width: 1, color: c.grid },
                             labels: { style: { color: c.text2, fontSize: '12px' } } }, options.xAxis),
      yAxis: Object.assign({ title: { text: null }, gridLineColor: c.grid,
                             labels: { format: '{value:,.0f}', style: { color: c.text2, fontSize: '12px' } } },
                           options.yAxis),
      legend: { enabled: manySeries, align: 'left', verticalAlign: 'top', margin: 8, padding: 0, symbolWidth: 14,
                symbolRadius: 2, itemStyle: { color: c.text, fontWeight: '500' }, itemHoverStyle: { color: c.text } },
      tooltip: Object.assign({ shared: true, backgroundColor: c.surface, borderColor: c.grid, borderRadius: 10,
                               shadow: false, style: { color: c.text, fontSize: '12.5px' },
                               valueSuffix: options.unit ? ' ' + options.unit : '', valueDecimals: options.decimals || 0 },
                             options.tooltip),
      plotOptions: {
        series: { animation: false, states: { inactive: { opacity: 1 } },
                  marker: { enabled: false, symbol: 'circle', states: { hover: { enabled: true, radius: 4 } } } },
        column: { borderWidth: 0, borderRadius: 4, maxPointWidth: 24, groupPadding: 0.15 }
      },
      series: options.series
    };
  }

  /* End label of a line: value next to the last point. With two lines that end close together the upper
     label goes above its point and the lower one below, so they never overlap. */
  function withEndLabels(c, list, unit) {
    var last = list.map(function (s) { return s.data[s.data.length - 1]; });
    return list.map(function (s, index) {
      var data = s.data.slice(), value = data[data.length - 1];
      var above = last.every(function (other, i) { return i === index || value > other || (value === other && index < i); });
      data[data.length - 1] = {
        y: value,
        marker: { enabled: true, radius: 4, lineWidth: 2, lineColor: c.surface },
        dataLabels: { enabled: true, format: '{y:,.0f}' + (unit ? ' ' + unit : ''), align: 'left', x: 8,
                      y: above ? -6 : 16,
                      crop: false, overflow: 'allow', allowOverlap: true,
                      style: { color: c.text, fontWeight: '600', fontSize: '12px', textOutline: 'none' } }
      };
      return Object.assign({}, s, { data: data });
    });
  }

  function register(id, build) {
    var element = document.getElementById(id);
    if (!element || typeof Highcharts === 'undefined') { return; }
    var draw = function () { Highcharts.chart(id, build(palette())); };
    registry.push(draw);
    draw();
  }

  window.hrpCharts = {
    /* Lines over categories (months). options: {categories, series: [{name, data}], unit, endLabels} */
    lines: function (id, options) {
      register(id, function (c) {
        var series = options.series.map(function (s, i) {
          return { name: s.name, data: s.data, color: c.series[i % c.series.length], lineWidth: 2 };
        });
        if (options.endLabels !== false) { series = withEndLabels(c, series, options.unit); }
        return base(c, { type: 'line', unit: options.unit, endLabels: options.endLabels !== false, series: series,
                         decimals: options.decimals,
                         xAxis: { categories: options.categories },
                         yAxis: options.fromZero === false ? {} : { min: 0 } });
      });
    },

    /* Columns over categories, one series; negative values hang below the zero line. */
    columns: function (id, options) {
      register(id, function (c) {
        return base(c, { type: 'column', unit: options.unit, decimals: options.decimals,
                         series: [{ name: options.name, data: options.data, color: c.series[0] }],
                         xAxis: { categories: options.categories },
                         yAxis: { plotLines: [{ value: 0, width: 1, color: c.text2, zIndex: 3 }] } });
      });
    },

    /* Two (or one) series side by side per category, as horizontal bars - for long category names.
       options: {categories, series: [{name, data}], unit} */
    grouped: function (id, options) {
      register(id, function (c) {
        var config = base(c, { type: 'bar', unit: options.unit, decimals: options.decimals,
                               series: options.series.map(function (s, i) {
                                 return { name: s.name, data: s.data, color: c.series[i % c.series.length] };
                               }),
                               xAxis: { categories: options.categories, crosshair: false },
                               yAxis: { min: 0 } });
        config.plotOptions.bar = { borderWidth: 0, borderRadius: 4, maxPointWidth: 14, groupPadding: 0.12, pointPadding: 0.08 };
        return config;
      });
    },

    /* Price over real dates. options: {name, unit, points: [{date: 'YYYY-MM-DD', price, shop}]} */
    timeline: function (id, options) {
      register(id, function (c) {
        var data = options.points.map(function (p) {
          return { x: Date.parse(p.date), y: p.price, shop: p.shop };
        });
        return base(c, { type: 'line', unit: options.unit, decimals: 2,
                         series: [{ name: options.name, data: data, color: c.series[0], lineWidth: 2,
                                    marker: { enabled: true, radius: 4, lineWidth: 2, lineColor: c.surface } }],
                         xAxis: { type: 'datetime', dateTimeLabelFormats: { day: '%e.%m', week: '%e.%m', month: '%m.%Y' } },
                         yAxis: { labels: { format: '{value:,.2f}', style: { color: c.text2, fontSize: '12px' } } },
                         tooltip: { shared: false, xDateFormat: '%e.%m.%Y',
                                    pointFormat: '<b>{point.y:,.2f} ' + (options.unit || '') + '</b><br>{point.shop}' } });
      });
    },

    /* Read JSON written by Django's {{ value|json_script:"id" }} */
    data: function (id) {
      var node = document.getElementById(id);
      return node ? JSON.parse(node.textContent) : null;
    },

    /* Switch between a chart and its table view. */
    toggleView: function (chartId, tableId, chartButtonId, tableButtonId) {
      var chart = document.getElementById(chartId), table = document.getElementById(tableId);
      var chartButton = document.getElementById(chartButtonId), tableButton = document.getElementById(tableButtonId);
      if (!chart || !table || !chartButton || !tableButton) { return; }
      function show(asTable) {
        chart.classList.toggle('d-none', asTable);
        table.classList.toggle('d-none', !asTable);
        chartButton.classList.toggle('active', !asTable);
        tableButton.classList.toggle('active', asTable);
        chartButton.setAttribute('aria-pressed', String(!asTable));
        tableButton.setAttribute('aria-pressed', String(asTable));
      }
      chartButton.addEventListener('click', function () { show(false); });
      tableButton.addEventListener('click', function () { show(true); });
    }
  };

  if (typeof Highcharts !== 'undefined') {
    Highcharts.setOptions({ lang: { thousandsSep: ' ', decimalPoint: ',' } });
  }
  document.addEventListener('hrp-theme', function () { registry.forEach(function (draw) { draw(); }); });
})();
