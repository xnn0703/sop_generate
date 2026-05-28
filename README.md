# sop_generate · 作业指导书生成器

把工艺数据（YAML）一键渲染为 A3 排版的作业指导书 HTML / PDF。

- **仓库**：<<your gitee repo>>
- **克隆**：`git clone <release.config.json 中 gitee_owner/gitee_repo 对应的 git 地址>`

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
│   ├── DEMO01.yaml                # 示例产品
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
git clone <release.config.json 中 gitee_owner/gitee_repo 对应的 git 地址>
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
.venv/bin/python gen.py products/DEMO01.yaml --check

# 仅生成 HTML
.venv/bin/python gen.py products/DEMO01.yaml

# 同时生成 HTML + PDF（需 Chrome 或 Edge）
.venv/bin/python gen.py products/DEMO01.yaml --pdf

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

> "参考 DEMO01，给我新建 DEMO02，工序如下：
>  1. 清洁壳体
>  2. 安装电池
>  3. ..."

Claude 会读 SKILL.md，按规范创建 `products/DEMO02.yaml` 并调用 `gen.py` 生成 PDF。

---

## YAML schema

详见 `products/_schema.yaml`。核心字段：

```yaml
product:
  model: DEMO01                # 仅字母数字
  name: 演示产品                # 推荐 ≤ 12 汉字
  company: 公司名称
  doc_id: SH-ZY-DEMO
  version: A/0
  publish_date: 2026-1-1
  effective_date: 2026-1-15

processes:                     # 1-32 项；流程图 > 8 个自动分页
  - name: 测试工序一            # 推荐 ≤ 12 汉字
    key: false                 # true 时加 ★ 标记关键工序
    operations:                # 1-18 条，单页 6 条，超 6 自动拆页
      - 第一步：示例操作步骤一
    notes:                     # 0-4 条
      - 示例注意事项一
    images:                    # 1-2 张，须在 assets/images/<MODEL>/
      - step01.png
    tools:                     # 1-4 项
      - 测试工具 A
    materials:                 # 1-4 项
      - 测试材料 A
```

---

## 字段约束速查

| 字段 | 限制 | 超限处理 |
|------|------|---------|
| processes 数 | 1-32 | 流程图按 8/页 自动分页 |
| operations 条数 | 1-18 | 单页 6 条，超 6 自动拆成多页（标"续 N/M"） |
| notes 条数 | 0-4 | 错误，建议拆工序 |
| tools / materials 项数 | 0-4 | 错误，建议拆工序 |
| images 张数 | 1-2 | 错误，建议拆工序 |
| 工序名 / 操作说明 / 注意事项 / 工具材料 字符长度 | 无硬限 | 超长自动换行；单元格 overflow:hidden 兜底 |

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

---

## 版本升级

老版本里 `products/*.yaml` 和 `assets/images/*/` 是**纯数据**，跨版本兼容。升级新版本时两种方式：

### 方式 1（推荐）：用 GUI 的"导入旧数据"按钮

1. 解压新版本到任意新目录（如 `D:\sop_generate-v1.1.0\`）
2. 启动新版本 `sop_generate.exe`
3. 工具栏点 **"导入旧数据"** → 选老版本根目录（含 `products/` 子目录）
4. 自动复制所有产品 YAML + 图片到新版本；同名文件**跳过不覆盖**，安全

### 方式 2：手动复制

解压新版本 → 把老版本的 `products/` 和 `assets/images/` 复制到新版本目录（覆盖示例）。

⚠️ **不要直接用 7-Zip 把新版本解压覆盖老目录**——会把老的 products 和 assets 覆盖成示例数据。
