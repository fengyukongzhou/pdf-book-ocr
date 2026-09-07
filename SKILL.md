---
name: pdf-book-ocr
description: PDF 图书数字化工具，将扫描版或包含文字层的 PDF 转换为 EPUB 3 与 Markdown。包含页面切片、并发子任务识别、断缝文本核验、章节脚注重映射与排版处理。适用于长篇 PDF 转电子书、分片 OCR 与双向弹框脚注生成。
---

# PDF Book OCR (图书 OCR 与排版工具)

本技能提供 PDF 图书数字化处理流程，通过预处理（封面提取、文字层检测、切片规划）、并发子任务识别与脚本清洗汇编，处理长文档上下文超限与跨页断点问题。

> **技术边界说明**：PDF 底层为页面描述格式，缺少段落、标题与脚注等文档结构语义。带文字层的文档提取后需要重构段落与排版；扫描件则走分片视觉识别流程。

> 📖 **开源仓库与详细使用指南**：请查阅 [README.md](README.md)。

---

## 处理流程与架构

```
[原始 PDF 图书 (100~500+页)]
       │
       ▼ (Layer 0: 预处理)
 digitize_book.py ──> 提取封面图像、检测文字层质量、生成切片任务单 (subagent_jobs.json)
       │
   ┌───┴───────────────────────────────────────┐
   │ [数字文字版 PDF]                          │ [扫描版 PDF]
   ▼                                           ▼ (Layer 1: 切片)
本地提取纯文本                               pdf_slicer ──> 10~15 页微型 PDF
   │                                           │
   ▼ (Layer 1.5: 文本 Agent 语义重构)          ▼ (Layer 2: 分片视觉识别)
text_restructurer ──> 段落缝合、           ocr_specialist ──> 各子任务处理对应分片
 脚注绑定、页眉剥离、格式转换                 写入 raw_md/*.md
   │                                           │
   │                                           ▼ (Layer 3: 接缝核验与合流)
   │                                     seam_auditor ──> 比对分片首尾文本
   │                                     chapter_assembler ──> 为脚注添加章节前缀 ([^c01_1])
   │                                           │
   └───────────────────┬───────────────────────┘
                       ▼ (Layer 4: 编译与后处理)
  epub_builder ──> Pandoc 编译 + CSS 样式 + 注释弹框属性
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
《书名》.epub (微信读书/Apple Books)    《书名》.md (Obsidian 笔记)
```

---

## 使用模式与执行标准

### 模式 A：对话执行流程 (Agent SOP)

当用户在对话中发送类似“帮我把这本 PDF 转成电子书”、“做成 EPUB”、“OCR 这本书”时，可按以下流程处理：

1. **环境检查**：
   运行 `python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --doctor`，确认依赖正常。
2. **探测与预处理**：
   运行 `python .agent/skills/pdf-book-ocr/scripts/digitize_book.py "<PDF文件路径>"`。
   - 若检测为**可用数字版**（文字层覆盖率 > 75% 且抽检无乱码）：脚本提取纯文本至 `raw_md/`，后续由文本 Agent 进行段落规整、页眉剥离与脚注匹配。
   - 若检测为**图像扫描件或文字层不完整**：读取输出目录下的 `subagent_jobs.json`，进入分片识别流程。
3. **分发分片识别**：
   参考 `references/prompt_templates.md` 的提示词模板，根据 `subagent_jobs.json` 使用 `invoke_subagent` 派发任务进行分片识别。
   - 要求子任务将 Markdown 写入磁盘 `raw_md/*.md`，避免长文本返回主会话。
4. **汇编成书**：
   所有切片处理完成后，运行：
   ```bash
   python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --assemble "<输出工作目录>" [--drama]
   ```
5. **输出结果**：
   将生成的 `.epub` 和 `.md` 存入 `_inbox/`，并向用户提供包含字数、章节及接缝状态的说明。

---

### 模式 B：命令行使用方式 (CLI)

在终端中按顺序执行：

```bash
# 1. 检查依赖
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --doctor

# 2. 开始处理 PDF
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py "book.pdf"

# 3. 汇编切片生成电子书
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --assemble "book_output"
```

---

### 模式 C：模块化脚本说明

| 模块脚本 | 核心功能 |
| :--- | :--- |
| `pdf_analyzer.py` | 提取封面图像、检测文字层质量、解析书签生成 `slice_plan.json` |
| `pdf_slicer.py` | 将原始 PDF 切分为 10~15 页的微型子文件存入 `parts/` |
| `seam_auditor.py` | 比对相邻分片首尾文本，排查断句或重叠内容 |
| `chapter_assembler.py` | 合并切片，为局部脚注添加章节前缀 (`[^c01_1]`)，规范列表排版 |
| `epub_builder.py` | 调用 Pandoc 生成 EPUB 3，注入 CSS 样式并配置注释属性 |

---

## 资源索引

- **项目文档**：[README.md](README.md)（环境配置与用法说明）。
- **提示词模板**：[references/prompt_templates.md](references/prompt_templates.md)（包含散文小说、戏剧剧本、学术专著三套提示词）。
- **格式问题说明**：[references/troubleshooting.md](references/troubleshooting.md)（解析跨章节脚注冲突、列表空行等格式排查）。
- **排版样式表**：[assets/styles_book.css](assets/styles_book.css)（字体回退、间距、暗色模式与注释展示样式）。


