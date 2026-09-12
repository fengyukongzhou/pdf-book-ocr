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
   - **数字文字版**：自动扫描图题并提取矢量信息图（300 DPI 紧致锁边、严防吞字）至 `images/`，并提供带配图标记的 `parts/*.raw.txt` 供纯文本低 Token 清洗；
   - **扫描版**：自动提供纯微型 PDF 供视觉多模态转写。
- **Gate 1 验收门禁**：检查 `subagent_jobs.json` 已生成，分片任务清单条目数 > 0。

### Step 2: 分发分片并发清洗/转写
读取 `subagent_jobs.json`，根据体裁从 `references/prompts/` 读取对应原子提示词模具（数字版选 `digital.txt`，散文小说选 `prose.txt`，戏剧选 `drama.txt`，学术专著选 `academic.txt`；路由索引参见 [references/prompt_templates.md](references/prompt_templates.md)），使用 `invoke_subagent` 派发任务：
- **批次滚动派发（Rolling Batching）**：分片总数 > 4 时，**强制以 3~4 个分片为一组滚动派发**。当前批次分片全部完成并落盘后，再拉起下一批，严禁一次性全量并发冲击 API 限流（429）。
- **极简中继与静默推进（Silent Relaying）**：批次推进期间，父 Agent **严禁对每个分片进行篇目罗列、剧情概要或细节长篇汇报**（严重膨胀对话历史上下文）。批次转换时仅允许输出单行紧凑状态（如 `批次 [01~04/24] 完成，推进批次 [05~08]`）。子 Agent 之间同样执行单行状态汇报。
- **多模态全流程履约铁律（Anti-Downgrade Redline）**：扫描版必须完整执行视觉子 Agent 转写，以确保版式拓扑理解、跨页自然断句缝合与插图定位品质。严禁以节省 Token 或速度为由擅自切换为纯本地机械 OCR；若遇长篇任务，唯一合规路径为批次滚动推进。任何技术管道变更必须事先向用户明确请示并获得授权。
- **目标路径**：所有子任务必须直接落盘写入 `raw_md/{md_file}`。
- **配图规范**：无图题的插图 alt 文本保持为空 `![](images/...)`，禁止添加多余“插图”二字；仅原书印有图题时才写 `![图题](images/...)`。
- **非线性图表切图铁律**：严禁将饼图、柱状图、走势图或横向多列表格强行转写为 Markdown 表格或未渲染的 Mermaid 代码（移动端与离线 EPUB 必崩）；数字版已由脚本自动生成 300 DPI 紧凑锁边图（保留 `![图题](images/fig_XX.png)` 即可），扫描版统一使用 `<!-- FIGURE: page=... bbox=[...] -->` 标定。
- **随文注忠实保留**：正文中的括号随文注/夹注（如“（注：……”）必须原样保留在正文中，禁止转为 `[^n]` 脚注。
- **版权信息剔除**：文前与文后的版权页、出版声明、CIP 编目、公众号/二维码推广等信息直接丢弃，不保留进正文。
- **Gate 2 验收门禁**：检查 `raw_md/` 下文件数量**必须 100% 等于分片总数**，且每个文件大小 > 100 字节。未全部就绪前严禁执行组装！

### Step 3: 一键语义汇编成书
所有切片完成且门禁通过后，运行：
```bash
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --assemble "<输出工作目录>"
```
流水线自动执行三重汇编：
1. **接缝连续性审计与焊接 (`seam_auditor`)**：自动诊断相邻切片接口首尾对，执行跨切片引号闭环焊接（`MERGE` 对白）、未完结断句缝合（`MERGE`）与文本重叠剔除（`MERGE_DEDUP`），并生成 `seam_report.md`。
2. **逻辑章节聚合 (`chapter_assembler`)**：依接缝仲裁平滑拼接连续文本流，按正文真实 `## 章节标题` 动态切分章节，隔离各章脚注命名空间。
3. **出版级编译 (`epub_builder`)**：Pandoc 编译 EPUB 3，注入双向弹框注释与排版样式。
- **Gate 3 验收门禁**：确认生成 `seam_report.md`（接口仲裁表无异常阻断）、`assembled_chapters/`（按书本真实章节命名）、全书主 Markdown 笔记与 `.epub` 文件。

### Step 4: 出版级闭环验收
交付给用户前，执行快速自检：
1. 抽查 `assembled_chapters/`，确认章节名皆为书本真实章节名而非机械切片号。
2. 确认生成的成果文件存入 `_inbox/`，向用户汇报电子书与笔记已就绪。

---

## 资源索引

- **提示词路由与原子模具**：[references/prompt_templates.md](references/prompt_templates.md)（体裁分支路由与 `references/prompts/` 原子模具集）。
- **排版陷阱与防御**：[references/troubleshooting.md](references/troubleshooting.md)（脚注隔离、随文注防悬空、列表空行等踩坑指南）。
- **排版样式表**：[assets/styles_book.css](assets/styles_book.css)（EPUB 3 弹框注释、字体回退与对白样式）。
