#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钉钉免登服务
提供 access_token 缓存与用户信息获取
"""
import os
from datetime import datetime, timedelta

import requests

from models.database import get_db
from utils.logger import SecurityLogger


DINGTALK_BASE_URL = "https://oapi.dingtalk.com"
TOKEN_CACHE_ID = 1
TOKEN_TTL_SECONDS = 110 * 60


def get_access_token():
    """获取 access_token，带本地缓存（110分钟）"""
    cached = _get_cached_token()
    if cached:
        return cached

    app_key = os.environ.get("DINGTALK_APP_KEY", "").strip()
    app_secret = os.environ.get("DINGTALK_APP_SECRET", "").strip()
    if not app_key or not app_secret:
        raise RuntimeError("DINGTALK_APP_KEY or DINGTALK_APP_SECRET not configured")

    resp = requests.get(
        f"{DINGTALK_BASE_URL}/gettoken",
        params={"appkey": app_key, "appsecret": app_secret},
        timeout=10
    )
    data = resp.json()
    _handle_dingtalk_error(data, "gettoken")

    token = data.get("access_token")
    if not token:
        raise RuntimeError("Missing access_token in DingTalk response")

    expires_at = datetime.now() + timedelta(seconds=TOKEN_TTL_SECONDS)
    _save_token(token, expires_at)
    return token


def get_userid_by_auth_code(auth_code):
    """通过免登码获取 userid"""
    access_token = get_access_token()
    resp = requests.post(
        f"{DINGTALK_BASE_URL}/topapi/v2/user/getuserinfo",
        params={"access_token": access_token},
        json={"code": auth_code},
        timeout=10
    )
    data = resp.json()
    _handle_dingtalk_error(data, "getuserinfo")

    result = data.get("result") or {}
    userid = result.get("userid") or result.get("userId") or data.get("userid")
    if not userid:
        raise RuntimeError("Missing userid in DingTalk response")
    return userid


def get_user_profile(userid):
    """获取用户详情（包含姓名）"""
    access_token = get_access_token()
    resp = requests.post(
        f"{DINGTALK_BASE_URL}/topapi/v2/user/get",
        params={"access_token": access_token},
        json={"userid": userid, "language": "zh_CN"},
        timeout=10
    )
    data = resp.json()
    _handle_dingtalk_error(data, "getuser")

    result = data.get("result") or {}
    return result


def get_jsapi_ticket():
    """获取 jsapi_ticket，用于前端 JSAPI 鉴权"""
    # 先尝试从缓存读取
    cached = _get_cached_jsapi_ticket()
    if cached:
        return cached

    access_token = get_access_token()
    resp = requests.get(
        f"{DINGTALK_BASE_URL}/get_jsapi_ticket",
        params={"access_token": access_token},
        timeout=10
    )
    data = resp.json()
    _handle_dingtalk_error(data, "get_jsapi_ticket")

    ticket = data.get("ticket")
    if not ticket:
        raise RuntimeError("Missing ticket in DingTalk response")

    # 缓存 ticket（有效期 7200 秒，我们缓存 110 分钟）
    expires_at = datetime.now() + timedelta(seconds=TOKEN_TTL_SECONDS)
    _save_jsapi_ticket(ticket, expires_at)
    return ticket


def _get_cached_jsapi_ticket():
    """读取本地缓存的 jsapi_ticket"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT jsapi_ticket, ticket_expires_at FROM dingtalk_token_cache WHERE id = %s",
        (TOKEN_CACHE_ID,)
    )
    row = cur.fetchone()
    if not row:
        return None

    ticket_expires_at = row.get("ticket_expires_at")
    if not ticket_expires_at or ticket_expires_at <= datetime.now():
        return None

    return row.get("jsapi_ticket")


def _save_jsapi_ticket(jsapi_ticket, expires_at):
    """保存 jsapi_ticket 到本地缓存"""
    conn = get_db()
    cur = conn.cursor()
    
    # 先检查记录是否存在
    cur.execute("SELECT id FROM dingtalk_token_cache WHERE id = %s", (TOKEN_CACHE_ID,))
    exists = cur.fetchone()
    
    if exists:
        # 更新现有记录
        cur.execute(
            """
            UPDATE dingtalk_token_cache 
            SET jsapi_ticket = %s, ticket_expires_at = %s 
            WHERE id = %s
            """,
            (jsapi_ticket, expires_at, TOKEN_CACHE_ID)
        )
    else:
        # 插入新记录
        cur.execute(
            """
            INSERT INTO dingtalk_token_cache (id, jsapi_ticket, ticket_expires_at)
            VALUES (%s, %s, %s)
            """,
            (TOKEN_CACHE_ID, jsapi_ticket, expires_at)
        )
    
    conn.commit()


def _get_cached_token():
    """读取本地缓存的 access_token"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT access_token, expires_at FROM dingtalk_token_cache WHERE id = %s",
        (TOKEN_CACHE_ID,)
    )
    row = cur.fetchone()
    if not row:
        return None

    expires_at = row.get("expires_at")
    if not expires_at or expires_at <= datetime.now():
        return None

    return row.get("access_token")


def _save_token(access_token, expires_at):
    """保存 access_token 到本地缓存"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        REPLACE INTO dingtalk_token_cache (id, access_token, expires_at)
        VALUES (%s, %s, %s)
        """,
        (TOKEN_CACHE_ID, access_token, expires_at)
    )
    conn.commit()


def _handle_dingtalk_error(data, action):
    """处理钉钉接口错误"""
    errcode = data.get("errcode")
    if errcode in (None, 0, "0"):
        return

    try:
        code_value = int(errcode)
    except (TypeError, ValueError):
        code_value = None

    if code_value == 60020:
        SecurityLogger.suspicious_activity(
            "dingtalk_ip_not_whitelisted",
            {"action": action, "errcode": errcode, "errmsg": data.get("errmsg")}
        )
        raise RuntimeError("DingTalk IP not in whitelist")

    raise RuntimeError(f"DingTalk {action} failed: {errcode} {data.get('errmsg')}")
