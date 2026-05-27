# sop_generate · 打包发布说明

## 重要：跨平台限制

**PyInstaller 是宿主机原生工具，不能跨平台打包。** 要产出 `.exe` 必须在 **Windows 机器上**运行；要产出 `.app` 必须在 **macOS 上**运行。本目录提供了两个平台各自的打包脚本。

如果你想完全自动化（一台机器搞定全平台），后续可加 GitHub Actions（`windows-latest` runner），参见末尾"CI 方案"。

---

## 文件清单

```
packaging/
├── build.spec              # PyInstaller 跨平台配置（macOS/Windows 通用）
├── build_macos.sh          # macOS 一键打包
├── build_windows.bat       # Windows 一键打包
├── icon.svg                # 图标源文件
├── icon.icns               # macOS 图标（make_icons.py 生成）
├── icon.ico                # Windows 图标（同上）
├── icon_pngs/              # 各尺寸 PNG（含 iconset）
└── make_icons.py           # SVG → ICNS / ICO 生成脚本
```

---

## Windows 打包流程（产出 `.exe`）

### 在 Windows 机器上一次性操作

1. 安装 **Python 3.9+**（从 [python.org](https://www.python.org/downloads/) 下载，安装时**勾选 "Add Python to PATH"**）
2. 安装 **Microsoft Edge** 或 **Google Chrome**（运行时 PDF 导出依赖；Win10/11 一般预装 Edge）
3. 把整个项目目录拷到 Windows（如 `D:\sop_generate\`）

### 打包

在项目根目录打开 `cmd`，运行：

```bat
packaging\build_windows.bat
```

脚本会自动：
1. 检测 Python
2. 创建 `.venv`
3. 安装 jinja2 / pyyaml / PySide6 / PyInstaller
4. 调 PyInstaller 打包
5. 把 `products/` `assets/` 拷贝到 `dist\sop_generate\` 同级

**产物**：`dist\sop_generate\sop_generate.exe`（GUI 主程序）

### 分发

把 `dist\sop_generate\` **整个文件夹**拷给最终用户。用户操作：

1. 在 Windows 上解压到任意目录（如 `D:\sop_generate\`）
2. 双击 `sop_generate.exe` 启动
3. 在界面里编辑/新建产品，输出 HTML / PDF 到 `output\`

**注意事项**：
- 首次启动 Windows Defender 可能会拦截（未签名应用），点"仍要运行"
- 用户机器需装 Edge / Chrome 才能导出 PDF；仅 HTML 不需要
- `_internal\` 文件夹是运行时库，**不可删除**

---

## macOS 打包流程（产出 `.app`）

```bash
packaging/build_macos.sh
```

**产物**：
- `dist/sop_generate.app`（双击启动）
- `dist/sop_generate_data/`（用户数据骨架：products / assets / output）

**首次运行**：macOS 会问"无法验证开发者"，到「系统设置 → 隐私与安全性」点"仍要打开"。

---

## 图标重新生成

如果改了 `icon.svg`，重新生成多尺寸图标：

```bash
.venv/bin/python packaging/make_icons.py
```

生成的 `icon.icns` / `icon.ico` 会自动被 `build.spec` 引用。

---

## 路径处理逻辑

`core/paths.py` 统一管理路径：

| 路径 | 开发态 | 打包态 |
|------|--------|--------|
| `templates/` | 项目根 | `_internal/templates/`（只读，内嵌） |
| `products/` | 项目根 | exe/app 同级（用户可编辑） |
| `assets/images/` | 项目根 | exe/app 同级（用户可编辑） |
| `output/` | 项目根 | exe/app 同级（生成结果） |

判定逻辑：`sys.frozen` 为 True 时按"打包态"处理。

---

## 已知问题

1. **macOS 打包后 .app 体积大（~500MB）**：主要是 PySide6 + QtWebEngine 运行时
2. **Windows 首次启动较慢**：Defender 扫描文件夹；之后启动正常
3. **跨架构**：本配置默认本机架构（M 系列 Mac 出 arm64，Intel Win 出 x64）。如需 Universal 二进制需另配
4. **代码签名**：未配置；企业内部分发问题不大，对外正式发布需购买签名证书

---

## CI 方案（可选，未启用）

在 `.github/workflows/build.yml` 加 windows-latest runner，可在 Mac 上 push 后自动拿到 .exe：

```yaml
jobs:
  windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt pyinstaller
      - run: pyinstaller packaging/build.spec --clean --noconfirm
      - uses: actions/upload-artifact@v4
        with: { name: sop_generate-windows, path: dist/sop_generate/ }
```

需要这个就告诉我，我加上。
