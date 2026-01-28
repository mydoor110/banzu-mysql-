#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Insert curated stopword additions into database (category: custom).
"""
from dotenv import load_dotenv

load_dotenv()

from models.database import get_db
from services.text_mining_service import TextMiningService


ADDITIONAL_STOPWORDS = [
    "司机", "确认", "询问", "回答", "是否", "有无", "申请", "汇报", "报行调", "行调",
    "报行", "报单", "填写", "签名", "点击", "建立", "一次", "分钟", "一分钟", "再次",
    "重新", "车站", "站台", "列车",
    "贾河", "宇航", "南四环", "朝阳", "刘庄", "五里", "庄上",
    "周子捷", "刘力", "鹏飞", "张强", "志强", "杨成", "陈洋", "罗柏豪", "王绍华", "王永超",
    "张浩", "潘思宇", "李闯", "赵顺", "庞永辉", "郭逸", "李志轩", "张舒阳", "张建营",
    "彭哲", "冯恩", "陈书毫", "胡双印", "李家",
]


def main():
    conn = get_db()
    cur = conn.cursor()

    inserted = 0
    for word in ADDITIONAL_STOPWORDS:
        cur.execute(
            "INSERT IGNORE INTO stopwords (word, category) VALUES (%s, 'custom')",
            (word,)
        )
        if cur.rowcount > 0:
            inserted += 1

    conn.commit()
    TextMiningService.clear_cache()

    print(f"Inserted {inserted} new stopwords (requested {len(ADDITIONAL_STOPWORDS)}).")


if __name__ == "__main__":
    main()
