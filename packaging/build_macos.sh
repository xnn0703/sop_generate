#!/usr/bin/env bash
# ============================================================
#  SOP Generate · macOS 打包脚本（v1.1.0 结构）
#  产出：dist/sop_generate-mac-<版本>/  (整个目录拷给客户即可)
# ============================================================
set -e
cd "$(dirname "$0")/.."

VERSION=$(grep -oE '__version__ *= *"[^"]+"' core/__init__.py | grep -oE '[0-9][^"]*')
RELEASE="dist/sop_generate-mac-v${VERSION}"

echo "=== [1/4] 准备 venv（版本 v${VERSION}）==="
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "=== [2/4] 安装依赖 ==="
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install -r packaging/requirements-build.txt --quiet

echo "=== [3/4] 调 PyInstaller ==="
rm -rf build dist
pyinstaller packaging/build.spec --clean --noconfirm

echo "=== [4/4] 整理发布目录 ==="
mkdir -p "$RELEASE/sop_packages" "$RELEASE/output"
mv dist/sop_generate.app "$RELEASE/"
# 拷贝示例 SOP 工程包（用户可改 / 删除）
cp -r sop_packages/* "$RELEASE/sop_packages/" 2>/dev/null || true
# 删除 onedir 中间产物（仅留 .app）
rm -rf dist/sop_generate

# 拷贝使用手册（HTML + 截图）
cp docs/使用说明.html "$RELEASE/使用说明.html" 2>/dev/null || true
[ -d docs/images ] && cp -r docs/images "$RELEASE/images" || true

# 生成给客户看的"使用说明.txt"
cat > "$RELEASE/使用说明.txt" <<'EOF'
SOP Generate · 作业指导书生成器
================================

【启动】
    双击 sop_generate.app

【首次运行】
    macOS 会问"无法验证开发者"，请：
    系统设置 → 隐私与安全性 → 找到 sop_generate → 点"仍要打开"

【首次使用】
    启动后会要求填写用户名（用于记录 SOP 修改人），必填。

【数据目录说明（所有数据在 .app 同级）】
    sop_packages/    各 SOP 工程包（每个产品一个独立文件夹）
                     <型号>/product.yaml + images/ + output/
    config/          应用配置（用户名等）
    output/          CLI 批量导出的产物

【导出 PDF 的前置条件】
    本机需装 Microsoft Edge 或 Google Chrome（任一即可）。
    若未装，仅 HTML 仍可正常生成，再用浏览器手动 ⌘P。

【详细操作说明】
    用浏览器打开同目录下的 使用说明.html
EOF

echo ""
echo "============================================================"
echo " [OK] 打包完成"
echo " 发布目录：$(pwd)/$RELEASE/"
echo "   ├── sop_generate.app"
echo "   ├── sop_packages/   （示例 SOP 工程包）"
echo "   ├── output/"
echo "   ├── images/         （使用手册截图）"
echo "   ├── 使用说明.html"
echo "   └── 使用说明.txt"
echo ""
echo " 分发：把整个 $RELEASE/ 文件夹打 zip 发给客户即可"
echo "============================================================"
