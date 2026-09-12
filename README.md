# PDF Book OCR

将 PDF 图书（扫描图像或含文字层文档）转换为流式 EPUB 3 电子书与结构化 Markdown 笔记的工具。

---

## 功能说明

- **文档预检与切片**：自动检测数字文字层比例与书籍体裁，按设定页数（默认 15 页）切分长文档，避免单次处理上下文过长。
- **图像与矢量图表提取**：
  - 提取高分辨率封面（300 DPI）；
  - 提取页面内嵌位图，按全书绝对页码命名；
  - 自动识别数字 PDF 中的矢量信息图与统计图表，基于图题与说明文字计算紧凑边界并光栅化为 300 DPI 图片，避免将图表误转为窄屏易坍塌的表格或未渲染代码。
- **双轨分片处理**：
  - 数字文字版：提取原始文字层草稿，供轻量文本模型清洗排版，降低 token 消耗；
  - 图像扫描版：提供微型 PDF 切片，供多模态模型逐页视觉转写。
- **接缝审计与平滑缝合**：比对相邻分片首尾文本，自动处理跨页未完结断句、跨分片未闭合对白引号与转写重叠，输出审计报告。
- **真实章节聚合**：依据正文二级标题（`##`）重组为逻辑章节，避免机械按切片划分。
- **脚注隔离与弹框注解**：为各章节脚注添加命名空间前缀（`[^c01_1]`），防止跨章覆盖，并注入 EPUB 3 弹框注释属性。
- **原子提示词路由**：提供按体裁（数字文字、散文小说、戏剧剧本、学术专著）物理隔离的提示词模具与路由索引，按需加载。

---

## 处理流程

```
[原始 PDF 文件]
       │
       ▼ (Step 1: 预处理与规划)
 digitize_book.py
   ├── 提取封面与内嵌插图
   ├── 自动截取矢量图表（300 DPI 紧凑锁边）
   ├── 切分为 10~15 页物理分片
   └── 生成任务清单 subagent_jobs.json
       │
       ▼ (Step 2: 分片清洗或转写)
 模型派发 / 人工处理 (参考 references/prompts/ 对应模具)
   ├── 数字文字版：基于 parts/*.raw.txt 清洗与段落整理
   └── 图像扫描版：基于 parts/*.pdf 逐页识别
   └── 结果分别存入 raw_md/*.md
       │
       ▼ (Step 3: 汇编与编译成书)
 digitize_book.py --assemble
   ├── seam_auditor.py: 审计首尾接缝，缝合断句与未闭合对白
   ├── chapter_assembler.py: 依 ## 标题聚合章节，隔离脚注命名空间
   └── epub_builder.py: 调用 Pandoc 编译 EPUB 3 并注入双向弹框注释
       │
       ▼ (Step 4: 成果交付)
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

### 步骤 1：分析 PDF 并生成分片

```bash
python scripts/digitize_book.py "book.pdf"
```

脚本将提取封面、切出分片文件，并在工作目录下生成 `subagent_jobs.json` 任务清单。数字文字版会自动提取矢量图表并输出 `parts/*.raw.txt`。

### 步骤 2：清洗或转写分片

根据 `references/prompt_templates.md` 的路由指引，调用 `references/prompts/` 中对应的原子模具处理各分片，将生成的 Markdown 写入 `raw_md/` 目录。分片较多时（>4 个），建议以 3~4 个分片为一组滚动派发，避免单次瞬时请求过大。

### 步骤 3：汇编成书

```bash
python scripts/digitize_book.py --assemble "book_output"
```

脚本将依次执行接缝审计、章节聚合、脚注重映射，并编译输出 EPUB 电子书与整书 Markdown 笔记。

---

## 命令行参数 (`digitize_book.py`)

| 参数 | 说明 | 默认值 |
| :--- | :--- | :---: |
| `pdf` | PDF 文件路径 | 必需 |
| `--doctor` | 检查运行环境与依赖完整性 | `False` |
| `--assemble DIR` | 汇编指定工作目录下的分片 Markdown | `None` |
| `--drama` | 启用剧本对白与舞台动作专用排版规则 | `False` |
| `--extract-figures PDF` | 独立提取数字 PDF 中的矢量信息图与图表 | `None` |
| `--status DIR` | 查看指定工作目录中各分片的落盘完成进度 | `None` |
| `--title TITLE` | 指定图书标题（默认自动清洗文件名） | 自动识别 |
| `--author AUTHOR` | 指定作者名称 | 自动识别 |
| `--out-dir DIR` | 指定输出工作目录 | 自动生成 |
| `--chunk-size N` | 单个分片的页数 | `15` |
| `--force-scan` | 忽略文字层，强制按纯图像切片处理 | `False` |

---

## 目录结构

```
pdf-book-ocr/
├── README.md                     # 项目说明文档
├── SKILL.md                      # Agent 行为指南与执行规约
├── requirements.txt              # Python 依赖清单
├── assets/
│   └── styles_book.css           # EPUB 排版样式表
├── references/
│   ├── prompt_templates.md       # 体裁路由与模具索引
│   ├── prompts/                  # 原子提示词模具目录
│   │   ├── digital.txt           # 数字文字版清洗模具
│   │   ├── prose.txt             # 散文/小说/通用非虚构模具
│   │   ├── drama.txt             # 戏剧/剧本专用模具
│   │   └── academic.txt          # 学术专著模具
│   └── troubleshooting.md        # 格式问题说明与解决方案
└── scripts/
    ├── digitize_book.py          # 主控入口脚本
    ├── vector_figure_extractor.py # 矢量图表提取引擎
    ├── pdf_analyzer.py           # 预检与分片规划脚本
    ├── pdf_slicer.py             # 物理切片脚本
    ├── seam_auditor.py           # 文本接缝审计脚本
    ├── chapter_assembler.py      # 章节聚合与脚注重映射脚本
    └── epub_builder.py           # EPUB 编译与注释注入脚本
```

---

## 许可证

本项目采用 [MIT License](LICENSE) 授权。
