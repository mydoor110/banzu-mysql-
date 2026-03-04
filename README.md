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

### 1. 环境要求

当前项目实际运行要求：

- Python 3.8+
- MySQL 8.0+
- 建议安装 `mysqldump`，否则“备份管理”功能会降级

安装 MySQL 客户端示例：

```bash
# Ubuntu / Debian
sudo apt-get install -y mysql-client

# CentOS / RHEL
sudo yum install -y mysql

# macOS
brew install mysql-client
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
vim .env
```

至少需要确认以下配置：

- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `APP_USER`
- `APP_PASS`
- `SECRET_KEY`
- `PORT`

生产环境额外建议：

- 设置 `FLASK_ENV=production`
- 使用高强度 `SECRET_KEY`
- 如已启用 HTTPS，设置 `SESSION_COOKIE_SECURE=True`

注意：

- 项目代码只支持 MySQL，不再支持 SQLite。
- `python app.py` 会自动执行数据库初始化。
- `flask run`、`gunicorn` 或其他 WSGI 启动方式不会自动执行 `init-db`，部署前必须先手动执行一次 `flask --app app init-db`。

---

## 数据库初始化与升级

项目当前实际使用 `models/db_mgmt.py` 中的 `DBVersionManager`，目标数据库版本为 `v6`：

- `v1`: 基线表结构与部门外键补齐
- `v2`: 钉钉相关字段补齐
- `v3`: `ppt_export_cache` 表
- `v4`: `employee_id` 治理 + 多张表日期字段结构化
- `v5`: 算法配置版本治理（`config_version`）
- `v6`: 培训项目主数据、PPT 模板、异步任务等结构补齐

### 自动迁移机制说明

执行 `flask --app app init-db` 时，系统会按以下顺序工作：

1. 幂等创建缺失表。
2. 读取 `system_metadata.key_name='db_version'`。
3. 按版本顺序执行缺失迁移。
4. 重建视图、补齐索引。
5. 初始化基础数据：
   - 顶级部门
   - 默认管理员
   - 停用词
   - AI 分析配置
   - 算法预设与当前生效配置

### 重要数据库风险说明

这部分务必注意，尤其是生产升级：

1. MySQL 的 `CREATE TABLE`、`ALTER TABLE` 等 DDL 会隐式提交，失败时不能像普通事务那样完整回滚。
2. `init-db` 是“幂等补齐 + 增量迁移”，不是“全量回滚式发布”。
3. `v4` 中的日期迁移会把无法识别的日期清洗为 `NULL`，不是保留原字符串。
4. `v4` 中的 `employee_id` 回填依赖匹配规则：
   - `performance_records.emp_no -> employees.emp_no`
   - `training_records.emp_no -> employees.emp_no`
   - `safety_inspection_records.inspected_person -> employees.name`
5. 如果历史数据质量差，迁移可能“部分成功并带 warning”，因此升级后必须人工核验结果，不能只看命令退出码。
6. 生产环境不要直接通过首次启动 `python app.py` 触发升级，应该先备份，再执行 `flask --app app init-db`，确认无误后再启动服务。

---

## 首次部署

以下流程适用于“数据库中还没有该系统业务表”的全新部署。

### 1. 创建数据库

请先在 MySQL 中手动创建空数据库：

```sql
CREATE DATABASE team_management
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

如果你使用其他库名，请同步修改 `.env` 中的 `MYSQL_DATABASE`。

### 2. 配置 `.env`

建议至少配置如下内容：

```env
APP_USER=admin
APP_PASS=请替换为强密码
SECRET_KEY=请替换为随机高强度密钥
PORT=5001

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=你的MySQL账号
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=team_management

FLASK_ENV=production
SESSION_COOKIE_SECURE=False
```

如果是 HTTPS 反向代理后的正式环境，再把 `SESSION_COOKIE_SECURE` 调整为 `True`。

### 3. 首次初始化数据库

推荐使用 CLI，而不是直接先跑服务：

```bash
flask --app app init-db
```

该命令会：

1. 创建所有表和视图。
2. 将数据库版本写到 `system_metadata.db_version`。
3. 初始化管理员账号、默认部门、停用词、AI 配置、算法预设。

### 4. 初始化完成后的核验

建议至少执行以下 SQL：

```sql
SELECT value
FROM system_metadata
WHERE key_name = 'db_version';

SELECT COUNT(*) AS departments_cnt FROM departments;
SELECT COUNT(*) AS users_cnt FROM users;
SELECT COUNT(*) AS presets_cnt FROM algorithm_presets;
```

预期：

- `db_version = 6`
- `departments` 至少 1 条
- `users` 至少 1 条
- `algorithm_presets` 至少 3 条

### 5. 启动应用

```bash
python app.py
```

默认监听：

- `0.0.0.0:${PORT}`
- 未设置 `PORT` 时默认 `5001`

默认管理员账号来自 `.env`：

- 用户名：`APP_USER`
- 密码：`APP_PASS`

---

## 升级已有数据库

以下流程适用于“旧版本数据库保留历史业务数据并升级到当前代码”。

### 升级原则

1. 先备份，再升级。
2. 先 dry-run/预检查，再执行正式迁移。
3. 先执行 `init-db`，再启动新版本服务。
4. 升级后必须核验版本号、字段类型、回填结果和关键业务页面。

### 1. 升级前备份

推荐至少做一次逻辑备份：

```bash
mysqldump -h 127.0.0.1 -P 3306 -u root -p \
  --default-character-set=utf8mb4 \
  team_management > team_management_$(date +%F_%H%M%S).sql
```

如果生产库名、主机、账号不同，请自行替换。

### 2. 升级前预检查

先确认当前版本号：

```sql
SELECT value
FROM system_metadata
WHERE key_name = 'db_version';
```

如果没有返回结果，通常表示：

- 这是非常旧的库，版本记录尚未建立
- 或者库是手工搭建的半成品

这种情况下更应该先备份，再在测试环境验证升级流程。

针对 `v4` 数据治理，建议额外检查以下风险：

```sql
SELECT COUNT(*) AS perf_unmatched
FROM performance_records p
LEFT JOIN employees e ON p.emp_no = e.emp_no
WHERE p.emp_no IS NOT NULL AND p.emp_no != '' AND e.id IS NULL;

SELECT COUNT(*) AS training_unmatched
FROM training_records t
LEFT JOIN employees e ON t.emp_no = e.emp_no
WHERE t.emp_no IS NOT NULL AND t.emp_no != '' AND e.id IS NULL;

SELECT COUNT(*) AS safety_unmatched
FROM safety_inspection_records s
LEFT JOIN employees e ON s.inspected_person = e.name
WHERE s.inspected_person IS NOT NULL AND s.inspected_person != '' AND e.id IS NULL;
```

如果这些计数很大，说明 `employee_id` 回填后会残留较多 `NULL`，需要先治理人员主数据。

日期字段迁移前，建议先用专项 dry-run：

```bash
flask --app app migrate-dates --dry-run
```

如果输出里出现大量“置NULL”，请先确认这些历史日期是否允许被清洗为空。

### 3. 执行正式升级

```bash
flask --app app init-db
```

如果你想先专项预演，可按顺序使用：

```bash
flask --app app migrate-employee-id --dry-run
flask --app app migrate-dates --dry-run
```

必要时也可以单独执行正式专项迁移：

```bash
flask --app app migrate-employee-id
flask --app app migrate-dates
```

但对绝大多数情况，仍以 `flask --app app init-db` 作为统一升级入口。

### 4. 升级后核验

升级完成后，至少检查以下内容：

```sql
SELECT value
FROM system_metadata
WHERE key_name = 'db_version';

SHOW COLUMNS FROM employees LIKE 'birth_date';
SHOW COLUMNS FROM employees LIKE 'certification_date';
SHOW COLUMNS FROM training_records LIKE 'training_date';
SHOW COLUMNS FROM safety_inspection_records LIKE 'inspection_date';

SELECT COUNT(*) AS perf_employee_id_null
FROM performance_records
WHERE emp_no IS NOT NULL AND emp_no != '' AND employee_id IS NULL;

SELECT COUNT(*) AS training_employee_id_null
FROM training_records
WHERE emp_no IS NOT NULL AND emp_no != '' AND employee_id IS NULL;

SELECT COUNT(*) AS safety_employee_id_null
FROM safety_inspection_records
WHERE inspected_person IS NOT NULL AND inspected_person != '' AND employee_id IS NULL;
```

预期：

- `db_version = 6`
- 关键日期字段类型为 `date`
- `employee_id` 的残留 `NULL` 数量符合预期，且已知原因清楚

如果升级日志中出现以下情况，不要直接上线：

- `migration failed`
- `Backfill warning`
- 某些字段被大量清洗为 `NULL`
- `employee_id` 回填残留异常偏多

应先修正数据，再重新验证。

---

## 启动与运维建议

### 推荐启动顺序

生产环境建议固定为：

1. 更新代码
2. 更新依赖
3. 执行 `flask --app app init-db`
4. 验证数据库结果
5. 启动或重启 WSGI 服务

### 系统依赖检查

可手动执行：

```bash
flask --app app check-system
```

它当前主要检查 `mysqldump`，缺失时不会阻止系统运行，但会影响备份能力。

---

## CLI 命令参考

所有 CLI 命令通过 Flask CLI 调用：

| 命令 | 说明 | 常用选项 |
|------|------|----------|
| `flask --app app init-db` | 初始化/升级数据库与基础数据 | `--silent` 静默模式 |
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
│   ├── db_mgmt.py              # 数据库版本与迁移管理（核心，v6）
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
- **部署**: 原生部署，升级入口统一为 `flask --app app init-db`

## 版本历史

### 2026年3月（当前代码状态）
- ✅ **数据库版本**: `DBVersionManager` 当前目标版本为 `v6`
- ✅ **统一升级入口**: 使用 `flask --app app init-db` 完成建表、迁移、视图、索引和基础数据初始化
- ✅ **数据治理**: 已包含 `employee_id` 回填、日期字段结构化、算法配置版本治理
- ✅ **业务结构补齐**: 已包含培训项目主数据、PPT 模板、异步任务相关表结构
- ✅ **运维建议更新**: README 已按“首次部署 / 旧库升级 / 数据库核验”重写

### v3.2.0 - 2026年1月
- ✅ **钉钉集成**: 支持钉钉免登与通讯录同步。
- ✅ **算法重构**: 引入时间和波动加权的稳定性算法。

### v3.1.0 - 2026年1月
- ✅ **性能优化**: 针对百万级数据表添加复合索引。
- ✅ **备份增强**: 优化 MySQL `mysqldump` 备份流程。

---

**文档维护**: 系统管理员
**最后更新**: 2026年2月
