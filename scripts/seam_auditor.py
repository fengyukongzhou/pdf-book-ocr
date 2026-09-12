#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seam_auditor.py
---------------
出版级切片接缝连续性审计与语义断句分析引擎：
1. 自动提取相邻切片接口处的尾句与首句上下文对 (Junction Pairs)；
2. 智能诊断接缝语义特征：
   - 跨分片未闭合引号 (如前切片有 “，后切片有 ”)；
   - 句末标点缺失与未完结断句；
   - 跨分片破折号与省略号；
   - 重复文本重叠 (Duplicate Overlap)。
3. 产出结构化接缝决策与人类/Agent 双向可读的 seam_report.md。
"""

import os
import sys
import re
import json
import argparse

sys.stdout.reconfigure(encoding='utf-8')

# 终结标点符号集
TERMINAL_PUNCT = '。！？！”…；:：）】》」』'
BLOCK_PREFIXES = ('#', '!', '<', '>', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')

def extract_edge_lines(md_path, max_lines=5):
    """提取 Markdown 切片的首尾非空、非注释正文行"""
    if not os.path.exists(md_path):
        return [], []

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 过滤文末的脚注定义 [^...]: ...
    body_lines = []
    for line in lines:
        if re.match(r'^\s*\[\^[^\]]+\]:\s*.+$', line):
            continue
        body_lines.append(line)

    # 过滤出非空有效行
    non_empty = [l.strip() for l in body_lines if l.strip() and l.strip() != '---']

    head_lines = non_empty[:max_lines] if non_empty else []
    tail_lines = non_empty[-max_lines:] if non_empty else []
    return head_lines, tail_lines

def analyze_junction(prev_file, next_file):
    """深度分析相邻切片交界处的语义连续性并给出仲裁决策"""
    b1_name = os.path.basename(prev_file)
    b2_name = os.path.basename(next_file)
    junction_id = f"{os.path.splitext(b1_name)[0]} -> {os.path.splitext(b2_name)[0]}"

    _, tail1_lines = extract_edge_lines(prev_file, max_lines=3)
    head2_lines, _ = extract_edge_lines(next_file, max_lines=3)

    tail_line = tail1_lines[-1] if tail1_lines else ""
    head_line = head2_lines[0] if head2_lines else ""

    # 1. 检查文本重叠 (Duplicate Overlap)
    tail_clean = re.sub(r'\s+', '', tail_line[-80:])
    head_clean = re.sub(r'\s+', '', head_line[:80])
    overlap = ""
    for length in range(min(len(tail_clean), len(head_clean)), 4, -1):
        sub = tail_clean[-length:]
        if head_clean.startswith(sub):
            overlap = sub
            break

    # 2. 语义特征探测
    has_unclosed_quote = False
    quote_open_count = tail_line.count('“') - tail_line.count('”')
    if quote_open_count > 0 and (head_line.startswith('”') or '”' in head_line[:20]):
        has_unclosed_quote = True

    is_prev_block = tail_line.startswith(BLOCK_PREFIXES)
    is_next_block = head_line.startswith(BLOCK_PREFIXES)
    has_terminal_punct = bool(tail_line and tail_line[-1] in TERMINAL_PUNCT)

    # 3. 智能决策仲裁
    action = "SPLIT"
    reason = "自然段落正常终结 (独立段落)"
    status = "OK"

    if overlap:
        status = "WARN_OVERLAP"
        reason = f"检测到 {len(overlap)} 字重复文本重叠: '{overlap}'"
        action = "MERGE_DEDUP"
    elif has_unclosed_quote:
        action = "MERGE"
        reason = "跨切片对白引号未闭合 (自动闭环焊接)"
    elif not has_terminal_punct and not is_prev_block and not is_next_block:
        action = "MERGE"
        reason = "末尾缺少终结标点 (跨切片断句缝合)"
    elif tail_line.endswith(('，', '、', '—', '–', '…')) and not is_next_block:
        action = "MERGE"
        reason = "连词/停顿符号未完结 (跨切片延续句)"

    return {
        "junction": junction_id,
        "prev_file": prev_file,
        "next_file": next_file,
        "b1_name": b1_name,
        "b2_name": b2_name,
        "status": status,
        "action": action,
        "reason": reason,
        "tail_sample": tail_line[-80:] if tail_line else "",
        "head_sample": head_line[:80] if head_line else "",
        "overlap": overlap
    }

def audit_seams(file_list, report_path=None):
    """批量审计所有顺序切片的接缝连续性并生成出版级报告"""
    print(f"[*] 启动切片接缝连续性与语义断句审计 (共 {len(file_list)-1} 处接口)...")
    findings = []

    for i in range(len(file_list) - 1):
        info = analyze_junction(file_list[i], file_list[i+1])
        findings.append(info)

        # 终端实时状态打印
        tag = "[MERGE]" if info["action"].startswith("MERGE") else "[SPLIT]"
        print(f"  {tag} [{i+1:02d}] {info['junction']}")
        print(f"       原因: {info['reason']}")
        if info["overlap"]:
            print(f"       重叠: '{info['overlap']}'")

    # 生成 Markdown 审计报告
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 切片接缝连续性审计与语义断句报告 (Seam Continuity Report)\n\n")
            f.write(f"- 审计时间: 当前\n")
            f.write(f"- 切片总数: {len(file_list)} 个\n")
            f.write(f"- 接口总数: {len(findings)} 处\n\n")
            f.write("---\n\n")

            f.write("## 接口决策明细表\n\n")
            f.write("| 序号 | 接口位置 | 决策动作 | 判定依据 | 尾部样句 | 头部样句 |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
            for idx, item in enumerate(findings, start=1):
                clean_tail = item["tail_sample"].replace('|', '\\|').replace('\n', ' ')
                clean_head = item["head_sample"].replace('|', '\\|').replace('\n', ' ')
                f.write(f"| {idx:02d} | `{item['junction']}` | **{item['action']}** | {item['reason']} | `{clean_tail}` | `{clean_head}` |\n")

            f.write("\n---\n\n")
            f.write("## 详细上下文诊断\n\n")
            for idx, item in enumerate(findings, start=1):
                f.write(f"### [{idx:02d}] {item['junction']}\n\n")
                f.write(f"- **处理动作**: `{item['action']}`\n")
                f.write(f"- **语义理由**: {item['reason']}\n")
                f.write(f"- **前一切片末尾**: `{item['tail_sample']}`\n")
                f.write(f"- **后一切片开头**: `{item['head_sample']}`\n\n")

        print(f"[OK] 接缝连续性与语义断句报告已生成: {report_path}")

    return findings

def main():
    parser = argparse.ArgumentParser(description="Audit seams between sequential transcribed Markdown slices")
    parser.add_argument("files", nargs="+", help="Ordered list of Markdown slice files to check")
    parser.add_argument("--report", default=None, help="Optional output report path")
    args = parser.parse_args()

    audit_seams(args.files, args.report)

if __name__ == "__main__":
    main()
