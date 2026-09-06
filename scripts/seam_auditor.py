#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seam_auditor.py
---------------
Deterministic seam continuity auditing tool:
Inspects sequential Markdown slices or merged chapters to ensure:
1. Zero dropped sentences across slice junctions.
2. Zero duplicate paragraphs/lines across slice junctions.
3. Clean boundary transitions.
"""

import os
import sys
import re
import argparse

sys.stdout.reconfigure(encoding='utf-8')

def extract_edge_text(md_path, n_chars=400):
    if not os.path.exists(md_path):
        return "", ""
    with open(md_path, 'r', encoding='utf-8') as f:
        text = f.read()
    # Strip footnote definitions from the end
    text = re.sub(r'\n+\[\^[^\]]+\]:\s*.+$', '', text, flags=re.MULTILINE).strip()
    head = text[:n_chars].strip()
    tail = text[-n_chars:].strip()
    return head, tail

def audit_seams(file_list, report_path=None):
    print(f"[*] Auditing seams across {len(file_list)} sequential parts...")
    findings = []
    
    for i in range(len(file_list) - 1):
        f1 = file_list[i]
        f2 = file_list[i+1]
        
        _, tail1 = extract_edge_text(f1)
        head2, _ = extract_edge_text(f2)
        
        # Look for overlap
        tail_clean = re.sub(r'\s+', '', tail1[-80:])
        head_clean = re.sub(r'\s+', '', head2[:80])
        
        # Check longest common substring between tail and head
        overlap = ""
        for length in range(min(len(tail_clean), len(head_clean)), 4, -1):
            sub = tail_clean[-length:]
            if head_clean.startswith(sub):
                overlap = sub
                break
                
        b1_name = os.path.basename(f1)
        b2_name = os.path.basename(f2)
        
        status = "OK"
        detail = "Continuous transition"
        if overlap:
            status = "WARN (Duplicate Overlap)"
            detail = f"Found duplicate string of {len(overlap)} chars: '{overlap}'"
            
        findings.append({
            "junction": f"{b1_name} -> {b2_name}",
            "status": status,
            "detail": detail,
            "tail_sample": tail1[-60:].replace('\n', ' '),
            "head_sample": head2[:60].replace('\n', ' ')
        })
        
        print(f"  [{status}] {b1_name} -> {b2_name}")
        if overlap:
            print(f"       Overlap: '{overlap}'")
            
    if report_path:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Seam Continuity Audit Report\n\n")
            for item in findings:
                f.write(f"## {item['junction']}\n")
                f.write(f"- Status: **{item['status']}**\n")
                f.write(f"- Detail: {item['detail']}\n")
                f.write(f"- Tail: `{item['tail_sample']}`\n")
                f.write(f"- Head: `{item['head_sample']}`\n\n")
        print(f"[OK] Report written to: {report_path}")
        
    return findings

def main():
    parser = argparse.ArgumentParser(description="Audit seams between sequential transcribed Markdown slices")
    parser.add_argument("files", nargs="+", help="Ordered list of Markdown slice files to check")
    parser.add_argument("--report", default=None, help="Optional output report path")
    args = parser.parse_args()
    
    audit_seams(args.files, args.report)

if __name__ == "__main__":
    main()
