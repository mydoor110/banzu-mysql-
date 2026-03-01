# 乘务数字化管理平台 - 企业级管理平台

## 项目简介

乘务数字化管理平台是一个全功能的企业级管理平台，为基层班组提供绩效管理、培训管理、安全管理、人员管理和部门管理等核心功能。基于 Flask Blueprint 架构开发，使用 Bootstrap 5 构建现代化响应式界面。

项目遵循"轻量、易部署、易维护"的设计理念，支持多部门层级管理、自动化的数据库维护和灵活的算法配置。

## 系统功能

### 🏢 部门管理系统
- **层级部门结构**: 支持多级部门嵌套，自动计算部门路径和层级
- **权限控制**: 基于部门的数据访问控制，上级部门可查看下级部门数据
- **角色管理**: 系统管理员、部门管理员、普通用户三级权限体系
- **组织架构**: 可视化部门树状结构，支持拖拽式管理

### 📊 绩效管理系统
- **绩效工作台**: 集中展示年度总览、PDF 上传、区间统计、绩效计算器、季度绩效
- **数据导入**: 支持 PDF 文件批量解析和 Excel 数据导入
- **统计分析**: 多维度绩效统计和数据可视化
- **季度绩效**: 季度成绩聚合和人工覆盖调整
- **算法配置**: 支持严格/标准/宽松三档算法预设

### 🎓 培训管理系统
- **培训工作台**: 集中管理培训记录、数据分析、计划制定等功能
- **培训记录**: 详细的培训档案管理，支持多种培训类型
- **培训项目**: 培训项目分类管理
- **智能分析**: 结合"培训失格"与"违章记录"，自动分析实操弱项
- **不合格管理**: 专门的不合格人员跟踪和管理

### 👥 人员管理系统
- **档案管理**: 完整的员工档案信息维护
- **数据统计**: 年龄结构、学历分布、司龄分析等
- **能力画像**: 员工综合能力评估和画像，包含**学习能力**与**稳定性**分析
- **风险挖掘**: 基于数据的风险预警分析
- **批量操作**: Excel 批量导入导出功能

### 🛡️ 安全管理系统
- **安全检查**: 安全检查记录和隐患管理
- **整改跟踪**: 安全隐患整改进度跟踪
- **双轨制评分**: 结合"行为频率"与"严重程度"的双轨制评分模型
- **分类管理**: 多维度安全检查分类

### 🤖 AI 智能分析
- **多 AI 提供商**: 支持配置多个 AI 服务提供商
- **智能诊断**: 员工绩效智能分析和建议
- **分析缓存**: AI 分析结果缓存，节省成本
- **提示词配置**: 可自定义 AI 提示词模板

### ⚙️ 系统管理
- **用户管理**: 用户账号创建、角色分配、部门设置
- **部门管理**: 部门结构维护、权限配置
- **导入日志**: 完整的数据导入审计日志
- **算法配置**: 综合评分算法参数配置，可视化预览效果
- **备份管理**: 数据备份和恢复功能

---

## 核心算法逻辑

系统内置了高度可配置的算法模型，用于评估员工的综合素质。所有参数均可在系统后台进行调整或一键切换预设（严格/标准/宽松）。

### 1. 稳定度算法 (Stability)
衡量员工在安全表现上的稳定性，识别"忽高忽低"的潜在风险。
- **时间窗口**: 支持 6/9/12 个月滚动窗口分析。
- **波动指标**: 计算月度分数的平均变化幅度 (Mean |Δ|)。
- **评分逻辑**:
  - **稳定**: 波动小，成绩持续平稳（>= 75分）。
  - **波动偏大**: 存在一定起伏，需关注（60-75分）。
  - **波动较大/异常**: 忽好忽坏，安全隐患大（< 60分）。
- **特殊机制**:
  - **样本不足**: 有效数据不足6个月时标记为低置信度。
  - **低水平提示**: 即使稳定，如果分数一直很低，依然会发出预警。

### 2. 学习能力算法 (Learning Potential)
基于历史趋势预测未来的安全风险，引入"风险惯性"概念。
- **动态水位**: 动态计算 关注线 (Warning) 和 熔断线 (Critical)。
- **风险惯性**: 识别连续处于"危险区"的员工，随着时间推移累积"惯性惩罚"，防止短期洗白。
- **状态判定**:
  - **事故前兆**: 惯性惩罚极高，极易发生事故。
  - **高危**: 综合评分不及格。
  - **重点关注**: 处于危险边缘。
  - **安全**: 表现良好。

### 3. 三档算法预设
- **严格档 (Strict)**: 适用于高要求场景，惩罚力度大（如：波动容忍度低，惯性惩罚启动快）。
- **标准档 (Standard)**: 平衡公平与激励（默认配置）。
- **宽松档 (Lenient)**: 适用于培养阶段或新员工，容忍度较高。

---

## 快速开始

### 1. 环境准备
确保已安装 Python 3.8+ 和 MySQL 8.0+。

```bash
# 安装系统依赖 (MySQL 客户端)
# Ubuntu/Debian
sudo apt-get install -y mysql-client
# CentOS/RHEL
sudo yum install -y mysql
```

### 2. 安装项目依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境

复制环境变量示例文件并修改配置：

```bash
cp .env.example .env
vim .env
```

配置重点：
- `DB_TYPE=mysql`
- `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`

### 4. 数据库初始化与升级

项目集成了 `DBVersionManager`（当前版本 v4），支持自动化的数据库版本管理。

#### 新库初始化

```bash
# CLI 方式（推荐）
flask --app app init-db

# 或者直接启动应用（python app.py 会自动初始化）
python app.py
```

系统会自动：
1. 检测当前数据库版本
2. 创建缺失的表
3. 执行增量迁移（v1→v2→v3→v4）
4. 初始化基础数据（管理员账号、默认部门、算法预设）

#### 老库升级

对于 **已有数据的老库**，执行同样的命令即可自动升级：

```bash
flask --app app init-db
```

`DBVersionManager` 会检测当前版本号并执行缺失的迁移：
- **v4 数据模型治理**: 自动为 `performance_records`、`training_records`、`safety_inspection_records` 添加 `employee_id` 外键并回填，同时将 `employees` 表的日期字段迁移为 `DATE` 类型。

#### 专项迁移（dry-run 模式）

如果需要单独预览迁移效果或手动补救，可使用以下 CLI 命令：

```bash
# 预览 employee_id 外键迁移（不执行）
flask --app app migrate-employee-id --dry-run

# 执行 employee_id 外键迁移
flask --app app migrate-employee-id

# 预览日期字段迁移（不执行）
flask --app app migrate-dates --dry-run

# 执行日期字段迁移
flask --app app migrate-dates
```

### 5. 启动服务

```bash
python app.py
```
访问 `http://localhost:5001`，默认管理员账号请查看 `.env` 配置（默认为 `admin` / `admin123`）。

---

## CLI 命令参考

所有 CLI 命令通过 Flask CLI 调用：

| 命令 | 说明 | 常用选项 |
|------|------|----------|
| `flask --app app init-db` | 初始化/升级数据库 | `--silent` 静默模式 |
| `flask --app app check-system` | 检查系统依赖 | — |
| `flask --app app migrate-employee-id` | employee_id 外键迁移 | `--dry-run` 仅预览 |
| `flask --app app migrate-dates` | 日期字段类型迁移 | `--dry-run` 仅预览 |

---

## 项目结构

```
.
├── app.py                      # Flask 主应用入口（工厂函数 + CLI 命令）
├── config/                     # 配置文件
├── models/                     # 数据模型层
│   ├── database.py             # 数据库连接管理
│   ├── db_mgmt.py              # 数据库版本与迁移管理（核心，v4）
│   ├── db_transaction.py       # 事务上下文管理器
│   └── schema_defs.py          # 表结构定义
├── blueprints/                 # 功能模块 (Blueprint)
│   ├── auth.py                 # 认证模块
│   ├── performance.py          # 绩效管理
│   ├── training.py             # 培训管理
│   ├── safety.py               # 安全管理 (含双轨制算法)
│   ├── export_ppt.py           # PPT 导出
│   ├── personnel/              # 人员管理 (子模块)
│   │   ├── __init__.py         # Blueprint 定义 + 常量
│   │   ├── routes_crud.py      # CRUD 路由
│   │   ├── routes_dashboard.py # 仪表盘路由
│   │   ├── routes_analytics.py # 分析路由
│   │   └── routes_ai.py        # AI 画像路由
│   ├── decorators.py           # 权限装饰器
│   └── helpers.py              # 通用辅助函数
├── services/                   # 业务逻辑层
│   ├── personnel_service.py    # 人员管理服务
│   ├── ai_config_service.py    # AI 配置管理
│   ├── algorithm_config_service.py  # 算法配置
│   ├── bootstrap_service.py    # 系统启动初始化
│   ├── async_task_service.py   # 异步任务管理
│   └── domain/                 # 领域算法
│       ├── personnel_algo.py   # 人员评估算法
│       └── safety_utils.py     # 安全评分工具
├── utils/                      # 工具函数
├── templates/                  # 前端模板
├── static/                     # 静态资源
├── scripts/                    # 辅助脚本（dry-run 工具）
├── tests/                      # 测试
│   └── test_smoke.py           # 冒烟测试
└── requirements.txt            # Python 依赖
```

## 技术架构

- **后端**: Flask 2.x + Blueprint + 应用工厂模式
- **数据库**: MySQL (pymysql + 原生 SQL 优化)
- **事务管理**: `db_transaction()` 上下文管理器
- **权限控制**: 请求级 `g.user_ctx` 缓存，消除重复查询
- **数据处理**: Pandas + NumPy
- **前端**: Bootstrap 5 + ECharts
- **部署**: 原生支持，集成自动迁移与备份

## 版本历史

### v3.4.0 - 2026年2月 (当前版本)
- ✅ **数据模型治理**: employee_id 外键迁移和日期字段类型迁移纳入 DBVersionManager v4
- ✅ **权限统一**: 全部替换 `session['role']` → `g.user_ctx`，session 仅存储认证信息
- ✅ **事务管理**: 核心写操作统一使用 `db_transaction()` 上下文管理器
- ✅ **模块瘦身**: `personnel/__init__.py` 业务逻辑下沉至 `services/personnel_service.py`
- ✅ **CLI 完善**: 新增 `migrate-employee-id`、`migrate-dates` 命令

### v3.3.0 - 2026年2月
- ✅ **数据库自动化**: 引入 `DBVersionManager`，实现数据库自动初始化与无感升级。
- ✅ **算法文档整合**: 统一核心算法逻辑说明至主文档。

### v3.2.0 - 2026年1月
- ✅ **钉钉集成**: 支持钉钉免登与通讯录同步。
- ✅ **算法重构**: 引入时间和波动加权的稳定性算法。

### v3.1.0 - 2026年1月
- ✅ **性能优化**: 针对百万级数据表添加复合索引。
- ✅ **备份增强**: 优化 MySQL `mysqldump` 备份流程。

---

**文档维护**: 系统管理员
**最后更新**: 2026年2月
