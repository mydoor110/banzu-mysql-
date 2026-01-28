#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze database text fields to propose stopword candidates.
Outputs high-frequency tokens (by document frequency) excluding existing stopwords.
"""
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

from models.database import get_db
from services.text_mining_service import TextMiningService


def fetch_texts() -> list[str]:
    conn = get_db()
    cur = conn.cursor()

    texts = []

    cur.execute("SELECT hazard_description FROM safety_inspection_records")
    rows = cur.fetchall()
    texts.extend([row.get("hazard_description") for row in rows if row and row.get("hazard_description")])

    cur.execute("SELECT specific_problem FROM training_records")
    rows = cur.fetchall()
    texts.extend([row.get("specific_problem") for row in rows if row and row.get("specific_problem")])

    return texts


def main():
    texts = fetch_texts()
    total_docs = len(texts)
    if total_docs == 0:
        print("No text records found.")
        return

    stopwords = TextMiningService._load_stopwords(force_reload=True)

    term_tf = Counter()
    term_df = Counter()

    for text in texts:
        tokens = TextMiningService.tokenize(text, remove_stopwords=False)
        if not tokens:
            continue
        term_tf.update(tokens)
        term_df.update(set(tokens))

    candidates = []
    for term, df in term_df.items():
        if term in stopwords:
            continue
        tf = term_tf.get(term, 0)
        df_ratio = df / total_docs
        candidates.append((term, df, df_ratio, tf))

    candidates.sort(key=lambda x: (-x[1], -x[3]))

    print(f"Total docs: {total_docs}")
    print("term\tdf\tdf_ratio\ttf")
    for term, df, df_ratio, tf in candidates[:300]:
        print(f"{term}\t{df}\t{df_ratio:.3f}\t{tf}")


if __name__ == "__main__":
    main()
