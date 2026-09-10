---
name: pdf-book-ocr
description: Convert PDF books (scanned or digital) to EPUB 3 and Obsidian Markdown. Triggers on "PDF转电子书", "做成EPUB", "OCR整本书", "扫描件数字化", "PDF书籍排版". Unified pipeline with chunking, subagent transcription, semantic H2 assembly, and popup footnotes.
---

# PDF Book OCR (出版级图书数字化工具)

将长篇 PDF（100~500+页，扫描或数字版）转换为出版级 EPUB 3 与 Obsidian 典藏笔记。采用**单轨统一流水线**（Unified Single Pipeline），自动规避长文档上下文超限与跨页断裂。

---

## 统一处理架构

```
[原始 PDF 图书 (扫描版或数字文字版)]
       │
       ▼ (Step 1: 预处理与切片规划)
 digitize_book.py ──> 提取封面、切片为 10~15 页微型 PDF、生成 subagent_jobs.json
       │              (数字版附带 raw.txt 纯文本草稿，扫描版提供微型 PDF)
       ▼
[Step 2: Subagent 并发转写/清洗] ──> 逐分片落盘至 raw_md/*.md
       │
       ▼ (Step 3: 语义汇编与编译成书)
 digitize_book.py --assemble
       ├── seam_auditor: 校验首尾断缝与段落连续性
       ├── chapter_assembler: 按内文 ## 真实标题聚合章节、隔离脚注命名空间
       └── epub_builder: Pandoc 编译 EPUB 3 + 注入双向弹框注释
       │
       ▼ (Step 4: 出厂验收)
《书名》.epub + 《书名》.md + images/ (存入 _inbox/)
```

---

## 执行标准与作业规约 (Agent SOP)

当用户提出 PDF 转电子书或 OCR 请求时，严格按以下步骤与**验收门禁（Completion Gates）**执行：

### Step 1: 环境检查与切片规划
1. 运行 `python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --doctor`，确认依赖正常。
2. 运行 `python .agent/skills/pdf-book-ocr/scripts/digitize_book.py "<PDF路径>"`。
   - 脚本自动提取封面、配图并生成 10~15 页物理切片，建立 `subagent_jobs.json`。
   - **数字文字版**：自动提供 `parts/*.raw.txt` 供纯文本低 Token 清洗；
   - **扫描版**：自动提供纯微型 PDF 供视觉多模态转写。
- **Gate 1 验收门禁**：检查 `subagent_jobs.json` 已生成，分片任务清单条目数 > 0。

### Step 2: 分发分片并发清洗/转写
读取 `subagent_jobs.json`，根据 `references/prompt_templates.md`（数字版选模板 0，扫描版选模板 1~3）使用 `invoke_subagent` 并发派发任务：
- **目标路径**：所有子任务必须直接落盘写入 `raw_md/{md_file}`。
- **配图规范**：无图题的插图 alt 文本保持为空 `![](images/...)`，禁止添加多余“插图”二字；仅原书印有图题时才写 `![图题](images/...)`。
- **随文注忠实保留**：正文中的括号随文注/夹注（如“（注：……”）必须原样保留在正文中，禁止转为 `[^n]` 脚注。
- **版权信息剔除**：文前与文后的版权页、出版声明、CIP 编目、公众号/二维码推广等信息直接丢弃，不保留进正文。
- **Gate 2 验收门禁**：检查 `raw_md/` 下文件数量**必须 100% 等于分片总数**，且每个文件大小 > 100 字节。未全部就绪前严禁执行组装！

### Step 3: 一键语义汇编成书
所有切片完成且门禁通过后，运行：
```bash
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --assemble "<输出工作目录>"
```
脚本将按文本内真实 `## 章节标题` 自动聚合逻辑章节、隔离脚注命名空间、执行断缝审计并打包 EPUB 3。
- **Gate 3 验收门禁**：确认生成 `assembled_chapters/`（按书本真实章节命名）、`seam_report.md`、主 Markdown 笔记以及 `.epub` 文件。

### Step 4: 出版级闭环验收
交付给用户前，执行快速自检：
1. 抽查 `assembled_chapters/`，确认章节名皆为书本真实章节名而非机械切片号。
2. 确认生成的成果文件存入 `_inbox/`，向用户汇报电子书与笔记已就绪。

---

## 资源索引

- **提示词模板**：[references/prompt_templates.md](references/prompt_templates.md)（子智能体低 Token 派发模板）。
- **排版陷阱与防御**：[references/troubleshooting.md](references/troubleshooting.md)（脚注隔离、随文注防悬空、列表空行等踩坑指南）。
- **排版样式表**：[assets/styles_book.css](assets/styles_book.css)（EPUB 3 弹框注释、字体回退与对白样式）。
