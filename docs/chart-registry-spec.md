# chart-registry.js 新增图表接入规范

> **状态**：最小版草稿（Phase 0 产出），Phase 5 完善完整示例和边界案例。

---

## 一、图表对象必须字段（最小接入 checklist）

接入一张新图表时，必须在 `chart-registry.js` 的图表对象中声明以下所有字段：

### 1.1 基础标识字段

| 字段 | 类型 | 是否必须 | 说明 |
|---|---|---|---|
| `id` | string | ✅ | 唯一图表 ID，全局不重复，snake_case 格式 |
| `title` | string | ✅ | 图表标题，用于 PPT 页面 title 和配置页卡片展示 |
| `exportable` | boolean | ✅ | 是否参与 PPT 导出，不参与导出的图表填 `false` |
| `defaultSelected` | boolean | ✅ | 配置页默认是否勾选 |
| `priority` | string | ✅ | `'high'`/`'medium'`/`'low'`，影响配置页排序 |

### 1.2 能力声明字段（Phase 0 新增）

| 字段 | 类型 | 是否必须 | 说明 |
|---|---|---|---|
| `schema` | string | ✅ | 图表视觉类型，见下方 schema 分层表 |
| `supportsPreview` | boolean | ✅ | 是否支持配置页缩略图预览（Phase 1 暂全部 `false`） |
| `supportsSummary` | boolean | ✅ | 是否支持摘要页（须配合 `pptEnhance.type = 'decision_summary'`） |
| `supportsManualBullets` | boolean | ✅ | 是否支持人工选题（仅 `supportsSummary: true` 的图表可以为 `true`） |

### 1.3 数据配置字段

| 字段 | 类型 | 是否必须 | 说明 |
|---|---|---|---|
| `apiIndex` | number | ✅ | 当前模块的 `apis[]` 数组中对应的接口下标 |
| `extractData` | function | ✅ | 从 apiResp 中提取本图所需数据的函数 |
| `buildOption` | function | ✅ | 生成 ECharts option 对象的函数 |
| `chartLabels` | object | ✅（exportable=true 时） | 图表导出补充信息，见下方 chartLabels 结构 |
| `summaryHint` | string | ⚠️ 推荐 | PPT 图表副标题，为空则不展示 |

### 1.4 drilldown 字段（可选，按需配置）

| 字段 | 类型 | 说明 |
|---|---|---|
| `drilldown` | boolean | 是否支持下钻 |
| `drilldownUrl` | string | 下钻接口地址 |
| `clickBehavior` | string | `'modal'` 或 `'none'` |
| `drilldownParamBuilder` | function | 从点击事件生成接口参数 |
| `drilldownColumns` | array | 下钻表格列定义 |

### 1.5 pptEnhance 字段（可选，按类型配置）

| 增强类型 | 说明 |
|---|---|
| `{ type: 'trend', ... }` | 趋势图增强（high/peak/average 等选项） |
| `{ type: 'risk_matrix', annotateTopN, showSideList }` | 风险矩阵增强 |
| `{ type: 'decision_summary', summaryMode, statsRule, bulletsRule }` | 决策摘要（摘要页支持） |

---

## 二、`schema` 字段分层表

| schema 值 | 对应图表类型 | 说明 |
|---|---|---|
| `'bar_chart'` | 普通柱状图/条形图 | 单序列，横/纵轴 |
| `'ranked_bar'` | TOP N 条形图 | 按数值排序，通常水平展示 |
| `'group_bar'` | 分组柱状图 | 多序列对比 |
| `'trend_chart'` | 趋势折线图 | 时间序列，单轴或双轴 |
| `'pie_chart'` | 饼图/环图 | 占比类 |
| `'scatter_chart'` | 散点图 | 二维散点分布 |
| `'matrix_chart'` | 矩阵图 | 风险矩阵等 |

---

## 三、`chartLabels` 字段结构

```js
chartLabels: {
    scope: '统计对象',      // 例如 '安全问题记录'
    unit: '单位',           // 例如 '次'、'分'
    sortRule: '排序规则',   // 例如 '按累计扣分降序'
    note: '补充说明',       // 例如 '3分及以上可下钻'
    sampleType: '...',      // 采样类型: 'sum_values'/'array_length'/'count' 等
    sampleField: null,      // 采样字段，null 表示默认
    extra: null,            // 扩展字段
    rangeType: 'filter'     // 范围类型
}
```

---

## 四、接入 checklist（新增图表时逐项确认）

```
□ id 已确定，全局不重复
□ title 已填写
□ exportable / defaultSelected / priority 已填写
□ schema 已按分层表选择正确类型
□ supportsPreview = false（Phase 1 阶段固定）
□ supportsSummary 已确定（decision_summary 类型为 true，其余 false）
□ supportsManualBullets 已确定（同 supportsSummary）
□ apiIndex 已指向正确的 apis[] 下标
□ extractData 函数已实现并通过测试
□ buildOption 函数已实现，图表可正常渲染
□ chartLabels 已填写（至少 scope/unit 不为空）
□ summaryHint 已填写（可选，建议填）
□ 如需下钻：drilldown/drilldownUrl/clickBehavior/drilldownParamBuilder/drilldownColumns 已实现
□ 如需 PPT 增强：pptEnhance 已按增强类型配置
□ 如支持摘要（supportsSummary=true）：pptEnhance.statsRule / bulletsRule 已配置
□ 如支持人工选题（supportsManualBullets=true）：candidateProvider 已实现（Phase 3 补）
```

---

## 五、当前图表全量声明（Phase 0 状态）

| 图表 ID | 模块 | schema | supportsSummary | supportsManualBullets |
|---|---|---|---|---|
| `risk_distribution` | 人员 | bar_chart | false | false |
| `team_power` | 人员 | bar_chart | false | false |
| `experience_scatter` | 人员 | scatter_chart | false | false |
| `stability_scatter` | 人员 | scatter_chart | false | false |
| `hometown_stats` | 人员 | bar_chart | false | false |
| `political_stats` | 人员 | bar_chart | false | false |
| `dept_rookie_compare` | 人员 | group_bar | false | false |
| `dept_backbone_compare` | 人员 | group_bar | false | false |
| `training_monthly_rate` | 培训 | trend_chart | false | false |
| `training_project_top10` | 培训 | ranked_bar | **true** | **true** |
| `training_problem_type` | 培训 | pie_chart | false | false |
| `training_monthly_count` | 培训 | trend_chart | false | false |
| `training_project_count_top20` | 培训 | ranked_bar | false | false |
| `training_person_count` | 培训 | bar_chart | false | false |
| `training_dept_rate_compare` | 培训 | group_bar | false | false |
| `safety_severity` | 安全 | ranked_bar | **true** | **true** |
| `safety_top_loss` | 安全 | ranked_bar | **true** | **true** |
| `safety_risk_matrix` | 安全 | matrix_chart | false | false |
| `safety_daily_trend` | 安全 | trend_chart | false | false |
| `safety_top_contributors` | 安全 | ranked_bar | false | false |
| `safety_top_frequency` | 安全 | ranked_bar | **true** | **true** |
| `safety_dept_issue_compare` | 安全 | group_bar | false | false |
| `safety_dept_risk_compare` | 安全 | group_bar | false | false |
