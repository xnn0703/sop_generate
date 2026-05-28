# sop_generate · 开发计划（历史档案）

> 目标：把当前手写 HTML 抽象为可复用、可批量生成、并能给非技术人员使用的工具。
> 决策依据：使用者含工艺员/班长（需 GUI）；PDF 同时支持自动（Edge headless）和手动两种方式。
>
> **注**：本文档为 M1 阶段初版规划存档。下文示例中的"射频终端 / 安装硅胶O型圈"等是历史叙述上下文，
> 实际项目代码与文档已替换为通用测试数据（DEMO01）。最新设计请看 README.md 和 _schema.yaml。

---

## 1. 总体架构

```
                       ┌────────────────────────────────┐
                       │       数据层（单一事实源）       │
                       │   products/XXXX.yaml + images/  │
                       └──────┬────────────────┬─────────┘
                              │                │
            ┌─────────────────┘                └─────────────────┐
            │                                                    │
   ┌────────▼─────────┐                                ┌─────────▼─────────┐
   │  CLI 入口 gen.py │                                │ PySide6 GUI       │
   │  （工程师 / CI）  │                                │ （工艺员/班长）    │
   └────────┬─────────┘                                └─────────┬─────────┘
            │                                                    │
            └──────────────────────┬─────────────────────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  Jinja2 模板渲染引擎   │
                       │  templates/*.html.j2  │
                       └───────────┬───────────┘
                                   │
                  ┌────────────────┼────────────────┐
                  ▼                ▼                ▼
              output/XXXX.html  Edge headless   手动 ⌘P
                                    │
                                    ▼
                              output/XXXX.pdf

   ┌─────────────────────────────────────────────────────────────┐
   │ Claude Code Skill（.claude/skills/doc-gen/SKILL.md）         │
   │  用户用自然语言描述工艺 → Claude 生成/修改 YAML → 调用脚本     │
   └─────────────────────────────────────────────────────────────┘
```

**核心理念：YAML 是单一事实源**
- CLI / GUI / Skill 全部读写同一份 YAML
- Jinja2 模板与 YAML 完全解耦，调样式不动数据，加产品不动模板

---

## 2. 目录结构

```
4-documents_generate/
├── gen.py                          # CLI 入口
├── core/
│   ├── __init__.py
│   ├── renderer.py                 # Jinja2 渲染封装
│   ├── pdf_export.py               # Edge headless PDF 导出
│   └── validator.py                # YAML 校验（字段约束）
├── templates/
│   ├── manual.html.j2              # 主模板（封面 + 目录 + 流程图 + 工序页）
│   ├── style.css.j2                # 样式（从现有 HTML 抽出）
│   ├── cover.html.j2               # 封面分片
│   ├── toc.html.j2                 # 目录分片
│   ├── flow.html.j2                # 工艺流程图分片
│   └── process.html.j2             # 单个工序页分片
├── products/
│   ├── DEMO01.yaml                 # 第一个产品（从现有内容迁移）
│   └── _schema.yaml                # YAML 字段说明 + 示例
├── assets/
│   └── images/
│       └── DEMO01/                 # 每个产品一个图片子目录
│           ├── 安装硅胶O型圈.png
│           └── ...
├── output/                         # 生成产物（.gitignore）
│   ├── DEMO01.html
│   └── DEMO01.pdf
├── gui/                            # 阶段 3 再做
│   ├── main.py
│   ├── editor.py
│   └── preview.py
├── .claude/
│   └── skills/
│       └── doc-gen/
│           └── SKILL.md            # Skill 定义
├── requirements.txt
├── README.md
├── plan.md                         # 本文件
└── 验收标准.md
```

---

## 3. YAML 数据结构

`products/DEMO01.yaml`：

```yaml
product:
  model: DEMO01
  name: 射频终端
  company: 公司名称
  doc_id: SH-ZY-04
  version: A/0
  publish_date: 2026-3-30
  effective_date: 2026-4-1

processes:
  - name: 安装硅胶O型圈
    key: false                          # 是否关键工序（★）
    operations:                         # 操作说明（有序列表）
      - 用镊子取一根硅胶O型圈
      - 将O型圈安装到对应壳体凹槽中，注意安装到位，不可扭曲、拉伸
    notes:                              # 注意事项
      - O型圈安装前须清洁凹槽，无毛刺、无异物
      - 安装后目视检查O型圈无扭曲、无外露、无破损
    images:                             # 1 或 2 张，自动布局
      - 安装硅胶O型圈.png
    tools:                              # 工具设备（最多 4 项）
      - 不锈钢镊子
      - 防静电手环
    materials:                          # 作业材料（最多 4 项）
      - 硅胶O型圈
      - 无尘布
      - 酒精
```

---

## 4. 字段约束（防止超页 / 截断）

| 字段 | 限制 | 超限处理 |
|------|------|----------|
| `processes[].name`（工序名） | ≤ 12 个汉字 | 校验报错 |
| `operations[]` 单条 | ≤ 30 个汉字 | 校验警告 |
| `operations[]` 条数 | ≤ 6 条 | 校验报错 |
| `notes[]` 单条 | ≤ 28 个汉字 | 校验警告 |
| `notes[]` 条数 | ≤ 4 条 | 校验报错 |
| `tools[]` / `materials[]` 单项 | ≤ 10 个汉字 | 校验警告 |
| `tools[]` / `materials[]` 条数 | ≤ 4 项 | 校验报错 |
| `images[]` | 1 或 2 张 | 校验报错 |

`core/validator.py` 在渲染前严格校验，未通过不渲染。

---

## 5. CLI 使用

```bash
# 仅生成 HTML（最快，便于预览/手动 ⌘P）
python gen.py products/DEMO01.yaml

# 同时生成 HTML + PDF（Edge headless）
python gen.py products/DEMO01.yaml --pdf

# 批量
python gen.py products/*.yaml --pdf

# 校验但不渲染（CI 用）
python gen.py products/DEMO01.yaml --check
```

---

## 6. Claude Skill 用法

`SKILL.md` 描述：
- YAML schema + 字段约束
- 触发条件（关键字："作业指导书"、"工艺指导书"、"XESA"、""）
- 调用流程：理解需求 → 起草/修改 YAML → 触发 `python gen.py` → 报告结果

用户场景示例：
> "给 DEMO02 加一道工序：安装电源滤波器，工序号 3，用 M3×6 螺钉固定，需要防静电手环"

Claude 据此修改 `products/DEMO02.yaml`，调用 `python gen.py products/DEMO02.yaml --pdf`。

---

## 7. PySide6 GUI（阶段 3）

主要功能：
- 左侧：产品树（列出 `products/*.yaml`）+ 工序列表（拖拽排序）
- 中间：当前工序编辑表单（操作说明、注意事项、工具、材料、图片）
  - 字段输入实时校验，超长红色标注
  - 图片拖入即上传到 `assets/images/<model>/`
- 右侧：实时 HTML 预览（QWebEngineView 嵌入渲染结果）
- 工具栏：保存 YAML / 导出 HTML / 导出 PDF / 复制为新产品（基于现有 YAML 派生）

---

## 8. 阶段划分

| 里程碑 | 内容 | 预计 |
|--------|------|------|
| **M1：CLI 核心** | gen.py + 模板拆分 + DEMO01.yaml + 校验 + Edge PDF | 1 天 |
| **M2：Claude Skill** | SKILL.md + schema 文档 + 示例 | 半天 |
| **M3：PySide6 GUI** | 主窗口 + 工序编辑 + 实时预览 + 导出 | 2-3 天 |

每个里程碑独立可交付。M1 完成后即可开始用脚本批量生成；M3 完成后才是给工艺员/班长的最终形态。

---

## 9. 关键技术点

- **模板**：Jinja2（whitespace 控制用 `{%- ... -%}` 避免空白）
- **HTML**：复用现有 CSS（已调好的 A4 布局），仅把硬编码内容换成变量
- **PDF**：`subprocess` 调 `Microsoft Edge --headless --print-to-pdf`，CLI 透传 `--pdf-orientation auto` 让 @page 命名页生效
- **图片**：相对路径 `assets/images/<model>/xxx.png`，Edge headless 渲染时用 `file://` 协议加载
- **GUI 预览**：QWebEngineView 加载渲染后的 HTML，热重载（YAML 变更 → 重渲染 → reload）

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Edge headless 对命名页 portrait/landscape 混合支持不稳 | 保留 `--html-only` 模式 + 手动 ⌘P 兜底；M1 阶段先验证一份 PDF 比对 |
| 工艺员漏字段、字符超长 | validator 必跑，GUI 实时高亮，CLI 错误码非零 |
| 图片命名混乱 | 强约定：`assets/images/<model>/<工序名>.png`，validator 校验文件存在 |
| 修改模板后回归测试 | 每个 PR 跑 `python gen.py products/*.yaml --check`，比较输出快照 |
