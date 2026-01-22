#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF解析性能诊断脚本
用于定位22秒慢速的具体瓶颈
"""
import time
from blueprints.performance import extract_text_from_pdf, parse_pdf_text

def diagnose_pdf_performance(pdf_path):
    """诊断PDF解析各阶段的耗时"""
    print("=== PDF解析性能诊断 ===\n")
    
    # 1. PDF文本提取
    print("1. 开始PDF文本提取...")
    start = time.time()
    text = extract_text_from_pdf(pdf_path)
    extract_time = time.time() - start
    print(f"   ✓ PDF文本提取耗时: {extract_time:.2f}秒")
    print(f"   ✓ 提取文本长度: {len(text)} 字符")
    
    # 2. 文本解析
    print("\n2. 开始文本解析...")
    start = time.time()
    parsed_year, parsed_month, rows = parse_pdf_text(text)
    parse_time = time.time() - start
    print(f"   ✓ 文本解析耗时: {parse_time:.2f}秒")
    print(f"   ✓ 解析出记录数: {len(rows)} 条")
    
    # 3. 数据库查询（模拟）
    print("\n3. 模拟数据库查询...")
    from models.database import get_db
    from blueprints.helpers import build_department_filter
    
    conn = get_db()
    cur = conn.cursor()
    
    start = time.time()
    where_clause, join_clause, dept_params = build_department_filter()
    cur.execute(
        f"""
        SELECT emp_no
        FROM employees
        {join_clause}
        WHERE {where_clause}
        """,
        dept_params
    )
    roster = {record['emp_no'] for record in cur.fetchall()}
    query_time = time.time() - start
    print(f"   ✓ 员工查询耗时: {query_time:.2f}秒")
    print(f"   ✓ 员工总数: {len(roster)} 人")
    
    # 4. 数据过滤
    print("\n4. 数据过滤...")
    start = time.time()
    filtered = [r for r in rows if r["emp_no"] in roster]
    filter_time = time.time() - start
    print(f"   ✓ 数据过滤耗时: {filter_time:.2f}秒")
    print(f"   ✓ 有效记录数: {len(filtered)} 条")
    
    # 5. 批量插入（模拟）
    print("\n5. 模拟批量插入...")
    start = time.time()
    if filtered:
        batch_data = [
            (r["emp_no"], r["name"], 2026, 1, r["score"], r["grade"], "test.pdf", 1)
            for r in filtered[:10]  # 只测试10条
        ]
        # 不实际插入，只测试数据准备
    insert_time = time.time() - start
    print(f"   ✓ 数据准备耗时: {insert_time:.2f}秒")
    
    # 总结
    total_time = extract_time + parse_time + query_time + filter_time + insert_time
    print("\n" + "=" * 50)
    print("性能分析总结：")
    print(f"  PDF文本提取: {extract_time:6.2f}秒 ({extract_time/total_time*100:5.1f}%)")
    print(f"  文本解析:     {parse_time:6.2f}秒 ({parse_time/total_time*100:5.1f}%)")
    print(f"  员工查询:     {query_time:6.2f}秒 ({query_time/total_time*100:5.1f}%)")
    print(f"  数据过滤:     {filter_time:6.2f}秒 ({filter_time/total_time*100:5.1f}%)")
    print(f"  数据准备:     {insert_time:6.2f}秒 ({insert_time/total_time*100:5.1f}%)")
    print(f"  预估总耗时:   {total_time:6.2f}秒")
    print("=" * 50)
    
    # 瓶颈分析
    print("\n瓶颈分析：")
    times = {
        'PDF文本提取': extract_time,
        '文本解析': parse_time,
        '员工查询': query_time,
        '数据过滤': filter_time,
        '数据准备': insert_time
    }
    bottleneck = max(times, key=times.get)
    print(f"  ⚠️  最大瓶颈: {bottleneck} ({times[bottleneck]:.2f}秒)")
    
    if extract_time > 10:
        print("\n建议：")
        print("  - PDF文本提取过慢，可能是PDF文件过大或格式复杂")
        print("  - 考虑使用PyMuPDF (fitz) 替代pdfplumber")
        print("  - 检查PDF文件大小和页数")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("用法: python3 diagnose_pdf_performance.py <pdf文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    diagnose_pdf_performance(pdf_path)
