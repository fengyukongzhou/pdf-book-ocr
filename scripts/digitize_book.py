#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
digitize_book.py
----------------
产品级 PDF 图书数字化一键主控脚本 (Product-Grade PDF Book Digitizer)

小白与产品级核心特性：
1. 【环境自检与自愈 --doctor】：一键诊断 Python、PyMuPDF、Pandoc、BeautifulSoup，并提供一键安装指引。
2. 【智能书名清洗】：自动剥离文件名中的 Z-Library、网盘等杂音标记，自动识别书名与作者。
3. 【体裁自适应识别】：自动检测图书是小说、戏剧还是学术专著，自动挂载最佳排版引擎。
4. 【智能双轨省 Token 策略】：
   - 数字文字版 PDF：本地秒级提取纯文本，交由轻量文本 Agent 完成语义重构（Token 消耗约为视觉转写的 ~10%）。
   - 扫描版 PDF：自动切分微型分片、生成并发任务队列、自动缝合断缝与隔离脚注。
5. 【成果看板生成】：生成包含封面图、字数统计、目录树与脚注匹配率的独立 HTML/Markdown 可视化看板。
"""

import os
import sys
import re
import json
import shutil
import argparse
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

# 颜色控制（支持 Windows 终端）
class Color:
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log(msg, level='info'):
    if os.name == 'nt':
        # 兼容旧控制台
        os.system('')
    prefix = {
        'info': f"{Color.CYAN}[*]{Color.END}",
        'ok': f"{Color.GREEN}[√]{Color.END}",
        'warn': f"{Color.YELLOW}[!]{Color.END}",
        'err': f"{Color.RED}[×]{Color.END}",
        'step': f"{Color.BOLD}{Color.CYAN}==>{Color.END}"
    }.get(level, '[*]')
    print(f"{prefix} {msg}")

def check_environment():
    """运行环境与依赖检查 (Doctor Mode)"""
    log("正在检查运行环境与依赖库...", 'step')
    all_ok = True

    # 1. Python 版本
    py_ver = sys.version.split()[0]
    log(f"Python 环境: {py_ver}", 'ok')

    # 2. PyMuPDF (fitz)
    try:
        import fitz
        log(f"PDF 解析引擎 (PyMuPDF): {fitz.__version__}", 'ok')
    except ImportError:
        log("缺少 PyMuPDF 库，安装命令: pip install pymupdf", 'err')
        all_ok = False

    # 3. BeautifulSoup4
    try:
        import bs4
        log(f"HTML/EPUB DOM 引擎 (BeautifulSoup4): {bs4.__version__}", 'ok')
    except ImportError:
        log("缺少 BeautifulSoup4 库，安装命令: pip install beautifulsoup4", 'err')
        all_ok = False

    # 4. Pandoc 可执行文件
    pandoc_path = shutil.which('pandoc')
    if not pandoc_path:
        for c in [r'E:\Pandoc\pandoc.exe', r'C:\Program Files\Pandoc\pandoc.exe']:
            if os.path.exists(c):
                pandoc_path = c
                break
    if pandoc_path:
        log(f"编译器 (Pandoc): {pandoc_path}", 'ok')
    else:
        log("未检测到 Pandoc", 'err')
        log("  - Windows: winget install JohnMacFarlane.Pandoc", 'warn')
        log("  - macOS:   brew install pandoc", 'warn')
        log("  - 官方下载: https://pandoc.org/installing.html", 'warn')
        all_ok = False

    if all_ok:
        log("运行环境已就绪。\n", 'ok')
    else:
        log("运行环境存在缺失，请按提示安装后重试。\n", 'warn')
    return all_ok

def clean_book_filename(filename):
    """智能清洗书名与作者"""
    base = os.path.splitext(os.path.basename(filename))[0]
    # 剔除常见的电子书网站噪音
    cleaned = re.sub(r'\(z-library[^\)]*\)', '', base, flags=re.I)
    cleaned = re.sub(r'\(1lib[^\)]*\)', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\(z-lib[^\)]*\)', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\[.*?\]', '', cleaned)
    cleaned = cleaned.strip()

    # 尝试提取书名与作者：例如 "百年孤独 (加西亚·马尔克斯)"
    m = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]$', cleaned)
    if m:
        title = m.group(1).strip()
        author = m.group(2).strip()
    else:
        title = cleaned
        author = "佚名"
    return title, author

def detect_text_layer_and_genre(doc):
    """检测 PDF 数字文字层比例与潜在体裁"""
    total_pages = len(doc)
    sample_pages = min(total_pages, 25)
    step = max(1, total_pages // sample_pages)
    
    text_count = 0
    dialogue_cues = 0
    total_chars = 0
    
    for pno in range(0, total_pages, step):
        t = doc[pno].get_text()
        total_chars += len(t)
        if len(t.strip()) > 60:
            text_count += 1
        # 检测戏剧对话特征
        if len(re.findall(r'[\u4e00-\u9fa5]{1,6}：', t)) > 3:
            dialogue_cues += 1
            
    ratio = text_count / max(1, sample_pages)
    is_digital = ratio > 0.75 and total_chars > 3000
    is_drama = dialogue_cues > (sample_pages * 0.3)
    
    return is_digital, is_drama

def run_pipeline(pdf_path, out_dir=None, chunk_size=15, title=None, author=None, force_scan=False):
    """一键流水线主入口"""
    if not os.path.exists(pdf_path):
        log(f"找不到指定的 PDF 文件: {pdf_path}", 'err')
        return

    import fitz
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    # 1. 智能推断书名与作者
    auto_title, auto_author = clean_book_filename(pdf_path)
    book_title = title or auto_title
    book_author = author or auto_author
    
    log(f"数字化任务启动: 《{book_title}》", 'step')
    log(f"作者/署名: {book_author} | 总页数: {total_pages} 页")
    
    # 2. 规划输出路径
    if out_dir is None:
        parent = os.path.dirname(os.path.abspath(pdf_path))
        out_dir = os.path.join(parent, f"{book_title}_output")
    os.makedirs(out_dir, exist_ok=True)
    
    # 3. 提取 300 DPI 超清封面
    cover_path = os.path.join(out_dir, f"{book_title}_Cover.png")
    page0 = doc[0]
    zoom = 300 / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page0.get_pixmap(matrix=mat, alpha=False)
    pix.save(cover_path)
    log(f"已提取 300 DPI 高清封面: {os.path.basename(cover_path)} ({pix.width}x{pix.height})", 'ok')
    
    # 4. 检测文本层与体裁
    is_digital, is_drama = detect_text_layer_and_genre(doc)
    log(f"体裁推断: {'戏剧/剧本' if is_drama else '散文/小说/专著'}")
    
    if force_scan:
        is_digital = False
    return plan_book(doc, pdf_path, book_title, book_author, cover_path, out_dir, chunk_size, is_digital, is_drama)

def extract_digital_page_with_images(doc, pno, images_dir, min_size=80, global_pno=None):
    """
    Extracts text and embedded images from a digital PDF page.
    Combines text blocks and get_image_info by Y-coordinate.
    Uses paragraph-aware buffering: images are flushed only after natural paragraph ends
    (terminal punctuation like 。！？！”… or .!?), never breaking sentences in half.
    """
    import fitz
    page = doc[pno]
    eff_pno = global_pno if global_pno is not None else pno
    
    # 1. Collect text blocks
    raw_text_blocks = page.get_text("blocks")
    items = []
    for tb in raw_text_blocks:
        text = tb[4].strip()
        if text:
            items.append({
                "type": "text",
                "y0": tb[1],
                "x0": tb[0],
                "content": text
            })

    # 2. Collect image blocks via get_image_info(xrefs=True)
    img_counter = 1
    try:
        img_infos = page.get_image_info(xrefs=True)
        for info in img_infos:
            bbox = info.get('bbox')
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            w = x1 - x0
            h = y1 - y0
            if w < min_size or h < min_size:
                continue
            ratio = max(w / max(1, h), h / max(1, w))
            if ratio > 15:
                continue
                
            img_fname = f"fig_p{eff_pno+1:03d}_{img_counter:02d}.png"
            img_target = os.path.join(images_dir, img_fname)
            
            # Prefer extracting raw image via xref to preserve original lossless quality
            xref = info.get('xref', 0)
            saved = False
            if xref > 0:
                try:
                    img_data = doc.extract_image(xref)
                    if img_data and "image" in img_data:
                        ext = img_data.get("ext", "png")
                        if ext != "png":
                            img_fname = f"fig_p{eff_pno+1:03d}_{img_counter:02d}.{ext}"
                            img_target = os.path.join(images_dir, img_fname)
                        with open(img_target, "wb") as f_img:
                            f_img.write(img_data["image"])
                        saved = True
                except Exception:
                    pass
            if not saved:
                try:
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(bbox), alpha=False)
                    pix.save(img_target)
                    saved = True
                except Exception:
                    pass

            if saved:
                items.append({
                    "type": "image",
                    "y0": y0,
                    "x0": x0,
                    "content": f"images/{img_fname}"
                })
                img_counter += 1
    except Exception as e:
        print(f"[-] Notice: error getting image info on page {pno+1}: {e}")

    # 3. Sort text and images by physical Y-coordinate
    items.sort(key=lambda it: (it["y0"], it["x0"]))

    # 4. Paragraph-aware buffering
    body_elements = []
    pending_images = []

    for it in items:
        if it["type"] == "image":
            pending_images.append(it["content"])
        else:
            text = it["content"]
            body_elements.append(text)
            # Flush pending images only after paragraph-ending punctuation
            if text.endswith(('。', '！', '？', '”', '…', '.', '!', '?')) and pending_images:
                for img_rel in pending_images:
                    body_elements.append(f"\n\n![]({img_rel})\n\n")
                pending_images.clear()

    # Page end fallback: flush any remaining images
    for img_rel in pending_images:
        body_elements.append(f"\n\n![]({img_rel})\n\n")

    return "\n\n".join(body_elements).strip()

def plan_book(doc, pdf_path, title, author, cover_path, out_dir, chunk_size, is_digital, is_drama):
    """
    统一图书切分与子任务规划 (Unified Slicing & Subagent Planning)
    无论是数字文字版还是扫描版，均统一采用【物理切片 -> Subagent 语义清洗/转写 -> 汇编成书】的出版级流水线。
    """
    from pdf_analyzer import analyze_pdf
    from pdf_slicer import slice_pdf
    import fitz

    log(f"启动统一切片与任务规划（{'数字文字版' if is_digital else '图像扫描版'}）...", 'step')

    # 1. 生成规划与物理切分
    plan = analyze_pdf(pdf_path, out_dir=out_dir, chunk_size=chunk_size, cover_target=cover_path)
    parts_dir = slice_pdf(os.path.join(out_dir, "slice_plan.json"), out_dir=os.path.join(out_dir, "parts"))

    images_dir = os.path.join(out_dir, "images")
    raw_md_dir = os.path.join(out_dir, "raw_md")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(raw_md_dir, exist_ok=True)

    # 2. 生成子智能体一键派发清单 (jobs.json)
    jobs = []
    vector_figs_by_pno = {}
    if is_digital:
        try:
            from vector_figure_extractor import extract_tight_vector_figures
            vector_figs = extract_tight_vector_figures(pdf_path, images_dir)
            if vector_figs:
                log(f"已自动提取 {len(vector_figs)} 个矢量信息图/图表至 images/（300 DPI 紧致锁边）", 'ok')
                for fnum, finfo in vector_figs.items():
                    vector_figs_by_pno.setdefault(finfo['pno'], []).append(finfo)
        except Exception as e:
            log(f"矢量图表自动提取提示: {e}", 'warn')

    for p in plan['parts']:
        pdf_file_path = os.path.join(parts_dir, p['pdf_file'])
        raw_txt_path = None

        if is_digital:
            raw_txt_file = p['md_file'].replace('.md', '.raw.txt')
            raw_txt_path = os.path.join(parts_dir, raw_txt_file)

            # 本地提取该切片内各页的文本与插图草稿
            slice_doc = fitz.open(pdf_file_path)
            slice_pages_text = []
            for p_idx in range(len(slice_doc)):
                global_pno = p['start_page'] + p_idx
                page_text = extract_digital_page_with_images(slice_doc, p_idx, images_dir, global_pno=global_pno)

                # 若当前页包含自动提取的紧致矢量图表，追加标准图片引用
                if global_pno in vector_figs_by_pno:
                    for vf in vector_figs_by_pno[global_pno]:
                        fig_tag = f"\n\n![{vf['title']}]({vf['image_rel_path']})\n\n"
                        if vf['image_rel_path'] not in page_text:
                            page_text += fig_tag

                slice_pages_text.append(f"<!-- === Page {p_idx+1} (Global Page {global_pno+1}) === -->\n\n" + page_text)
            slice_doc.close()

            with open(raw_txt_path, 'w', encoding='utf-8') as f_raw:
                f_raw.write("\n\n---\n\n".join(slice_pages_text) + "\n")

        job_item = {
            "part_index": p['part_index'],
            "part_name": p['part_name'],
            "pdf_path": pdf_file_path,
            "target_md": os.path.join(raw_md_dir, p['md_file']),
            "page_count": p['page_count'],
            "is_digital": is_digital,
            "is_drama": is_drama
        }
        if raw_txt_path:
            job_item["raw_text_path"] = raw_txt_path

        jobs.append(job_item)

    jobs_path = os.path.join(out_dir, "subagent_jobs.json")
    with open(jobs_path, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    log(f"已生成统一子智能体任务单: {jobs_path}", 'ok')
    log(f"共规划 {len(jobs)} 个切片任务（每切片 {chunk_size} 页）。", 'step')
    if is_digital:
        log("【数字版专属增益】：已提取 raw.txt 与插图至 parts/，供 Agent 进行免视觉浪费的出版级语义清洗！", 'ok')
    log("【下一步操作】：请指示 Agent 根据 subagent_jobs.json 派发处理 raw_md/，全部完成后执行 --assemble 汇编成书。")
    return jobs_path

# 兼容别名
plan_scanned_book = plan_book

def assemble_scanned_book(work_dir, title=None, author=None, drama=False, preview_toc=False):
    """
    汇编切片与出版级成书 (Assemble Mode)
    1. 自动定位 slice_plan.json 或扫描 raw_md 目录
    2. 执行 seam_auditor 校验接缝
    3. 执行 chapter_assembler 隔离各章节脚注命名空间 & 排版纠偏
    4. 执行 epub_builder 编译 EPUB 3 & 生成 Obsidian 主笔记
    """
    log(f"开始汇编工作目录: {work_dir}", 'step')
    if not os.path.exists(work_dir):
        log(f"指定的工作目录不存在: {work_dir}", 'err')
        return

    plan_path = os.path.join(work_dir, "slice_plan.json")
    plan = {}
    if os.path.exists(plan_path):
        try:
            with open(plan_path, 'r', encoding='utf-8') as f:
                plan = json.load(f)
        except Exception:
            pass

    book_title = title or plan.get('book_name') or os.path.basename(os.path.abspath(work_dir)).replace('_output', '').replace('_work', '')
    book_author = author or "佚名"
    
    # 查找封面
    cover_path = plan.get('cover_path')
    if not cover_path or not os.path.exists(cover_path):
        for fname in os.listdir(work_dir):
            if fname.lower().endswith(('_cover.png', '_cover.jpg', 'cover.png', 'cover.jpg')):
                cover_path = os.path.join(work_dir, fname)
                break

    # 查找切片 MD 文件
    raw_md_dir = os.path.join(work_dir, "raw_md")
    search_dir = raw_md_dir if os.path.exists(raw_md_dir) else work_dir
    
    md_files = []
    for f in os.listdir(search_dir):
        if f.endswith('.md') and not f.endswith(('_Master.md', 'seam_report.md', 'README.md')) and f != f"{book_title}.md":
            md_files.append(os.path.join(search_dir, f))
            
    # 自然排序
    def nat_sort(s):
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]
    md_files.sort(key=nat_sort)
    
    if not md_files:
        log(f"在 {search_dir} 未找到切片 Markdown 文件！请确认转写文件已存入。", 'err')
        return

    log(f"发现 {len(md_files)} 个转写切片 Markdown 文件", 'ok')

    # 1. 运行断缝核验
    from seam_auditor import audit_seams, is_line_terminated
    seam_report_path = os.path.join(work_dir, "seam_report.md")
    seam_findings = audit_seams(md_files, report_path=seam_report_path)
    log(f"接缝连续性审计完成，报告已生成: {seam_report_path}", 'ok')

    # 1.5 扫描并裁剪切片中的插图与图表 (300 DPI + 投影锁边)
    from chapter_assembler import crop_figures_for_work_dir
    cropped_count = crop_figures_for_work_dir(work_dir)
    if cropped_count > 0:
        log(f"正文插图锁边裁剪完成，共导出 {cropped_count} 张高清图片至 images/", 'ok')

    # 2. 以 ## 标题为边界切割真实逻辑章节
    from chapter_assembler import assemble_chapter
    assembled_dir = os.path.join(work_dir, "assembled_chapters")
    os.makedirs(assembled_dir, exist_ok=True)

    # 2a. 将所有切片顺序拼合为一个完整文本流，智能平滑缝合跨分片断句
    all_lines = []
    block_prefixes = ('#', '!', '<', '>', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')
    seam_actions = {f"{os.path.basename(item['prev_file'])} -> {os.path.basename(item['next_file'])}": item for item in seam_findings}
    prev_mf = None

    for mf in md_files:
        with open(mf, 'r', encoding='utf-8') as f:
            chunk_lines = f.readlines()
        if not chunk_lines:
            continue

        if all_lines and prev_mf:
            # 找到前一切片的最后一个非空行索引
            last_idx = len(all_lines) - 1
            while last_idx >= 0 and not all_lines[last_idx].strip():
                last_idx -= 1

            # 找到当前切片的第一个非空行索引
            first_idx = 0
            while first_idx < len(chunk_lines) and not chunk_lines[first_idx].strip():
                first_idx += 1

            if last_idx >= 0 and first_idx < len(chunk_lines):
                prev_line = all_lines[last_idx].rstrip('\r\n')
                next_line = chunk_lines[first_idx].lstrip()
                prev_stripped = prev_line.strip()

                # 获取接缝审计裁决
                junction_key = f"{os.path.basename(prev_mf)} -> {os.path.basename(mf)}"
                decision = seam_actions.get(junction_key)
                action = decision["action"] if decision else None

                if action is None:
                    # 保底规则：前行末尾非终结标点且双方非排版块元素
                    if (prev_stripped and not is_line_terminated(prev_stripped)
                            and not prev_stripped.startswith(block_prefixes)
                            and not next_line.startswith(block_prefixes)):
                        action = "MERGE"
                    else:
                        action = "SPLIT"

                if action == "MERGE_DEDUP" and decision and decision.get("overlap"):
                    # 消除接缝处的文本重叠
                    overlap = decision["overlap"]
                    if next_line.startswith(overlap):
                        next_line = next_line[len(overlap):].lstrip()
                    all_lines[last_idx] = prev_line + next_line
                    chunk_lines = chunk_lines[first_idx + 1:]
                elif action == "MERGE":
                    # 缝合跨页跨分片断句/未闭合对白：直接衔接同一自然段
                    all_lines[last_idx] = prev_line + next_line
                    chunk_lines = chunk_lines[first_idx + 1:]
                else:
                    # 属于独立段落，确保留一个空行分隔
                    if all_lines and all_lines[-1].strip():
                        all_lines.append('\n')
                    chunk_lines = chunk_lines[first_idx:]

        all_lines.extend(chunk_lines)
        prev_mf = mf

    # 2b. 按 ## 标题边界切割章节
    # 收集 (标题, [行列表]) 的列表
    chapters_raw = []       # list of (title_str, [lines])
    preamble_lines = []     # 第一个 ## 之前的内容（前置页）
    found_first_h2 = False
    current_title = None
    current_lines = []

    for line in all_lines:
        if line.startswith('## '):
            if not found_first_h2:
                # 遇到第一个 ## 标题，仅当之前存在实质性文本（如长篇题记/序言）才保留前置页
                found_first_h2 = True
                preamble_text = "".join(preamble_lines).strip()
                substantive_text = re.sub(r'#+.*|\s+|[-*_=~`]', '', preamble_text)
                if len(substantive_text) > 40:
                    chapters_raw.insert(0, ('前置信息', preamble_lines))
            else:
                # 保存上一章
                if current_title is not None:
                    chapters_raw.append((current_title, current_lines))
            # 开始新章节（标题文本去掉 ## 前缀及换行）
            current_title = line[3:].strip()
            current_lines = [line]
        else:
            if not found_first_h2:
                preamble_lines.append(line)
            else:
                current_lines.append(line)

    # 收尾最后一章
    if current_title is not None and current_lines:
        chapters_raw.append((current_title, current_lines))
    elif not found_first_h2 and preamble_lines:
        # 全文没有任何 ## 标题，作为单章处理
        chapters_raw.append((book_title, preamble_lines))

    # 过滤文前文后的纯版权与推广章节
    filtered_chapters = []
    copyright_keywords = ('版权信息', '版权声明', '版权页', '出版信息', '图书在版编目', '出版说明')
    for t, lines in chapters_raw:
        clean_t = t.strip()
        if any(kw in clean_t for kw in copyright_keywords):
            log(f"  [跳过版权信息章节]: {clean_t}", 'ok')
            continue
        filtered_chapters.append((t, lines))
    chapters_raw = filtered_chapters

    log(f"识别到 {len(chapters_raw)} 个有效逻辑章节（已自动过滤版权信息）", 'ok')
    toc_manifest = []
    for idx, (t, lines) in enumerate(chapters_raw, start=1):
        char_count = sum(len(l) for l in lines)
        is_short = char_count < 1500
        is_single_word = bool(re.match(r'^[A-Za-z0-9_\-–—]+$', t.strip()))
        warn_flag = " [⚠️ 疑似微小节/短章]" if (is_short and is_single_word) else ""
        log(f"  [{idx:02d}] {t[:40]} ({char_count:,} 字符){warn_flag}", 'step')
        toc_manifest.append({
            "index": idx,
            "title": t,
            "char_count": char_count,
            "warning": bool(warn_flag)
        })

    toc_manifest_path = os.path.join(work_dir, "toc_manifest.json")
    with open(toc_manifest_path, 'w', encoding='utf-8') as f_toc:
        json.dump(toc_manifest, f_toc, ensure_ascii=False, indent=2)

    if preview_toc:
        log("=" * 55, 'step')
        log(f"【章节目录树预览完毕】共 {len(chapters_raw)} 章，清单已保存至: {toc_manifest_path}", 'ok')
        log("请主 Agent 检查章节结构与篇幅体量，确认无异常后再执行完整汇编。", 'step')
        log("=" * 55, 'step')
        return None, None
    assembled_chapters = []
    for ch_counter, (ch_name, ch_lines) in enumerate(chapters_raw, start=1):
        ch_id = f"c{ch_counter:02d}"
        # 对文件名中不合法字符进行清洗
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', ch_name)[:60]
        out_chapter_md = os.path.join(assembled_dir, f"{ch_counter:02d}_{safe_name}.md")
        # 写入临时切片（assemble_chapter 会负责脚注隔离 & 排版归一化）
        tmp_src = out_chapter_md + ".tmp.md"
        with open(tmp_src, 'w', encoding='utf-8') as f:
            f.writelines(ch_lines)
        assemble_chapter(
            chapter_id=ch_id,
            title=ch_name,
            source_md_paths=[tmp_src],
            out_path=out_chapter_md,
            is_drama=drama
        )
        try:
            os.remove(tmp_src)
        except Exception:
            pass
        assembled_chapters.append(out_chapter_md)
        log(f"  [{ch_counter:02d}] {ch_name[:40]} → {os.path.basename(out_chapter_md)}", 'ok')

    log(f"成功汇编 {len(assembled_chapters)} 个逻辑章节，脚注已完成命名空间隔离！", 'ok')

    # 3. 编译 EPUB 3 & Obsidian 主笔记
    from epub_builder import build_epub_and_master
    out_epub = os.path.join(work_dir, f"{book_title}.epub")
    out_master_md = os.path.join(work_dir, f"{book_title}.md")
    
    build_epub_and_master(
        title=book_title,
        author=book_author,
        chapter_paths=assembled_chapters,
        cover_image=cover_path,
        out_epub=out_epub,
        out_master_md=out_master_md,
        resource_path=work_dir
    )
    
    log("=" * 55, 'step')
    log("【出版级数字化完成！】", 'ok')
    log(f"  EPUB 电子书: {out_epub}", 'ok')
    log(f"  Obsidian 典藏笔记: {out_master_md}", 'ok')
    log(f"  接缝审计报告: {seam_report_path}", 'ok')
    log("=" * 55, 'step')
    return out_epub, out_master_md

def main():
    parser = argparse.ArgumentParser(
        description="PDF Book Digitizer - 产品级低Token图书数字化主控工具",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("pdf", nargs="?", help="要数字化的 PDF 图书文件路径")
    parser.add_argument("--doctor", action="store_true", help="诊断系统环境与依赖完整性")
    parser.add_argument("--assemble", metavar="DIR", help="将指定工作目录下的切片 Markdown 汇编成最终 EPUB 与主笔记")
    parser.add_argument("--preview-toc", metavar="DIR", help="仅预览指定工作目录下的章节划分与字数（TOC 审计门禁），不生成最终 EPUB")
    parser.add_argument("--drama", action="store_true", help="启用戏剧/剧本专用排版格式规约")
    parser.add_argument("--title", default=None, help="自定义图书标题（默认自动清洗）")
    parser.add_argument("--author", default=None, help="自定义作者/译者署名")
    parser.add_argument("--out-dir", default=None, help="成果输出目录")
    parser.add_argument("--chunk-size", type=int, default=15, help="扫描分片每切片页数 (默认 15 页)")
    parser.add_argument("--force-scan", action="store_true", help="强制作为扫描版切分，即使存在文字层")
    parser.add_argument("--extract-figures", metavar="PDF", help="直接从数字 PDF 中提取 300 DPI 紧致矢量图表至指定目录")
    parser.add_argument("--status", metavar="DIR", help="查看指定工作目录中各分片的落盘与转写完成进度")
    
    args = parser.parse_args()
    
    if args.doctor:
        check_environment()
        return

    if args.status:
        work_dir = os.path.abspath(args.status)
        raw_md_dir = os.path.join(work_dir, "raw_md")
        plan_path = os.path.join(work_dir, "slice_plan.json")
        total = 0
        if os.path.exists(plan_path):
            with open(plan_path, 'r', encoding='utf-8') as f:
                total = len(json.load(f).get('parts', []))
        ready_files = [f for f in os.listdir(raw_md_dir) if f.endswith('.md')] if os.path.exists(raw_md_dir) else []
        print(f"[*] 切片完成进度: {len(ready_files)}/{total if total else '?'} 已落盘")
        for f in sorted(ready_files):
            size = os.path.getsize(os.path.join(raw_md_dir, f))
            print(f"  - {f}: {size:,} 字节")
        return

    if args.extract_figures:
        from vector_figure_extractor import extract_tight_vector_figures
        target_pdf = os.path.abspath(args.extract_figures)
        out_imgs = args.out_dir or os.path.join(os.path.dirname(target_pdf), "images")
        extract_tight_vector_figures(target_pdf, out_imgs)
        return

    if args.preview_toc:
        assemble_scanned_book(
            work_dir=args.preview_toc,
            title=args.title,
            author=args.author,
            drama=args.drama,
            preview_toc=True
        )
        return

    if args.assemble:
        assemble_scanned_book(
            work_dir=args.assemble,
            title=args.title,
            author=args.author,
            drama=args.drama,
            preview_toc=False
        )
        return

    if not args.pdf:
        parser.print_help()
        print("\n常用命令示例：")
        print("  1. 环境诊断:     python digitize_book.py --doctor")
        print('  2. 一键数字化:   python digitize_book.py "百年孤独.pdf"')
        print('  3. 汇编切片成书: python digitize_book.py --assemble "百年孤独_work" --drama')
        print('  4. 提取矢量图表: python digitize_book.py --extract-figures "研报.pdf"')
        return

    run_pipeline(
        pdf_path=args.pdf,
        out_dir=args.out_dir,
        chunk_size=args.chunk_size,
        title=args.title,
        author=args.author,
        force_scan=args.force_scan
    )

if __name__ == "__main__":
    main()
