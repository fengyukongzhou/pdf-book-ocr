#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_slicer.py
-------------
Slices a large PDF into lightweight, context-friendly chunk PDFs
based on a slice_plan.json or uniform page range.
"""

import os
import sys
import json
import argparse
import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding='utf-8')

def slice_pdf(plan_path_or_pdf, out_dir=None, chunk_size=15):
    if plan_path_or_pdf.endswith('.json'):
        with open(plan_path_or_pdf, 'r', encoding='utf-8') as f:
            plan = json.load(f)
        pdf_path = plan['pdf_path']
        parts = plan['parts']
        if out_dir is None:
            out_dir = os.path.join(os.path.dirname(plan_path_or_pdf), 'parts')
    else:
        pdf_path = plan_path_or_pdf
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        book_name = os.path.splitext(os.path.basename(pdf_path))[0]
        if out_dir is None:
            out_dir = os.path.join(os.path.dirname(pdf_path), f"{book_name}_parts")
        parts = []
        part_idx = 1
        for start_p in range(0, total_pages, chunk_size):
            end_p = min(total_pages - 1, start_p + chunk_size - 1)
            pname = f"part_{part_idx:02d}_p{start_p+1:03d}-{end_p+1:03d}"
            parts.append({
                "part_index": part_idx,
                "part_name": pname,
                "start_page": start_p,
                "end_page": end_p,
                "pdf_file": f"{pname}.pdf"
            })
            part_idx += 1

    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"[*] Slicing {os.path.basename(pdf_path)} ({total_pages} pages) into {len(parts)} parts in: {out_dir}")

    for p in parts:
        start_p = p['start_page']
        end_p = p['end_page']
        part_pdf = os.path.join(out_dir, p['pdf_file'])
        
        part_doc = fitz.open()
        part_doc.insert_pdf(doc, from_page=start_p, to_page=end_p)
        part_doc.save(part_pdf)
        part_doc.close()
        print(f"  [OK] Slice #{p['part_index']:02d}: pages {start_p+1}..{end_p+1} ({end_p-start_p+1}p) -> {p['pdf_file']}")

    doc.close()
    print(f"[OK] Slicing complete! Total slices: {len(parts)}")
    return out_dir

def main():
    parser = argparse.ArgumentParser(description="Slice a PDF into lightweight parts for subagent OCR")
    parser.add_argument("plan_or_pdf", help="Path to slice_plan.json or PDF file")
    parser.add_argument("--out-dir", default=None, help="Output directory for slice PDFs")
    parser.add_argument("--chunk-size", type=int, default=15, help="Pages per slice if PDF is passed directly")
    args = parser.parse_args()

    slice_pdf(args.plan_or_pdf, args.out_dir, args.chunk_size)

if __name__ == "__main__":
    main()
