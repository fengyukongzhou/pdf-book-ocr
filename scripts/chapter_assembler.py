#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter_assembler.py
--------------------
Assembles slice Markdown files into clean, publishing-grade chapter files:
1. Merges sequential sub-part slices into full chapters.
2. Isolates footnotes with chapter namespace prefixes ([^c01_1]...) to avoid EPUB collisions.
3. Automatically fixes common Markdown formatting issues:
   - Injects missing blank lines before list blocks (prevents list collapse).
   - Normalizes dialogue blocks (prevents dialogue cramming & indent defects).
   - Normalizes stage directions and metadata.
   - Strips code fencing and trailing soft-break spaces.
"""

import os
import sys
import re
import json
import argparse

sys.stdout.reconfigure(encoding='utf-8')

def normalize_text_layout(text, is_drama=False):
    """Clean and normalize markdown layout for publishing."""
    # Strip accidental markdown code blocks
    text = re.sub(r'^```markdown\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```$', '', text.strip(), flags=re.MULTILINE)
    
    # 1. Fix unspaced lists: ensure blank line before list if preceded by text
    # e.g., 'Text\n- Item' -> 'Text\n\n- Item'
    text = re.sub(r'([^\n])\n([-*]\s+[^\n]+)', r'\1\n\n\2', text)
    # Ensure blank line after list block ends
    text = re.sub(r'(\n[-*]\s+[^\n]+)\n+([^-*\n\s])', r'\1\n\n\2', text)
    
    if is_drama:
        # Drama specific normalization
        text = text.replace(r'\*其余剧中只提及名字的人物', '*其余剧中只提及名字的人物')
        text = re.sub(r'(\*\*时代\*\*：[^\n]+)\n+(\*\*地点\*\*：[^\n]+)', r'\1  \n\2', text)
        text = re.sub(r'(\*\*地点\*\*：[^\n]+)\n+(\*\*登场人物\*\*：)', r'\1\n\n\2', text)
        text = re.sub(r'(\*\*登场人物\*\*：)\n+([-*]\s+)', r'\1\n\n\2', text)
        
        lines = text.splitlines()
        new_lines = []
        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith('>') or re.match(r'^\s*\[\^[^\]]+\]:', line) or re.match(r'^\s*[-*]\s+', line):
                new_lines.append(line)
                continue
            if re.match(r'^\s*\*\*(时代|地点|登场人物)\*\*：', line):
                new_lines.append(line)
                if '登场人物' in line:
                    new_lines.append('')
                continue
            if re.match(r'^\s*\*\*[^*]+\*\*：', line):
                clean_line = re.sub(r'\s+$', '', line)
                new_lines.append(clean_line)
                new_lines.append('')
                continue
            if re.match(r'^\s*\*[^*]+\*\s*$', trimmed):
                clean_line = re.sub(r'\s+$', '', trimmed)
                new_lines.append(clean_line)
                new_lines.append('')
                continue
            new_lines.append(line)
        text = '\n'.join(new_lines)
    else:
        # Prose: eliminate trailing double spaces that cause accidental <br /> inside paragraphs
        lines = text.splitlines()
        new_lines = []
        for line in lines:
            if line.strip().startswith('>'):
                new_lines.append(line)  # keep poetry / song lines inside blockquotes
            else:
                new_lines.append(re.sub(r'  +$', '', line))
        text = '\n'.join(new_lines)

    # Punctuation normalization: convert ASCII punctuation between Chinese characters to full-width
    text = re.sub(r'([\u4e00-\u9fa5]),([\u4e00-\u9fa5\s])', r'\1，\2', text)
    text = re.sub(r'([\u4e00-\u9fa5]);([\u4e00-\u9fa5\s])', r'\1；\2', text)
    text = re.sub(r'([\u4e00-\u9fa5]):([\u4e00-\u9fa5])', r'\1：\2', text)
    text = re.sub(r'([\u4e00-\u9fa5])\(([\d\u4e00-\u9fa5]+)\)', r'\1（\2）', text)

    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text

def assemble_chapter(chapter_id, title, source_md_paths, out_path, is_drama=False):
    """Merge source markdown files and remap footnotes with chapter namespace."""
    combined_body = []
    definitions = {}

    for src in source_md_paths:
        if not os.path.exists(src):
            print(f"[-] Warning: missing source slice: {src}")
            continue
        with open(src, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        part_lines = []
        for line in lines:
            m_def = re.match(r'^\s*\[\^([^\]]+)\]:\s*(.+)$', line)
            if m_def:
                k = m_def.group(1).strip()
                v = m_def.group(2).strip()
                definitions[k] = v
            elif line.strip() == '---':
                continue
            else:
                part_lines.append(line)
        combined_body.append("".join(part_lines).strip())

    full_text = "\n\n".join(combined_body)
    
    # Ensure H1 title
    if not full_text.startswith('# '):
        full_text = f"# {title}\n\n" + full_text

    # Remap footnotes in order of appearance
    ref_keys = []
    for m in re.finditer(r'\[\^([^\]]+)\]', full_text):
        k = m.group(1).strip()
        if k not in ref_keys:
            ref_keys.append(k)

    def_keys = list(definitions.keys())
    id_map = {}
    for idx, old_k in enumerate(ref_keys, start=1):
        new_k = f"{chapter_id}_{idx}"
        id_map[old_k] = new_k
        if old_k not in definitions and idx <= len(def_keys):
            definitions[old_k] = definitions[def_keys[idx-1]]

    def ref_replacer(match):
        old_k = match.group(1).strip()
        new_k = id_map.get(old_k, old_k)
        return f"[^{new_k}]"

    full_text = re.sub(r'\[\^([^\]]+)\]', ref_replacer, full_text)
    
    # Layout normalization
    full_text = normalize_text_layout(full_text, is_drama=is_drama)

    # Append mapped footnote definitions
    if id_map:
        full_text += "\n\n---\n\n"
        for old_k, new_k in sorted(id_map.items(), key=lambda x: int(x[1].split('_')[1])):
            content = definitions.get(old_k, "（注释文本缺失）")
            full_text += f"[^{new_k}]: {content}\n"

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(full_text + '\n')

    print(f"[OK] Chapter '{title}' -> {out_path} ({len(full_text)} chars, {len(id_map)} footnotes)")
    return out_path

def main():
    parser = argparse.ArgumentParser(description="Assemble markdown slices into full normalized chapters")
    parser.add_argument("--id", required=True, help="Chapter ID prefix (e.g. c01)")
    parser.add_argument("--title", required=True, help="Chapter title (e.g. 'Chapter 1')")
    parser.add_argument("--sources", nargs="+", required=True, help="List of slice markdown files in order")
    parser.add_argument("--out", required=True, help="Output markdown path")
    parser.add_argument("--drama", action="store_true", help="Apply drama script normalization")
    args = parser.parse_args()

    assemble_chapter(args.id, args.title, args.sources, args.out, is_drama=args.drama)

if __name__ == "__main__":
    main()
