/**
 * export-config-store.js
 * PPT 导出配置持久化工具（localStorage）
 *
 * 用法：
 *   ExportConfigStore.save(config)       保存当前配置
 *   ExportConfigStore.load()             加载上次配置（返回 null 若无）
 *   ExportConfigStore.saveAsDefault(cfg) 保存为默认配置
 *   ExportConfigStore.loadDefault()      加载默认配置（返回 null 若无）
 *   ExportConfigStore.clear()            清除上次配置
 *   ExportConfigStore.clearDefault()     清除默认配置
 *   ExportConfigStore.lastSavedAt()      上次保存时间（ISO 字符串，若无则 null）
 */
(function (global) {
    'use strict';

    var KEY_LAST   = 'ppt_export_config_last';
    var KEY_DEFAULT = 'ppt_export_config_default';

    /**
     * 将 ExportConfig 序列化为可持久化的纯对象。
     * 去掉函数等不可序列化字段，只保留用户配置数据。
     */
    function serialize(config) {
        return {
            startMonth:          config.startMonth,
            endMonth:            config.endMonth,
            theme:               config.theme,
            appendSummaryGlobal: config.appendSummaryGlobal,
            summaryBulletLimit:  config.summaryBulletLimit,
            selectedCharts:      Array.from(config.selectedCharts || []),
            chartConfigs:        config.chartConfigs ? JSON.parse(JSON.stringify(config.chartConfigs)) : {},
            enhance: {
                trendShowLatest:         (config.enhance || {}).trendShowLatest  !== undefined ? config.enhance.trendShowLatest  : true,
                trendShowPeak:           (config.enhance || {}).trendShowPeak    !== undefined ? config.enhance.trendShowPeak    : true,
                trendShowAverage:        (config.enhance || {}).trendShowAverage !== undefined ? config.enhance.trendShowAverage : true,
                riskMatrixEnabled:       (config.enhance || {}).riskMatrixEnabled,
                riskMatrixTopN:          (config.enhance || {}).riskMatrixTopN,
                decisionSummaryEnabled:  (config.enhance || {}).decisionSummaryEnabled,
            },
            _savedAt: new Date().toISOString(),
        };
    }

    function parse(raw) {
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    var ExportConfigStore = {

        /** 保存当前配置为"上次配置" */
        save: function (config) {
            try {
                localStorage.setItem(KEY_LAST, JSON.stringify(serialize(config)));
            } catch (e) {
                console.warn('[ExportConfigStore] save 失败:', e);
            }
        },

        /** 加载上次配置，返回 plain object 或 null */
        load: function () {
            return parse(localStorage.getItem(KEY_LAST));
        },

        /** 保存为默认配置 */
        saveAsDefault: function (config) {
            try {
                localStorage.setItem(KEY_DEFAULT, JSON.stringify(serialize(config)));
            } catch (e) {
                console.warn('[ExportConfigStore] saveAsDefault 失败:', e);
            }
        },

        /** 加载默认配置，返回 plain object 或 null */
        loadDefault: function () {
            return parse(localStorage.getItem(KEY_DEFAULT));
        },

        /** 上次保存时间（ISO 字符串，若无则 null） */
        lastSavedAt: function () {
            var d = this.load();
            return d ? (d._savedAt || null) : null;
        },

        /** 格式化保存时间为可读字符串 */
        lastSavedAtDisplay: function () {
            var iso = this.lastSavedAt();
            if (!iso) return null;
            try {
                var d = new Date(iso);
                var pad = function (n) { return n < 10 ? '0' + n : '' + n; };
                return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
                    + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
            } catch (e) {
                return iso;
            }
        },

        /** 将已加载的 plain object 应用到 ExportConfig 对象 */
        applyTo: function (storedObj, ExportConfig) {
            if (!storedObj || !ExportConfig) return false;
            try {
                if (storedObj.startMonth) ExportConfig.startMonth = storedObj.startMonth;
                if (storedObj.endMonth)   ExportConfig.endMonth   = storedObj.endMonth;
                if (storedObj.theme)      ExportConfig.theme      = storedObj.theme;
                if (storedObj.appendSummaryGlobal !== undefined)
                    ExportConfig.appendSummaryGlobal = storedObj.appendSummaryGlobal;
                if (storedObj.summaryBulletLimit !== undefined)
                    ExportConfig.summaryBulletLimit = storedObj.summaryBulletLimit;

                // 恢复选中图表集合
                if (Array.isArray(storedObj.selectedCharts)) {
                    ExportConfig.selectedCharts = new Set(storedObj.selectedCharts);
                }

                // 恢复图表级配置
                if (storedObj.chartConfigs) {
                    ExportConfig.chartConfigs = storedObj.chartConfigs;
                }

                // 恢复增强配置
                if (storedObj.enhance) {
                    Object.assign(ExportConfig.enhance, storedObj.enhance);
                    delete ExportConfig.enhance._savedAt;
                }
                return true;
            } catch (e) {
                console.warn('[ExportConfigStore] applyTo 失败:', e);
                return false;
            }
        },

        /** 清除上次配置 */
        clear: function () {
            localStorage.removeItem(KEY_LAST);
        },

        /** 清除默认配置 */
        clearDefault: function () {
            localStorage.removeItem(KEY_DEFAULT);
        },
    };

    global.ExportConfigStore = ExportConfigStore;

})(window);
