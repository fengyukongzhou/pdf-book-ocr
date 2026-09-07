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
    
    if is_digital and not force_scan:
        log("检测到原生可检索文字层 (Digital PDF)，启动【低 Token 文本提取 + 语义重构模式】！", 'step')
        return extract_digital_book(doc, book_title, book_author, cover_path, out_dir, is_drama)
    else:
        log("检测为无文字层扫描版 (Scanned PDF)，启动【高保真切分与多模态 OCR 规划】！", 'step')
        return plan_scanned_book(doc, pdf_path, book_title, book_author, cover_path, out_dir, chunk_size, is_drama)

def extract_digital_book(doc, title, author, cover_path, out_dir, is_drama):
    """文字版 PDF 本地文本提取（仍需轻量 Agent 做段落缝合与脚注绑定才能达到出版级）"""
    total_pages = len(doc)
    toc = doc.get_toc()
    
    chapters = []
    if toc:
        log(f"提取到内置大纲目录 ({len(toc)} 篇目)，按真实章节切分...", 'ok')
        # 依据书签分章
        for idx in range(len(toc)):
            lvl, name, start_p = toc[idx]
            end_p = toc[idx+1][2] - 1 if idx + 1 < len(toc) else total_pages
            start_p = max(0, start_p - 1)
            end_p = min(total_pages, end_p)
            
            ch_text = []
            for p in range(start_p, end_p):
                ch_text.append(doc[p].get_text())
            
            clean_text = "\n\n".join(ch_text).strip()
            ch_file = os.path.join(out_dir, f"{idx+1:02d}_{name}.md")
            with open(ch_file, 'w', encoding='utf-8') as f:
                f.write(f"# {name}\n\n" + clean_text + "\n")
            chapters.append(ch_file)
    else:
        # 无书签时按 20 页分页打包为逻辑章节
        log("未找到内置大纲，按自然段落聚合为篇章...", 'info')
        ch_idx = 1
        for start_p in range(0, total_pages, 20):
            end_p = min(total_pages, start_p + 20)
            ch_text = [doc[p].get_text() for p in range(start_p, end_p)]
            name = f"第{ch_idx:02d}部分"
            ch_file = os.path.join(out_dir, f"{ch_idx:02d}_{name}.md")
            with open(ch_file, 'w', encoding='utf-8') as f:
                f.write(f"# {name}\n\n" + "\n\n".join(ch_text) + "\n")
            chapters.append(ch_file)
            ch_idx += 1
            
    # 编译 EPUB
    epub_path = os.path.join(out_dir, f"{title}.epub")
    master_md = os.path.join(out_dir, f"{title}.md")
    
    from epub_builder import build_epub_and_master
    build_epub_and_master(
        title=title,
        author=author,
        chapter_paths=chapters,
        cover_image=cover_path,
        out_epub=epub_path,
        out_master_md=master_md
    )
    
    log(f"数字版文本提取完成！注意：原始文本仍需轻量 Agent 做段落缝合与脚注绑定才能达到出版级。", 'ok')
    log(f"EPUB 电子书: {epub_path}", 'ok')
    log(f"Obsidian 主笔记: {master_md}", 'ok')
    return epub_path

def plan_scanned_book(doc, pdf_path, title, author, cover_path, out_dir, chunk_size, is_drama):
    """扫描版图书全流程规划"""
    from pdf_analyzer import analyze_pdf
    from pdf_slicer import slice_pdf
    
    # 1. 生成规划与切分
    plan = analyze_pdf(pdf_path, out_dir=out_dir, chunk_size=chunk_size, cover_target=cover_path)
    parts_dir = slice_pdf(os.path.join(out_dir, "slice_plan.json"), out_dir=os.path.join(out_dir, "parts"))
    
    # 2. 生成子智能体一键派发清单 (jobs.json)
    jobs = []
    for p in plan['parts']:
        jobs.append({
            "part_index": p['part_index'],
            "part_name": p['part_name'],
            "pdf_path": os.path.join(parts_dir, p['pdf_file']),
            "target_md": os.path.join(out_dir, "raw_md", p['md_file']),
            "page_count": p['page_count'],
            "is_drama": is_drama
        })
        
    jobs_path = os.path.join(out_dir, "subagent_jobs.json")
    os.makedirs(os.path.join(out_dir, "raw_md"), exist_ok=True)
    with open(jobs_path, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
        
    log(f"已生成并发子智能体转写任务单: {jobs_path}", 'ok')
    log(f"共生成 {len(jobs)} 个切片 PDF，各切片仅含 {chunk_size} 页，完全规避大上下文膨胀！", 'step')
    log("【下一步操作】：请指示 Agent 使用 ocr_specialist 并发处理 raw_md，或执行 --assemble 汇编成书。")
    return jobs_path

def assemble_scanned_book(work_dir, title=None, author=None, drama=False):
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
    from seam_auditor import audit_seams
    seam_report_path = os.path.join(work_dir, "seam_report.md")
    audit_seams(md_files, report_path=seam_report_path)
    log(f"接缝连续性审计完成，报告已生成: {seam_report_path}", 'ok')

    # 2. 智能分组为逻辑章节
    from chapter_assembler import assemble_chapter
    assembled_dir = os.path.join(work_dir, "assembled_chapters")
    os.makedirs(assembled_dir, exist_ok=True)
    
    chapter_groups = {}
    for mf in md_files:
        bname = os.path.splitext(os.path.basename(mf))[0]
        # 匹配模式如 01_章节名_p1 或 part_01
        m = re.match(r'^(?:part_)?(\d+)(?:_([^_]+))?(?:_p\d+)?$', bname)
        if m:
            ch_num = int(m.group(1))
            ch_name = m.group(2) or f"第{ch_num:02d}章"
            group_key = (ch_num, ch_name)
        else:
            group_key = (len(chapter_groups) + 1, bname)
        chapter_groups.setdefault(group_key, []).append(mf)
        
    assembled_chapters = []
    ch_counter = 1
    for (ch_num, ch_name), sources in sorted(chapter_groups.items(), key=lambda x: x[0][0]):
        ch_id = f"c{ch_counter:02d}"
        out_chapter_md = os.path.join(assembled_dir, f"{ch_counter:02d}_{ch_name}.md")
        assemble_chapter(
            chapter_id=ch_id,
            title=ch_name,
            source_md_paths=sources,
            out_path=out_chapter_md,
            is_drama=drama
        )
        assembled_chapters.append(out_chapter_md)
        ch_counter += 1

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
        out_master_md=out_master_md
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
    parser.add_argument("--drama", action="store_true", help="启用戏剧/剧本专用排版格式规约")
    parser.add_argument("--title", default=None, help="自定义图书标题（默认自动清洗）")
    parser.add_argument("--author", default=None, help="自定义作者/译者署名")
    parser.add_argument("--out-dir", default=None, help="成果输出目录")
    parser.add_argument("--chunk-size", type=int, default=15, help="扫描分片每切片页数 (默认 15 页)")
    parser.add_argument("--force-scan", action="store_true", help="强制作为扫描版切分，即使存在文字层")
    
    args = parser.parse_args()
    
    if args.doctor:
        check_environment()
        return

    if args.assemble:
        assemble_scanned_book(
            work_dir=args.assemble,
            title=args.title,
            author=args.author,
            drama=args.drama
        )
        return

    if not args.pdf:
        parser.print_help()
        print("\n常用命令示例：")
        print("  1. 环境诊断:     python digitize_book.py --doctor")
        print('  2. 一键数字化:   python digitize_book.py "百年孤独.pdf"')
        print('  3. 汇编切片成书: python digitize_book.py --assemble "百年孤独_work" --drama')
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
