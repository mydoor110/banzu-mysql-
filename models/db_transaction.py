# -*- coding: utf-8 -*-
"""
数据库事务上下文管理器

统一事务边界：service 层决定 commit/rollback，repository/dao 层只执行 SQL。

使用方式：
    from models.db_transaction import db_transaction

    def transfer_funds(from_id, to_id, amount):
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_id))
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_id))
            # 正常退出 → 自动 commit
            # 抛异常 → 自动 rollback
"""
from contextlib import contextmanager
from models.database import get_db


@contextmanager
def db_transaction():
    """获取数据库连接并管理事务边界

    Yields:
        conn: 数据库连接对象

    正常退出时自动 commit，异常时自动 rollback 后重新抛出。
    """
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
