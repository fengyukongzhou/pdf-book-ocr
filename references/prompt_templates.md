# Subagent Prompt Templates Router (体裁路由与原子模具索引)

根据《writing-for-agents》的**渐进式呈现（Progressive Disclosure）与分支解耦法则**，各体裁提示词已物理隔离为独立原子模具（Atomic Templates）。

主 Agent 在派发子任务时，**严禁一次性加载全量模具**。请依据当前任务在 `subagent_jobs.json` 中的体裁标记，仅通过 `view_file` 读取命中的单个原子模板文件：

---

## 路由分支表 (Branch Routing)

| 体裁分支 | 触发条件 (Job Indicator) | 模具路径 (Pointer) | 核心特性 |
| :--- | :--- | :--- | :--- |
| **0. 数字文字版** | `is_digital: true` | [prompts/digital.txt](prompts/digital.txt) | 零视觉消耗、文本重构、300 DPI 矢量图紧凑承接、信息封闭原则 |
| **1. 散文/小说/通识** | `is_digital: false` 且非戏剧/学术 | [prompts/prose.txt](prompts/prose.txt) | 视觉转写、长段落硬折行缝合、插图归一化标注 [ymin, xmin, ymax, xmax] |
| **2. 戏剧/剧本** | `is_drama: true` | [prompts/drama.txt](prompts/drama.txt) | 角色对白强制分段与空行、舞台动作独立斜体、和歌/童谣引用块 |
| **3. 学术专著** | 专著/密集外文与注释 | [prompts/academic.txt](prompts/academic.txt) | 密集脚注严格映射 [^p_n]、学术引文逐字保真、插表 GFM 还原 |

---

## 派发调用规约 (Agent SOP)

1. **按需单取**：判断体裁后，仅调用 `view_file` 读取对应的 `references/prompts/<branch>.txt` 获取提示词。
2. **变量注入**：将读取到的模具中的 `{slice_pdf_path}`、`{raw_text_path}`、`{out_slice_md_path}` 等占位符替换为 `subagent_jobs.json` 对应分片的物理路径。
3. **并发派发**：使用 `invoke_subagent` 派发子任务，子 Agent 将结果直接落盘至 `raw_md/*.md`，实现 0 跨分支干扰与极限 Token 节约。
