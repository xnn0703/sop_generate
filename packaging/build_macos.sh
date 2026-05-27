#!/usr/bin/env bash
# ============================================================
#  sop_generate · macOS 打包脚本
#  产出：dist/sop_generate-mac/  (整个目录拷给客户即可)
# ============================================================
set -e
cd "$(dirname "$0")/.."

echo "=== [1/4] 准备 venv ==="
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
RELEASE="dist/sop_generate-mac"
mkdir -p "$RELEASE/products" "$RELEASE/assets/images" "$RELEASE/output"
mv dist/sop_generate.app "$RELEASE/"
# 拷贝示例数据（用户可改 / 删除）
cp -r products/* "$RELEASE/products/" 2>/dev/null || true
cp -r assets/images/* "$RELEASE/assets/images/" 2>/dev/null || true
# 删除 onedir 中间产物（仅留 .app）
rm -rf dist/sop_generate

# 生成给客户看的"使用说明.txt"
cat > "$RELEASE/使用说明.txt" <<'EOF'
sop_generate · 作业指导书生成器
================================

【启动】
    双击 sop_generate.app

【首次运行】
    macOS 会问"无法验证开发者"，请：
    系统设置 → 隐私与安全性 → 找到 sop_generate → 点"仍要打开"

【数据目录说明】
    products/        各产品的 YAML（可在 GUI 里新建/编辑）
    assets/images/   产品图片（每个产品一个子目录）
    output/          生成的 HTML / PDF

【导出 PDF 的前置条件】
    本机需装 Microsoft Edge 或 Google Chrome（任一即可）。
    若未装，仅 HTML 仍可正常生成，再用浏览器手动 ⌘P。
EOF

echo ""
echo "============================================================"
echo " [OK] 打包完成"
echo " 发布目录：$(pwd)/$RELEASE/"
echo "   ├── sop_generate.app"
echo "   ├── products/"
echo "   ├── assets/images/"
echo "   ├── output/"
echo "   └── 使用说明.txt"
echo ""
echo " 分发：把整个 $RELEASE/ 文件夹打 zip 发给客户即可"
echo "============================================================"
