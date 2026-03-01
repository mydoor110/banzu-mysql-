#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人员管理 - 领域常量

P1.2 下沉：原定义在 blueprints/personnel/__init__.py 中。
Service 层和 Blueprint 层均应从此处导入，避免反向依赖。
"""

# ── 字段定义 ──

PERSONNEL_FIELD_SCHEME = [
    {"name": "emp_no", "label": "工号", "input_type": "text", "required": True},
    {"name": "name", "label": "姓名", "input_type": "text", "required": True},
    {"name": "department_id", "label": "所属部门", "input_type": "department_select", "required": True},
    {"name": "class_name", "label": "班级", "input_type": "text"},
    {"name": "position", "label": "岗位", "input_type": "text"},
    {"name": "birth_date", "label": "出生年月", "input_type": "date"},
    {"name": "certification_date", "label": "取证时间", "input_type": "date"},
    {"name": "solo_driving_date", "label": "单独驾驶时间", "input_type": "date"},
    {"name": "marital_status", "label": "婚姻状况", "input_type": "select"},
    {"name": "hometown", "label": "籍贯", "input_type": "text"},
    {"name": "political_status", "label": "政治面貌", "input_type": "select"},
    {"name": "education", "label": "学历", "input_type": "select"},
    {"name": "graduation_school", "label": "毕业院校", "input_type": "text"},
    {"name": "work_start_date", "label": "参加工作时间", "input_type": "date"},
    {"name": "entry_date", "label": "入司时间", "input_type": "date"},
    {"name": "specialty", "label": "特长及兴趣爱好", "input_type": "textarea"},
]

PERSONNEL_DB_COLUMNS = [
    field["name"] for field in PERSONNEL_FIELD_SCHEME if field["name"] not in {"emp_no", "name"}
]

PERSONNEL_DATE_FIELDS = {"birth_date", "work_start_date", "entry_date", "certification_date", "solo_driving_date"}

PERSONNEL_SELECT_OPTIONS = {
    "marital_status": ["未婚", "已婚", "离异", "其它"],
    "political_status": ["中共党员", "中共预备党员", "共青团员", "群众", "其它"],
    "education": ["博士研究生", "硕士研究生", "本科", "大专", "中专", "高中", "其它"],
}

PERSONNEL_IMPORT_HEADER_MAP = {
    "工号": "emp_no",
    "姓名": "name",
    "所属部门": "department_id",
    "部门": "department_id",
    "班级": "class_name",
    "岗位": "position",
    "出生年月": "birth_date",
    "取证时间": "certification_date",
    "取证日期": "certification_date",
    "单独驾驶时间": "solo_driving_date",
    "单独驾驶日期": "solo_driving_date",
    "婚否": "marital_status",
    "婚姻状况": "marital_status",
    "籍贯": "hometown",
    "政治面貌": "political_status",
    "特长及兴趣爱好": "specialty",
    "特长": "specialty",
    "学历": "education",
    "毕业院校": "graduation_school",
    "参加工作时间": "work_start_date",
    "入司时间": "entry_date",
}
