# v1.1.0 改造计划 · 协作支持

## 目标
- 一个 SOP = 一个独立工程文件夹（自包含，便于传递）
- 修改追溯（每个工序记录最后修改人）
- 一键导入/导出 .sopkg 包

## 新目录结构
```
sop_packages/                ← 替代 products/ 和 assets/images/
├── XESA01/
│   ├── product.yaml         ← YAML + _meta 追溯字段
│   ├── images/              ← 该产品所有图片
│   └── output/              ← 该产品生成的 HTML/PDF
└── XESA02/
config/
└── current_user.json        ← 当前用户名（必填）
_legacy_v1_backup/           ← 老结构备份（迁移后自动建）
```

## 用户决策（已确认）
1. **用户名强制必填**，否则不能修改、不能导出
2. .sopkg 包不加密
3. _legacy_v1_backup 保留 1 个月，超时弹窗提示可删

## 实施步骤
- M1：新目录结构 + paths.py / model.py 重构
- M2：修改追溯（用户名管理 + _meta + GUI 显示）
- M3：.sopkg 导入/导出
- M4：自动迁移 + CLI 兼容 + 打包脚本同步
- 测试 + 发版 v1.1.0

## 关键约束
- 老 v1.0.x 数据**必须**能自动迁移，不丢数据
- CLI 三种路径都兼容：XESA01 / sop_packages/XESA01/ / products/XESA01.yaml
- _meta 字段在 GUI 中不可手动编辑（只能由保存逻辑自动写）
