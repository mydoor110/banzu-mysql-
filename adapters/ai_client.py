#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 提供商统一客户端（适配层）

P2.2：将 OpenAI / Anthropic / Gemini 三种协议差异收敛到此层。
业务层（ai_config_service, ai_diagnosis_service）只面对统一的
chat() / chat_async() 接口，不再处理第三方协议细节。

支持的提供商类型：
  - openai（及所有 OpenAI 兼容接口，如 OpenRouter、DeepSeek 等）
  - anthropic
  - gemini
"""
from dataclasses import dataclass, field
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """AI 调用统一返回结构"""
    success: bool
    text: str = ""
    tokens_used: int = 0
    model: str = ""
    error: Optional[str] = None


def _build_headers(provider: dict) -> dict:
    """构建请求 headers（按提供商类型差异化）"""
    provider_type = provider.get('provider_type', 'openai')
    api_key = provider.get('api_key', '')
    extra_headers = provider.get('extra_headers') or {}

    headers = {
        "Content-Type": "application/json",
    }

    if provider_type == 'anthropic':
        headers['x-api-key'] = api_key
    elif provider_type == 'gemini':
        pass  # Gemini 通过 URL 参数传 key
    else:
        headers['Authorization'] = f"Bearer {api_key}"

    if extra_headers:
        headers.update(extra_headers)

    return headers


def _build_endpoint(provider: dict) -> str:
    """构建 API endpoint URL"""
    provider_type = provider.get('provider_type', 'openai')
    base_url = provider.get('base_url', '')
    model = provider.get('model', '')
    api_key = provider.get('api_key', '')

    if provider_type == 'gemini':
        return f"{base_url}/models/{model}:generateContent?key={api_key}"
    elif provider_type == 'anthropic':
        return f"{base_url}/messages"
    else:
        return f"{base_url}/chat/completions"


def _build_payload(provider: dict, prompt: str,
                   max_tokens: Optional[int] = None,
                   temperature: Optional[float] = None) -> dict:
    """构建请求体（按提供商类型差异化）"""
    provider_type = provider.get('provider_type', 'openai')
    model = provider.get('model', '')
    _max_tokens = max_tokens if max_tokens is not None else provider.get('max_tokens', 500)
    _temperature = temperature if temperature is not None else provider.get('temperature', 0.7)

    # Gemini 免费版最大 8192
    if provider_type == 'gemini' and _max_tokens > 8000:
        _max_tokens = 8000

    if provider_type == 'gemini':
        return {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
            "generationConfig": {
                "temperature": _temperature,
                "maxOutputTokens": _max_tokens
            }
        }
    else:
        return {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": _max_tokens,
            "temperature": _temperature
        }


def _parse_response(provider_type: str, data: dict) -> tuple:
    """
    解析 API 响应，返回 (text, tokens_used)。

    按提供商类型差异化提取回复文本和 token 消耗。
    """
    if provider_type == 'gemini':
        candidates = data.get('candidates', [{}])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [{}])
            text = parts[0].get('text', '').strip() if parts else ''
        else:
            text = ''
        usage = data.get('usageMetadata', {})
        tokens = usage.get('totalTokenCount', 0)
    elif provider_type == 'anthropic':
        text = data.get('content', [{}])[0].get('text', '').strip()
        tokens = (data.get('usage', {}).get('input_tokens', 0) +
                  data.get('usage', {}).get('output_tokens', 0))
    else:
        text = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        tokens = data.get('usage', {}).get('total_tokens', 0)

    return text, tokens


def _parse_http_error(e) -> str:
    """从 httpx.HTTPStatusError 中提取可读错误信息"""
    error_msg = f"HTTP错误: {e.response.status_code}"
    try:
        error_detail = e.response.json()
        if 'error' in error_detail:
            error_msg = error_detail['error'].get('message', error_msg)
    except Exception:
        pass
    return error_msg


def chat(provider: dict, prompt: str,
         max_tokens: Optional[int] = None,
         temperature: Optional[float] = None) -> AIResponse:
    """
    同步调用 AI 提供商（统一入口）

    Args:
        provider: 提供商配置 dict（含 provider_type, api_key, base_url, model, timeout 等）
        prompt: 用户提示语
        max_tokens: 最大输出 token（可选，默认用 provider 配置）
        temperature: 温度（可选）

    Returns:
        AIResponse: 统一返回结构
    """
    import httpx

    provider_type = provider.get('provider_type', 'openai')
    model = provider.get('model', '')
    timeout = provider.get('timeout', 30)

    headers = _build_headers(provider)
    endpoint = _build_endpoint(provider)
    payload = _build_payload(provider, prompt, max_tokens, temperature)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text, tokens = _parse_response(provider_type, data)
        return AIResponse(success=True, text=text, tokens_used=tokens, model=model)

    except httpx.HTTPStatusError as e:
        error = _parse_http_error(e)
        logger.error("AI调用失败 provider=%s model=%s: %s", provider.get('name', ''), model, error)
        return AIResponse(success=False, error=error, model=model)
    except httpx.RequestError as e:
        error = f"网络错误: {str(e)}"
        logger.error("AI网络错误 provider=%s: %s", provider.get('name', ''), error)
        return AIResponse(success=False, error=error, model=model)
    except Exception as e:
        error = f"未知错误: {str(e)}"
        logger.error("AI未知错误 provider=%s: %s", provider.get('name', ''), error)
        return AIResponse(success=False, error=error, model=model)


async def chat_async(provider: dict, prompt: str,
                     max_tokens: Optional[int] = None,
                     temperature: Optional[float] = None) -> AIResponse:
    """
    异步调用 AI 提供商（统一入口）

    Args:
        provider: 提供商配置 dict
        prompt: 用户提示语
        max_tokens: 最大输出 token（可选）
        temperature: 温度（可选）

    Returns:
        AIResponse: 统一返回结构
    """
    import httpx

    provider_type = provider.get('provider_type', 'openai')
    model = provider.get('model', '')
    timeout = provider.get('timeout', 30)

    headers = _build_headers(provider)
    endpoint = _build_endpoint(provider)
    payload = _build_payload(provider, prompt, max_tokens, temperature)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text, tokens = _parse_response(provider_type, data)
        return AIResponse(success=True, text=text, tokens_used=tokens, model=model)

    except httpx.HTTPStatusError as e:
        error = _parse_http_error(e)
        logger.error("AI异步调用失败 provider=%s model=%s: %s", provider.get('name', ''), model, error)
        return AIResponse(success=False, error=error, model=model)
    except httpx.RequestError as e:
        error = f"网络错误: {str(e)}"
        logger.error("AI异步网络错误 provider=%s: %s", provider.get('name', ''), error)
        return AIResponse(success=False, error=error, model=model)
    except Exception as e:
        error = f"未知错误: {str(e)}"
        logger.error("AI异步未知错误 provider=%s: %s", provider.get('name', ''), error)
        return AIResponse(success=False, error=error, model=model)
