/**
 * ═══════════════════════════════════════════════════════════════
 * 图表注册表 (Chart Registry)
 * 
 * 统一定义所有模块图表的渲染配置。
 * 仪表板页面 和 PPT导出 共享同一份配置。
 * 
 * 新增图表只需：
 *   1. 在对应模块的 charts 数组中添加一条配置
 *   2. 在仪表板 HTML 中添加容器 <div>
 *   3. PPT导出自动读取 — 无需修改
 * ═══════════════════════════════════════════════════════════════
 */
(function () {
    'use strict';

    // ── 模块定义 ──────────────────────────────────────────────────

    const MODULES = {

        // ═══════════════════════════════════════
        // 人员数据分析模块
        // ═══════════════════════════════════════
        analytics: {
            label: '人员数据分析',
            apiUrl: '/personnel/api/analytics-data',
            // 单接口：apiUrl 返回一个 JSON 对象，所有图表共享
            multiApi: false,
            charts: [
                {
                    id: 'risk_distribution', title: '驾龄风险分布',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'bar_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：电客车司机 | 单位：人 | 按入司后单驾年限分级，识别新手集中风险',
                    chartLabels: {
                        scope: '电客车司机', unit: '人',
                        sortRule: '按单驾年限分级', note: '识别新手集中风险',
                        sampleType: 'resp_field', sampleField: 'driver_count',
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) {
                        return Object.entries(resp.risk_distribution || {}).filter(function (e) { return e[1] > 0 && e[0] !== '未知'; });
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
                            legend: { bottom: '5%', type: 'scroll' },
                            color: ['#F53F3F', '#FF7D00', '#FADC19', '#00B42A', '#C9CDD4'],
                            series: [{
                                type: 'pie', radius: ['35%', '60%'], center: ['50%', '46%'],
                                label: { formatter: '{b}\n{c}人 ({d}%)', fontSize: 12 },
                                data: data.map(function (e) { return { name: e[0], value: e[1] }; })
                            }]
                        };
                    }
                },
                {
                    id: 'team_power', title: '班组经验结构对比',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'bar_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：电客车司机 | 单位：年 | 各部门平均司龄/驾龄/取证年限对比',
                    chartLabels: {
                        scope: '电客车司机', unit: '年',
                        sortRule: '各部门平均司龄/驾龄对比', note: '评估各部门经验结构',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) { return resp.team_power || []; },
                    buildOption: function (data) {
                        // 分组条形图（替代雷达图，更直观可读）
                        var teams = data.slice(0, 8).map(function (t) {
                            return (t.team || t.name || '') + '(' + (t.member_count || 0) + '人)';
                        });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            legend: { top: 35, data: ['平均司龄', '平均驾龄', '取证年限'] },
                            grid: { left: 120, right: 30, top: 70, bottom: 30 },
                            yAxis: { type: 'category', data: teams.reverse(), axisLabel: { fontSize: 11 } },
                            xAxis: { type: 'value', name: '年' },
                            series: [
                                { name: '平均司龄', type: 'bar', data: data.slice(0, 8).map(function (t) { return Number(Number(t.avg_tenure || 0).toFixed(1)); }).reverse(), itemStyle: { color: '#165DFF' }, barWidth: '22%' },
                                { name: '平均驾龄', type: 'bar', data: data.slice(0, 8).map(function (t) { return Number(Number(t.avg_solo || 0).toFixed(1)); }).reverse(), itemStyle: { color: '#14C9C9' }, barWidth: '22%' },
                                { name: '取证年限', type: 'bar', data: data.slice(0, 8).map(function (t) { return Number(Number(t.avg_cert || 0).toFixed(1)); }).reverse(), itemStyle: { color: '#F7BA1E' }, barWidth: '22%' }
                            ]
                        };
                    }
                },
                {
                    id: 'experience_scatter', title: '司龄 vs 取证年限散点图',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'scatter_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：电客车司机 | 单位：年 | 取证年限vs单驾年限，识别准师傅人选',
                    chartLabels: {
                        scope: '电客车司机', unit: '年',
                        sortRule: '单驾vs取证年限', note: '识别准师傅人选',
                        sampleType: 'array_length', sampleField: 'experience_scatter',
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) { return resp.experience_scatter || []; },
                    buildOption: function (data) {
                        var categories = ['新手', '普通', '准师傅', '资深师傅'];
                        var colorMap = { '新手': '#1f77b4', '普通': '#aec7e8', '准师傅': '#ff7f0e', '资深师傅': '#2ca02c' };
                        return {
                            tooltip: { trigger: 'item', formatter: function (p) { return p.data[2] + '<br/>取证: ' + p.data[0] + '年<br/>单驾: ' + p.data[1] + '年'; } },
                            legend: { bottom: '5%', data: categories },
                            grid: { left: 70, right: 40, top: 55, bottom: 60, containLabel: true },
                            xAxis: { type: 'value', name: '取证年限', splitLine: { lineStyle: { type: 'dashed' } } },
                            yAxis: { type: 'value', name: '单独驾驶年限', splitLine: { lineStyle: { type: 'dashed' } } },
                            series: categories.map(function (cat) {
                                return {
                                    name: cat, type: 'scatter', symbolSize: 10,
                                    itemStyle: { color: colorMap[cat] },
                                    data: data.filter(function (i) { return i.category === cat; }).map(function (i) { return [i.cert_years, i.solo_years, i.name]; })
                                };
                            })
                        };
                    }
                },
                {
                    id: 'stability_scatter', title: '工龄 vs 司龄散点图',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'scatter_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：电客车司机 | 单位：年 | 司龄vs工龄，区分应届/社招/老员工结构',
                    chartLabels: {
                        scope: '电客车司机', unit: '年',
                        sortRule: '工龄vs司龄', note: '区分人员来源结构',
                        sampleType: 'array_length', sampleField: 'stability_scatter',
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) { return resp.stability_scatter || []; },
                    buildOption: function (data) {
                        var cats = ['应届入职', '社招(新)', '社招(老)'];
                        var colors = { '应届入职': '#2ca02c', '社招(新)': '#1f77b4', '社招(老)': '#ff7f0e' };
                        return {
                            tooltip: { trigger: 'item', formatter: function (p) { return p.data[2] + '<br/>司龄: ' + p.data[0] + '年<br/>工龄: ' + p.data[1] + '年'; } },
                            legend: { bottom: '5%', data: cats },
                            grid: { left: 70, right: 40, top: 55, bottom: 60, containLabel: true },
                            xAxis: { type: 'value', name: '司龄', splitLine: { lineStyle: { type: 'dashed' } } },
                            yAxis: { type: 'value', name: '工龄', splitLine: { lineStyle: { type: 'dashed' } } },
                            series: cats.map(function (cat) {
                                return {
                                    name: cat, type: 'scatter', symbolSize: 10,
                                    itemStyle: { color: colors[cat] },
                                    data: data.filter(function (i) { return i.category === cat; }).map(function (i) { return [i.tenure, i.working, i.name]; })
                                };
                            })
                        };
                    }
                },
                {
                    id: 'hometown_stats', title: '籍贯分布统计',
                    exportable: true, defaultSelected: false, priority: 'low',
                    schema: 'bar_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：全部在册人员 | 单位：人 | 排序：按人数降序 | 补充图',
                    chartLabels: {
                        scope: '在册人员', unit: '人',
                        sortRule: '按人数降序', note: '补充参考',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) {
                        return Object.entries(resp.hometown_stats || {}).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 15);
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis' },
                            grid: { left: '3%', right: '4%', bottom: '5%', containLabel: true },
                            xAxis: { type: 'category', data: data.map(function (h) { return h[0]; }), axisLabel: { interval: 0, rotate: 30 } },
                            yAxis: { type: 'value', name: '人数' },
                            series: [{
                                type: 'bar', data: data.map(function (h) { return h[1]; }),
                                label: { show: true, position: 'top' },
                                itemStyle: { color: '#14C9C9' }
                            }]
                        };
                    }
                },
                {
                    id: 'political_stats', title: '政治面貌分布',
                    exportable: true, defaultSelected: false, priority: 'low',
                    schema: 'bar_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：全部在册人员 | 单位：人 | 党员/团员/群众占比统计 | 补充图',
                    chartLabels: {
                        scope: '在册人员', unit: '人',
                        sortRule: '分类占比统计', note: '补充参考',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) {
                        return Object.entries(resp.political_stats || {}).filter(function (e) { return e[1] > 0; });
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
                            legend: { orient: 'vertical', left: 'left', top: '10%' },
                            color: ['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4', '#9467bd'],
                            series: [{
                                type: 'pie', radius: ['35%', '65%'], center: ['55%', '55%'],
                                itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
                                label: { formatter: '{b}\n{c}人', fontSize: 12 },
                                data: data.map(function (e) { return { name: e[0], value: e[1] }; })
                            }]
                        };
                    }
                },
                // ── 对比型图表（仅多部门管理账号可见）──
                {
                    id: 'dept_rookie_compare', title: '各部门新手占比对比',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'group_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    visibility: 'multi_dept',
                    summaryHint: '统计对象：电客车司机 | 单位：% | 仅多部门管理账号展示 | 横向对比各部门新手占比',
                    chartLabels: {
                        scope: '电客车司机', unit: '%',
                        sortRule: '按新手占比降序', note: '仅多部门管理账号展示',
                        sampleType: 'none', sampleField: null,
                        extra: { label: '司机总数', sampleType: 'resp_field', sampleField: 'driver_count' },
                        rangeType: 'snapshot'
                    },
                    extractData: function (resp) { return resp.dept_rookie_compare || []; },
                    buildOption: function (data) {
                        var sorted = data.slice().sort(function (a, b) { return b.rate - a.rate; });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: function (p) { return p[0].name + '<br/>新手占比: ' + p[0].value + '%<br/>新手人数: ' + (sorted[p[0].dataIndex] || {}).count + '人'; } },
                            grid: { left: 120, right: 50, top: 50, bottom: 30 },
                            yAxis: { type: 'category', data: sorted.map(function (d) { return d.name; }).reverse(), axisLabel: { fontSize: 11 } },
                            xAxis: { type: 'value', name: '%', max: 100 },
                            series: [{
                                type: 'bar', barWidth: '55%',
                                data: sorted.map(function (d) { return d.rate; }).reverse(),
                                itemStyle: { color: '#FF7D00' },
                                label: { show: true, position: 'right', formatter: '{c}%', fontSize: 11 }
                            }]
                        };
                    }
                },
                {
                    id: 'dept_backbone_compare', title: '各部门骨干人数对比',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'group_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    visibility: 'multi_dept',
                    summaryHint: '统计对象：电客车司机(单驾>=3年) | 单位：人 | 仅多部门管理账号展示',
                    chartLabels: {
                        scope: '骨干司机(单驾≥3年)', unit: '人',
                        sortRule: '按骨干人数降序', note: '仅多部门管理账号展示',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'snapshot'
                    },
                    extractData: function (resp) { return resp.dept_backbone_compare || []; },
                    buildOption: function (data) {
                        var sorted = data.slice().sort(function (a, b) { return b.count - a.count; });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: 120, right: 50, top: 50, bottom: 30 },
                            yAxis: { type: 'category', data: sorted.map(function (d) { return d.name; }).reverse(), axisLabel: { fontSize: 11 } },
                            xAxis: { type: 'value', name: '人数' },
                            series: [{
                                type: 'bar', barWidth: '55%',
                                data: sorted.map(function (d) { return d.count; }).reverse(),
                                itemStyle: { color: '#00B42A' },
                                label: { show: true, position: 'right', formatter: '{c}人', fontSize: 11 }
                            }]
                        };
                    }
                }
            ]
        },

        // ═══════════════════════════════════════
        // 培训统计分析模块
        // ═══════════════════════════════════════
        training: {
            label: '培训统计分析',
            apiUrl: '/training/api/data',
            multiApi: false,
            // 培训数据是原始记录数组，需要预处理
            preprocessor: function (rawRows) {
                var rows = Array.isArray(rawRows) ? rawRows : [];
                var monthMap = {};
                var projectCounts = {};
                var personStats = {};
                rows.forEach(function (r) {
                    var m = (r.training_date || '').slice(0, 7);
                    if (m) {
                        if (!monthMap[m]) monthMap[m] = { total: 0, qualified: 0 };
                        monthMap[m].total++;
                        if (r.is_qualified) monthMap[m].qualified++;
                    }
                    // 项目级统计
                    var proj = r.project_name || r.specific_problem || '未知';
                    projectCounts[proj] = (projectCounts[proj] || 0) + 1;
                    // 人员级统计
                    var name = r.name || '未知';
                    if (!personStats[name]) personStats[name] = { qualified: 0, disqualified: 0 };
                    if (r.is_qualified) { personStats[name].qualified++; }
                    else { personStats[name].disqualified++; }
                });
                var monthKeys = Object.keys(monthMap).sort();
                return { rows: rows, monthMap: monthMap, monthKeys: monthKeys, projectCounts: projectCounts, personStats: personStats };
            },
            charts: [
                {
                    id: 'training_monthly_rate', title: '月度培训合格率趋势',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'trend_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    pptEnhance: { type: 'trend', seriesType: 'single', seriesNames: ['合格率'], yUnit: '%' },
                    summaryHint: '统计对象：培训记录 | 单位：% | 观察合格率趋势，识别培训质量拐点',
                    chartLabels: {
                        scope: '培训记录', unit: '%',
                        sortRule: '按月份顺序', note: '识别培训质量拐点',
                        sampleType: 'processed_rows', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    extractData: function (resp, processed) { return processed.monthKeys; },
                    buildOption: function (data, processed) {
                        var monthMap = processed.monthMap;
                        return {
                            tooltip: { trigger: 'axis' },
                            grid: { left: 65, right: 30, top: 55, bottom: 50 },
                            xAxis: { type: 'category', data: data, axisLabel: { rotate: 30 } },
                            yAxis: { type: 'value', min: 0, max: 100, name: '合格率(%)', axisLabel: { formatter: '{value}%' } },
                            series: [{
                                type: 'line', smooth: true,
                                data: data.map(function (m) { return monthMap[m].total > 0 ? +(monthMap[m].qualified / monthMap[m].total * 100).toFixed(1) : 0; }),
                                areaStyle: { opacity: 0.15, color: '#165DFF' },
                                itemStyle: { color: '#165DFF' },
                                label: { show: true, formatter: '{c}%' },
                                markLine: { data: [{ type: 'average', name: '平均' }], lineStyle: { color: '#F53F3F', type: 'dashed' } }
                            }]
                        };
                    }
                },
                {
                    id: 'training_project_top10', title: '失格最多项目 Top10',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'ranked_bar', supportsPreview: true, supportsSummary: true, supportsManualBullets: true,
                    candidateProvider: { type: 'project_top1' },
                    pptEnhance: { type: 'decision_summary', summaryMode: 'project_top10' },
                    chartLabels: {
                        scope: '培训记录', unit: '次',
                        sortRule: '按不合格次数降序', note: '定位失格集中的项目',
                        sampleType: 'disqualified_rows', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    drilldown: true, drilldownUrl: '/training/api/analytics/project-drilldown',
                    clickBehavior: 'modal',
                    drilldownParamBuilder: function (params) { return { project: params.name }; },
                    drilldownColumns: [
                        { key: 'date', label: '日期', width: '90px' },
                        { key: 'empNo', label: '工号', width: '80px' },
                        { key: 'name', label: '姓名', width: '80px' },
                        { key: 'team', label: '班组', width: '100px' },
                        { key: 'projectName', label: '项目', width: '120px' },
                        { key: 'problemType', label: '问题类型', width: '100px' },
                        { key: 'specificProblem', label: '具体问题' },
                        { key: 'assessor', label: '鉴定人', width: '80px' },
                        { key: 'score', label: '分数', width: '60px' }
                    ],
                    summaryHint: '统计对象：培训记录 | 单位：次 | 排序：按不合格次数降序 | 定位失格集中的项目',
                    extractData: function (resp, processed) {
                        var projFail = {};
                        processed.rows.filter(function (r) { return !r.is_qualified; }).forEach(function (r) {
                            var k = r.project_name || r.specific_problem || '未知';
                            projFail[k] = (projFail[k] || 0) + 1;
                        });
                        return Object.entries(projFail).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 10);
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis' },
                            grid: { left: 190, right: 50, top: 55, bottom: 40 },
                            xAxis: { type: 'value', name: '不合格次数' },
                            yAxis: {
                                type: 'category', data: data.map(function (e) { return e[0]; }).reverse(),
                                axisLabel: { width: 170, overflow: 'truncate', fontSize: 11 }
                            },
                            series: [{
                                type: 'bar', data: data.map(function (e) { return e[1]; }).reverse(),
                                itemStyle: { color: '#F53F3F' }, label: { show: true, position: 'right' }
                            }]
                        };
                    }
                },
                {
                    id: 'training_problem_type', title: '培训问题分类占比',
                    exportable: true, defaultSelected: true, priority: 'medium',
                    schema: 'pie_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：不合格故障记录 | 单位：次 | 分析故障分类，明确改进方向',
                    chartLabels: {
                        scope: '不合格故障记录', unit: '次',
                        sortRule: '按发生次数降序', note: '明确改进方向',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    extractData: function (resp, processed) {
                        var probMap = {};
                        processed.rows.filter(function (r) { return !r.is_qualified; }).forEach(function (r) {
                            var category = r.category_name || '未分类';
                            probMap[category] = (probMap[category] || 0) + 1;
                        });
                        return Object.entries(probMap).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 8);
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'item', formatter: '{b}: {c}次 ({d}%)' },
                            legend: { bottom: '5%', type: 'scroll' },
                            color: ['#F53F3F', '#FF7D00', '#FADC19', '#165DFF', '#00B42A', '#14C9C9', '#722ED1', '#C9CDD4'],
                            series: [{
                                type: 'pie', radius: ['30%', '60%'], center: ['50%', '46%'],
                                label: { formatter: '{b}\n{c}次 ({d}%)', fontSize: 12 },
                                data: data.map(function (e) { return { name: e[0], value: e[1] }; })
                            }]
                        };
                    }
                },
                {
                    id: 'training_monthly_count', title: '月度培训人次趋势',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'trend_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    pptEnhance: { type: 'trend', seriesType: 'double', seriesNames: ['总人次', '不合格人次'], yUnit: '人次' },
                    summaryHint: '统计对象：培训记录 | 单位：人次 | 培训规模趋势，合格与不合格人次对比',
                    chartLabels: {
                        scope: '培训记录', unit: '人次',
                        sortRule: '按月份顺序', note: '合格与不合格人次对比',
                        sampleType: 'processed_rows', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    extractData: function (resp, processed) { return processed.monthKeys; },
                    buildOption: function (data, processed) {
                        var monthMap = processed.monthMap;
                        return {
                            tooltip: { trigger: 'axis' },
                            legend: { top: 30 },
                            grid: { left: 60, right: 30, top: 65, bottom: 50 },
                            xAxis: { type: 'category', data: data, axisLabel: { rotate: 30 } },
                            yAxis: { type: 'value', name: '人次' },
                            series: [
                                {
                                    name: '总人次', type: 'bar',
                                    data: data.map(function (m) { return monthMap[m].total; }),
                                    itemStyle: { color: '#165DFF' },
                                    label: { show: true, position: 'top' }
                                },
                                {
                                    name: '不合格人次', type: 'bar',
                                    data: data.map(function (m) { return monthMap[m].total - monthMap[m].qualified; }),
                                    itemStyle: { color: '#F53F3F' }
                                }
                            ]
                        };
                    }
                },
                {
                    id: 'training_project_count_top20', title: '实操项目人次 Top20',
                    exportable: true, defaultSelected: false, priority: 'low',
                    schema: 'ranked_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：培训记录 | 单位：次 | 排序：按总次数降序 | 补充图',
                    chartLabels: {
                        scope: '实操项目', unit: '项',
                        sortRule: '按总训练人次降序', note: '了解重点考核项目分布',
                        sampleType: 'array_length', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    extractData: function (resp, processed) {
                        return Object.entries(processed.projectCounts)
                            .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 20);
                    },
                    buildOption: function (data) {
                        var projects = data.map(function (e) { return e[0]; }).reverse();
                        var counts = data.map(function (e) { return e[1]; }).reverse();
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: 190, right: 50, top: 55, bottom: 40 },
                            xAxis: { type: 'value', name: '次数' },
                            yAxis: {
                                type: 'category', data: projects,
                                axisLabel: { width: 170, overflow: 'truncate', fontSize: 11 }
                            },
                            series: [{
                                type: 'bar', data: counts,
                                itemStyle: { color: '#165DFF' },
                                label: { show: true, position: 'right', formatter: '{c}次' }
                            }]
                        };
                    }
                },
                {
                    id: 'training_person_count', title: '人员培训合格/失格次数',
                    exportable: true, defaultSelected: false, priority: 'low',
                    schema: 'bar_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    drilldown: true, drilldownUrl: '/training/api/analytics/person-disqualified-drilldown',
                    clickBehavior: 'modal',
                    drilldownParamBuilder: function (params) { return { name: params.name }; },
                    drilldownGuard: function (params) {
                        return params.seriesName === '失格次数' && params.value > 0;
                    },
                    drilldownColumns: [
                        { key: 'date', label: '日期', width: '90px' },
                        { key: 'empNo', label: '工号', width: '80px' },
                        { key: 'name', label: '姓名', width: '80px' },
                        { key: 'team', label: '班组', width: '100px' },
                        { key: 'projectName', label: '项目', width: '120px' },
                        { key: 'problemType', label: '问题类型', width: '100px' },
                        { key: 'specificProblem', label: '具体问题' },
                        { key: 'assessor', label: '鉴定人', width: '80px' },
                        { key: 'score', label: '分数', width: '60px' }
                    ],
                    summaryHint: '统计对象：人员 | 单位：次 | 排序：按总次数降序 | 补充图（非风险排序）',
                    chartLabels: {
                        scope: '被考核人员', unit: '人',
                        sortRule: '按总次数降序', note: '非风险排序',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    extractData: function (resp, processed) {
                        return Object.entries(processed.personStats)
                            .sort(function (a, b) { return (b[1].qualified + b[1].disqualified) - (a[1].qualified + a[1].disqualified); });
                    },
                    buildOption: function (data) {
                        var names = data.map(function (e) { return e[0]; });
                        var qualified = data.map(function (e) { return e[1].qualified; });
                        var disqualified = data.map(function (e) { return e[1].disqualified; });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            legend: { top: 30 },
                            grid: { left: 60, right: 30, top: 65, bottom: 60 },
                            xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 30 } },
                            yAxis: { type: 'value', name: '次数' },
                            dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 0 }],
                            series: [
                                { name: '合格次数', type: 'bar', stack: 'total', data: qualified, itemStyle: { color: '#165DFF' }, barWidth: '60%' },
                                { name: '失格次数', type: 'bar', stack: 'total', data: disqualified, itemStyle: { color: '#F53F3F' }, barWidth: '60%' }
                            ]
                        };
                    }
                },
                // ── 对比型图表（仅多部门管理账号可见）──
                {
                    id: 'training_dept_rate_compare', title: '各部门培训合格率对比',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'group_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    visibility: 'multi_dept',
                    summaryHint: '统计对象：培训记录 | 单位：% | 仅多部门管理账号展示 | 横向对比各部门合格率',
                    chartLabels: {
                        scope: '基层部门', unit: '%',
                        sortRule: '按合格率降序', note: '多部门管理员专有',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    selfFetchUrl: '/training/api/analytics/dept-rate-compare',
                    extractData: function (resp) { return Array.isArray(resp) ? resp : []; },
                    buildOption: function (data) {
                        var sorted = data.slice().sort(function (a, b) { return a.rate - b.rate; });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: 120, right: 50, top: 40, bottom: 30 },
                            yAxis: { type: 'category', data: sorted.map(function (d) { return d.name; }), axisLabel: { fontSize: 11 } },
                            xAxis: { type: 'value', name: '%', min: 0, max: 100 },
                            series: [{
                                type: 'bar', barWidth: '55%',
                                data: sorted.map(function (d) {
                                    return { value: d.rate, itemStyle: { color: d.rate < 80 ? '#F53F3F' : d.rate < 90 ? '#FF7D00' : '#00B42A' } };
                                }),
                                label: { show: true, position: 'right', formatter: '{c}%', fontSize: 11 }
                            }]
                        };
                    }
                }
            ]
        },

        // ═══════════════════════════════════════
        // 安全管理分析模块
        // ═══════════════════════════════════════
        safety: {
            label: '安全管理分析',
            apiUrls: [
                '/safety/api/analytics/severity-distribution',
                '/safety/api/analytics/top-loss-items',
                '/safety/api/analytics/personnel-risk-matrix',
                '/safety/api/analytics/daily-trend',
                '/safety/api/analytics/top-contributors',
                '/safety/api/analytics/top-frequency-items',
                '/safety/api/analytics/dept-issue-compare',
                '/safety/api/analytics/dept-risk-compare'
            ],
            multiApi: true,
            charts: [
                {
                    id: 'safety_severity', title: '安全问题严重度分级',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'ranked_bar', supportsPreview: true, supportsSummary: true, supportsManualBullets: true,
                    candidateProvider: { type: 'severity_all_scores', minScore: 3 },
                    pptEnhance: {
                        type: 'decision_summary',
                        summaryMode: 'severity',
                        statsRule: { minScore: 3 },
                        bulletsRule: {
                            minScore: 4,
                            fallbackMinScore: 3,
                            maxItems: 5,
                            sort: 'score_desc_date_desc',
                            fields: ['date', 'person', 'problem', 'score']
                        }
                    },
                    chartLabels: {
                        scope: '安全问题记录', unit: '次',
                        sortRule: '按扣分分值分级', note: '3分及以上可下钻',
                        sampleType: 'sum_values', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    drilldown: true, drilldownUrl: '/safety/api/analytics/severity-drilldown',
                    clickBehavior: 'modal',
                    drilldownParamBuilder: function (params) { return { score: params.name }; },
                    drilldownColumns: [
                        { key: 'date', label: '日期', width: '90px' },
                        { key: 'inspectedPerson', label: '被检查人', width: '80px' },
                        { key: 'team', label: '班组', width: '100px' },
                        { key: 'location', label: '地点', width: '80px' },
                        { key: 'inspectionItem', label: '检查项目', width: '100px' },
                        { key: 'hazardDescription', label: '问题描述' },
                        { key: 'correctiveMeasures', label: '整改措施', width: '120px' },
                        { key: 'score', label: '扣分', width: '60px' }
                    ],
                    summaryHint: '统计对象：安全问题记录 | 单位：次 | 按实际扣分分值统计，3分及以上可下钻',
                    apiIndex: 0,
                    extractData: function (resp) {
                        var arr = Array.isArray(resp) ? resp : [];
                        return arr.filter(function (i) { return (i.value || 0) > 0; });
                    },
                    buildOption: function (data) {
                        // 横向条形图（替代饼图，更清晰对比各级别差异）
                        var sorted = data.slice().sort(function (a, b) { return a.value - b.value; });
                        var colorMap = { '重大': '#F53F3F', '严重': '#FF7D00', '一般': '#FADC19', '轻微': '#00B42A' };
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: 100, right: 50, top: 50, bottom: 30 },
                            yAxis: { type: 'category', data: sorted.map(function (d) { return d.name; }), axisLabel: { fontSize: 12 } },
                            xAxis: { type: 'value', name: '次数', minInterval: 1 },
                            series: [{
                                type: 'bar', barWidth: '55%',
                                data: sorted.map(function (d) {
                                    return { value: d.value, itemStyle: { color: colorMap[d.name] || '#165DFF' } };
                                }),
                                label: { show: true, position: 'right', formatter: '{c}次', fontSize: 12 }
                            }]
                        };
                    }
                },
                {
                    id: 'safety_top_loss', title: '高频失分问题 Top10',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'ranked_bar', supportsPreview: true, supportsSummary: true, supportsManualBullets: true,
                    candidateProvider: { type: 'top_loss_top1' },
                    pptEnhance: { type: 'decision_summary', summaryMode: 'top_loss' },
                    chartLabels: {
                        scope: '违规项', unit: '分',
                        sortRule: '按累计扣分降序', note: '聚焦核心失分点',
                        sampleType: 'array_length', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    drilldown: true, drilldownUrl: '/safety/api/analytics/top-loss-drilldown',
                    clickBehavior: 'modal',
                    drilldownParamBuilder: function (params) { return { item: params.name }; },
                    drilldownColumns: [
                        { key: 'date', label: '日期', width: '90px' },
                        { key: 'inspectedPerson', label: '被检查人', width: '80px' },
                        { key: 'team', label: '班组', width: '100px' },
                        { key: 'department', label: '部门', width: '100px' },
                        { key: 'location', label: '地点', width: '80px' },
                        { key: 'hazardDescription', label: '问题描述' },
                        { key: 'correctiveMeasures', label: '整改措施', width: '120px' },
                        { key: 'score', label: '扣分', width: '60px' }
                    ],
                    summaryHint: '统计对象：安全问题记录 | 单位：分 | 排序：按累计扣分降序 | 定位总损失最大的问题项',
                    apiIndex: 1,
                    extractData: function (resp) {
                        // resp = {items: [...], scores: [...]}
                        if (!resp || !resp.items) return [];
                        return resp.items.map(function (name, i) { return { name: name, score: resp.scores[i] || 0 }; });
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis' },
                            grid: { left: 200, right: 50, top: 55, bottom: 40 },
                            xAxis: { type: 'value', name: '扣分总计' },
                            yAxis: {
                                type: 'category', data: data.map(function (d) { return d.name; }).reverse(),
                                axisLabel: { width: 180, overflow: 'truncate', fontSize: 11 }
                            },
                            series: [{
                                type: 'bar', data: data.map(function (d) { return d.score; }).reverse(),
                                itemStyle: { color: '#FF7D00' }, label: { show: true, position: 'right' }
                            }]
                        };
                    }
                },
                {
                    id: 'safety_risk_matrix', title: '人员安全风险矩阵',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'matrix_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    chartLabels: {
                        scope: '被检查人员', unit: '人',
                        sortRule: '违规次数 × 累计扣分双维度', note: '右上象限为高风险人员',
                        sampleType: 'array_length', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    drilldown: true,
                    clickBehavior: 'navigate',
                    navigateUrlBuilder: function (dataItem) {
                        if (dataItem && dataItem.matched !== false && dataItem.emp_no) {
                            return '/personnel/capability-profile?emp_no=' + encodeURIComponent(dataItem.emp_no);
                        }
                        return null; // 返回 null 表示不可跳转，bindDrilldown 会 toast
                    },
                    pptEnhance: { type: 'risk_matrix', annotateTopN: 5, showSideList: true },
                    summaryHint: '统计对象：人员 | 单位：次/分 | 违规次数vs累计扣分，识别右上象限高风险人员',
                    apiIndex: 2,
                    extractData: function (resp) {
                        return Array.isArray(resp) ? resp : [];
                    },
                    buildOption: function (data) {
                        // 计算均值用于象限线
                        var sumX = 0, sumY = 0;
                        var pts = data.map(function (m) {
                            var x = Array.isArray(m.value) ? m.value[0] : (m.count || 0);
                            var y = Array.isArray(m.value) ? m.value[1] : (m.total_score || 0);
                            sumX += x; sumY += y;
                            return [x, y, m.name || ''];
                        });
                        var avgX = pts.length ? (sumX / pts.length) : 1;
                        var avgY = pts.length ? (sumY / pts.length) : 1;
                        return {
                            tooltip: {
                                trigger: 'item',
                                formatter: function (p) {
                                    var m = data[p.dataIndex] || {};
                                    var label = (p.data[2] || '') + '<br/>违规: ' + p.data[0] + '次<br/>累计扣分: ' + p.data[1];
                                    if (m.matched === false) {
                                        label += '<br/><span style="color:#F53F3F">未匹配工号，不可跳转</span>';
                                    } else if (m.emp_no) {
                                        label += '<br/>工号: ' + m.emp_no;
                                    }
                                    if (m.team) label += '<br/>班组: ' + m.team;
                                    return label;
                                }
                            },
                            grid: { left: 70, right: 30, top: 55, bottom: 55 },
                            xAxis: { type: 'value', name: '违规次数', minInterval: 1 },
                            yAxis: { type: 'value', name: '累计扣分' },
                            series: [
                                {
                                    type: 'scatter', symbolSize: 14,
                                    data: pts,
                                    itemStyle: { color: '#F53F3F', opacity: 0.75 },
                                    label: { show: data.length <= 20, formatter: function (p) { return p.data[2]; }, position: 'right', fontSize: 10 }
                                },
                                {
                                    // 均值竖线（违规次数均值）
                                    type: 'line', symbol: 'none', silent: true,
                                    markLine: {
                                        silent: true,
                                        lineStyle: { color: '#999', type: 'dashed', width: 1.5 },
                                        label: { show: true, fontSize: 10, color: '#666' },
                                        data: [
                                            { xAxis: avgX, label: { formatter: '均值 ' + avgX.toFixed(1), position: 'end' } },
                                            { yAxis: avgY, label: { formatter: '均值 ' + avgY.toFixed(1), position: 'end' } }
                                        ]
                                    }
                                }
                            ]
                        };
                    }
                },
                {
                    id: 'safety_daily_trend', title: '安全问题日趋势',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'trend_chart', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    pptEnhance: { type: 'trend', seriesType: 'dual_axis', seriesNames: ['违规次数', '累计扣分'], yUnits: ['次', '分'] },
                    summaryHint: '统计对象：安全问题记录 | 单位：次/分 | 观察阶段性风险抬头和整改效果',
                    chartLabels: {
                        scope: '安全问题记录', unit: '次/分',
                        sortRule: '近30日趋势', note: '观察阶段性风险抬头和整改效果',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    apiIndex: 3,
                    extractData: function (resp) {
                        // resp = {dates: [...], counts: [...], scores: [...]}
                        if (!resp || !resp.dates || resp.dates.length === 0) return [];
                        return resp;
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis' },
                            legend: { top: 30 },
                            grid: { left: 60, right: 50, top: 65, bottom: 60 },
                            xAxis: { type: 'category', data: data.dates, axisLabel: { rotate: 35, fontSize: 10 } },
                            yAxis: [
                                { type: 'value', name: '违规次数', minInterval: 1 },
                                { type: 'value', name: '扣分', position: 'right' }
                            ],
                            series: [
                                {
                                    name: '违规次数', type: 'bar', data: data.counts,
                                    itemStyle: { color: '#FF7D00' },
                                    label: { show: true, position: 'top' }
                                },
                                {
                                    name: '累计扣分', type: 'line', yAxisIndex: 1, data: data.scores,
                                    itemStyle: { color: '#F53F3F' }, smooth: true
                                }
                            ]
                        };
                    }
                },
                {
                    id: 'safety_top_contributors', title: '整改任务最多人员',
                    exportable: true, defaultSelected: false, priority: 'low',
                    schema: 'ranked_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    summaryHint: '统计对象：整改责任人(rectifier) | 单位：次 | 排序：按整改次数降序 | 补充图',
                    chartLabels: {
                        scope: '整改责任人', unit: '次',
                        sortRule: '按整改次数降序', note: '关注工作负担',
                        sampleType: 'array_length', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    apiIndex: 4,
                    extractData: function (resp) {
                        // resp = {names: [...], counts: [...]}
                        if (!resp || !resp.names || resp.names.length === 0) return [];
                        return resp;
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                            xAxis: { type: 'category', data: data.names, axisLabel: { rotate: 45 } },
                            yAxis: { type: 'value', name: '整改次数' },
                            series: [{
                                name: '整改次数', type: 'bar', data: data.counts,
                                itemStyle: { color: '#f39c12' },
                                barWidth: '50%',
                                label: { show: true, position: 'top' }
                            }]
                        };
                    }
                },
                // ── 新增：高频问题项（按次数）──
                {
                    id: 'safety_top_frequency', title: '高频安全问题 Top10',
                    exportable: true, defaultSelected: true, priority: 'high',
                    schema: 'ranked_bar', supportsPreview: true, supportsSummary: true, supportsManualBullets: true,
                    pptEnhance: { type: 'decision_summary', summaryMode: 'top_frequency' },
                    chartLabels: {
                        scope: '安全问题记录', unit: '次',
                        sortRule: '按发生次数降序', note: '定位最常发生的问题项',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    drilldown: true, drilldownUrl: '/safety/api/analytics/top-frequency-drilldown',
                    clickBehavior: 'modal',
                    drilldownParamBuilder: function (params) { return { item: params.name }; },
                    drilldownColumns: [
                        { key: 'date', label: '日期', width: '90px' },
                        { key: 'inspectedPerson', label: '被检查人', width: '80px' },
                        { key: 'team', label: '班组', width: '100px' },
                        { key: 'department', label: '部门', width: '100px' },
                        { key: 'location', label: '地点', width: '80px' },
                        { key: 'hazardDescription', label: '问题描述' },
                        { key: 'correctiveMeasures', label: '整改措施', width: '120px' },
                        { key: 'score', label: '扣分', width: '60px' }
                    ],
                    summaryHint: '统计对象：安全问题记录 | 单位：次 | 排序：按发生次数降序 | 定位最常发生的问题项',
                    apiIndex: 5,
                    extractData: function (resp) {
                        if (!resp || !resp.items) return [];
                        return resp.items.map(function (name, i) { return { name: name, count: resp.counts[i] || 0 }; });
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis' },
                            grid: { left: 200, right: 50, top: 55, bottom: 40 },
                            xAxis: { type: 'value', name: '发生次数', minInterval: 1 },
                            yAxis: {
                                type: 'category', data: data.map(function (d) { return d.name; }).reverse(),
                                axisLabel: { width: 180, overflow: 'truncate', fontSize: 11 }
                            },
                            series: [{
                                type: 'bar', data: data.map(function (d) { return d.count; }).reverse(),
                                itemStyle: { color: '#F53F3F' }, label: { show: true, position: 'right', formatter: '{c}次' }
                            }]
                        };
                    }
                },
                // ── 对比型图表（仅多部门管理账号可见）──
                {
                    id: 'safety_dept_issue_compare', title: '各部门问题数对比',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'group_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    visibility: 'multi_dept',
                    summaryHint: '统计对象：安全问题记录 | 单位：次 | 仅多部门管理账号展示',
                    chartLabels: {
                        scope: '基层部门', unit: '个',
                        sortRule: '按问题数降序', note: '仅多部门管理账号展示',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    apiIndex: 6,
                    extractData: function (resp) {
                        return Array.isArray(resp) ? resp : [];
                    },
                    buildOption: function (data) {
                        var sorted = data.slice().sort(function (a, b) { return b.count - a.count; });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: 120, right: 50, top: 50, bottom: 30 },
                            yAxis: { type: 'category', data: sorted.map(function (d) { return d.name; }).reverse(), axisLabel: { fontSize: 11 } },
                            xAxis: { type: 'value', name: '问题数', minInterval: 1 },
                            series: [{
                                type: 'bar', barWidth: '55%',
                                data: sorted.map(function (d) { return d.count; }).reverse(),
                                itemStyle: { color: '#FF7D00' },
                                label: { show: true, position: 'right', formatter: '{c}', fontSize: 11 }
                            }]
                        };
                    }
                },
                {
                    id: 'safety_dept_risk_compare', title: '各部门高风险人员对比',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    schema: 'group_bar', supportsPreview: true, supportsSummary: false, supportsManualBullets: false,
                    visibility: 'multi_dept',
                    summaryHint: '统计对象：人员 | 单位：人 | 仅多部门管理账号展示 | 高风险=右上象限',
                    chartLabels: {
                        scope: '基层部门', unit: '个',
                        sortRule: '按高风险人数降序', note: '仅多部门管理账号展示',
                        sampleType: 'none', sampleField: null,
                        extra: null, rangeType: 'filter'
                    },
                    apiIndex: 7,
                    extractData: function (resp) {
                        return Array.isArray(resp) ? resp : [];
                    },
                    buildOption: function (data) {
                        var sorted = data.slice().sort(function (a, b) { return b.count - a.count; });
                        return {
                            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                            grid: { left: 120, right: 50, top: 50, bottom: 30 },
                            yAxis: { type: 'category', data: sorted.map(function (d) { return d.name; }).reverse(), axisLabel: { fontSize: 11 } },
                            xAxis: { type: 'value', name: '高风险人员数', minInterval: 1 },
                            series: [{
                                type: 'bar', barWidth: '55%',
                                data: sorted.map(function (d) { return d.count; }).reverse(),
                                itemStyle: { color: '#F53F3F' },
                                label: { show: true, position: 'right', formatter: '{c}人', fontSize: 11 }
                            }]
                        };
                    }
                }
            ]
        }
    };

    // ── 公共 API ──────────────────────────────────────────────────

    var ChartRegistry = {

        /**
         * 获取所有模块定义
         */
        getModules: function () { return MODULES; },

        /**
         * 获取指定模块
         */
        getModule: function (moduleKey) { return MODULES[moduleKey] || null; },

        /**
         * 获取指定模块的所有图表定义
         */
        getCharts: function (moduleKey) {
            var mod = MODULES[moduleKey];
            return mod ? mod.charts : [];
        },

        /**
         * 从 API 响应中提取某个图表的数据
         * @param {string} moduleKey - 模块key
         * @param {string} chartId - 图表id
         * @param {*} apiResp - API 原始响应（单接口模块）或对应 apiIndex 的响应（多接口模块）
         * @param {*} processed - 预处理后的数据（可选，由 preprocessor 生成）
         * @returns {*} 提取后的数据，或 null
         */
        extractChartData: function (moduleKey, chartId, apiResp, processed) {
            var chart = this._findChart(moduleKey, chartId);
            if (!chart) return null;
            try {
                var data = chart.extractData(apiResp, processed);
                if (data == null) return null;
                if (Array.isArray(data) && data.length === 0) return null;
                return data;
            } catch (e) {
                console.warn('[ChartRegistry] extractData error:', moduleKey, chartId, e);
                return null;
            }
        },

        /**
         * 构建图表的 ECharts option
         */
        buildChartOption: function (moduleKey, chartId, data, processed) {
            var chart = this._findChart(moduleKey, chartId);
            if (!chart) return null;
            try {
                var option = chart.buildOption(data, processed);
                // 统一注入 animation: false 和 backgroundColor（PPT导出需要）
                option.animation = false;
                option.backgroundColor = 'transparent';
                return option;
            } catch (e) {
                console.warn('[ChartRegistry] buildOption error:', moduleKey, chartId, e);
                return null;
            }
        },

        /**
         * 渲染到 DOM 容器（仪表板用）
         * @param {string} moduleKey
         * @param {string} chartId
         * @param {*} apiResp - API 原始响应
         * @param {HTMLElement|echarts.ECharts} target - DOM元素或已初始化的图表实例
         * @param {*} processed - 预处理后的数据
         * @param {object|null} [dateParams] - 日期筛选参数 { start_month, end_month }，供 rangeType:'filter' 图表展示区间
         * @returns {echarts.ECharts|null}
         */
        renderToContainer: function (moduleKey, chartId, apiResp, target, processed, dateParams) {
            var data = this.extractChartData(moduleKey, chartId, apiResp, processed);
            if (!data) return null;

            var chart = this._findChart(moduleKey, chartId);
            if (!chart) return null;

            var option;
            try {
                option = chart.buildOption(data, processed);
            } catch (e) {
                console.warn('[ChartRegistry] buildOption error:', moduleKey, chartId, e);
                return null;
            }

            // 自动注入图表标题
            if (chart.title && !option.title) {
                option.title = { text: chart.title, left: 'center', textStyle: { fontSize: 15, fontWeight: 'bold' } };
            }

            // target 可以是 DOM 元素或已初始化的 echarts 实例
            var chartInstance;
            if (target && typeof target.setOption === 'function') {
                chartInstance = target;
            } else if (target) {
                chartInstance = echarts.init(target);
            } else {
                return null;
            }

            chartInstance.setOption(option, true);  // notMerge=true，避免旧配置残留

            // 自动注入标签区（优先用 chartLabels，兼容降级至 summaryHint）
            if (target && typeof target.setOption !== 'function') {
                this.injectChartLabels(moduleKey, chartId, target, apiResp, processed, dateParams || null);
            }

            return chartInstance;
        },

        /**
         * 离线渲染所有图表（PPT导出用）
         * 返回 [{title, image}] 数组
         * 
         * @param {string} moduleKey
         * @param {*} apiResp - 单接口模块：完整响应；多接口模块：响应数组
         * @param {number} width
         * @param {number} height
         * @returns {Array<{title: string, image: string}>}
         */
        renderOfflineAll: function (moduleKey, apiResp, width, height, dateParams) {
            return this._renderOfflineAllSync(moduleKey, apiResp, width, height, dateParams);
        },

        /**
         * 异步离线渲染所有图表（PPT导出用，支持 selfFetchUrl 图表）
         * 返回 Promise<[{title, image}]>
         *
         * @param {string} moduleKey
         * @param {*} apiResp
         * @param {string} params - URL 参数字符串
         * @param {number} [deptCount=99] - 当前用户可访问基层部门数，用于过滤 multi_dept 图表
         * @param {number} [width]
         * @param {number} [height]
         */
        renderOfflineAllAsync: async function (moduleKey, apiResp, params, deptCount, width, height) {
            deptCount = (typeof deptCount === 'number') ? deptCount : 99;
            width = width || 900;
            height = height || 500;
            var mod = MODULES[moduleKey];
            if (!mod) return [];

            var dateParams = null;
            if (params && typeof params === 'string') {
                var dp = {};
                var pairs = params.split('&');
                pairs.forEach(function (pair) {
                    var kv = pair.split('=');
                    if (kv.length === 2 && kv[0]) {
                        dp[kv[0]] = decodeURIComponent(kv[1]);
                    }
                });
                if (Object.keys(dp).length > 0) dateParams = dp;
            }

            var images = [];
            var processed = null;

            if (!mod.multiApi && mod.preprocessor) {
                processed = mod.preprocessor(apiResp);
            }

            for (var i = 0; i < mod.charts.length; i++) {
                var chart = mod.charts[i];
                try {
                    // 权限过滤：multi_dept 图表在单部门账号下不导出
                    if (chart.visibility === 'multi_dept' && deptCount < 2) continue;

                    var resp, data;

                    if (chart.selfFetchUrl) {
                        // 自取型图表：独立拉取 API
                        var url = chart.selfFetchUrl + (params ? '?' + params : '');
                        var fetchResp = await fetch(url);
                        if (!fetchResp.ok) continue;
                        resp = await fetchResp.json();
                        data = chart.extractData(resp, null);
                    } else if (mod.multiApi) {
                        resp = Array.isArray(apiResp) ? apiResp[chart.apiIndex] : null;
                        if (!resp) continue;
                        data = chart.extractData(resp, processed);
                    } else {
                        resp = apiResp;
                        data = chart.extractData(resp, processed);
                    }

                    if (data == null) continue;
                    if (Array.isArray(data) && data.length === 0) continue;

                    var option = chart.buildOption(data, processed);
                    option.animation = false;
                    option.backgroundColor = 'transparent';
                    if (chart.title && !option.title) {
                        option.title = { text: chart.title, left: 'center', textStyle: { fontSize: 15, fontWeight: 'bold' } };
                    }

                    var img = ChartRegistry._renderToCanvas(option, width, height);
                    if (img) {
                        var lblsAsync = null;
                        try { lblsAsync = ChartRegistry.resolveLabels(moduleKey, chart.id, resp, processed, dateParams); } catch (e) { }
                        images.push({
                            title: chart.title, image: img,
                            hint: chart.summaryHint || '', labels: lblsAsync,
                            // PPT 增强元信息（供导出页打包 enhanceData/summaryData）
                            chartId: chart.id,
                            moduleKey: moduleKey,
                            pptEnhance: chart.pptEnhance || null
                        });
                    }
                } catch (e) {
                    console.warn('[ChartRegistry] renderOfflineAsync error:', moduleKey, chart.id, e);
                }
            }

            return images;
        },

        /**
         * 同步离线渲染（内部方法，跳过 selfFetchUrl 图表）
         */
        _renderOfflineAllSync: function (moduleKey, apiResp, width, height, dateParams) {
            width = width || 900;
            height = height || 500;
            var mod = MODULES[moduleKey];
            if (!mod) return [];

            var images = [];
            var processed = null;

            // 对单接口模块，判断是否有预处理器
            if (!mod.multiApi && mod.preprocessor) {
                processed = mod.preprocessor(apiResp);
            }

            mod.charts.forEach(function (chart) {
                if (chart.selfFetchUrl) return; // 跳过自取型图表，由 renderOfflineAllAsync 处理
                try {
                    // 多接口模块：从 apiResp 数组中取对应 index 的响应
                    var resp;
                    if (mod.multiApi) {
                        resp = Array.isArray(apiResp) ? apiResp[chart.apiIndex] : null;
                    } else {
                        resp = apiResp;
                    }
                    if (!resp) return;

                    var data = chart.extractData(resp, processed);
                    if (data == null) return;
                    if (Array.isArray(data) && data.length === 0) return;

                    var option = chart.buildOption(data, processed);
                    option.animation = false;
                    option.backgroundColor = 'transparent';
                    // 注入图表标题
                    if (chart.title && !option.title) {
                        option.title = { text: chart.title, left: 'center', textStyle: { fontSize: 15, fontWeight: 'bold' } };
                    }

                    var img = ChartRegistry._renderToCanvas(option, width, height);
                    if (img) {
                        var lblsSync = null;
                        try { lblsSync = ChartRegistry.resolveLabels(moduleKey, chart.id, resp, processed, dateParams || null); } catch (e) { }
                        images.push({ title: chart.title, image: img, hint: chart.summaryHint || '', labels: lblsSync });
                    }
                } catch (e) {
                    console.warn('[ChartRegistry] renderOffline error:', moduleKey, chart.id, e);
                }
            });

            return images;
        },

        /**
         * 计算结构化标签的动态字段（sampleN、range）
         * @param {string} moduleKey
         * @param {string} chartId
         * @param {*} apiResp
         * @param {*} processed
         * @param {object|null} dateParams - { start_month, end_month } 或 null
         * @returns {object|null} 含 scope/unit/sortRule/note/sampleN/extraLabel/range 的平铺对象；若图无 chartLabels 则返回 null
         */
        resolveLabels: function (moduleKey, chartId, apiResp, processed, dateParams) {
            var chart = this._findChart(moduleKey, chartId);
            if (!chart || !chart.chartLabels) return null;
            var cl = chart.chartLabels;

            // ── 计算 sampleN ──────────────────────────
            var N = null;
            try {
                switch (cl.sampleType) {
                    case 'resp_field':
                        N = (apiResp && cl.sampleField) ? apiResp[cl.sampleField] : null;
                        break;
                    case 'array_length':
                        N = Array.isArray(apiResp) ? apiResp.length : null;
                        break;
                    case 'processed_rows':
                        N = (processed && processed.rows) ? processed.rows.length : null;
                        break;
                    case 'disqualified_rows':
                        N = (processed && processed.rows)
                            ? processed.rows.filter(function (r) { return !r.is_qualified; }).length
                            : null;
                        break;
                    case 'sum_values':
                        N = Array.isArray(apiResp)
                            ? apiResp.reduce(function (s, i) { return s + (i.value || 0); }, 0)
                            : null;
                        break;
                    default: // 'none' 或未知
                        N = null;
                }
            } catch (e) {
                N = null;
            }

            // ── 计算 extra 标签（对比图补充规模信息）─────
            var extraLabel = null;
            if (cl.extra && cl.extra.label) {
                var extraN = null;
                try {
                    switch (cl.extra.sampleType) {
                        case 'resp_field':
                            extraN = (apiResp && cl.extra.sampleField) ? apiResp[cl.extra.sampleField] : null;
                            break;
                        case 'array_length':
                            extraN = Array.isArray(apiResp) ? apiResp.length : null;
                            break;
                        default: extraN = null;
                    }
                } catch (e) { }
                extraLabel = extraN != null ? cl.extra.label + ': ' + extraN : cl.extra.label;
            }

            // ── 计算区间文字 ──────────────────────────
            var range = null;
            switch (cl.rangeType) {
                case 'filter':
                    if (dateParams && (dateParams.start_month || dateParams.start_date)) {
                        var s = dateParams.start_month || dateParams.start_date || '';
                        var e = dateParams.end_month || dateParams.end_date || '';
                        range = (s && e) ? (s + ' ~ ' + e) : (s || e || null);
                    }
                    break;
                case 'snapshot':
                    range = '当前在册快照';
                    break;
                default: // 'none'
                    range = null;
            }

            return {
                scope: cl.scope || '',
                unit: cl.unit || '',
                sortRule: cl.sortRule || '',
                note: cl.note || '',
                sampleN: (N != null && !isNaN(N)) ? N : null,
                extraLabel: extraLabel,
                range: range
            };
        },

        /**
         * 向图表容器 DOM 注入结构化标签条（优先 chartLabels chip，降级 summaryHint 文本）
         * @param {string} moduleKey
         * @param {string} chartId
         * @param {HTMLElement} containerDom - ECharts div 容器元素
         * @param {*} apiResp
         * @param {*} processed
         * @param {object|null} dateParams
         */
        injectChartLabels: function (moduleKey, chartId, containerDom, apiResp, processed, dateParams) {
            if (!containerDom || !containerDom.parentNode) return;
            var parentNode = containerDom.parentNode;

            // 移除已有的注入（避免重复）
            var existingBar = parentNode.querySelector('.chart-labels-bar[data-chart-id="' + chartId + '"]');
            if (existingBar) existingBar.parentNode.removeChild(existingBar);
            var existingHint = parentNode.querySelector('.chart-hint-text[data-chart-id="' + chartId + '"]');
            if (existingHint) existingHint.parentNode.removeChild(existingHint);

            var chart = this._findChart(moduleKey, chartId);
            if (!chart) return;

            // ── 优先：chartLabels → chip 行 ────────────
            if (chart.chartLabels) {
                var resolved = this.resolveLabels(moduleKey, chartId, apiResp, processed, dateParams);
                if (!resolved) return;

                var bar = document.createElement('div');
                bar.className = 'chart-labels-bar';
                bar.setAttribute('data-chart-id', chartId);

                var chips = [];
                if (resolved.scope) chips.push({ cls: 'cl-scope', text: '🏷\u00a0' + resolved.scope });
                if (resolved.unit) chips.push({ cls: 'cl-unit', text: '单位：' + resolved.unit });
                if (resolved.sampleN != null) chips.push({ cls: 'cl-n', text: 'N\u202f=\u202f' + resolved.sampleN });
                if (resolved.extraLabel) chips.push({ cls: 'cl-extra', text: resolved.extraLabel });
                if (resolved.range) chips.push({ cls: 'cl-range', text: resolved.range });
                if (resolved.sortRule) chips.push({ cls: 'cl-sort', text: resolved.sortRule });
                if (resolved.note) chips.push({ cls: 'cl-note', text: resolved.note });

                chips.forEach(function (c) {
                    var span = document.createElement('span');
                    span.className = 'cl-chip ' + c.cls;
                    span.textContent = c.text;
                    bar.appendChild(span);
                });

                parentNode.insertBefore(bar, containerDom.nextSibling);
                return;
            }

            // ── 降级：summaryHint → 原有 <p> 文本 ────────
            if (chart.summaryHint) {
                var hintEl = document.createElement('p');
                hintEl.className = 'chart-hint-text';
                hintEl.setAttribute('data-chart-id', chartId);
                hintEl.textContent = chart.summaryHint;
                parentNode.insertBefore(hintEl, containerDom.nextSibling);
            }
        },

        /**
         * 预处理器入口（供仪表板使用）
         */
        preprocess: function (moduleKey, rawResp) {
            var mod = MODULES[moduleKey];
            if (mod && mod.preprocessor) {
                return mod.preprocessor(rawResp);
            }
            return null;
        },

        // ── 内部工具 ──────────────────────────────────

        _findChart: function (moduleKey, chartId) {
            var mod = MODULES[moduleKey];
            if (!mod) return null;
            for (var i = 0; i < mod.charts.length; i++) {
                if (mod.charts[i].id === chartId) return mod.charts[i];
            }
            return null;
        },

        _renderToCanvas: function (option, width, height) {
            try {
                // 使用离屏 div 容器 + SVG 渲染器，避免 ECharts 注册 mousewheel 事件监听
                var container = document.createElement('div');
                container.style.cssText = 'position:absolute;left:-9999px;top:-9999px;width:' + width + 'px;height:' + height + 'px;';
                document.body.appendChild(container);
                var chart = echarts.init(container, null, { renderer: 'canvas', width: width, height: height });
                // 禁用所有交互组件以避免 passive event listener 警告
                option.tooltip = option.tooltip || {};
                option.tooltip.triggerOn = 'none';
                chart.setOption(option);
                var dataUrl = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#fff' });
                chart.dispose();
                document.body.removeChild(container);
                return dataUrl;
            } catch (e) {
                return '';
            }
        },

        /**
         * 按 visibility 过滤图表列表
         * @param {string} moduleKey
         * @param {number} deptCount - 当前用户可访问的基层部门数
         * @returns {Array} 过滤后的图表定义数组
         */
        filterByVisibility: function (moduleKey, deptCount) {
            var charts = this.getCharts(moduleKey);
            return charts.filter(function (c) {
                if (c.visibility === 'multi_dept') {
                    return deptCount >= 2;
                }
                return true;
            });
        },

        // ── 统一下钻框架 ─────────────────────────────────

        /**
         * 为图表实例绑定统一下钻交互
         * @param {string} moduleKey - 模块键
         * @param {string} chartId - 图表 ID
         * @param {Object} chartInstance - ECharts 实例
         * @param {Object} [context] - 额外上下文（如 { getDateParams: fn, rawData: [...] }）
         */
        bindDrilldown: function (moduleKey, chartId, chartInstance, context) {
            var chartDef = this._findChart(moduleKey, chartId);
            if (!chartDef || !chartDef.drilldown || !chartInstance) return;

            var self = this;
            chartInstance.off('click'); // 移除旧的 click 绑定
            chartInstance.on('click', function (params) {
                // drilldownGuard 前置校验
                if (chartDef.drilldownGuard && !chartDef.drilldownGuard(params)) return;

                var behavior = chartDef.clickBehavior || 'modal';

                // ── navigate / toast（风险矩阵专用）──
                if (behavior === 'navigate') {
                    var rawData = (context && context.rawData) || [];
                    var dataItem = rawData[params.dataIndex] || {};
                    if (chartDef.navigateUrlBuilder) {
                        var url = chartDef.navigateUrlBuilder(dataItem);
                        if (url) {
                            window.location.href = url;
                        } else {
                            self._showToast('未匹配工号，不可跳转');
                        }
                    }
                    return;
                }

                // ── modal ──
                if (behavior === 'modal' && chartDef.drilldownUrl && chartDef.drilldownParamBuilder) {
                    var drillParams = chartDef.drilldownParamBuilder(params);
                    if (!drillParams) return;

                    // 构建请求 URL（含日期参数）
                    var urlParams = new URLSearchParams(drillParams);
                    if (context && context.getDateParams) {
                        var dateP = context.getDateParams();
                        Object.keys(dateP).forEach(function (k) {
                            if (dateP[k]) urlParams.set(k, dateP[k]);
                        });
                    }
                    var fetchUrl = chartDef.drilldownUrl + '?' + urlParams.toString();
                    var title = chartDef.title + ' — ' + (drillParams[Object.keys(drillParams)[0]] || '详情');

                    self.showDrilldownModal(title, fetchUrl, chartDef.drilldownColumns || []);
                }
            });
        },

        /**
         * 显示统一下钻 modal
         * @param {string} title - 弹窗标题
         * @param {string} fetchUrl - 请求 URL
         * @param {Array} columns - 列定义 [{key, label, width?}]
         */
        showDrilldownModal: function (title, fetchUrl, columns) {
            var modal = this._ensureDrilldownModal();
            var titleEl = document.getElementById('_crDrilldownTitle');
            var bodyEl = document.getElementById('_crDrilldownBody');

            titleEl.textContent = title;
            bodyEl.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><p class="mt-2 text-muted">加载中...</p></div>';

            // 显示 modal
            var bsModal = bootstrap.Modal.getOrCreateInstance(modal);
            bsModal.show();

            var self = this;
            fetch(fetchUrl)
                .then(function (r) { return r.json(); })
                .then(function (resp) {
                    if (!resp.canDrilldown) {
                        // 不可下钻 — 显示提示
                        bodyEl.innerHTML =
                            '<div class="alert alert-warning">' +
                            '<i class="bi bi-info-circle"></i> ' + (resp.message || '不支持下钻') +
                            '</div>' +
                            (resp.problemCount ? '<p class="text-muted">该范围共有 <strong>' + resp.problemCount + '</strong> 条记录。</p>' : '');
                        return;
                    }

                    var problems = resp.problems || [];
                    if (problems.length === 0) {
                        bodyEl.innerHTML = '<div class="text-center text-muted py-4"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">暂无明细数据</p></div>';
                        return;
                    }

                    // 更新标题含记录数
                    titleEl.textContent = title + '（共' + resp.problemCount + '条）';

                    // 渲染表格
                    bodyEl.innerHTML = self._buildDrilldownTable(problems, columns);
                })
                .catch(function (err) {
                    console.error('下钻请求失败:', err);
                    bodyEl.innerHTML = '<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> 加载失败，请重试</div>';
                });
        },

        /** 创建/获取全局 drilldown modal DOM */
        _ensureDrilldownModal: function () {
            var existing = document.getElementById('_crDrilldownModal');
            if (existing) return existing;

            var div = document.createElement('div');
            div.innerHTML =
                '<div class="modal fade" id="_crDrilldownModal" tabindex="-1" aria-hidden="true">' +
                '  <div class="modal-dialog modal-xl">' +
                '    <div class="modal-content">' +
                '      <div class="modal-header">' +
                '        <h5 class="modal-title" id="_crDrilldownTitle">详情</h5>' +
                '        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
                '      </div>' +
                '      <div class="modal-body" id="_crDrilldownBody"></div>' +
                '      <div class="modal-footer">' +
                '        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>' +
                '      </div>' +
                '    </div>' +
                '  </div>' +
                '</div>';
            document.body.appendChild(div.firstChild);
            return document.getElementById('_crDrilldownModal');
        },

        /** 根据列定义构建 HTML 表格 */
        _buildDrilldownTable: function (rows, columns) {
            var esc = this._escapeHtml;
            var html = '<div class="table-responsive"><table class="table table-hover table-bordered table-sm">';
            // 表头
            html += '<thead class="table-light"><tr><th style="width:40px">#</th>';
            columns.forEach(function (col) {
                html += '<th' + (col.width ? ' style="width:' + col.width + '"' : '') + '>' + esc(col.label) + '</th>';
            });
            html += '</tr></thead><tbody>';
            // 表体
            rows.forEach(function (row, idx) {
                html += '<tr><td class="text-center">' + (idx + 1) + '</td>';
                columns.forEach(function (col) {
                    var val = row[col.key];
                    if (val == null) val = '';
                    html += '<td>' + esc(String(val)) + '</td>';
                });
                html += '</tr>';
            });
            html += '</tbody></table></div>';
            return html;
        },

        /** HTML 实体转义 */
        _escapeHtml: function (str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        },

        /** 简易 toast 提示 */
        _showToast: function (message) {
            // 优先用全局 alert，简洁可靠
            alert(message);
        }
    };

    // 暴露到全局
    window.ChartRegistry = ChartRegistry;

})();
