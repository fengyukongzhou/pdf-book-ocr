#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vector_figure_extractor.py
--------------------------
出版级数字 PDF 矢量信息图/图表紧凑裁切提取引擎 (Tight Vector Figure Extractor)

核心解决问题：
1. 解决数字 PDF 中矢量图表（如 Excel/Matplotlib 渲染的饼图、柱状图、走势图）无法被 extract_image 提取的问题。
2. 解决大模型将图表逆向为脆弱 Markdown 宽表或离线无法渲染的裸 Mermaid 代码问题。
3. 【紧凑锁边算法 (Tight Bounding)】：
   - 顶部 y0：从图题下方紧贴开始；
   - 底部 y1：严格锚定在图表附带的数据说明（“注：”、“数据来源”、“数据截至”）之后，
     且【绝对阻断】在下一个正文自然段落或标题的起始坐标 y0 之前；
   - 彻底避免因回退到底部而将正文文字吞入图片（导致 EPUB 出现图片与正文重叠文字的 Bug）。
"""

import os
import sys
import re
import argparse
import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding='utf-8')

def extract_tight_vector_figures(pdf_path, out_images_dir, dpi=300, prefix="fig_"):
    """
    Scans a digital PDF for vector figure captions, calculates tight boundaries,
    and exports lossless 300 DPI rasterized images to out_images_dir.
    
    Returns:
        dict: {
            fig_number: {
                "pno": page_index_0_based,
                "page": page_number_1_based,
                "title": title_str,
                "image_filename": filename,
                "image_rel_path": "images/" + filename,
                "bbox": [ymin, xmin, ymax, xmax]
            }
        }
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    os.makedirs(out_images_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    # 1. 扫描所有页面的图题
    # 匹配模式：如 "图 1：2022年各市场占比" 或 "图1: ..."
    fig_title_pattern = re.compile(r'^(?:图|表)\s*(\d+)[:：]\s*(.*)', re.MULTILINE)
    
    figures = []
    for pno, page in enumerate(doc):
        blocks = page.get_text('blocks')
        for b in blocks:
            text = b[4].strip()
            for line in text.splitlines():
                line_str = line.strip()
                m = fig_title_pattern.match(line_str)
                if m:
                    fnum = int(m.group(1))
                    ftitle = m.group(2).strip()
                    figures.append({
                        'fnum': fnum,
                        'title': ftitle,
                        'pno': pno,
                        'title_box': b,
                        'raw_title_line': line_str
                    })
                    break

    # 按图号自然排序
    figures.sort(key=lambda x: (x['fnum'], x['pno']))

    # 2. 逐图计算严格紧凑边界
    results = {}
    note_pattern = re.compile(r'^(?:数据[截至来源]|注[:：]|来源[:：]|资料来源[:：]|数据来源及说明)', re.I)
    section_pattern = re.compile(r'^[（(][一二三四五六七八九十\d]+[)）]|^第[一二三四五六七八九十\d]+[章节部分]')

    for fig in figures:
        fnum = fig['fnum']
        pno = fig['pno']
        page = doc[pno]
        page_rect = page.rect
        blocks = page.get_text('blocks')
        tb = fig['title_box']

        # 找出当前图题下方的所有文本块
        below_blocks = [b for b in blocks if b[1] > tb[3] and b[3] < (page_rect.height - 20)]

        # 检查同一页内是否还有后续图表
        next_figs_on_page = [f for f in figures if f['pno'] == pno and f['title_box'][1] > tb[3]]
        next_fig_top = next_figs_on_page[0]['title_box'][1] if next_figs_on_page else None

        # 过滤出当前图表范围内的数据说明块
        note_blocks = []
        for b in below_blocks:
            if next_fig_top and b[3] >= next_fig_top:
                continue
            b_text = b[4].strip()
            if note_pattern.search(b_text):
                note_blocks.append(b)

        # 过滤出当前图表下方的正文文本块（用于阻断边界，防止吞并正文）
        body_blocks = []
        for b in below_blocks:
            if next_fig_top and b[3] >= next_fig_top:
                continue
            b_text = b[4].strip()
            if note_pattern.search(b_text) or fig_title_pattern.search(b_text):
                continue
            # 正文特征：长度超过 25 字符，或者是明显的小节标题（如“（一）海外资产...”）
            if len(b_text) > 25 or section_pattern.search(b_text):
                body_blocks.append(b)

        note_max_y = max([b[3] for b in note_blocks]) if note_blocks else None
        first_body_y = min([b[1] for b in body_blocks]) if body_blocks else None

        # 严格计算顶部 y0 与底部 y1
        # y0: 紧随图题底部开始 (+2 pt)
        y0 = max(0.0, tb[3] + 2.0)

        # y1 紧凑阻断决断：
        # 优先级 1: 如果下方有下一个图题，绝对不能超过它
        # 优先级 2: 如果下方有正文自然段落/小节标题，必须在正文顶部之前截断（留 6 pt 安全边距）
        # 优先级 3: 如果有数据说明/注，包含说明文字 (+10 pt)
        # 优先级 4: 保底截断在版心底边或页高 85% 处
        if next_fig_top:
            candidate_y1 = next_fig_top - 6.0
            if first_body_y:
                candidate_y1 = min(candidate_y1, first_body_y - 6.0)
            y1 = candidate_y1
        elif first_body_y:
            y1 = first_body_y - 6.0
        elif note_max_y:
            y1 = min(note_max_y + 12.0, page_rect.height - 35.0)
        else:
            # 单图且无明确下方正文时，使用绘图对象包围盒或安全底边
            y1 = min(page_rect.height * 0.88, page_rect.height - 40.0)

        # 水平边距：默认使用版心左右边距
        x0 = max(0.0, page_rect.width * 0.08)
        x1 = min(page_rect.width, page_rect.width * 0.92)

        # 确保高度有效 (至少 40 pt)
        if y1 <= y0 + 40:
            y1 = min(page_rect.height - 30.0, y0 + 150.0)

        clip_rect = fitz.Rect(x0, y0, x1, y1)
        pix = page.get_pixmap(matrix=mat, clip=clip_rect, alpha=False)

        img_name = f"{prefix}{fnum:02d}.png"
        img_target = os.path.join(out_images_dir, img_name)
        pix.save(img_target)

        results[fnum] = {
            "fnum": fnum,
            "pno": pno,
            "page": pno + 1,
            "title": fig['title'],
            "image_filename": img_name,
            "image_rel_path": f"images/{img_name}",
            "bbox_pt": [y0, x0, y1, x1],
            "bbox_norm": [
                int((y0 / page_rect.height) * 1000),
                int((x0 / page_rect.width) * 1000),
                int((y1 / page_rect.height) * 1000),
                int((x1 / page_rect.width) * 1000)
            ],
            "width": pix.width,
            "height": pix.height
        }

    doc.close()
    return results

def main():
    parser = argparse.ArgumentParser(description="Extract vector figures from digital PDF with tight bounding")
    parser.add_argument("pdf_path", help="Path to input digital PDF")
    parser.add_argument("--out", default=None, help="Output directory for extracted images (default: <pdf_name>_output/images)")
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI (default: 300)")
    parser.add_argument("--prefix", default="fig_", help="Image filename prefix (default: fig_)")
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf_path)
    if args.out:
        out_dir = os.path.abspath(args.out)
    else:
        book_name = os.path.splitext(os.path.basename(pdf_path))[0]
        out_dir = os.path.join(os.path.dirname(pdf_path), f"{book_name}_output", "images")

    print(f"[*] 开始提取矢量图表: {pdf_path}")
    print(f"[*] 输出目录: {out_dir}")
    figures = extract_tight_vector_figures(pdf_path, out_dir, dpi=args.dpi, prefix=args.prefix)
    print(f"[√] 成功提取 {len(figures)} 个紧致矢量图表！")
    for fnum, info in sorted(figures.items()):
        print(f"  - 图 {fnum:02d} (P{info['page']}): {info['image_filename']} ({info['width']}x{info['height']}) - {info['title']}")

if __name__ == "__main__":
    main()
