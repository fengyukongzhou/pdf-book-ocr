---
name: pdf-book-ocr
description: 低 Token 消耗的 PDF 图书全流程 OCR 数字化与出版级 EPUB 制作引擎。支持对任意无文字层扫描版或混合版 PDF 图书进行零 Token 预检、智能物理切分、并发多模态视觉 OCR、断缝代码级核验、章节命名空间脚注防碰撞、排版净化与出版级 EPUB 3 及 Obsidian 典藏 Markdown 一键生成。适用场景包括：(1) 用户提出“OCR 这本书”、“切分 PDF 后 OCR”、“制作 EPUB”、“扫描版电子书数字化”、“节省 token 做 OCR”；(2) 面对百页级大型扫描 PDF 需避免爆上下文与 API 配额耗尽；(3) 需要高保真保留戏剧/诗歌排版与出版级原生双向气泡弹窗脚注。
---

# PDF Book OCR (低 Token 出版级图书 OCR 与数字化引擎)

本技能提供一套**工业级、适用于任意通用 PDF 图书**的低 Token 消耗 OCR 数字化流水线。通过“本地 0-Token 物理预处理 + 上下文隔离的并发子智能体视觉转写 + 确定性脚本自动清洗缝合”，彻底杜绝超长上下文导致的 Token 浪费、幻觉遗漏与 API 配额限制。

> 📖 **开源仓库与详细使用指南**：请查阅 [README.md](README.md)。

---

## 核心架构与省 Token 原理

传统 OCR 方式将数百页 PDF 直接塞进主智能体对话，会迅速耗尽数十万甚至百万 Token，导致上下文截断崩溃；直接调用外部第三方 API 则易受每日配额制约。本架构采用**产品级四层分治法**：

```
[原始 PDF 图书 (100~500+页)]
       │
       ▼ (Layer 0: 本地 0-Token 探针)
 digitize_book.py ──> 抽高清封面、检文字层、生成分片与任务单 (subagent_jobs.json)
       │
   ┌───┴───────────────────────────────────────┐
   │ [数字文字版 PDF]                          │ [扫描版 PDF]
   ▼                                           ▼ (Layer 1: 物理微切片)
本地无损直提 (0 Token 秒级完成)          pdf_slicer ──> 10~15 页微型 PDF
   │                                           │
   │                                           ▼ (Layer 2: 隔离上下文并发视觉转写)
   │                                     ocr_specialist ──> 各子智能体独享 15 页上下文
   │                                     (并发 10~25 个)      写入 raw_md/*.md，父会话 0 膨胀
   │                                           │
   │                                           ▼ (Layer 3: 确定性代码合流与清洗)
   │                                     seam_auditor ──> 逐字断缝核验，确保 0 丢句、0 重复
   │                                     chapter_assembler ──> 命名空间隔离 ([^c01_1])
   │                                           │
   └───────────────────┬───────────────────────┘
                       ▼ (Layer 4: 出版级编译)
  epub_builder ──> Pandoc 编译 + 纸书 CSS + EPUB 3 双向气泡弹窗注增强
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
《书名》.epub (微信读书/Apple Books)    《书名》.md (Obsidian 典藏笔记)
```

---

## 使用模式与执行标准

### 模式 A：AI 对话向导与无感托管（面向普通用户，SOP）

当用户在对话中发送类似“帮我把这本 PDF 转成电子书”、“做成 EPUB”、“OCR 这本书”时，智能体应按照以下标准化流程全自动托管：

1. **自动体检**：
   运行 `python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --doctor`，确认依赖正常。
2. **执行切分与检测**：
   运行 `python .agent/skills/pdf-book-ocr/scripts/digitize_book.py "<PDF文件路径>"`。
   - 若检测为数字版：脚本自动生成 EPUB，直接向用户交货！
   - 若检测为扫描版：读取输出目录下的 `subagent_jobs.json`。
3. **并发派发子智能体转写**：
   读取 `references/prompt_templates.md` 的提示词模板，根据 `subagent_jobs.json` 批量使用 `invoke_subagent` 派发 `ocr_specialist` 并发转写微型分片。
   - **铁律**：要求子智能体将 Markdown 直接写入磁盘 `raw_md/*.md`，完成后仅回复一句完成摘要，保持主对话极简。
4. **一键汇编成书**：
   所有切片转写完成后，运行：
   ```bash
   python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --assemble "<输出工作目录>" [--drama]
   ```
5. **交付成品**：
   将生成的 `.epub` 和 `.md` 确保放置于 `_inbox/`，向用户呈递带有封面图、字数、章节目录与断缝审计状态的成果卡片。

---

### 模式 B：控制台一键直达模式 (Product-Grade CLI)

适用于在终端操作的独立用户，只需两到三行命令即可闭环：

```bash
# 1. 环境自检（缺少任何库会给出复制即用的安装指令）
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --doctor

# 2. 一键开始数字化流水线
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py "百年孤独.pdf"

# 3. 汇编切片成书（扫描版 OCR 完成后执行）
python .agent/skills/pdf-book-ocr/scripts/digitize_book.py --assemble "百年孤独_output"
```

---

### 模式 C：专家自定义模块化工作流

针对需要高度精细化调控的场景，可分别直接调用各专业子脚本：

| 模块脚本 | 核心功能与命令 |
| :--- | :--- |
| `pdf_analyzer.py` | 0-Token 探针：提取 300 DPI 封面、检文字层、解析书签生成 `slice_plan.json` |
| `pdf_slicer.py` | 物理切片：将原始 PDF 切割为 10~15 页的微型分片存入 `parts/` |
| `seam_auditor.py` | 断缝质检：扫描相邻切片接缝（尾部 80 字与首部 80 字），确保 0 丢句、0 重复 |
| `chapter_assembler.py` | 章节隔离：合并切片，将分片内局部脚注重构为 `[^c01_1]` 全局唯一键，修复列表缩进 |
| `epub_builder.py` | 出版级编译：调用 Pandoc 编译 EPUB 3，注入双向气泡弹窗与纸书 CSS，生成 Obsidian 主笔记 |

---

## 资源索引与指引

- **GitHub 完整文档**：[README.md](README.md)（项目设计哲学、环境配置与完整用法）。
- **提示词模板**：[references/prompt_templates.md](references/prompt_templates.md)（含散文小说、戏剧剧本、学术专著三套低 Token 提示词）。
- **避坑全指南**：[references/troubleshooting.md](references/troubleshooting.md)（深度解析全局脚注命名空间、列表空行坍塌、软换行对白挤塞等核心排版坑点）。
- **古典纸书 CSS**：[assets/styles_book.css](assets/styles_book.css)（宣纸微黄底色、暗色模式适配、气泡弹窗样式）。


