# -*- coding: utf-8 -*-
"""
export_config_builder.py — PPT 导出中间组装层（Phase 2 新建）

职责：
  接收前端传来的 export_config（配置意图）和 raw_images（图像资产），
  组装出后端 PPTExportService 所需的 module_slides。

  明确不做的事（防止职责蔓延）：
  - 不重新生成截图（图像由前端 ECharts 离线截取）
  - 不重新调用 drilldown API 生成 enhanceData / summaryData
    （前端已生成并随 raw_images 一起传来）
  - 不处理关键人员画像（由 export_ppt.py 调 ComprehensiveProfileService 处理）

数据契约（前端 POST body 新格式）：
  {
    "start_month": "2026-01",
    "end_month": "2026-02",
    "theme": "blue",
    "export_config": {
      "chartConfigs": {
        "<chartId>": {
          "selected": true,
          "enhanceEnabled": true,
          "appendSummary": true
        }
      },
      "appendSummaryGlobal": true,
      "enhance": {
        "trendEnabled": true,
        "riskMatrixEnabled": true,
        "riskMatrixTopN": 5,
        "decisionSummaryEnabled": true
      }
    },
    "raw_images": {
      "<chartId>": {
        "image": "<base64>",
        "title": "图表标题",
        "hint": "副标题说明",
        "labels": null,
        "moduleKey": "safety",
        "pptEnhance": { "type": "decision_summary", "summaryMode": "severity" },
        "enhanceData": null,          // trend/risk_matrix 图已由前端生成
        "summaryData": { ... }        // decision_summary 图已由前端生成
      }
    },
    // Phase 2 补：关键人员（旧字段兼容）
    "key_persons": [],
    "radar_images": {},
    "person_profiles": {}
  }
"""

from __future__ import annotations
from typing import Any

# 模块顺序定义（控制 PPT 章节顺序）
_MODULE_ORDER = ['analytics', 'training', 'safety']

_MODULE_META = {
    'analytics': {'title': '人员数据分析',   'note': '基于人员基础档案数据统计分析'},
    'training':  {'title': '培训数据分析',   'note': '重点关注员工各项培训及考核合格情况'},
    'safety':    {'title': '安全数据分析',   'note': '基于日常安全检查、隐患排查等维度统计'},
}


def build_module_slides_from_config(
    export_config: dict,
    raw_images: dict[str, dict],
) -> list[dict]:
    """
    按 export_config 从 raw_images 中筛选、排序并组装 module_slides。

    Args:
        export_config: 前端 ExportConfig 序列化对象
        raw_images:    key=chartId，value=图像对象（含 image/title/hint/pptEnhance/enhanceData/summaryData）

    Returns:
        module_slides: list of { title, images: [...], note }
        每个 images 元素：{ title, image, hint, labels, chartId, moduleKey,
                            pptEnhance, enhanceData, summaryData }
    """
    chart_configs: dict = export_config.get('chartConfigs') or {}
    append_summary_global: bool = export_config.get('appendSummaryGlobal', True)
    enhance_cfg: dict = export_config.get('enhance') or {}
    decision_summary_enabled: bool = enhance_cfg.get('decisionSummaryEnabled', True)

    # 按模块order聚合
    module_slide_map: dict[str, dict] = {}

    for module_key in _MODULE_ORDER:
        # 从 raw_images 中收集属于本模块且被 selected 的图表
        selected_for_module = []
        for chart_id, img_obj in raw_images.items():
            if img_obj.get('moduleKey') != module_key:
                continue
            cfg = chart_configs.get(chart_id, {})
            if not cfg.get('selected', False):
                continue
            if not img_obj.get('image'):
                continue  # 缺少图像数据，跳过

            pe = img_obj.get('pptEnhance') or {}

            # ── 图表级 enhanceEnabled：用户对单张图关闭增强时清空 enhanceData ──
            enhance_enabled: bool = cfg.get('enhanceEnabled', True)
            enhance_data = img_obj.get('enhanceData') if enhance_enabled else None

            # ── 图表级 appendSummary：结合全局开关共同决定是否保留 summaryData ──
            # 规则：全局 OR 单图任意一个为 False → 清空
            per_chart_summary: bool = cfg.get('appendSummary', True)
            summary_data = img_obj.get('summaryData')
            if pe.get('type') == 'decision_summary':
                if not (append_summary_global and decision_summary_enabled and per_chart_summary):
                    summary_data = None

            selected_for_module.append({
                'title':       img_obj.get('title', chart_id),
                'image':       img_obj['image'],
                'hint':        img_obj.get('hint', ''),
                'labels':      img_obj.get('labels'),
                'chartId':     chart_id,
                'moduleKey':   module_key,
                'pptEnhance':  pe if pe else None,
                'enhanceData': enhance_data,
                'summaryData': summary_data,
            })

        if not selected_for_module:
            continue

        meta = _MODULE_META.get(module_key, {'title': module_key, 'note': ''})
        module_slide_map[module_key] = {
            'title':  meta['title'],
            'images': selected_for_module,
            'note':   meta['note'],
        }

    return [module_slide_map[k] for k in _MODULE_ORDER if k in module_slide_map]


def estimate_page_count(module_slides: list[dict]) -> int:
    """
    预估 PPT 页数：封面(1) + 各模块图表页 + 摘要页 + 末页(1)
    图表双排：每两张共1页；单排：每张1页。
    摘要页：每张有 summaryData 的图表一页。
    """
    cover = 1
    end = 1
    chart_pages = 0
    summary_pages = 0

    for mod in module_slides:
        images = mod.get('images', [])
        chart_pages += (len(images) + 1) // 2  # 双排取ceil
        for img in images:
            if img.get('summaryData'):
                summary_pages += 1

    return cover + chart_pages + summary_pages + end
