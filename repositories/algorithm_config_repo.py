#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
算法配置 Repository（数据访问层）

P2.1：将 SQL 从 AlgorithmConfigService 下沉到此层。
Service 只做业务编排，Repository 专门负责数据库读写。

所有方法接收 cursor 参数，不自行管理连接和事务。
"""
from typing import Optional, List
from datetime import datetime


class AlgorithmConfigRepo:
    """算法配置数据访问层"""

    # ==================== active_config ====================

    @staticmethod
    def get_config_version(cur) -> int:
        """获取当前配置版本号（轻量查询）"""
        cur.execute("SELECT config_version FROM algorithm_active_config WHERE id = 1")
        row = cur.fetchone()
        return row['config_version'] if row else 0

    @staticmethod
    def get_active_config_data(cur) -> Optional[dict]:
        """读取当前生效配置（含 config_data + config_version）"""
        cur.execute("""
            SELECT config_data, config_version FROM algorithm_active_config WHERE id = 1
        """)
        return cur.fetchone()

    @staticmethod
    def get_active_config_data_only(cur) -> Optional[str]:
        """仅读取当前 config_data JSON 字符串（用于日志对比）"""
        cur.execute("""
            SELECT config_data FROM algorithm_active_config WHERE id = 1
        """)
        row = cur.fetchone()
        return row['config_data'] if row else None

    @staticmethod
    def get_active_info(cur) -> Optional[dict]:
        """读取当前配置元信息"""
        cur.execute("""
            SELECT based_on_preset, is_customized, updated_at, config_version
            FROM algorithm_active_config
            WHERE id = 1
        """)
        return cur.fetchone()

    @staticmethod
    def get_active_preset_status(cur) -> Optional[dict]:
        """读取当前配置的预设使用状态和版本号"""
        cur.execute("""
            SELECT based_on_preset, is_customized, config_version
            FROM algorithm_active_config WHERE id = 1
        """)
        return cur.fetchone()

    @staticmethod
    def update_active_apply_preset(cur, preset_key: str, config_data: str,
                                   user_id: int, updated_at: str) -> int:
        """应用预设：更新 active_config 并自增版本号，返回新版本号"""
        cur.execute("""
            UPDATE algorithm_active_config
            SET based_on_preset = %s, is_customized = 0, config_data = %s,
                updated_by = %s, updated_at = %s, config_version = config_version + 1
            WHERE id = 1
        """, (preset_key, config_data, user_id, updated_at))
        return AlgorithmConfigRepo.get_config_version(cur)

    @staticmethod
    def update_active_custom(cur, config_data_json: str,
                             user_id: int, updated_at: str) -> int:
        """自定义更新：更新 active_config 并自增版本号，返回新版本号"""
        cur.execute("""
            UPDATE algorithm_active_config
            SET based_on_preset = NULL, is_customized = 1, config_data = %s,
                updated_by = %s, updated_at = %s, config_version = config_version + 1
            WHERE id = 1
        """, (config_data_json, user_id, updated_at))
        return AlgorithmConfigRepo.get_config_version(cur)

    @staticmethod
    def update_active_sync_preset(cur, config_data: str, updated_at: str,
                                  user_id: Optional[int] = None) -> int:
        """同步预设变更到 active_config 并自增版本号，返回新版本号"""
        if user_id is not None:
            cur.execute("""
                UPDATE algorithm_active_config
                SET config_data = %s, updated_by = %s, updated_at = %s, config_version = config_version + 1
                WHERE id = 1
            """, (config_data, user_id, updated_at))
        else:
            cur.execute("""
                UPDATE algorithm_active_config
                SET config_data = %s, updated_at = %s, config_version = config_version + 1
                WHERE id = 1
            """, (config_data, updated_at))
        return AlgorithmConfigRepo.get_config_version(cur)

    # ==================== presets ====================

    @staticmethod
    def get_preset(cur, preset_key: str) -> Optional[dict]:
        """根据 preset_key 查询预设方案"""
        cur.execute("""
            SELECT preset_name, config_data FROM algorithm_presets
            WHERE preset_key = %s
        """, (preset_key,))
        return cur.fetchone()

    @staticmethod
    def get_preset_by_name(cur, preset_name: str) -> Optional[dict]:
        """根据 preset_name 查询预设方案（含 preset_key）"""
        cur.execute("""
            SELECT preset_key, config_data FROM algorithm_presets
            WHERE preset_name = %s
        """, (preset_name,))
        return cur.fetchone()

    @staticmethod
    def get_all_presets(cur) -> list:
        """获取所有预设方案列表"""
        cur.execute("""
            SELECT preset_key, preset_name, description, config_data
            FROM algorithm_presets
            ORDER BY id
        """)
        return cur.fetchall()

    @staticmethod
    def update_preset_config(cur, preset_key: str, config_data_json: str):
        """更新预设方案的配置数据"""
        cur.execute("""
            UPDATE algorithm_presets
            SET config_data = %s
            WHERE preset_key = %s
        """, (config_data_json, preset_key))

    # ==================== logs ====================

    @staticmethod
    def insert_log(cur, action: str, config_version: int,
                   preset_name: Optional[str] = None,
                   old_config: Optional[str] = None,
                   new_config: Optional[str] = None,
                   change_reason: Optional[str] = None,
                   changed_by: Optional[int] = None,
                   changed_by_name: Optional[str] = None,
                   ip_address: Optional[str] = None):
        """插入配置变更日志"""
        cur.execute("""
            INSERT INTO algorithm_config_logs
            (action, preset_name, old_config, new_config, change_reason,
             changed_by, changed_by_name, ip_address, config_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (action, preset_name, old_config, new_config, change_reason,
              changed_by, changed_by_name, ip_address, config_version))

    @staticmethod
    def get_logs(cur, limit: int = 50, offset: int = 0) -> list:
        """获取配置变更日志列表"""
        cur.execute("""
            SELECT
                id, action, preset_name, change_reason,
                changed_by, changed_by_name, changed_at, ip_address, config_version
            FROM algorithm_config_logs
            ORDER BY changed_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return cur.fetchall()

    @staticmethod
    def get_log_by_id(cur, log_id: int) -> Optional[dict]:
        """获取单条日志详情（含 old/new config）"""
        cur.execute("""
            SELECT
                id, action, preset_name, change_reason, changed_by, changed_by_name,
                changed_at, ip_address, old_config, new_config
            FROM algorithm_config_logs
            WHERE id = %s
        """, (log_id,))
        return cur.fetchone()

    # ==================== 辅助 ====================

    @staticmethod
    def get_username(cur, user_id: int) -> str:
        """根据 user_id 查询用户名"""
        cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return row['username'] if row else f"用户{user_id}"
