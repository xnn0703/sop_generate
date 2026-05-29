# 更新日志

版本号管理在 [`core/__init__.py`](core/__init__.py) 的 `__version__`，所有地方（GUI 标题 / CLI `--version` / 打包元信息）从同一处读取。

---

## v1.0.8 — 2026-05-29

- 自动更新闭环验证版本：v1.0.7 → v1.0.8 升级
  - 新增的 Content-Length 校验 + 重试 + 7z 魔数校验全链路应该一次成功
  - 无功能改动，仅版本号 +1

---

## v1.0.7 — 2026-05-29

**修复 Bug**：自动更新 `Bad7zFile: invalid header data`

- 旧版 updater 下载分卷时无 Content-Length 校验、无重试，网络抖动会留下截断文件
- 客户端合并后的 .7z 文件头不对，py7zr 报魔数错误
- 修复：
  - `_download_one()` 单文件下载，校验 Content-Length，失败自动重试 4 次（指数退避 2s/4s/8s/10s）
  - 中途失败的文件自动删除避免污染
  - 合并后立即校验 7z 魔数（37 7a bc af 27 1c），早报错给用户清晰提示
- ⚠️ v1.0.5 / v1.0.6 客户端自身的下载逻辑无修复，无法自动跨过这版升级；需**手动重装** v1.0.7

---

## v1.0.6 — 2026-05-29

- 自动更新端到端验证版本：从 v1.0.5 自动升级到 v1.0.6 应当一气呵成
  - updater self-relocation 到临时目录
  - 替换 sop_generate.exe / updater.exe / _internal/
  - 保留 products / assets / output 用户数据
  - 自动启动新版本主程序

---

## v1.0.5 — 2026-05-29

**修复关键 Bug**：Windows 自动更新失败 `PermissionError: [WinError 5] 拒绝访问: updater.exe`

- Windows 上运行中的 .exe 不能被删除（与 Linux/Mac 行为不同）
- updater.exe 试图替换自己所在目录的文件 → 删自己失败
- 修复：把之前 macOS 才有的 self-relocation 扩展到 Windows：
  - 启动时把 updater.exe + _internal/ 复制到 %TEMP%/sop_updater_clone_<ts>/
  - 从临时目录跑，原 updater.exe 就能被替换
  - 退出 30 秒后由 cmd 异步清理临时目录
- v1.0.2 / v1.0.3 / v1.0.4 用户需**手动**重装本版本（旧 updater 无此修复，无法自动跨过这步）

---

## v1.0.4 — 2026-05-29

**修复关键 Bug**：自动更新解压失败 `UnsupportedCompressionMethodError: BCJ2 filter is not supported by py7zr`

- 7-Zip `-mx=9` 极限压缩对 x86 可执行文件默认启用 BCJ2 滤镜（提升压缩率），但客户端 py7zr 1.1.x 不支持解 BCJ2
- CI 加 `-mf=off` 禁用执行过滤器：体积增加约 5-10%，换来 py7zr 兼容
- v1.0.2 / v1.0.3 客户端从这版起可以正常自动更新

---

## v1.0.3 — 2026-05-29

- **多图布局扩展**：图片上限 2 → **4** 张
  - 1 张：全占工序页右半区
  - 2 张：上下排列
  - 3-4 张：2×2 网格自动缩放（不再被截断）
- **CI 双平台并行**：拆出 `prepare-release` job（轻量 Linux）先建空 Release，
  Windows 与 macOS 在创建好的 Release 上并行追加分卷。
  墙钟从 ~3 小时（串行）降到 ~80 分钟（并行）

---

## v1.0.2 — 2026-05-28

- **macOS 自动更新升级为 self-relocation 模式**：updater 启动时把整个 .app 复制到 /tmp 跑，
  完成后原地替换 .app（不再留隔壁旧目录）；/tmp 副本 30 秒后自动清理
- macOS 升级体验现在与 Windows 一致：原地替换 → 启动新版本，无残留旧目录
- 双平台 CI（windows + macOS）：tag 触发时同时构建 .exe 和 .app，分卷上传到同一 Gitee Release
- 客户端按当前 OS 自动筛选下载对应平台的分卷

---

## v1.0.1 — 2026-05-28

- 新增**自动更新**机制（独立 updater 子程序 + Gitee Release 增量分发）
- 双 EXE 打包（PyInstaller MERGE 共享运行时，增量体积仅 14MB）
- 启动时后台检查更新，弹窗"立即更新 / 暂不 / 跳过此版本"
- 升级时自动保留 `products/` / `assets/` / `output/` 用户数据
- 改用独立公开 Gitee 仓库 `sop_generate-releases` 分发，主仓可保持私有
- 通过 `release.config.json` 配置发版仓库地址，CI 自动从 Secrets 注入
- 移除所有业务信息硬编码（公司名、产品代号等改为占位）

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
