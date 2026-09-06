#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_analyzer.py
---------------
Zero-token preflight inspection for PDF books:
1. Detects whether PDF has an embedded digital text layer (saves 100% vision tokens if digital).
2. Extracts high-resolution cover image from page 0/1.
3. Parses embedded PDF table of contents / bookmarks.
4. Generates an optimal slicing plan (slice_plan.json).
"""

import os
import sys
import json
import argparse
import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding='utf-8')

def analyze_pdf(pdf_path, out_dir=None, chunk_size=15, cover_target=None):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    book_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(pdf_path), f"{book_name}_work")
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"[*] Analyzing: {book_name} ({total_pages} pages)")
    
    # 1. Check text layer ratio across a sample of pages
    sample_size = min(total_pages, 20)
    step = max(1, total_pages // sample_size)
    text_pages = 0
    sampled = 0
    for pno in range(0, total_pages, step):
        page = doc[pno]
        txt = page.get_text().strip()
        if len(txt) > 50:
            text_pages += 1
        sampled += 1
        
    text_ratio = text_pages / max(1, sampled)
    is_digital = text_ratio > 0.7
    print(f"[*] Text layer sample ratio: {text_ratio:.1%} -> {'DIGITAL (Text-layer detected)' if is_digital else 'SCANNED (Image-based)'}")
    
    # 2. Extract cover image from page 0
    if cover_target is None:
        cover_target = os.path.join(out_dir, f"{book_name}_Cover.png")
        
    page0 = doc[0]
    # Render at 300 DPI for high quality cover
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page0.get_pixmap(matrix=mat, alpha=False)
    pix.save(cover_target)
    print(f"[OK] Cover extracted: {cover_target} ({pix.width}x{pix.height})")
    
    # 3. Extract TOC/Bookmarks if available
    toc = doc.get_toc()
    print(f"[*] Embedded bookmarks/TOC entries found: {len(toc)}")
    
    # 4. Generate Slicing Plan
    parts = []
    part_idx = 1
    
    for start_p in range(0, total_pages, chunk_size):
        end_p = min(total_pages - 1, start_p + chunk_size - 1)
        part_name = f"part_{part_idx:02d}_p{start_p+1:03d}-{end_p+1:03d}"
        parts.append({
            "part_index": part_idx,
            "part_name": part_name,
            "start_page": start_p,       # 0-indexed
            "end_page": end_p,           # 0-indexed, inclusive
            "page_count": end_p - start_p + 1,
            "pdf_file": f"{part_name}.pdf",
            "md_file": f"{part_name}.md"
        })
        part_idx += 1
        
    plan = {
        "book_name": book_name,
        "pdf_path": os.path.abspath(pdf_path),
        "total_pages": total_pages,
        "is_digital": is_digital,
        "cover_path": os.path.abspath(cover_target),
        "chunk_size": chunk_size,
        "total_parts": len(parts),
        "parts": parts,
        "toc": toc
    }
    
    plan_file = os.path.join(out_dir, "slice_plan.json")
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        
    print(f"[OK] Slicing plan generated: {plan_file} ({len(parts)} parts)")
    return plan

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF and generate low-token digitizing plan")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--chunk-size", type=int, default=15, help="Pages per slice chunk (default: 15)")
    parser.add_argument("--out-dir", default=None, help="Output working directory")
    args = parser.parse_args()
    
    analyze_pdf(args.pdf_path, args.out_dir, args.chunk_size)

if __name__ == "__main__":
    main()
