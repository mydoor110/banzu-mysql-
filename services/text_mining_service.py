#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Text Mining Service for NLP-based keyword extraction
Uses jieba for Chinese word segmentation
"""
import re
from collections import Counter
from typing import List, Dict, Optional, Set
from models.database import get_db


class TextMiningService:
    """
    Text mining service for extracting keywords from Chinese text.
    Supports stopword filtering and word frequency analysis.
    """

    _stopwords_cache: Optional[Set[str]] = None
    _cache_timestamp: Optional[float] = None
    CACHE_TTL = 300  # 5 minutes cache

    @classmethod
    def _load_stopwords(cls, force_reload: bool = False) -> Set[str]:
        """
        Load stopwords from database with caching.

        Args:
            force_reload: Force reload from database ignoring cache

        Returns:
            Set of stopwords
        """
        import time

        current_time = time.time()

        # Check cache validity
        if (not force_reload and
            cls._stopwords_cache is not None and
            cls._cache_timestamp is not None and
            current_time - cls._cache_timestamp < cls.CACHE_TTL):
            return cls._stopwords_cache

        # Load from database
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT word FROM stopwords")
        rows = cur.fetchall()

        cls._stopwords_cache = {row['word'] for row in rows}
        cls._cache_timestamp = current_time

        return cls._stopwords_cache

    @classmethod
    def clear_cache(cls):
        """Clear the stopwords cache"""
        cls._stopwords_cache = None
        cls._cache_timestamp = None

    @staticmethod
    def _preprocess_text(text: str) -> str:
        """
        Preprocess text before tokenization.

        Args:
            text: Raw text input

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters but keep Chinese and alphanumeric
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)

        return text.strip()

    @classmethod
    def tokenize(cls, text: str, remove_stopwords: bool = True) -> List[str]:
        """
        Tokenize Chinese text using jieba.

        Args:
            text: Input text to tokenize
            remove_stopwords: Whether to filter out stopwords

        Returns:
            List of tokens
        """
        try:
            import jieba
        except ImportError:
            raise ImportError("jieba is required for text mining. Install with: pip install jieba")

        # Preprocess
        text = cls._preprocess_text(text)
        if not text:
            return []

        # Tokenize with jieba
        tokens = list(jieba.cut(text, cut_all=False))

        # Filter: remove single characters, numbers, and optionally stopwords
        stopwords = cls._load_stopwords() if remove_stopwords else set()

        filtered_tokens = []
        for token in tokens:
            token = token.strip()
            # Skip empty, single char, pure numbers
            if len(token) < 2:
                continue
            if token.isdigit():
                continue
            # Skip stopwords
            if token in stopwords:
                continue
            filtered_tokens.append(token)

        return filtered_tokens

    @classmethod
    def extract_keywords(
        cls,
        texts: List[str],
        top_n: int = 20,
        min_freq: int = 2
    ) -> List[Dict[str, any]]:
        """
        Extract top keywords from multiple texts.

        Args:
            texts: List of text strings to analyze
            top_n: Number of top keywords to return
            min_freq: Minimum frequency threshold

        Returns:
            List of dicts with 'name' and 'value' keys, suitable for word cloud
        """
        # Tokenize all texts
        all_tokens = []
        for text in texts:
            if text:
                tokens = cls.tokenize(text, remove_stopwords=True)
                all_tokens.extend(tokens)

        if not all_tokens:
            return []

        # Count frequencies
        counter = Counter(all_tokens)

        # Filter by minimum frequency and get top N
        keywords = [
            {"name": word, "value": count}
            for word, count in counter.most_common(top_n * 2)  # Get extra for filtering
            if count >= min_freq
        ][:top_n]

        return keywords

    @classmethod
    def analyze_text_batch(
        cls,
        records: List[Dict],
        text_fields: List[str],
        top_n: int = 20
    ) -> Dict:
        """
        Analyze a batch of records for keyword extraction.

        Args:
            records: List of record dicts
            text_fields: List of field names containing text to analyze
            top_n: Number of top keywords to return

        Returns:
            Dict containing keyword analysis results
        """
        # Collect all texts from specified fields
        all_texts = []
        for record in records:
            for field in text_fields:
                text = record.get(field) if isinstance(record, dict) else getattr(record, field, None)
                if text:
                    all_texts.append(str(text))

        # Extract keywords
        keywords = cls.extract_keywords(all_texts, top_n=top_n)

        # Calculate statistics
        total_texts = len(all_texts)
        total_tokens = sum(len(cls.tokenize(t)) for t in all_texts) if all_texts else 0

        return {
            "keyword_cloud": keywords,
            "statistics": {
                "total_texts": total_texts,
                "total_tokens": total_tokens,
                "unique_keywords": len(keywords)
            }
        }


# Singleton instance for convenience
text_mining_service = TextMiningService()
