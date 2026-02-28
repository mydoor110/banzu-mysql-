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
                    id: 'risk_distribution',
                    title: '司龄风险等级分布',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '按入司后单驾年限分级，识别新手集中风险',
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
                    id: 'team_power',
                    title: '各部门人员战力雷达',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '各部门链花对比，快速定位短板部门',
                    extractData: function (resp) { return resp.team_power || []; },
                    buildOption: function (data) {
                        var maxT = Math.max.apply(null, data.map(function (t) { return t.avg_tenure || 0; })) || 10;
                        var maxS = Math.max.apply(null, data.map(function (t) { return t.avg_solo || 0; })) || 10;
                        var maxC = Math.max.apply(null, data.map(function (t) { return t.avg_cert || 0; })) || 10;
                        var indicator = [
                            { name: '平均司龄', max: Math.ceil(maxT * 1.3) || 10 },
                            { name: '平均驾龄', max: Math.ceil(maxS * 1.3) || 10 },
                            { name: '取证年限', max: Math.ceil(maxC * 1.3) || 10 }
                        ];
                        return {
                            tooltip: { trigger: 'item' },
                            legend: { bottom: '5%', type: 'scroll' },
                            radar: { indicator: indicator, radius: '55%' },
                            series: [{
                                type: 'radar',
                                data: data.slice(0, 6).map(function (t) {
                                    return {
                                        name: (t.team || t.name || '') + '(' + (t.member_count || 0) + '人)',
                                        value: [t.avg_tenure || 0, t.avg_solo || 0, t.avg_cert || 0],
                                        areaStyle: { opacity: 0.12 }
                                    };
                                })
                            }]
                        };
                    }
                },
                {
                    id: 'experience_scatter',
                    title: '经验溢出分析图',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    summaryHint: '取证年限与单驾年限对比，识别“准师傅”人选',
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
                    id: 'stability_scatter',
                    title: '职业稳定性分析',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    summaryHint: '司龄vs工龄，区分应届/社招人员结构',
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
                    id: 'hometown_stats',
                    title: '排班压力预警图(籍贯分布)',
                    exportable: true, defaultSelected: false, priority: 'low',
                    summaryHint: '籍贯集中度分析，识别节假日排班压力',
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
                    id: 'political_stats',
                    title: '政治面貌分布',
                    exportable: true, defaultSelected: false, priority: 'low',
                    summaryHint: '党员/团员/群众占比统计',
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
                    id: 'training_monthly_rate',
                    title: '月度培训合格率趋势',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '观察合格率趋势，识别培训质量拐点',
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
                    id: 'training_project_top10',
                    title: '不合格培训项目 TOP10',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '定位失格集中的项目，优先安排复训',
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
                    id: 'training_problem_type',
                    title: '不合格问题类型分布',
                    exportable: true, defaultSelected: true, priority: 'medium',
                    summaryHint: '失格原因分类，明确改进方向',
                    extractData: function (resp, processed) {
                        var probMap = {};
                        processed.rows.filter(function (r) { return !r.is_qualified && r.problem_type; }).forEach(function (r) {
                            probMap[r.problem_type] = (probMap[r.problem_type] || 0) + 1;
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
                    id: 'training_monthly_count',
                    title: '月度培训人次统计',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    summaryHint: '培训规模趋势，合格与不合格人次对比',
                    extractData: function (resp, processed) { return processed.monthKeys; },
                    buildOption: function (data, processed) {
                        var monthMap = processed.monthMap;
                        return {
                            tooltip: { trigger: 'axis' },
                            legend: { top: 5 },
                            grid: { left: 60, right: 30, top: 55, bottom: 50 },
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
                    id: 'training_project_count_top20',
                    title: '各实操项目总次数 Top20',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    summaryHint: '高频项目识别，关注培训资源分配',
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
                    id: 'training_person_count',
                    title: '人员实操次数统计',
                    exportable: true, defaultSelected: false, priority: 'low',
                    summaryHint: '按人员统计合格/失格次数，定位薄弱人员',
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
                            legend: { top: 5 },
                            grid: { left: 60, right: 30, top: 55, bottom: 60 },
                            xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 30 } },
                            yAxis: { type: 'value', name: '次数' },
                            dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 0 }],
                            series: [
                                { name: '合格次数', type: 'bar', stack: 'total', data: qualified, itemStyle: { color: '#165DFF' }, barWidth: '60%' },
                                { name: '失格次数', type: 'bar', stack: 'total', data: disqualified, itemStyle: { color: '#F53F3F' }, barWidth: '60%' }
                            ]
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
                '/safety/api/analytics/top-contributors'
            ],
            multiApi: true,
            charts: [
                {
                    id: 'safety_severity',
                    title: '扣分严重程度分布',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '严重级别占比，识别重大违规的比例',
                    apiIndex: 0,   // 使用 apiUrls[0] 的返回
                    extractData: function (resp) {
                        var arr = Array.isArray(resp) ? resp : [];
                        return arr.filter(function (i) { return (i.value || 0) > 0; });
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'item', formatter: '{b}: {c}次 ({d}%)' },
                            legend: { bottom: '5%', type: 'scroll' },
                            color: ['#F53F3F', '#FF7D00', '#FADC19', '#165DFF', '#00B42A', '#14C9C9'],
                            series: [{
                                type: 'pie', radius: ['30%', '60%'], center: ['50%', '46%'],
                                label: { formatter: '{b}\n{c}次', fontSize: 12 },
                                data: data
                            }]
                        };
                    }
                },
                {
                    id: 'safety_top_loss',
                    title: '安全扣分项 TOP10',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '定位最常见的安全问题项目',
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
                    id: 'safety_risk_matrix',
                    title: '人员安全风险矩阵',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '违规次数vs累计扣分，识别高风险人员',
                    apiIndex: 2,
                    extractData: function (resp) {
                        return Array.isArray(resp) ? resp : [];
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: {
                                trigger: 'item',
                                formatter: function (p) {
                                    return (p.data[2] || '') + '<br/>违规: ' + p.data[0] + '次<br/>累计扣分: ' + p.data[1];
                                }
                            },
                            grid: { left: 70, right: 30, top: 55, bottom: 55 },
                            xAxis: { type: 'value', name: '违规次数', minInterval: 1 },
                            yAxis: { type: 'value', name: '累计扣分' },
                            series: [{
                                type: 'scatter', symbolSize: 14,
                                data: data.map(function (m) {
                                    return [
                                        Array.isArray(m.value) ? m.value[0] : (m.count || 0),
                                        Array.isArray(m.value) ? m.value[1] : (m.total_score || 0),
                                        m.name || ''
                                    ];
                                }),
                                itemStyle: { color: '#F53F3F', opacity: 0.75 },
                                label: { show: data.length <= 20, formatter: function (p) { return p.data[2]; }, position: 'right', fontSize: 10 }
                            }]
                        };
                    }
                },
                {
                    id: 'safety_daily_trend',
                    title: '安全违规趋势',
                    exportable: true, defaultSelected: true, priority: 'high',
                    summaryHint: '观察阶段性风险抬头和整改效果',
                    apiIndex: 3,
                    extractData: function (resp) {
                        // resp = {dates: [...], counts: [...], scores: [...]}
                        if (!resp || !resp.dates || resp.dates.length === 0) return [];
                        return resp;
                    },
                    buildOption: function (data) {
                        return {
                            tooltip: { trigger: 'axis' },
                            legend: { top: 5 },
                            grid: { left: 60, right: 50, top: 55, bottom: 60 },
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
                    id: 'safety_top_contributors',
                    title: '问题发现能手榜 TOP10',
                    exportable: true, defaultSelected: false, priority: 'medium',
                    summaryHint: '表彰发现问题积极的检查人员',
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
                            yAxis: { type: 'value', name: '问题数量' },
                            series: [{
                                name: '发现/整改问题数', type: 'bar', data: data.counts,
                                itemStyle: { color: '#f39c12' },
                                barWidth: '50%',
                                label: { show: true, position: 'top' }
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
         * @returns {echarts.ECharts|null}
         */
        renderToContainer: function (moduleKey, chartId, apiResp, target, processed) {
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

            chartInstance.setOption(option);
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
        renderOfflineAll: function (moduleKey, apiResp, width, height) {
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
                        images.push({ title: chart.title, image: img });
                    }
                } catch (e) {
                    console.warn('[ChartRegistry] renderOffline error:', moduleKey, chart.id, e);
                }
            });

            return images;
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
        }
    };

    // 暴露到全局
    window.ChartRegistry = ChartRegistry;

})();

