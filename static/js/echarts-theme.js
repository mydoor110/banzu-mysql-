(function () {
  if (!window.echarts || window.echarts.__enterpriseThemeLoaded) {
    return;
  }

  const theme = {
    color: [
      '#2b5de6',
      '#0ea5e9',
      '#22c55e',
      '#f59e0b',
      '#ef4444',
      '#a855f7',
      '#14b8a6',
      '#f97316',
      '#64748b'
    ],
    backgroundColor: 'transparent',
    textStyle: {
      color: '#0f172a',
      fontFamily: 'IBM Plex Sans, Noto Sans SC, Microsoft YaHei, sans-serif'
    },
    title: {
      textStyle: {
        color: '#0f172a',
        fontWeight: 600
      },
      subtextStyle: {
        color: '#64748b'
      }
    },
    legend: {
      textStyle: {
        color: '#475569'
      }
    },
    tooltip: {
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderColor: 'rgba(148, 163, 184, 0.4)',
      textStyle: {
        color: '#f8fafc'
      },
      extraCssText: 'box-shadow: 0 12px 30px rgba(15, 23, 42, 0.25);'
    },
    grid: {
      left: 48,
      right: 32,
      top: 60,
      bottom: 44
    },
    categoryAxis: {
      axisLine: {
        lineStyle: { color: '#cbd5e1' }
      },
      axisTick: {
        lineStyle: { color: '#cbd5e1' }
      },
      axisLabel: {
        color: '#475569'
      },
      splitLine: {
        lineStyle: { color: '#e2e8f0' }
      }
    },
    valueAxis: {
      axisLine: {
        lineStyle: { color: '#cbd5e1' }
      },
      axisTick: {
        lineStyle: { color: '#cbd5e1' }
      },
      axisLabel: {
        color: '#475569'
      },
      splitLine: {
        lineStyle: { color: '#e2e8f0' }
      }
    },
    line: {
      smooth: true,
      symbolSize: 6,
      lineStyle: {
        width: 3
      },
      areaStyle: {
        opacity: 0.08
      }
    },
    bar: {
      barMaxWidth: 32,
      itemStyle: {
        borderRadius: [8, 8, 0, 0]
      }
    },
    pie: {
      label: {
        color: '#475569'
      },
      labelLine: {
        lineStyle: { color: '#cbd5e1' }
      }
    },
    radar: {
      axisName: {
        color: '#475569'
      },
      splitLine: {
        lineStyle: { color: '#e2e8f0' }
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(148, 163, 184, 0.06)', 'rgba(148, 163, 184, 0.12)']
        }
      }
    }
  };

  echarts.registerTheme('enterprise', theme);
  window.enterpriseChartPalette = theme.color;

  const originalInit = echarts.init;
  echarts.init = function (dom, themeName, opts) {
    return originalInit(dom, themeName || 'enterprise', opts);
  };

  echarts.__enterpriseThemeLoaded = true;
})();
