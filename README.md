# 📚 PDF Book OCR

<p align="center">
  <strong>低 Token 消耗的工业级 PDF 图书数字化与出版级 EPUB 3 制作引擎</strong><br>
  <em>Low-Token, Publishing-Grade Book OCR & EPUB/Markdown Digitization Pipeline</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Engine-PyMuPDF%20%7C%20Pandoc-blue?style=flat-square" alt="Engine">
  <img src="https://img.shields.io/badge/Output-EPUB%203%20%7C%20Obsidian-purple?style=flat-square" alt="Output">
  <img src="https://img.shields.io/badge/Token_Cost-Lowest%20Possible-orange?style=flat-square" alt="Token Efficiency">
</p>

---

## 💡 为什么需要 PDF Book OCR？

将扫描版 PDF、古籍影印本或学术专著转化为高质量的电子书，传统方案常常面临几大难以逾越的鸿沟：

1. **上下文膨胀与 Token 爆炸**：数百页的 PDF 直接塞给大语言模型，瞬间消耗数十万甚至上百万 Token，导致上下文窗口溢出崩溃；直接调用商用 OCR API 则受昂贵费用和每日配额卡脖子。
2. **切片拼接处的断句丢字与重复**：多模型分片识别时，跨页分界线往往丢失句子，或两片首尾大段内容重复。
3. **Pandoc 全局脚注交叉覆盖惨剧**：当全书多个章节均使用 `[^1]`、`[^2]` 时，EPUB 编译器在全局作用域下会将后一章的脚注覆盖前一章，导致全书注释错乱串台。
4. **注释翻页跳转极度折磨**：在手机或电纸书上阅读时，点击注释强行跳转至书末，翻回正文体验极差。
5. **复杂文体排版坍塌**：戏剧台词缩进错乱、舞台说明与台词挤成一坨、列表语法因缺失空行而塌陷为普通长文本。

**PDF Book OCR** 结合了"本地确定性预处理探针 + 微型切片隔离并发转写 + 确定性代码断缝质检与章节脚注隔离 + 出版级 EPUB 3 双向气泡增强"，彻底根治上述所有顽疾。

> ⚠️ **设计诚信声明**：即使 PDF 含有原生文字层，本地脚本直接提取的原始文本也**无法直接达到出版级品质**。PDF 底层本质是坐标画布（PostScript 演变），内部不存在"段落""标题""脚注"等文档结构语义——行末硬换行会撕裂句子、页眉页脚会混入正文、脚注变成无法绑定的孤立碎片、网盘流传的劣质伪文字层更是错字率极高。因此本项目对数字版 PDF 采用"本地文本提取 + 轻量级 Agent 语义重构"双步策略（Token 消耗仅为视觉转写的 ~10%），而非虚假的"0-Token 秒级出书"。

---

## 🏗️ 四层分治架构与省 Token 原理

```
[原始 PDF 图书 (100~500+页)]
       │
       ▼ (Layer 0: 本地确定性预处理)
 digitize_book.py ──> 提取 300 DPI 超清封面、检文字层质量与置信度、生成切片任务单
       │
   ┌───┴───────────────────────────────────────────┐
   │ [数字文字版 PDF (检索率 > 75%)]               │ [无文字扫描版 / 劣质伪文字层 PDF]
   ▼                                               ▼ (Layer 1: 物理微切片)
本地提取纯文本 (极低 Token)                  pdf_slicer.py ──> 10~15 页独立微型 PDF (parts/)
   │                                               │
   ▼ (Layer 1.5: 轻量文本 Agent 语义重构)          ▼ (Layer 2: 隔离上下文并发视觉转写)
text_restructurer ──> 段落缝合、               ocr_specialist ──> 各子智能体独享 15 页上下文
 页眉剥离、脚注绑定、格式升维                 (并发 10~25 个)      写入 raw_md/*.md
   │                                               │
   │                                               ▼ (Layer 3: 确定性代码合流与质检)
   │                                         seam_auditor.py ────> 逐字断缝核验
   │                                         chapter_assembler.py ─> 章节脚注命名空间隔离
   │                                               │
   └───────────────────────┬───────────────────────┘
                           ▼ (Layer 4: 出版级编译与格式净化)
  epub_builder.py ───> 调用 Pandoc 编译 EPUB 3 + 注入古典纸书 CSS + 激活双向气泡弹窗
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
《书名》.epub (微信读书/Apple Books/Kindle)    《书名》.md (Obsidian 典藏主笔记)
```

---

## ✨ 核心特性

- ⚡ **智能双轨省 Token 策略**：自动探针检测文字层质量。若 PDF 含有高质量原生文字层，本地秒级提取纯文本后交由轻量文本 Agent 完成语义重构（段落缝合、页眉剥离、脚注绑定），**Token 消耗仅为视觉转写的 ~10%**；若为扫描版或劣质伪文字层，则自动走视觉切片 OCR 流水线。
- 🛡️ **微切片并发隔离转写**：扫描版按 10~15 页自动切片，并发派发给独立的子智能体（Subagent）。主对话只接收进度汇报，父对话 Token 消耗控制在 < 2k。
- 🔍 **代码级断缝核验 (`seam_auditor`)**：自动对分片接缝处（前片尾部 80 字与后片头部 80 字）进行最长公共子串比对，确保**0 丢字、0 漏句、0 重复**。
- 🔒 **章节脚注命名空间隔离 (`chapter_assembler`)**：将各切片内的局部 `[^1]`、`[^2]` 映射重构为带逻辑章节前缀的全局唯一键（如 `[^c01_1]`、`[^c02_1]`），并纠正全角标点符号与列表空行。
- 📖 **古典纸书级排版美学 (`styles_book.css`)**：
  - **篇章落版下沉大标题**：优雅居中的古典宋体（`Source Han Serif SC / Songti SC`），配有字距微排印与顶部呼吸留白；
  - **中文出版级以楷代斜**：恪守中文严肃出版规范，强调与斜体文字（`*...*`、`<em>`、`<i>`、舞台动作指示）统一呈现为端正典雅的**楷体（KaiTi）**，坚决杜绝西文机械倾斜伪斜体造成的汉字笔划畸变；
  - **副标题/署名发丝分割线**：作者/译者署名字体切换为典雅楷体，下方自动注入居中 40px 浅灰微细发丝线（Hairline Divider）；
  - **引用块内严格对齐**：引用块文字顶格对齐（`text-indent: 0 !important;`），彻底解决传统排版中由于软换行导致的阶梯状凹陷错位；
  - **原生双向气泡弹窗**：生成的 EPUB 3 在微信读书、Apple Books 等现代阅读器上实现**点击即弹出的气泡浮窗**，告别翻到书末找注释的折磨；
  - **文体自适应支持**：专为话剧剧本对白（`<p.dialogue>`）、舞台动作指示（`<p.stage-direction>`）、无序号登场人物表以及学术引文定制样式。

---

## 🚀 快速上手 (Quick Start)

### 1. 安装依赖

需要 Python 3.10+ 以及系统环境中的 [Pandoc](https://pandoc.org/)：

```bash
# 安装 Python 核心依赖
pip install -r requirements.txt
```

#### 安装 Pandoc：
- **Windows**: `winget install JohnMacFarlane.Pandoc`
- **macOS**: `brew install pandoc`
- **Linux (Ubuntu/Debian)**: `sudo apt-get install pandoc`

---

### 2. 环境体检 (`--doctor`)

运行自检命令，确认系统具备出版级电子书重构的全部能力：

```bash
python scripts/digitize_book.py --doctor
```

> **输出示例**：
> ```
> ==> 正在体检系统环境与出版级依赖库...
> [√] Python 环境: 3.12.4
> [√] PDF 核心解析引擎 (PyMuPDF): 1.25.4
> [√] HTML/EPUB DOM 引擎 (BeautifulSoup4): 4.13.3
> [√] 电子书出版编译器 (Pandoc): E:\Pandoc\pandoc.EXE
> [√] 系统环境完全就绪，具备出版级数字化全部能力！
> ```

---

### 3. 一键执行数字化流程

#### 模式 A：作为独立命令行工具 (CLI)

```bash
# 步骤 1：开始数字化任务（自动提取 300 DPI 封面、检测文字层或进行微切片）
python scripts/digitize_book.py "你的图书.pdf"

# 步骤 2：切片转写完成后，一键汇编、审计接缝并编译 EPUB
python scripts/digitize_book.py --assemble "你的图书_output"
```
*如为剧本或包含大量对话，加上 `--drama` 参数即可启用戏剧级对白排版。*

#### 模式 B：与 AI 智能体配合（Antigravity / Claude Code / Obsidian AI）

在配备了 AI Agent 的环境中，用户甚至不需要使用命令行：
只需在聊天框输入：
> **“帮我把这本 PDF 转成出版级 EPUB 和 Obsidian 笔记：`@[路径/书名.pdf]`”**

Agent 将按照内置的 `SKILL.md` 标准 SOP 自动调用底层脚本切分、分发并发 `ocr_specialist` 转写、汇编并交付成果。

---

## 📂 项目目录结构

```
pdf-book-ocr/
├── README.md                 # 项目主文档（本文件）
├── SKILL.md                  # AI 智能体 (Agent) 专属行为规约与 SOP
├── LICENSE                   # MIT 开源许可证
├── requirements.txt          # Python 依赖清单
├── .gitignore                # Git 忽略配置
├── assets/
│   └── styles_book.css       # 古典纸书排版 CSS（宋体落版、发丝线、气泡弹窗、暗色模式）
├── references/
│   ├── prompt_templates.md   # 低 Token 视觉 OCR 提示词配方（散文、戏剧、学术）
│   └── troubleshooting.md    # 核心排版踩坑指南（Pandoc 全局脚注、列表空行等）
└── scripts/
    ├── digitize_book.py      # 一键主控 CLI（含 --doctor, --assemble, 双轨探针）
    ├── pdf_analyzer.py       # 本地预检、文字层质量采样、300 DPI 封面提取与切分规划
    ├── pdf_slicer.py         # PyMuPDF 物理微切片切割器
    ├── seam_auditor.py       # 切片断缝逐字质检与重复检测工具
    ├── chapter_assembler.py  # 章节合并、脚注命名空间隔离与排版纠偏
    └── epub_builder.py       # Pandoc EPUB 3 编译器与 XHTML DOM 后处理增强
```

---

## 🛠️ 高级参数说明 (`digitize_book.py`)

| 参数 | 说明 | 默认值 |
| :--- | :--- | :---: |
| `pdf` | 要数字化的 PDF 图书文件路径 | 必需 |
| `--doctor` | 诊断环境依赖完整性，并给出缺失依赖的一键安装指令 | `False` |
| `--assemble DIR` | 将指定工作目录下的切片 Markdown 汇编成最终 EPUB 与主笔记 | `None` |
| `--drama` | 启用戏剧/剧本专用排版格式规约（台词加粗、舞台指示斜体、人物列表无点） | `False` |
| `--title TITLE` | 自定义图书标题（默认自动清洗剔除网盘/Z-Lib等字符） | `自动提取` |
| `--author AUTHOR` | 自定义作者/译者署名 | `自动提取` |
| `--chunk-size N` | 扫描版分片每切片页数（推荐 10~15 页） | `15` |
| `--force-scan` | 强制作为扫描版切分，即使存在文字层 | `False` |

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。欢迎提 Issue、PR 或将本技能集成至你的 Obsidian、AI 知识库或数字出版工作流中。
