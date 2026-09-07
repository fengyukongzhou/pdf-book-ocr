# PDF Book OCR

<p align="center">
  <strong>基于分片与模型协作的 PDF 图书转 EPUB / Markdown 工具</strong><br>
  <em>A pipeline for converting PDF books to EPUB and Markdown</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Engine-PyMuPDF%20%7C%20Pandoc-blue?style=flat-square" alt="Engine">
  <img src="https://img.shields.io/badge/Output-EPUB%203%20%7C%20Obsidian-purple?style=flat-square" alt="Output">
</p>

---

## 背景与解决的问题

将扫描版 PDF、古籍影印本或学术专著转换为可重排的电子书（EPUB/Markdown）时，常见以下问题：

1. **上下文长度与成本**：书籍页数较多时，单次输入模型易超出上下文窗口限制；调用外部 OCR 接口也存在额度约束。
2. **分片拼接的文本连续性**：按页切片分发识别时，页面分界处可能出现重叠文本或遗漏字符。
3. **同名脚注的键名冲突**：若各章节均使用 `[^1]`、`[^2]` 等同名标识，经 Pandoc 全局编译时后章内容会覆盖前章。
4. **注释交互形式**：未配置特定属性的注释链接在部分阅读器中会跳转至文末，中断阅读。
5. **特定文体结构**：戏剧对话、舞台说明和列表项若缺少格式标记，排版容易退化为普通连续文本。

**PDF Book OCR** 通过预处理探测、分片识别、接缝字符比对、脚注命名空间重映射及后处理脚本处理上述问题。

> **技术边界说明**：PDF 为基于二维坐标的页面描述格式，底层不包含段落、标题、层级等文档结构信息。带文字层的 PDF 直接提取文本后，常见换行断裂、页眉页脚混入正文以及脚注脱落现象；部分扫描件内嵌的 OCR 文本可能存在错字。因此，本项目对数字版 PDF 采用提取文本后重构段落与注释的流程，对图像扫描件采用分片识别流程。

---

## 处理流程

```
[原始 PDF 图书 (100~500+页)]
       │
       ▼ (Layer 0: 预处理)
 digitize_book.py ──> 提取封面图像、检测文字层质量、生成切片任务列表
       │
   ┌───┴───────────────────────────────────────────┐
   │ [包含可用文字层的 PDF]                         │ [图像扫描版 / 文字层不完整 PDF]
   ▼                                               ▼ (Layer 1: 切片)
提取文本流                                   pdf_slicer.py ──> 切分为 10~15 页子文件
   │                                               │
   ▼ (Layer 1.5: 文本重构)                         ▼ (Layer 2: 分片识别)
text_restructurer ──> 规整段落、               ocr_specialist ──> 各子任务处理对应子文件
 清理页眉页脚、匹配脚注、转换格式             写入 raw_md/*.md
   │                                               │
   │                                               ▼ (Layer 3: 接缝比对与合流)
   │                                         seam_auditor.py ────> 比对首尾公共子串
   │                                         chapter_assembler.py ─> 为脚注键添加章节前缀
   │                                               │
   └───────────────────────┬───────────────────────┘
                           ▼ (Layer 4: 样式配置与编译)
  epub_builder.py ───> 调用 Pandoc 生成 EPUB 3，注入 CSS 并配置注释属性
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
《书名》.epub (流式电子书)                   《书名》.md (Markdown 笔记)
```

---

## 功能特性

- **双轨处理流程**：根据文字层采样结果选择路径。对于包含完整文字层的文档，提取文本流后规整格式；对于图像扫描件，切片后交由视觉模型识别。
- **分片并发识别**：按 10~15 页将文档切分为子文件，由独立子任务并行识别，控制单次任务的输入规模。
- **接缝校验 (`seam_auditor`)**：比对相邻分片首尾文本的最长公共子串，排查重叠或缺字情况。
- **章节脚注重编号 (`chapter_assembler`)**：为各分片内的脚注键添加章节前缀（如 `[^c01_1]`），避免跨章节标识冲突，并规范标点与列表排版。
- **样式配置 (`styles_book.css`)**：
  - **章节标题**：宋体居中排版，配置顶部间距；
  - **楷体替代斜体**：斜体与强调标签（`*...*`、`<em>`、`<i>`、舞台说明）使用楷体正体排版，不使用倾斜样式；
  - **作者署名**：楷体排版，下方配置细分隔线；
  - **引用块**：首行不缩进，保持边距对齐；
  - **注释属性**：添加 `epub:type="footnote"` 属性，使兼容阅读器能够调用浮层展示注释内容；
  - **剧本样式**：为对话段落（`<p class="dialogue">`）及舞台说明（`<p class="stage-direction">`）提供专用样式规则。

---

## 使用方法

### 1. 安装依赖

需要 Python 3.10+ 及 [Pandoc](https://pandoc.org/)：

```bash
pip install -r requirements.txt
```

#### 安装 Pandoc：
- **Windows**: `winget install JohnMacFarlane.Pandoc`
- **macOS**: `brew install pandoc`
- **Linux (Ubuntu/Debian)**: `sudo apt-get install pandoc`

---

### 2. 依赖检查 (`--doctor`)

运行检查命令，验证相关依赖是否安装：

```bash
python scripts/digitize_book.py --doctor
```

> **输出示例**：
> ```
> ==> 正在检查运行环境与依赖库...
> [√] Python 环境: 3.12.4
> [√] PDF 解析引擎 (PyMuPDF): 1.25.4
> [√] HTML/EPUB DOM 引擎 (BeautifulSoup4): 4.13.3
> [√] 编译器 (Pandoc): E:\Pandoc\pandoc.EXE
> [√] 运行环境已就绪。
> ```

---

### 3. 执行流程

#### 命令行使用方式 (CLI)

```bash
# 步骤 1：处理 PDF 文件（提取封面、检测文字层或规划切片）
python scripts/digitize_book.py "book.pdf"

# 步骤 2：识别完成后汇编并生成 EPUB
python scripts/digitize_book.py --assemble "book_output"
```
*包含戏剧对话时，可添加 `--drama` 参数应用对话样式规则。*

#### 配合 AI 智能体使用

在支持对应 Skill 的 AI 智能体中提供 PDF 文件路径，智能体将按照 `SKILL.md` 中定义的步骤调用脚本、分发分片识别并完成汇编。

---

## 目录结构

```
pdf-book-ocr/
├── README.md                 # 项目文档
├── SKILL.md                  # Agent 行为规约与执行流程
├── LICENSE                   # MIT 许可证
├── requirements.txt          # Python 依赖清单
├── .gitignore                # Git 忽略规则
├── assets/
│   └── styles_book.css       # 排版样式表（字体、间距、注释样式及暗色模式）
├── references/
│   ├── prompt_templates.md   # 视觉识别提示词模板（散文、戏剧、学术）
│   └── troubleshooting.md    # 格式问题说明（Pandoc 脚注冲突、列表缩进等）
└── scripts/
    ├── digitize_book.py      # 主控脚本（包含环境检查、输入检测与流程分发）
    ├── pdf_analyzer.py       # 封面提取、文字层采样与分片规划
    ├── pdf_slicer.py         # PDF 切片脚本
    ├── seam_auditor.py       # 相邻分片文本接缝比对脚本
    ├── chapter_assembler.py  # 章节合并与脚注前缀重映射脚本
    └── epub_builder.py       # EPUB 3 编译与后处理脚本
```

---

## 参数说明 (`digitize_book.py`)

| 参数 | 说明 | 默认值 |
| :--- | :--- | :---: |
| `pdf` | 待处理的 PDF 文件路径 | 必需 |
| `--doctor` | 检查环境依赖项是否完整 | `False` |
| `--assemble DIR` | 将指定目录下的 Markdown 分片汇编为 EPUB 与整合笔记 | `None` |
| `--drama` | 启用剧本对话样式（角色名加粗、说明文字使用楷体） | `False` |
| `--title TITLE` | 指定图书标题（默认根据文件名推断） | 自动推断 |
| `--author AUTHOR` | 指定作者名称 | 自动推断 |
| `--chunk-size N` | 扫描版每个分片的页数 | `15` |
| `--force-scan` | 忽略现有文字层，按图像切片处理 | `False` |

---

## 许可证

本项目采用 [MIT License](LICENSE) 授权。
