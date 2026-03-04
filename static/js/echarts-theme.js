(function () {
  function registerTheme() {
    if (!window.echarts || window.echarts.__enterpriseThemeLoaded) {
      return false;
    }

    // 引入大厂级可视化规范色板 (如 Arco Design / AntV)
    const colorPalette = [
      '#165DFF', // Primary Blue
      '#14C9C9', // Cyan
      '#FADC19', // Yellow
      '#FF7D00', // Orange
      '#F53F3F', // Red
      '#722ED1', // Purple
      '#00B42A', // Green
      '#F77234', // Tangerine
      '#3491FA', // Light Blue
      '#D91AD9'  // Magenta
    ];

    const theme = {
      color: colorPalette,
      backgroundColor: 'transparent',
      textStyle: {
        fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif'
      },
      title: {
        textStyle: {
          color: '#1D2129',
          fontWeight: 600,
          fontSize: 16
        },
        subtextStyle: {
          color: '#4E5969',
          fontSize: 12
        },
        padding: [8, 0, 12, 0]
      },
      legend: {
        textStyle: {
          color: '#4E5969',
          fontSize: 12
        },
        itemGap: 16,
        itemWidth: 14,
        itemHeight: 14,
        icon: 'circle'
      },
      tooltip: {
        backgroundColor: 'rgba(255, 255, 255, 0.98)',
        borderColor: '#E5E6EB',
        borderWidth: 1,
        padding: [8, 12],
        textStyle: {
          color: '#1D2129',
          fontSize: 13,
          fontWeight: 400
        },
        extraCssText: 'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); border-radius: 6px; backdrop-filter: blur(8px);'
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        top: 60,
        containLabel: true
      },
      categoryAxis: {
        axisLine: {
          show: true,
          lineStyle: {
            color: '#E5E6EB'
          }
        },
        axisTick: {
          show: false
        },
        axisLabel: {
          color: '#4E5969',
          margin: 12
        },
        splitLine: {
          show: false
        }
      },
      valueAxis: {
        axisLine: {
          show: false
        },
        axisTick: {
          show: false
        },
        axisLabel: {
          color: '#4E5969',
          margin: 12
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#E5E6EB',
            type: 'dashed'
          }
        }
      },
      line: {
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: {
          width: 3,
          shadowColor: 'rgba(0, 0, 0, 0.15)',
          shadowBlur: 8,
          shadowOffsetY: 4
        },
        itemStyle: {
          borderWidth: 2,
          borderColor: '#fff'
        },
        areaStyle: {
          opacity: 0.15
        }
      },
      bar: {
        barMaxWidth: 24,
        itemStyle: {
          borderRadius: [4, 4, 0, 0]
        }
      },
      pie: {
        emptyCircleStyle: {
          color: '#E5E6EB'
        },
        itemStyle: {
          borderWidth: 2,
          borderColor: '#fff'
        },
        label: {
          color: '#4E5969'
        },
        labelLine: {
          lineStyle: { color: '#E5E6EB' }
        }
      },
      radar: {
        axisName: {
          color: '#4E5969'
        },
        axisLine: {
          lineStyle: {
            color: '#E5E6EB'
          }
        },
        splitLine: {
          lineStyle: {
            color: '#E5E6EB'
          }
        },
        splitArea: {
          show: false
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
    return true;
  }

  if (registerTheme()) return;

  const timer = setInterval(() => {
    if (window.echarts) {
      registerTheme();
      clearInterval(timer);
    }
  }, 50);

  setTimeout(() => clearInterval(timer), 5000);
})();
