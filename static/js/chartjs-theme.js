(function () {
  if (!window.Chart || window.Chart.__enterpriseThemeLoaded) {
    return;
  }

  Chart.defaults.font.family = 'IBM Plex Sans, Noto Sans SC, Microsoft YaHei, sans-serif';
  Chart.defaults.color = '#475569';
  Chart.defaults.plugins.legend.labels.color = '#475569';
  Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(15, 23, 42, 0.92)';
  Chart.defaults.plugins.tooltip.borderColor = 'rgba(148, 163, 184, 0.4)';
  Chart.defaults.plugins.tooltip.titleColor = '#f8fafc';
  Chart.defaults.plugins.tooltip.bodyColor = '#e2e8f0';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.elements.line.borderWidth = 3;
  Chart.defaults.elements.line.tension = 0.35;
  Chart.defaults.elements.point.radius = 3;
  Chart.defaults.elements.point.hoverRadius = 5;
  Chart.defaults.elements.bar.borderRadius = 6;
  Chart.defaults.scale.grid.color = 'rgba(148, 163, 184, 0.25)';
  Chart.defaults.scale.ticks.color = '#64748b';

  Chart.__enterpriseThemeLoaded = true;
})();
