#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Configuration Service
管理AI提供商配置，支持多种国内外AI模型
参考 One-API 设计：https://github.com/songquanpeng/one-api
"""
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from models.database import get_db


@dataclass
class AIProvider:
    """AI提供商配置"""
    id: int
    name: str
    provider_type: str
    api_key: str
    base_url: str
    model: str
    is_active: bool
    is_default: bool
    priority: int
    timeout: int
    max_tokens: int
    temperature: float
    extra_headers: Dict
    description: str


# 预置的AI提供商模板
PROVIDER_TEMPLATES = {
    'openrouter': {
        'name': 'OpenRouter',
        'provider_type': 'openrouter',
        'base_url': 'https://openrouter.ai/api/v1',
        'models': [
            {'id': 'anthropic/claude-3-haiku', 'name': 'Claude 3 Haiku (快速)'},
            {'id': 'anthropic/claude-3-sonnet', 'name': 'Claude 3 Sonnet (平衡)'},
            {'id': 'openai/gpt-4o-mini', 'name': 'GPT-4o Mini'},
            {'id': 'openai/gpt-4o', 'name': 'GPT-4o'},
            {'id': 'google/gemini-pro', 'name': 'Gemini Pro'},
            {'id': 'meta-llama/llama-3-70b-instruct', 'name': 'Llama 3 70B'},
            {'id': 'deepseek/deepseek-chat', 'name': 'DeepSeek Chat'},
        ],
        'description': '聚合多种AI模型的API网关，支持Claude、GPT、Gemini等',
        'extra_headers': {'HTTP-Referer': 'https://github.com/your-app', 'X-Title': 'Risk Mining System'}
    },
    'openai': {
        'name': 'OpenAI',
        'provider_type': 'openai',
        'base_url': 'https://api.openai.com/v1',
        'models': [
            {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini (推荐)'},
            {'id': 'gpt-4o', 'name': 'GPT-4o'},
            {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo'},
            {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo'},
        ],
        'description': 'OpenAI官方API',
        'extra_headers': {}
    },
    'gemini': {
        'name': 'Google Gemini',
        'provider_type': 'gemini',
        'base_url': 'https://generativelanguage.googleapis.com/v1beta',
        'models': [
            {'id': 'gemini-2.5-flash-preview-05-20', 'name': 'Gemini 2.5 Flash (免费)'},
        ],
        'description': 'Google Gemini官方API，有免费额度（每天1500次）',
        'extra_headers': {}
    },
    'anthropic': {
        'name': 'Anthropic Claude',
        'provider_type': 'anthropic',
        'base_url': 'https://api.anthropic.com/v1',
        'models': [
            {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku (快速)'},
            {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet (平衡)'},
            {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus (强大)'},
        ],
        'description': 'Anthropic官方API',
        'extra_headers': {'anthropic-version': '2023-06-01'}
    },
    'deepseek': {
        'name': 'DeepSeek 深度求索',
        'provider_type': 'deepseek',
        'base_url': 'https://api.deepseek.com/v1',
        'models': [
            {'id': 'deepseek-chat', 'name': 'DeepSeek Chat (推荐)'},
            {'id': 'deepseek-coder', 'name': 'DeepSeek Coder'},
        ],
        'description': '国产大模型，性价比高，支持中文',
        'extra_headers': {}
    },
    'qwen': {
        'name': '通义千问 (阿里云)',
        'provider_type': 'qwen',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'models': [
            {'id': 'qwen-turbo', 'name': 'Qwen Turbo (快速)'},
            {'id': 'qwen-plus', 'name': 'Qwen Plus (增强)'},
            {'id': 'qwen-max', 'name': 'Qwen Max (最强)'},
            {'id': 'qwen-long', 'name': 'Qwen Long (长文本)'},
        ],
        'description': '阿里云通义千问，国内访问稳定',
        'extra_headers': {}
    },
    'zhipu': {
        'name': '智谱AI (ChatGLM)',
        'provider_type': 'zhipu',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'models': [
            {'id': 'glm-4-flash', 'name': 'GLM-4 Flash (快速)'},
            {'id': 'glm-4', 'name': 'GLM-4 (标准)'},
            {'id': 'glm-4-plus', 'name': 'GLM-4 Plus (增强)'},
        ],
        'description': '清华智谱AI，国内访问稳定',
        'extra_headers': {}
    },
    'moonshot': {
        'name': 'Moonshot 月之暗面',
        'provider_type': 'moonshot',
        'base_url': 'https://api.moonshot.cn/v1',
        'models': [
            {'id': 'moonshot-v1-8k', 'name': 'Moonshot V1 8K'},
            {'id': 'moonshot-v1-32k', 'name': 'Moonshot V1 32K'},
            {'id': 'moonshot-v1-128k', 'name': 'Moonshot V1 128K'},
        ],
        'description': '月之暗面Kimi，支持超长上下文',
        'extra_headers': {}
    },
    'baichuan': {
        'name': '百川智能',
        'provider_type': 'baichuan',
        'base_url': 'https://api.baichuan-ai.com/v1',
        'models': [
            {'id': 'Baichuan4', 'name': 'Baichuan 4'},
            {'id': 'Baichuan3-Turbo', 'name': 'Baichuan 3 Turbo'},
            {'id': 'Baichuan2-Turbo', 'name': 'Baichuan 2 Turbo'},
        ],
        'description': '百川智能大模型',
        'extra_headers': {}
    },
    'minimax': {
        'name': 'MiniMax',
        'provider_type': 'minimax',
        'base_url': 'https://api.minimax.chat/v1',
        'models': [
            {'id': 'abab6.5s-chat', 'name': 'ABAB 6.5s Chat'},
            {'id': 'abab5.5-chat', 'name': 'ABAB 5.5 Chat'},
        ],
        'description': 'MiniMax大模型',
        'extra_headers': {}
    },
    'spark': {
        'name': '讯飞星火',
        'provider_type': 'spark',
        'base_url': 'https://spark-api-open.xf-yun.com/v1',
        'models': [
            {'id': 'generalv3.5', 'name': '星火 V3.5'},
            {'id': 'generalv3', 'name': '星火 V3'},
            {'id': '4.0Ultra', 'name': '星火 4.0 Ultra'},
        ],
        'description': '科大讯飞星火大模型',
        'extra_headers': {}
    },
    'hunyuan': {
        'name': '腾讯混元',
        'provider_type': 'hunyuan',
        'base_url': 'https://api.hunyuan.cloud.tencent.com/v1',
        'models': [
            {'id': 'hunyuan-lite', 'name': '混元 Lite'},
            {'id': 'hunyuan-standard', 'name': '混元 Standard'},
            {'id': 'hunyuan-pro', 'name': '混元 Pro'},
        ],
        'description': '腾讯混元大模型',
        'extra_headers': {}
    },
    'silicon': {
        'name': 'SiliconFlow 硅基流动',
        'provider_type': 'silicon',
        'base_url': 'https://api.siliconflow.cn/v1',
        'models': [
            {'id': 'Qwen/Qwen2.5-7B-Instruct', 'name': 'Qwen 2.5 7B'},
            {'id': 'Qwen/Qwen2.5-72B-Instruct', 'name': 'Qwen 2.5 72B'},
            {'id': 'deepseek-ai/DeepSeek-V2.5', 'name': 'DeepSeek V2.5'},
            {'id': 'THUDM/glm-4-9b-chat', 'name': 'GLM-4 9B'},
        ],
        'description': '硅基流动，提供多种开源模型API',
        'extra_headers': {}
    },
    'custom': {
        'name': '自定义 (OpenAI兼容)',
        'provider_type': 'custom',
        'base_url': '',
        'models': [],
        'description': '自定义OpenAI兼容API端点',
        'extra_headers': {}
    }
}


class AIConfigService:
    """AI配置管理服务"""

    @classmethod
    def get_provider_templates(cls) -> Dict:
        """获取所有预置的提供商模板"""
        return PROVIDER_TEMPLATES

    @classmethod
    def get_all_providers(cls) -> List[Dict]:
        """获取所有已配置的AI提供商"""
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name, provider_type, api_key, base_url, model,
                   is_active, is_default, priority, timeout, max_tokens,
                   temperature, extra_headers, description, created_at, updated_at
            FROM ai_providers
            ORDER BY priority DESC, is_default DESC, id ASC
        """)
        rows = cur.fetchall()

        providers = []
        for row in rows:
            extra_headers = {}
            if row['extra_headers']:
                try:
                    extra_headers = json.loads(row['extra_headers'])
                except:
                    pass

            providers.append({
                'id': row['id'],
                'name': row['name'],
                'provider_type': row['provider_type'],
                'api_key': row['api_key'][:8] + '****' if row['api_key'] and len(row['api_key']) > 8 else '',
                'api_key_set': bool(row['api_key']),
                'base_url': row['base_url'],
                'model': row['model'],
                'is_active': bool(row['is_active']),
                'is_default': bool(row['is_default']),
                'priority': row['priority'],
                'timeout': row['timeout'],
                'max_tokens': row['max_tokens'],
                'temperature': row['temperature'],
                'extra_headers': extra_headers,
                'description': row['description'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })

        return providers

    @classmethod
    def has_providers(cls) -> bool:
        """是否存在任何AI提供商配置"""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM ai_providers")
            row = cur.fetchone()
            return bool(row and row['cnt'] > 0)
        except Exception:
            return False

    @classmethod
    def get_provider_by_id(cls, provider_id: int) -> Optional[Dict]:
        """根据ID获取提供商配置"""
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name, provider_type, api_key, base_url, model,
                   is_active, is_default, priority, timeout, max_tokens,
                   temperature, extra_headers, description
            FROM ai_providers
            WHERE id = %s
        """, (provider_id,))
        row = cur.fetchone()

        if not row:
            return None

        extra_headers = {}
        if row['extra_headers']:
            try:
                extra_headers = json.loads(row['extra_headers'])
            except:
                pass

        return {
            'id': row['id'],
            'name': row['name'],
            'provider_type': row['provider_type'],
            'api_key': row['api_key'],
            'base_url': row['base_url'],
            'model': row['model'],
            'is_active': bool(row['is_active']),
            'is_default': bool(row['is_default']),
            'priority': row['priority'],
            'timeout': row['timeout'],
            'max_tokens': row['max_tokens'],
            'temperature': row['temperature'],
            'extra_headers': extra_headers,
            'description': row['description']
        }

    @classmethod
    def get_default_provider(cls) -> Optional[Dict]:
        """获取默认的AI提供商（用于实际调用）"""
        conn = get_db()
        cur = conn.cursor()

        # 优先获取默认且激活的提供商
        cur.execute("""
            SELECT id, name, provider_type, api_key, base_url, model,
                   timeout, max_tokens, temperature, extra_headers
            FROM ai_providers
            WHERE is_active = 1 AND is_default = 1
            LIMIT 1
        """)
        row = cur.fetchone()

        # 如果没有默认的，获取优先级最高的激活提供商
        if not row:
            cur.execute("""
                SELECT id, name, provider_type, api_key, base_url, model,
                       timeout, max_tokens, temperature, extra_headers
                FROM ai_providers
                WHERE is_active = 1
                ORDER BY priority DESC
                LIMIT 1
            """)
            row = cur.fetchone()

        if not row:
            return None

        extra_headers = {}
        if row['extra_headers']:
            try:
                extra_headers = json.loads(row['extra_headers'])
            except:
                pass

        return {
            'id': row['id'],
            'name': row['name'],
            'provider_type': row['provider_type'],
            'api_key': row['api_key'],
            'base_url': row['base_url'],
            'model': row['model'],
            'timeout': row['timeout'],
            'max_tokens': row['max_tokens'],
            'temperature': row['temperature'],
            'extra_headers': extra_headers
        }

    @classmethod
    def add_provider(cls, data: Dict) -> Tuple[bool, str, Optional[int]]:
        """添加新的AI提供商"""
        try:
            conn = get_db()
            cur = conn.cursor()

            # 验证必填字段
            required_fields = ['name', 'provider_type', 'base_url', 'model']
            for field in required_fields:
                if not data.get(field):
                    return False, f'字段 {field} 不能为空', None

            # 处理extra_headers
            extra_headers = data.get('extra_headers', {})
            if isinstance(extra_headers, dict):
                extra_headers = json.dumps(extra_headers)

            # 如果设为默认，先取消其他默认
            is_default = data.get('is_default', False)
            if is_default:
                cur.execute("UPDATE ai_providers SET is_default = 0")

            cur.execute("""
                INSERT INTO ai_providers
                (name, provider_type, api_key, base_url, model, is_active, is_default,
                 priority, timeout, max_tokens, temperature, extra_headers, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data['name'],
                data['provider_type'],
                data.get('api_key', ''),
                data['base_url'],
                data['model'],
                1 if data.get('is_active', True) else 0,
                1 if is_default else 0,
                data.get('priority', 0),
                data.get('timeout', 30),
                data.get('max_tokens', 200),
                data.get('temperature', 0.7),
                extra_headers,
                data.get('description', '')
            ))
            conn.commit()

            return True, '添加成功', cur.lastrowid

        except Exception as e:
            return False, f'添加失败: {str(e)}', None

    @classmethod
    def update_provider(cls, provider_id: int, data: Dict) -> Tuple[bool, str]:
        """更新AI提供商配置"""
        try:
            conn = get_db()
            cur = conn.cursor()

            # 检查是否存在
            cur.execute("SELECT id FROM ai_providers WHERE id = %s", (provider_id,))
            if not cur.fetchone():
                return False, '提供商不存在'

            # 处理extra_headers
            extra_headers = data.get('extra_headers', {})
            if isinstance(extra_headers, dict):
                extra_headers = json.dumps(extra_headers)

            # 如果设为默认，先取消其他默认
            is_default = data.get('is_default', False)
            if is_default:
                cur.execute("UPDATE ai_providers SET is_default = 0 WHERE id != %s", (provider_id,))

            # 构建更新语句
            update_fields = []
            params = []

            field_mapping = {
                'name': 'name',
                'provider_type': 'provider_type',
                'base_url': 'base_url',
                'model': 'model',
                'is_active': 'is_active',
                'is_default': 'is_default',
                'priority': 'priority',
                'timeout': 'timeout',
                'max_tokens': 'max_tokens',
                'temperature': 'temperature',
                'description': 'description'
            }

            for key, field in field_mapping.items():
                if key in data:
                    value = data[key]
                    if key in ['is_active', 'is_default']:
                        value = 1 if value else 0
                    update_fields.append(f"{field} = %s")
                    params.append(value)

            # API Key 单独处理（允许为空表示不更新）
            if 'api_key' in data and data['api_key']:
                update_fields.append("api_key = %s")
                params.append(data['api_key'])

            # extra_headers
            if 'extra_headers' in data:
                update_fields.append("extra_headers = %s")
                params.append(extra_headers)

            # 添加更新时间
            update_fields.append("updated_at = NOW()")

            if update_fields:
                params.append(provider_id)
                cur.execute(
                    f"UPDATE ai_providers SET {', '.join(update_fields)} WHERE id = %s",
                    params
                )
                conn.commit()

            return True, '更新成功'

        except Exception as e:
            return False, f'更新失败: {str(e)}'

    @classmethod
    def delete_provider(cls, provider_id: int) -> Tuple[bool, str]:
        """删除AI提供商"""
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT name FROM ai_providers WHERE id = %s", (provider_id,))
            row = cur.fetchone()
            if not row:
                return False, '提供商不存在'

            cur.execute("DELETE FROM ai_providers WHERE id = %s", (provider_id,))
            conn.commit()

            return True, f'已删除提供商: {row["name"]}'

        except Exception as e:
            return False, f'删除失败: {str(e)}'

    @classmethod
    def set_default_provider(cls, provider_id: int) -> Tuple[bool, str]:
        """设置默认提供商"""
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT name FROM ai_providers WHERE id = %s", (provider_id,))
            row = cur.fetchone()
            if not row:
                return False, '提供商不存在'

            # 取消所有默认
            cur.execute("UPDATE ai_providers SET is_default = 0")
            # 设置新默认
            cur.execute("UPDATE ai_providers SET is_default = 1 WHERE id = %s", (provider_id,))
            conn.commit()

            return True, f'已设置 {row["name"]} 为默认提供商'

        except Exception as e:
            return False, f'设置失败: {str(e)}'

    @classmethod
    def toggle_provider_active(cls, provider_id: int) -> Tuple[bool, str, bool]:
        """切换提供商激活状态"""
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT name, is_active FROM ai_providers WHERE id = %s", (provider_id,))
            row = cur.fetchone()
            if not row:
                return False, '提供商不存在', False

            new_status = 0 if row['is_active'] else 1
            cur.execute("UPDATE ai_providers SET is_active = %s WHERE id = %s", (new_status, provider_id))
            conn.commit()

            status_text = '启用' if new_status else '禁用'
            return True, f'已{status_text} {row["name"]}', bool(new_status)

        except Exception as e:
            return False, f'操作失败: {str(e)}', False

    @classmethod
    def test_provider(cls, provider_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """测试AI提供商连接"""
        try:
            import httpx
        except ImportError:
            return False, 'httpx库未安装', None

        provider = cls.get_provider_by_id(provider_id)
        if not provider:
            return False, '提供商不存在', None

        if not provider['api_key']:
            return False, 'API Key未配置', None

        try:
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {provider['api_key']}"
            }

            # 添加额外headers
            if provider['extra_headers']:
                headers.update(provider['extra_headers'])

            # Anthropic 特殊处理
            if provider['provider_type'] == 'anthropic':
                headers['x-api-key'] = provider['api_key']
                del headers['Authorization']

            # Gemini 特殊处理 - 不需要 Authorization header
            if provider['provider_type'] == 'gemini':
                headers.pop('Authorization', None)

            # 根据提供商类型构建不同的请求格式
            if provider['provider_type'] == 'gemini':
                # Gemini API 格式
                payload = {
                    'contents': [
                        {
                            'parts': [
                                {'text': '请回复"连接成功"四个字'}
                            ]
                        }
                    ],
                    'generationConfig': {
                        'temperature': 0.1,
                        'maxOutputTokens': 50
                    }
                }
                endpoint = f"{provider['base_url']}/models/{provider['model']}:generateContent?key={provider['api_key']}"
            else:
                payload = {
                    'model': provider['model'],
                    'messages': [
                        {'role': 'user', 'content': '请回复"连接成功"四个字'}
                    ],
                    'max_tokens': 50,
                    'temperature': 0.1
                }
                # Anthropic API格式不同
                if provider['provider_type'] == 'anthropic':
                    endpoint = f"{provider['base_url']}/messages"
                else:
                    endpoint = f"{provider['base_url']}/chat/completions"

            with httpx.Client(timeout=provider['timeout']) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()

                # 解析响应
                if provider['provider_type'] == 'gemini':
                    # Gemini 响应格式
                    candidates = data.get('candidates', [{}])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [{}])
                        reply = parts[0].get('text', '') if parts else ''
                    else:
                        reply = ''
                    usage = data.get('usageMetadata', {})
                    tokens = usage.get('totalTokenCount', 0)
                elif provider['provider_type'] == 'anthropic':
                    reply = data.get('content', [{}])[0].get('text', '')
                    tokens = data.get('usage', {}).get('input_tokens', 0) + data.get('usage', {}).get('output_tokens', 0)
                else:
                    reply = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    tokens = data.get('usage', {}).get('total_tokens', 0)

                # 记录日志
                cls.log_usage(provider_id, provider['name'], provider['model'], tokens, True, None, 'test')

                return True, '连接成功', {
                    'reply': reply.strip(),
                    'tokens': tokens,
                    'model': provider['model']
                }

        except httpx.HTTPStatusError as e:
            error_msg = f'HTTP错误: {e.response.status_code}'
            try:
                error_detail = e.response.json()
                if 'error' in error_detail:
                    error_msg = error_detail['error'].get('message', error_msg)
            except:
                pass
            cls.log_usage(provider_id, provider['name'], provider['model'], 0, False, error_msg, 'test')
            return False, error_msg, None

        except httpx.RequestError as e:
            error_msg = f'网络错误: {str(e)}'
            cls.log_usage(provider_id, provider['name'], provider['model'], 0, False, error_msg, 'test')
            return False, error_msg, None

        except Exception as e:
            error_msg = f'未知错误: {str(e)}'
            cls.log_usage(provider_id, provider['name'], provider['model'], 0, False, error_msg, 'test')
            return False, error_msg, None

    @classmethod
    def log_usage(cls, provider_id: int, provider_name: str, model: str,
                  tokens: int, success: bool, error_message: Optional[str], request_type: str):
        """记录AI使用日志"""
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO ai_usage_logs
                (provider_id, provider_name, model, tokens_used, success, error_message, request_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                provider_id,
                provider_name,
                model,
                tokens,
                1 if success else 0,
                error_message,
                request_type
            ))
            conn.commit()

        except Exception as e:
            print(f"记录AI使用日志失败: {e}")

    @classmethod
    def get_usage_stats(cls, days: int = 30) -> Dict:
        """获取AI使用统计"""
        conn = get_db()
        cur = conn.cursor()

        # 总体统计
        cur.execute(f"""
            SELECT
                COUNT(*) as total_calls,
                SUM(tokens_used) as total_tokens,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
            FROM ai_usage_logs
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
        """)
        row = cur.fetchone() or {}

        total_calls = row.get('total_calls') or 0
        success_rate = (row.get('success_count', 0) / total_calls * 100) if total_calls > 0 else 0

        # 按提供商统计
        cur.execute(f"""
            SELECT
                provider_name,
                COUNT(*) as calls,
                SUM(tokens_used) as tokens
            FROM ai_usage_logs
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY provider_name
            ORDER BY calls DESC
        """)
        by_provider = [dict(row) for row in cur.fetchall()]

        # 最近错误
        cur.execute("""
            SELECT provider_name, model, error_message, created_at
            FROM ai_usage_logs
            WHERE success = 0
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent_errors = [dict(row) for row in cur.fetchall()]

        return {
            'total_calls': total_calls,
            'total_tokens': row.get('total_tokens') or 0,
            'success_count': row.get('success_count') or 0,
            'error_count': row.get('error_count') or 0,
            'success_rate': round(success_rate, 1),
            'by_provider': by_provider,
            'recent_errors': recent_errors
        }

    @classmethod
    def get_usage_logs(cls, page: int = 1, per_page: int = 50) -> Tuple[List[Dict], int]:
        """获取使用日志列表"""
        conn = get_db()
        cur = conn.cursor()

        # 获取总数
        cur.execute("SELECT COUNT(*) AS cnt FROM ai_usage_logs")
        row = cur.fetchone() or {}
        total = row.get('cnt') or 0

        # 获取分页数据
        offset = (page - 1) * per_page
        cur.execute("""
            SELECT id, provider_name, model, tokens_used, success, error_message, request_type, created_at
            FROM ai_usage_logs
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))

        logs = [dict(row) for row in cur.fetchall()]

        return logs, total


# 单例服务
ai_config_service = AIConfigService()
