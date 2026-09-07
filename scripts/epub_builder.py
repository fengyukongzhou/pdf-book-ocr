#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
epub_builder.py
---------------
Automated EPUB 3 and Obsidian Master Markdown builder:
1. Compiles Markdown chapters into EPUB 3 using Pandoc.
2. Injects classical paper-like CSS styles (styles_book.css).
3. Enhances XHTML:
   - Injects EPUB 3 popup footnote attributes and classes.
   - Tags dialogue and stage-direction classes.
4. Generates an Obsidian Master Note with complete YAML Frontmatter.
"""

import os
import sys
import re
import shutil
import zipfile
import subprocess
import argparse

sys.stdout.reconfigure(encoding='utf-8')

def find_pandoc():
    p = shutil.which('pandoc')
    if p: return p
    candidates = [
        r'E:\Pandoc\pandoc.exe',
        r'C:\Program Files\Pandoc\pandoc.exe',
        r'C:\Users\%s\AppData\Local\Pandoc\pandoc.exe' % os.environ.get('USERNAME', '')
    ]
    for c in candidates:
        if os.path.exists(c): return c
    raise FileNotFoundError("Pandoc executable not found! Please install Pandoc or add to PATH.")

def build_epub_and_master(
    title,
    author,
    chapter_paths,
    cover_image,
    out_epub,
    out_master_md=None,
    translator=None,
    publisher=None,
    css_path=None,
    front_matter_md=None
):
    pandoc_exe = find_pandoc()
    print(f"[*] Found Pandoc: {pandoc_exe}")
    
    if css_path is None:
        skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_path = os.path.join(skill_root, 'assets', 'styles_book.css')
        
    if not os.path.exists(css_path):
        raise FileNotFoundError(f"CSS file not found: {css_path}")

    # 1. Build Master Obsidian Markdown note
    if out_master_md:
        print(f"[*] Building Master Obsidian Markdown: {out_master_md}")
        header = f"""---
title: {title}
author: "{author}"
{f'translator: "{translator}"' if translator else ''}
date: {subprocess.check_output('date /t', shell=True, text=True).strip() if os.name == 'nt' else ''}
tags:
  - 来源/AIChat
  - 工具/Antigravity
  - 资源/电子书
{f'cover: "[[{os.path.basename(cover_image)}]]"' if cover_image else ''}
---

{f'![[{os.path.basename(cover_image)}|400]]' if cover_image else ''}

"""
        with open(out_master_md, 'w', encoding='utf-8') as f_out:
            f_out.write(header)
            if front_matter_md and os.path.exists(front_matter_md):
                with open(front_matter_md, 'r', encoding='utf-8') as f_fm:
                    f_out.write(f_fm.read() + "\n\n---\n\n")
            for cp in chapter_paths:
                with open(cp, 'r', encoding='utf-8') as f_c:
                    f_out.write(f_c.read() + "\n\n---\n\n")
        print(f"[OK] Master note saved: {out_master_md} ({os.path.getsize(out_master_md)} bytes)")

    # 2. Compile EPUB with Pandoc
    raw_epub = out_epub + '.tmp.epub'
    cmd = [
        pandoc_exe,
        '-s',
        '-o', raw_epub,
        '--from=markdown+smart+footnotes',
        '--to=epub3',
        '--metadata', f'title={title}',
        '--metadata', f'author={author}',
        '--metadata', 'language=zh-CN',
        '--toc',
        '--toc-depth=1',
        '--split-level=1'
    ]
    if translator:
        cmd.extend(['--metadata', f'translator={translator}'])
    if publisher:
        cmd.extend(['--metadata', f'publisher={publisher}'])
    if cover_image and os.path.exists(cover_image):
        cmd.extend([f'--epub-cover-image={cover_image}'])
    if css_path and os.path.exists(css_path):
        cmd.extend([f'--css={css_path}'])

    cmd.extend(chapter_paths)
    
    print(f"[*] Invoking Pandoc to compile EPUB 3 ({len(chapter_paths)} chapters)...")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if res.returncode != 0:
        print("Pandoc Error:", res.stderr)
        raise RuntimeError("Pandoc EPUB compilation failed!")

    print(f"[OK] Pandoc compiled initial EPUB ({os.path.getsize(raw_epub)} bytes)")

    # 3. Post-process EPUB archive
    print("[*] Post-processing EPUB files for popup footnotes & dialogue styling...")
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    files_data = {}
    with zipfile.ZipFile(raw_epub, 'r') as zin:
        for name in zin.namelist():
            files_data[name] = zin.read(name)

    # Inject updated CSS
    for name in list(files_data.keys()):
        if name.endswith('.css'):
            files_data[name] = css_content.encode('utf-8')

    # Process XHTML chapters
    def tag_p(m):
        content = m.group(1)
        if any(k in content for k in ['时代', '地点', '登场人物']):
            return f'<p class="play-meta">{content}'
        return f'<p class="dialogue">{content}'

    for name in list(files_data.keys()):
        if name.endswith(('.xhtml', '.html')) and not name.endswith('nav.xhtml'):
            text = files_data[name].decode('utf-8', errors='ignore')
            
            # Tag chapter author/subtitle right after <h1>
            def tag_author(m):
                h1_html = m.group(1)
                p_html = m.group(2)
                clean_p = re.sub(r'<[^>]+>', '', p_html).strip()
                if 0 < len(clean_p) <= 20 and not any(k in clean_p for k in ['。', '，', '、', '！', '？', '：', '；', '“', '”', '《']):
                    return f'{h1_html}\n<p class="chapter-author">{p_html}</p>'
                return f'{h1_html}\n<p>{p_html}</p>'

            text = re.sub(r'(<h1[^>]*>.*?</h1>)\s*<p>(.*?)</p>', tag_author, text, count=1)
            
            # If no chapter-author was tagged in this file, mark h1 as no-author
            if 'class="chapter-author"' not in text:
                text = re.sub(r'<h1(?!\s+class=)', r'<h1 class="no-author"', text, count=1)

            # Tag dialogue paragraphs
            text = re.sub(r'<p>(<strong>[^*<]+</strong>[：:])', tag_p, text)
            # Split metadata lines (时代/地点) joined by <br /> so each line receives full paragraph indent
            text = re.sub(r'<br\s*/?>\s*(<strong>(?:地点|时代|登场人物)</strong>[：:])', r'</p>\n<p class="play-meta">\1', text)
            # Tag stage direction paragraphs (single-line emphasis paragraphs)
            text = re.sub(r'<p>\s*(<em>.*?</em>)\s*</p>', r'<p class="stage-direction">\1</p>', text)
            
            # Ensure popover class on <aside epub:type="footnote">
            text = re.sub(r'<aside\s+([^>]*epub:type="footnote"[^>]*)>', r'<aside \1 class="footnote-popup">', text)
            # Ensure footnote-ref has noteref class
            text = re.sub(r'<a\s+([^>]*epub:type="noteref"[^>]*)>', r'<a \1 class="noteref">', text)
            
            files_data[name] = text.encode('utf-8')
        elif name.endswith('nav.xhtml'):
            nav_text = files_data[name].decode('utf-8', errors='ignore')
            # Ensure clean TOC text without residual footnote numbers
            nav_text = re.sub(r'<a\s+([^>]*)>([^<]*)<a[^>]*class="footnote-ref"[^>]*>.*?</a>(.*?)</a>', r'<a \1>\2\3</a>', nav_text)
            files_data[name] = nav_text.encode('utf-8')

    # Save final EPUB
    os.makedirs(os.path.dirname(os.path.abspath(out_epub)), exist_ok=True)
    with zipfile.ZipFile(out_epub, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        if 'mimetype' in files_data:
            zout.writestr('mimetype', files_data['mimetype'], compress_type=zipfile.ZIP_STORED)
            del files_data['mimetype']
        else:
            zout.writestr('mimetype', b'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            
        for fname, data in files_data.items():
            zout.writestr(fname, data)

    if os.path.exists(raw_epub):
        os.remove(raw_epub)

    print(f"[OK] FINAL EPUB GENERATED: {out_epub} ({os.path.getsize(out_epub)} bytes)")
    return out_epub

def main():
    parser = argparse.ArgumentParser(description="Build EPUB 3 and Master Markdown from assembled chapters")
    parser.add_argument("--title", required=True, help="Book Title")
    parser.add_argument("--author", required=True, help="Book Author")
    parser.add_argument("--chapters", nargs="+", required=True, help="Ordered list of chapter Markdown files")
    parser.add_argument("--cover", default=None, help="Cover image path")
    parser.add_argument("--out-epub", required=True, help="Output EPUB path")
    parser.add_argument("--out-master-md", default=None, help="Output Master Obsidian Markdown path")
    parser.add_argument("--translator", default=None, help="Translator name")
    parser.add_argument("--publisher", default=None, help="Publisher name")
    parser.add_argument("--css", default=None, help="Custom CSS file path")
    parser.add_argument("--front-matter", default=None, help="Front matter markdown file")
    args = parser.parse_args()

    build_epub_and_master(
        title=args.title,
        author=args.author,
        chapter_paths=args.chapters,
        cover_image=args.cover,
        out_epub=args.out_epub,
        out_master_md=args.out_master_md,
        translator=args.translator,
        publisher=args.publisher,
        css_path=args.css,
        front_matter_md=args.front_matter
    )

if __name__ == "__main__":
    main()
