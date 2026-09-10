# PDF Book OCR

PDF 图书转 EPUB 3 与 Markdown 工具。

---

## 功能说明

将 PDF 文件（扫描图像或含文字层文档）转换为流式 EPUB 3 电子书与 Markdown 文件。

功能包括：
- **页面切片**：将长篇 PDF 切分为指定页数（默认 15 页）的子文件。
- **图像抽取**：提取封面图像，按全局页码抽取页面内嵌插图。
- **统一分片处理**：
  - 数字文字版：提取文本草稿供清洗排版，降低 token 消耗。
  - 图像扫描版：提供微型 PDF 供视觉模型逐页转写。
- **接缝比对**：通过公共子串算法比对相邻分片的首尾文本，检查漏字与重叠。
- **语义分章**：依据正文二级标题（`##`）切分并重组章节，按真实目录建立章节文件。
- **脚注隔离**：为各章节脚注添加命名空间前缀，防止 Pandoc 编译时跨章节覆盖，并注入 EPUB 3 弹框注释属性。
- **版式规约**：
  - 插图：无图题插图标记为 `![](images/...)`，不添加多余字样；有图题插图保留图题。
  - 注释：正文随文括号注保留在正文段落；版心底部编号注转换为标准脚注。
  - 版权：文前与文后的出版声明、版权页与推广信息直接剔除。

---

## 处理流程

```
[原始 PDF 文件]
       │
       ▼ (Step 1: 预处理与切片)
 digitize_book.py
   ├── 提取封面与插图（按全局页码命名）
   ├── 切分为 10~15 页子文件
   └── 生成任务清单 subagent_jobs.json
       │
       ▼ (Step 2: 分片转写与清洗)
 AI Agent / 子任务
   ├── 数字文字版：基于 parts/*.raw.txt 清洗排版
   └── 图像扫描版：基于 parts/*.pdf 识别文本
   └── 结果落盘至 raw_md/*.md
       │
       ▼ (Step 3: 汇编与编译)
 digitize_book.py --assemble
   ├── seam_auditor.py: 比对切片首尾文本接缝
   ├── chapter_assembler.py: 依 ## 标题聚合章节，隔离脚注编号
   └── epub_builder.py: 调用 Pandoc 编译 EPUB 3，注入注释弹框
       │
       ▼ (Step 4: 成果输出)
《书名》.epub 与 《书名》.md
```

---

## 依赖与安装

- Python 3.10+
- [Pandoc](https://pandoc.org/)

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Pandoc

- **Windows**: `winget install JohnMacFarlane.Pandoc`
- **macOS**: `brew install pandoc`
- **Linux**: `sudo apt-get install pandoc`

### 3. 环境检测

运行依赖检测命令：

```bash
python scripts/digitize_book.py --doctor
```

---

## 使用方法

### 步骤 1：处理 PDF 并规划切片

```bash
python scripts/digitize_book.py "book.pdf"
```

脚本提取封面与插图，在输出目录下生成物理切片与 `subagent_jobs.json` 任务单。

### 步骤 2：转写与清洗分片

调用模型或人工处理各分片，将生成的 Markdown 存入 `raw_md/` 目录。

### 步骤 3：汇编成书

```bash
python scripts/digitize_book.py --assemble "book_output"
```

脚本执行接缝比对、按 `##` 标题聚合章节、隔离脚注命名空间，并生成 EPUB 与 Markdown 文件。

---

## 命令行参数 (`digitize_book.py`)

| 参数 | 说明 | 默认值 |
| :--- | :--- | :---: |
| `pdf` | PDF 文件路径 | 必需 |
| `--doctor` | 检查环境依赖 | `False` |
| `--assemble DIR` | 汇编指定目录下的分片 Markdown | `None` |
| `--drama` | 启用剧本对白样式规则 | `False` |
| `--title TITLE` | 指定图书标题（默认由文件名推断） | 自动推断 |
| `--author AUTHOR` | 指定作者名称 | 自动推断 |
| `--out-dir DIR` | 指定输出目录 | 自动推断 |
| `--chunk-size N` | 单个分片的页数 | `15` |
| `--force-scan` | 忽略文字层，按纯图像切片处理 | `False` |

---

## 目录结构

```
pdf-book-ocr/
├── README.md                 # 说明文档
├── SKILL.md                  # Agent 行为指南与执行标准
├── requirements.txt          # Python 依赖清单
├── assets/
│   └── styles_book.css       # EPUB 排版样式表
├── references/
│   ├── prompt_templates.md   # 模型转写提示词模板
│   └── troubleshooting.md    # 格式问题说明与解决方案
└── scripts/
    ├── digitize_book.py      # 主控入口脚本
    ├── pdf_analyzer.py       # 封面提取与分片规划脚本
    ├── pdf_slicer.py         # PDF 切片脚本
    ├── seam_auditor.py       # 文本接缝比对脚本
    ├── chapter_assembler.py  # 章节聚合与脚注重映射脚本
    └── epub_builder.py       # EPUB 编译脚本
```

---

## 许可证

本项目采用 [MIT License](LICENSE) 授权。
