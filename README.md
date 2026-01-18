# 班组管理系统 - 企业级管理平台

## 项目简介

班组管理系统是一个全功能的企业级管理平台，为基层班组提供绩效管理、培训管理、安全管理、人员管理和部门管理等核心功能。基于 Flask Blueprint 架构开发，使用 Bootstrap 5 构建现代化响应式界面。

项目遵循"轻量、易部署、易维护"的设计理念，支持 **SQLite** 和 **MySQL** 双数据库模式，支持多部门层级管理和权限控制。

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
- **数据分析**: ECharts 可视化培训效果分析
- **不合格管理**: 专门的不合格人员跟踪和管理

### 👥 人员管理系统
- **档案管理**: 完整的员工档案信息维护
- **数据统计**: 年龄结构、学历分布、司龄分析等
- **能力画像**: 员工综合能力评估和画像
- **风险挖掘**: 基于数据的风险预警分析
- **批量操作**: Excel 批量导入导出功能

### 🛡️ 安全管理系统
- **安全检查**: 安全检查记录和隐患管理
- **整改跟踪**: 安全隐患整改进度跟踪
- **统计报表**: 安全数据统计和趋势分析
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
- **算法配置**: 综合评分算法参数配置
- **备份管理**: 数据备份和恢复功能

## 技术架构

### 后端技术栈
- **框架**: Flask 2.x + Blueprint 模块化架构
- **数据库**: SQLite / MySQL 双模式支持
- **ORM**: 原生 SQL + 数据库抽象层
- **认证**: Session + werkzeug.security 密码哈希
- **文件处理**: pandas + openpyxl + pdfplumber

### 前端技术栈
- **UI 框架**: Bootstrap 5
- **图表库**: ECharts
- **交互**: 原生 JavaScript + Fetch API

## 项目结构

```
.
├── app.py                      # Flask 主应用入口
├── config/
│   ├── __init__.py
│   └── settings.py             # 配置管理（数据库、路径等）
├── models/
│   ├── __init__.py
│   └── database.py             # 数据库连接和初始化（支持 SQLite/MySQL）
├── blueprints/                 # 功能模块（Blueprint 架构）
│   ├── auth.py                 # 认证模块
│   ├── admin.py                # 管理员模块
│   ├── departments.py          # 部门管理
│   ├── personnel.py            # 人员管理
│   ├── performance.py          # 绩效管理
│   ├── training.py             # 培训管理
│   ├── safety.py               # 安全管理
│   ├── system_config.py        # 系统配置
│   ├── decorators.py           # 权限装饰器
│   └── helpers.py              # 辅助函数
├── services/                   # 业务服务层
├── utils/                      # 工具函数
├── templates/                  # Jinja2 模板
├── static/                     # 静态资源
├── uploads/                    # 上传文件目录
├── exports/                    # 导出文件目录
├── logs/                       # 日志目录
├── backups/                    # 备份目录
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量示例
└── README.md                   # 项目说明
```

## 数据模型

### 核心表（20 个）

| 表名 | 用途 |
|------|------|
| `users` | 用户账号 |
| `departments` | 部门管理（支持层级结构） |
| `employees` | 员工档案 |
| `performance_records` | 绩效记录 |
| `grade_map` | 绩效等级映射 |
| `quarter_overrides` | 季度绩效覆盖 |
| `quarter_grade_options` | 季度等级选项 |
| `training_records` | 培训记录 |
| `training_projects` | 培训项目 |
| `training_project_categories` | 培训项目分类 |
| `safety_inspection_records` | 安全检查记录 |
| `import_logs` | 导入日志审计 |
| `algorithm_presets` | 算法预设 |
| `algorithm_active_config` | 算法激活配置 |
| `algorithm_config_logs` | 算法配置变更日志 |
| `stopwords` | NLP 停用词 |
| `ai_providers` | AI 提供商配置 |
| `ai_usage_logs` | AI 使用日志 |
| `ai_analysis_history` | AI 分析缓存 |
| `ai_prompt_configs` | AI 提示词配置 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 环境配置

复制环境变量示例文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 管理员账户
APP_USER=admin
APP_PASS=your_secure_password

# Flask 密钥
SECRET_KEY=your_secret_key_here

# 应用端口
PORT=5001

# 数据库配置（二选一）
# 方式一：使用 SQLite（默认）
DB_TYPE=sqlite
DB_PATH=app.db

# 方式二：使用 MySQL
DB_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=team_management
MYSQL_CHARSET=utf8mb4
```

### 3. 启动服务

```bash
python app.py
```

或使用 Flask CLI：

```bash
flask --app app.py run --host=0.0.0.0 --port=5001
```

### 4. 访问系统

打开浏览器访问 `http://localhost:5001`，使用配置的管理员账号登录。

## MySQL 配置说明

### 创建数据库

```sql
CREATE DATABASE team_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 切换到 MySQL

1. 修改 `.env` 文件中的 `DB_TYPE=mysql`
2. 配置 MySQL 连接信息
3. 首次启动时会自动创建所有表和索引

## 权限体系

| 角色 | 权限范围 |
|------|---------|
| `admin` | 系统管理员，可访问所有数据和功能 |
| `manager` | 部门管理员，可管理本部门及下级部门数据 |
| `user` | 普通用户，只能查看本部门数据 |

## 版本历史

### v3.0.0 (当前版本) - 2025年1月
- ✅ **MySQL 数据库支持**: 支持 SQLite/MySQL 双模式
- ✅ **Blueprint 架构重构**: 模块化代码组织
- ✅ **AI 智能分析**: 多 AI 提供商支持
- ✅ **算法配置系统**: 三档算法预设（严格/标准/宽松）
- ✅ **导入日志审计**: 完整的数据导入追踪
- ✅ **人员能力画像**: 综合能力评估
- ✅ **风险挖掘分析**: 数据驱动的风险预警

### v2.0.0 - 2024年12月
- ✅ 完整的培训管理系统
- ✅ 部门层级管理和权限控制
- ✅ 多模块工作台架构
- ✅ 用户角色和权限体系

### v1.0.0 - 2024年初
- ✅ 绩效管理核心功能
- ✅ 人员档案管理
- ✅ 基础用户认证

## 后续规划

### 短期计划
- 🔄 数据导出格式扩展（PDF 报表）
- 🔄 移动端适配优化
- 🔄 批量操作性能优化

### 长期计划
- 📋 RESTful API 接口
- 📋 消息通知系统
- 📋 工作流引擎
- 📋 数据大屏展示

---

**文档版本**: v3.0.0
**最后更新**: 2025年1月18日
**维护者**: 系统管理员
