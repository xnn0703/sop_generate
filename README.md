# sop_generate · 作业指导书生成器

南京软赫电子科技有限公司内部工具：把工艺数据（YAML）一键渲染为 A4 排版的作业指导书 HTML / PDF。

- **仓库**：<https://gitee.com/soft-hertz/sop_generate>
- **克隆**：`git clone https://gitee.com/soft-hertz/sop_generate.git`

支持三种使用方式：
- **CLI**：工程师 / CI 用
- **PySide6 GUI**：工艺员 / 班长用（含打包好的 Mac/Win 版）
- **Claude Code Skill**：自然语言描述需求 → Claude 起草/修改 YAML 并触发生成

---

## 目录结构

```
sop_generate/
├── gen.py                         # CLI 入口
├── core/
│   ├── renderer.py                # Jinja2 渲染
│   ├── validator.py               # 字段约束校验
│   └── pdf_export.py              # Edge/Chrome headless 出 PDF
├── templates/
│   ├── manual.html.j2             # 主模板
│   ├── style.css.j2               # 样式
│   ├── cover.html.j2 / toc.html.j2 / flow.html.j2 / process.html.j2
├── products/
│   ├── XESA01.yaml                # 示例产品
│   └── _schema.yaml               # 字段规范
├── assets/images/<MODEL>/         # 每个产品的图片
├── output/                        # 渲染产物（gitignore）
├── gui/                           # PySide6 GUI
└── .claude/skills/doc-gen/        # Claude Skill
```

---

## 快速开始

### 0. 克隆

```bash
git clone https://gitee.com/soft-hertz/sop_generate.git
cd sop_generate
```

### 1. 初始化

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. CLI 用法

```bash
# 校验 YAML
.venv/bin/python gen.py products/XESA01.yaml --check

# 仅生成 HTML
.venv/bin/python gen.py products/XESA01.yaml

# 同时生成 HTML + PDF（需 Chrome 或 Edge）
.venv/bin/python gen.py products/XESA01.yaml --pdf

# 批量
.venv/bin/python gen.py products/*.yaml --pdf
```

### 3. GUI 用法

```bash
.venv/bin/python -m gui.main
```

界面三栏：
- **左**：产品列表 + 工序列表（可拖拽排序，± 增删）
- **中**：产品元信息 / 工序编辑（字段超长/超数量红字提示，图片可拖入）
- **右**：HTML 实时预览（编辑后 ~0.6s 自动刷新）

工具栏：新建产品 / 保存 / 导出 HTML / 导出 PDF / 派生新产品 / 打开图片目录 / 刷新预览。

### 4. Claude Skill 用法

在 Claude Code 中说类似的话：

> "参考 XESA01，给我新建 XESA02，工序如下：
>  1. 清洁壳体
>  2. 安装电池
>  3. ..."

Claude 会读 SKILL.md，按规范创建 `products/XESA02.yaml` 并调用 `gen.py` 生成 PDF。

---

## YAML schema

详见 `products/_schema.yaml`。核心字段：

```yaml
product:
  model: XESA01                # 仅字母数字
  name: 射频终端                # ≤ 12 汉字
  company: 南京软赫电子科技有限公司
  doc_id: SH-ZY-04
  version: A/0
  publish_date: 2026-3-30
  effective_date: 2026-4-1

processes:                     # 1-16 项
  - name: 安装硅胶O型圈        # ≤ 12 汉字
    key: false                 # 关键工序加 ★
    operations:                # 1-6 条，单条 ≤ 30 汉字
      - 用镊子取一根硅胶O型圈
    notes:                     # 0-4 条，单条 ≤ 28 汉字
      - O型圈安装前须清洁凹槽
    images:                    # 1-2 张，须在 assets/images/<MODEL>/
      - 安装硅胶O型圈.png
    tools:                     # 1-4 项，单项 ≤ 10 汉字
      - 不锈钢镊子
    materials:                 # 1-4 项，单项 ≤ 10 汉字
      - 硅胶O型圈
```

---

## 字段约束速查

| 字段 | 上限 | 超限处理 |
|------|------|---------|
| operations 条数 | 6 | 错误 |
| notes 条数 | 4 | 错误 |
| tools / materials 项数 | 4 | 错误 |
| images 张数 | 1-2 | 错误 |
| 工序名长度 | 12 汉字 | 错误 |
| 单条 operations 长度 | 30 汉字 | 警告 |
| 单条 notes 长度 | 28 汉字 | 警告 |
| tools/materials 单项 | 10 汉字 | 警告 |

---

## PDF 导出说明

- 自动模式（`--pdf`）：调 Edge / Chrome / Chromium / Brave headless（找到的第一个）
- 手动模式：浏览器打开 HTML → ⌘P → 保存为 PDF（布局选"自动"，背景图形勾选）
- PDF 中工序详情页自动横向、其他页纵向（命名页 `@page portrait/landscape`）

---

## 已知限制

- Chrome headless 偶尔对"纵横向混排"渲染抖动，复杂场景建议手动 ⌘P
- GUI 当前不直接支持图片预览缩略图（计划后续加）
- YAML 注释在保存时会被剥离（PyYAML 默认行为）

---

## 打包发布

详见 [`packaging/README.md`](packaging/README.md)。

- macOS：`bash packaging/build_macos.sh` → 产出 `dist/sop_generate-mac/`
- Windows：在 Win 机器上双击 `packaging\build_windows.bat` → 产出 `dist\sop_generate-win\`
- CI：本仓含 `.github/workflows/build-windows.yml`，若镜像到 GitHub 可自动出 Windows 版（Gitee Go 暂未配置）
