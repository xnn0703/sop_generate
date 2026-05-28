# 更新日志

版本号管理在 [`core/__init__.py`](core/__init__.py) 的 `__version__`，所有地方（GUI 标题 / CLI `--version` / 打包元信息）从同一处读取。

---

## v1.0.0 — 2026-05-28

首发版本。

### 核心功能
- **CLI** (`gen.py`)：YAML → HTML / PDF，支持批量与校验
- **PySide6 GUI**：左侧产品/工序树、中间编辑器、右侧实时预览，支持工序拖拽排序、图片拖入
- **Claude Code Skill**：自然语言描述需求 → Claude 起草/修改 YAML 并触发生成

### 文档排版
- **A3 大小**：封面 / 目录 / 工艺流程图（纵向 297×420mm），工序详情页（横向 420×297mm）
- **表格铺满**：工序详情页表格充满页面可用区
- **工序自动拆页**：operations 超 6 条自动拆成多页，工序号保持一致，标"续 N/M"
- **工艺流程图分页**：超 8 个节点自动续到下一页，加"接上页 / 续下页"提示
- **拆页时图片每页都显示**（注意事项 / 工具 / 材料仅首页）

### 字段约束
- processes 1-32 项
- operations 1-18 条（自动拆页）
- notes / tools / materials 0-4 项
- images 1-2 张（多图建议拆工序）
- 字符长度无硬限，超长由 CSS overflow:hidden 兜底

### 数据迁移
- GUI 工具栏新增 **"导入旧数据"** 按钮，从老版本目录一键迁移所有 YAML + 图片
- 同名文件跳过不覆盖，保护当前数据

### 打包发布
- macOS `.app` + Windows `.exe`（PyInstaller 跨平台 spec）
- 自定义应用图标（文档+齿轮+对勾+SOP 渐变设计）
- GitHub Actions windows-latest runner 自动出 Windows 版
- 打 tag 时 7z 极限压缩 + 30MB 分卷上传 Gitee Release（国内快速下载）+ 同步建 GitHub Release

### 代码托管
- 主仓与发版位置见 `release.config.json`
- `git push` 同时推到所有配置的远程
