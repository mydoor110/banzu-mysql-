#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统配置管理Blueprint
提供算法参数配置、停用词管理、AI提供商配置的管理界面和API接口
"""
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from blueprints.decorators import admin_required
from services.algorithm_config_service import AlgorithmConfigService
from models.database import get_db
import json

system_config_bp = Blueprint('system_config', __name__, url_prefix='/system/config')
APP_TITLE = "班组管理"


@system_config_bp.route('/algorithm')
@admin_required
def algorithm_config_page():
    """算法配置管理页面"""
    return render_template('system_algorithm_config.html', title='算法参数配置')


@system_config_bp.route('/api/current-config', methods=['GET'])
@admin_required
def api_get_current_config():
    """API: 获取当前生效的配置"""
    try:
        # 获取配置数据
        config_data = AlgorithmConfigService.get_active_config()
        config_info = AlgorithmConfigService.get_current_info()

        return jsonify({
            'success': True,
            'config': config_data,
            'info': config_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取配置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/presets', methods=['GET'])
@admin_required
def api_get_presets():
    """API: 获取所有预设方案"""
    try:
        presets = AlgorithmConfigService.get_presets()
        return jsonify({
            'success': True,
            'presets': presets
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取预设方案失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/apply-preset', methods=['POST'])
@admin_required
def api_apply_preset():
    """API: 应用预设方案"""
    try:
        data = request.get_json()
        preset_key = data.get('preset_key')
        reason = data.get('reason', '应用预设方案')

        if not preset_key:
            return jsonify({
                'success': False,
                'error': '预设方案标识不能为空'
            }), 400

        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': '用户信息缺失，请重新登录'
            }), 401
        user_id = int(user_id)
        username = session.get('username')
        ip_address = request.remote_addr

        success, message = AlgorithmConfigService.apply_preset(
            preset_key, user_id, reason, username, ip_address
        )

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'应用预设方案失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/update-config', methods=['POST'])
@admin_required
def api_update_config():
    """API: 更新自定义配置"""
    try:
        data = request.get_json()
        config_data = data.get('config_data')
        reason = data.get('reason', '自定义配置修改')

        if not config_data:
            return jsonify({
                'success': False,
                'error': '配置数据不能为空'
            }), 400

        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': '用户信息缺失，请重新登录'
            }), 401
        user_id = int(user_id)
        username = session.get('username')
        ip_address = request.remote_addr

        success, message = AlgorithmConfigService.update_custom_config(
            config_data, user_id, reason, username, ip_address
        )

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'更新配置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/update-preset', methods=['POST'])
@admin_required
def api_update_preset():
    """API: 保存为预设方案"""
    try:
        data = request.get_json()
        preset_key = data.get('preset_key')
        config_data = data.get('config_data')
        reason = data.get('reason', '更新预设方案')

        if not preset_key:
            return jsonify({
                'success': False,
                'error': '预设方案标识不能为空'
            }), 400

        if not config_data:
            return jsonify({
                'success': False,
                'error': '配置数据不能为空'
            }), 400

        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': '用户信息缺失，请重新登录'
            }), 401
        user_id = int(user_id)
        username = session.get('username')
        ip_address = request.remote_addr

        success, message = AlgorithmConfigService.update_preset(
            preset_key, config_data, user_id, reason, username, ip_address
        )

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'更新预设方案失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/rollback-preset', methods=['POST'])
@admin_required
def api_rollback_preset():
    """API: 回滚预设方案变更"""
    try:
        data = request.get_json()
        log_id = data.get('log_id')
        reason = data.get('reason', '回滚预设方案')

        if not log_id:
            return jsonify({
                'success': False,
                'error': '日志ID不能为空'
            }), 400

        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': '用户信息缺失，请重新登录'
            }), 401
        user_id = int(user_id)
        username = session.get('username')
        ip_address = request.remote_addr

        success, message = AlgorithmConfigService.rollback_preset_update(
            int(log_id), user_id, reason, username, ip_address
        )

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'回滚失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/simulate', methods=['POST'])
@admin_required
def api_simulate():
    """API: 模拟计算"""
    try:
        data = request.get_json()
        config_data = data.get('config_data')
        sample_data = data.get('sample_data')

        if not config_data or not sample_data:
            return jsonify({
                'success': False,
                'error': '配置数据和样例数据不能为空'
            }), 400

        # 执行模拟计算
        results = AlgorithmConfigService.simulate_calculation(config_data, sample_data)

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'模拟计算失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/change-logs', methods=['GET'])
@admin_required
def api_get_logs():
    """API: 获取配置变更日志"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        logs = AlgorithmConfigService.get_logs(limit, offset)

        return jsonify({
            'success': True,
            'logs': logs,
            'total': len(logs)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取日志失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/change-log/<int:log_id>', methods=['GET'])
@admin_required
def api_get_log_detail(log_id: int):
    """API: 获取日志详情"""
    try:
        detail = AlgorithmConfigService.get_log_detail(log_id)
        if not detail:
            return jsonify({
                'success': False,
                'error': '日志不存在'
            }), 404

        return jsonify({
            'success': True,
            'detail': detail
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取日志详情失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/validate-config', methods=['POST'])
@admin_required
def api_validate_config():
    """API: 验证配置数据"""
    try:
        data = request.get_json()
        config_data = data.get('config_data')

        if not config_data:
            return jsonify({
                'success': False,
                'error': '配置数据不能为空'
            }), 400

        is_valid, error_msg = AlgorithmConfigService.validate_config(config_data)

        return jsonify({
            'success': True,
            'is_valid': is_valid,
            'message': error_msg if not is_valid else '配置验证通过'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'验证失败: {str(e)}'
        }), 500


# ============================================================
# 停用词管理 API
# ============================================================

@system_config_bp.route('/stopwords')
@admin_required
def stopwords_page():
    """停用词管理页面"""
    return render_template('system_config/stopwords.html', title='停用词管理 | ' + APP_TITLE)


@system_config_bp.route('/api/stopwords', methods=['GET'])
@admin_required
def api_get_stopwords():
    """API: 获取停用词列表（分页+搜索）"""
    try:
        conn = get_db()
        cur = conn.cursor()

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        keyword = request.args.get('keyword', '').strip()
        category = request.args.get('category', '')

        # Build query with filters
        where_clauses = []
        params = []

        if keyword:
            where_clauses.append("word LIKE %s")
            params.append(f'%{keyword}%')

        if category:
            where_clauses.append("category = %s")
            params.append(category)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        cur.execute(f"SELECT COUNT(*) AS cnt FROM stopwords WHERE {where_sql}", params)
        total = cur.fetchone()['cnt']

        # Get paginated results
        offset = (page - 1) * per_page
        cur.execute(
            f"""SELECT id, word, category, created_at
                FROM stopwords
                WHERE {where_sql}
                ORDER BY category DESC, id DESC
                LIMIT %s OFFSET %s""",
            params + [per_page, offset]
        )
        rows = cur.fetchall()

        stopwords = [
            {
                'id': row['id'],
                'word': row['word'],
                'category': row['category'],
                'created_at': str(row['created_at']) if row['created_at'] else None
            }
            for row in rows
        ]

        return jsonify({
            'success': True,
            'stopwords': stopwords,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取停用词失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/stopwords', methods=['POST'])
@admin_required
def api_add_stopword():
    """API: 添加单个停用词"""
    try:
        from services.text_mining_service import TextMiningService

        data = request.get_json()
        word = data.get('word', '').strip()

        if not word:
            return jsonify({
                'success': False,
                'error': '停用词不能为空'
            }), 400

        if len(word) > 50:
            return jsonify({
                'success': False,
                'error': '停用词长度不能超过50个字符'
            }), 400

        conn = get_db()
        cur = conn.cursor()

        # Check if already exists
        cur.execute("SELECT id FROM stopwords WHERE word = %s", (word,))
        if cur.fetchone():
            return jsonify({
                'success': False,
                'error': f'停用词 "{word}" 已存在'
            }), 400

        # Insert new stopword
        cur.execute(
            "INSERT INTO stopwords (word, category) VALUES (%s, 'custom')",
            (word,)
        )
        conn.commit()

        # Clear cache
        TextMiningService.clear_cache()

        return jsonify({
            'success': True,
            'message': f'停用词 "{word}" 添加成功',
            'id': cur.lastrowid
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'添加停用词失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/stopwords/<int:stopword_id>', methods=['DELETE'])
@admin_required
def api_delete_stopword(stopword_id):
    """API: 删除单个停用词"""
    try:
        from services.text_mining_service import TextMiningService

        conn = get_db()
        cur = conn.cursor()

        # Check if exists
        cur.execute("SELECT word FROM stopwords WHERE id = %s", (stopword_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({
                'success': False,
                'error': '停用词不存在'
            }), 404

        word = row['word']

        # Delete
        cur.execute("DELETE FROM stopwords WHERE id = %s", (stopword_id,))
        conn.commit()

        # Clear cache
        TextMiningService.clear_cache()

        return jsonify({
            'success': True,
            'message': f'停用词 "{word}" 删除成功'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'删除停用词失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/stopwords/batch-delete', methods=['POST'])
@admin_required
def api_batch_delete_stopwords():
    """API: 批量删除停用词"""
    try:
        from services.text_mining_service import TextMiningService

        data = request.get_json()
        ids = data.get('ids', [])

        if not ids:
            return jsonify({
                'success': False,
                'error': '请选择要删除的停用词'
            }), 400

        conn = get_db()
        cur = conn.cursor()

        # Delete selected stopwords
        placeholders = ','.join(['%s'] * len(ids))
        cur.execute(f"DELETE FROM stopwords WHERE id IN ({placeholders})", ids)
        deleted_count = cur.rowcount
        conn.commit()

        # Clear cache
        TextMiningService.clear_cache()

        return jsonify({
            'success': True,
            'message': f'成功删除 {deleted_count} 个停用词'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'批量删除失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/stopwords/import', methods=['POST'])
@admin_required
def api_import_stopwords():
    """API: 批量导入停用词（从txt文件）"""
    try:
        from services.text_mining_service import TextMiningService

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '请上传文件'
            }), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({
                'success': False,
                'error': '请选择文件'
            }), 400

        # Read file content
        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                file.seek(0)
                content = file.read().decode('gbk')
            except:
                return jsonify({
                    'success': False,
                    'error': '文件编码不支持，请使用 UTF-8 或 GBK 编码'
                }), 400

        # Parse words (one per line)
        words = [line.strip() for line in content.split('\n') if line.strip()]

        if not words:
            return jsonify({
                'success': False,
                'error': '文件中没有有效的停用词'
            }), 400

        # Filter valid words
        valid_words = [w for w in words if len(w) <= 50]

        conn = get_db()
        cur = conn.cursor()

        # Insert words, ignore duplicates
        inserted_count = 0
        for word in valid_words:
            try:
                cur.execute(
                    "INSERT IGNORE INTO stopwords (word, category) VALUES (%s, 'custom')",
                    (word,)
                )
                if cur.rowcount > 0:
                    inserted_count += 1
            except:
                continue

        conn.commit()

        # Clear cache
        TextMiningService.clear_cache()

        return jsonify({
            'success': True,
            'message': f'导入完成：共 {len(words)} 个词，成功导入 {inserted_count} 个新词',
            'total': len(words),
            'inserted': inserted_count,
            'skipped': len(words) - inserted_count
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'导入失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/stopwords/reset', methods=['POST'])
@admin_required
def api_reset_stopwords():
    """API: 恢复默认停用词"""
    try:
        from models.database import bootstrap_stopwords
        from services.text_mining_service import TextMiningService

        conn = get_db()
        cur = conn.cursor()

        # Delete all stopwords
        cur.execute("DELETE FROM stopwords")
        conn.commit()

        # Re-initialize default stopwords
        bootstrap_stopwords()

        # Clear cache
        TextMiningService.clear_cache()

        # Get new count
        cur.execute("SELECT COUNT(*) AS cnt FROM stopwords")
        count = cur.fetchone()['cnt']

        return jsonify({
            'success': True,
            'message': f'已恢复默认停用词，共 {count} 个'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'恢复默认失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/stopwords/stats', methods=['GET'])
@admin_required
def api_stopwords_stats():
    """API: 获取停用词统计"""
    try:
        conn = get_db()
        cur = conn.cursor()

        # Get counts by category
        cur.execute("""
            SELECT category, COUNT(*) as count
            FROM stopwords
            GROUP BY category
        """)
        rows = cur.fetchall()

        stats = {row['category']: row['count'] for row in rows}
        total = sum(stats.values())

        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'builtin': stats.get('builtin', 0),
                'custom': stats.get('custom', 0)
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取统计失败: {str(e)}'
        }), 500


# ============================================================
# AI配置管理 API
# ============================================================

@system_config_bp.route('/ai')
@admin_required
def ai_config_page():
    """AI配置管理页面"""
    return render_template('system_config/ai_config.html', title='AI模型配置 | ' + APP_TITLE)


@system_config_bp.route('/api/ai/templates', methods=['GET'])
@admin_required
def api_get_ai_templates():
    """API: 获取AI提供商模板列表"""
    try:
        from services.ai_config_service import AIConfigService
        templates = AIConfigService.get_provider_templates()
        return jsonify({
            'success': True,
            'templates': templates
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取模板失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers', methods=['GET'])
@admin_required
def api_get_ai_providers():
    """API: 获取所有AI提供商配置"""
    try:
        from services.ai_config_service import AIConfigService
        providers = AIConfigService.get_all_providers()
        return jsonify({
            'success': True,
            'providers': providers
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取配置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers/<int:provider_id>', methods=['GET'])
@admin_required
def api_get_ai_provider(provider_id):
    """API: 获取单个AI提供商配置"""
    try:
        from services.ai_config_service import AIConfigService
        provider = AIConfigService.get_provider_by_id(provider_id)
        if not provider:
            return jsonify({
                'success': False,
                'error': '提供商不存在'
            }), 404

        return jsonify({
            'success': True,
            'provider': provider
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取配置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers', methods=['POST'])
@admin_required
def api_add_ai_provider():
    """API: 添加AI提供商"""
    try:
        from services.ai_config_service import AIConfigService

        data = request.get_json()
        success, message, provider_id = AIConfigService.add_provider(data)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'id': provider_id
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'添加失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers/<int:provider_id>', methods=['PUT'])
@admin_required
def api_update_ai_provider(provider_id):
    """API: 更新AI提供商配置"""
    try:
        from services.ai_config_service import AIConfigService

        data = request.get_json()
        success, message = AIConfigService.update_provider(provider_id, data)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'更新失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers/<int:provider_id>', methods=['DELETE'])
@admin_required
def api_delete_ai_provider(provider_id):
    """API: 删除AI提供商"""
    try:
        from services.ai_config_service import AIConfigService

        success, message = AIConfigService.delete_provider(provider_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'删除失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers/<int:provider_id>/default', methods=['POST'])
@admin_required
def api_set_default_ai_provider(provider_id):
    """API: 设置默认AI提供商"""
    try:
        from services.ai_config_service import AIConfigService

        success, message = AIConfigService.set_default_provider(provider_id)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'设置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers/<int:provider_id>/toggle', methods=['POST'])
@admin_required
def api_toggle_ai_provider(provider_id):
    """API: 切换AI提供商激活状态"""
    try:
        from services.ai_config_service import AIConfigService

        success, message, is_active = AIConfigService.toggle_provider_active(provider_id)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'is_active': is_active
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'操作失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/providers/<int:provider_id>/test', methods=['POST'])
@admin_required
def api_test_ai_provider(provider_id):
    """API: 测试AI提供商连接"""
    try:
        from services.ai_config_service import AIConfigService

        success, message, result = AIConfigService.test_provider(provider_id)

        return jsonify({
            'success': success,
            'message': message,
            'result': result
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'测试失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/stats', methods=['GET'])
@admin_required
def api_get_ai_stats():
    """API: 获取AI使用统计"""
    try:
        from services.ai_config_service import AIConfigService

        days = request.args.get('days', 30, type=int)
        stats = AIConfigService.get_usage_stats(days)

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取统计失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/logs', methods=['GET'])
@admin_required
def api_get_ai_logs():
    """API: 获取AI使用日志"""
    try:
        from services.ai_config_service import AIConfigService

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        logs, total = AIConfigService.get_usage_logs(page, per_page)

        return jsonify({
            'success': True,
            'logs': logs,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取日志失败: {str(e)}'
        }), 500


# ============================================================
# AI提示语配置管理 API
# ============================================================

@system_config_bp.route('/ai-prompts')
@admin_required
def ai_prompts_page():
    """AI提示语配置管理页面"""
    return render_template('system_config/ai_prompts.html', title='AI提示语配置 | ' + APP_TITLE)


@system_config_bp.route('/api/ai/prompts', methods=['GET'])
@admin_required
def api_get_ai_prompts():
    """API: 获取所有AI提示语配置"""
    try:
        from services.ai_prompt_config_service import AIPromptConfigService
        configs = AIPromptConfigService.get_all_configs()
        return jsonify({
            'success': True,
            'configs': configs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取配置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/prompts/<config_key>', methods=['GET'])
@admin_required
def api_get_ai_prompt(config_key):
    """API: 获取单个AI提示语配置"""
    try:
        from services.ai_prompt_config_service import AIPromptConfigService
        config = AIPromptConfigService.get_config_by_key(config_key)
        if not config:
            return jsonify({
                'success': False,
                'error': f'配置项 "{config_key}" 不存在'
            }), 404

        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取配置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/prompts/<config_key>', methods=['PUT'])
@admin_required
def api_update_ai_prompt(config_key):
    """API: 更新AI提示语配置"""
    try:
        from services.ai_prompt_config_service import AIPromptConfigService

        data = request.get_json()
        new_instruction = data.get('instruction', '').strip()

        if not new_instruction:
            return jsonify({
                'success': False,
                'error': '指令内容不能为空'
            }), 400

        success, message = AIPromptConfigService.update_config(config_key, new_instruction)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'更新失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/prompts/<config_key>/reset', methods=['POST'])
@admin_required
def api_reset_ai_prompt(config_key):
    """API: 重置单个AI提示语配置为默认值"""
    try:
        from services.ai_prompt_config_service import AIPromptConfigService

        success, message = AIPromptConfigService.reset_config(config_key)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'重置失败: {str(e)}'
        }), 500


@system_config_bp.route('/api/ai/prompts/reset-all', methods=['POST'])
@admin_required
def api_reset_all_ai_prompts():
    """API: 重置所有AI提示语配置为默认值"""
    try:
        from services.ai_prompt_config_service import AIPromptConfigService

        success, message = AIPromptConfigService.reset_all_configs()

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'重置失败: {str(e)}'
        }), 500
