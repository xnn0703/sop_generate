---
name: doc-gen
description: 根据自然语言描述生成或修改作业指导书（SOP）。当用户提到"作业指导书 / 工艺指导书 / SOP / 生成产品手册 / 给 XESA / 给宏图"等关键词时触发。底层调用 sop_generate 项目的 gen.py 渲染 HTML/PDF。
---

# Skill: doc-gen · 作业指导书生成

## 何时使用此 Skill

用户消息中出现以下任一关键字时优先调用本 Skill：
- 作业指导书 / 工艺指导书 / SOP / 工艺文件
- "给 XESA / 宏图 / 某型号 生成 / 修改 / 加一道工序"
- "新建产品手册"

## 项目位置

- 项目根：`/Users/xmac/Documents/project_manager/1-softHz/4-documents_generate/`
- Python 环境：项目下 `.venv/`（`.venv/bin/python`）
- 入口脚本：`gen.py`
- 产品 YAML：`products/<MODEL>.yaml`
- 图片目录：`assets/images/<MODEL>/`

## 公司名（固定常量）

**南京软赫电子科技有限公司** — 默认填入 `product.company`，除非用户明确改写。

## YAML schema（必须严格遵守）

```yaml
product:
  model: XESA01                  # ASCII 字母数字/下划线/横线
  name: 射频终端                  # ≤ 12 汉字
  company: 南京软赫电子科技有限公司
  doc_id: SH-ZY-04
  version: A/0                   # 形如 A/0、B/1
  publish_date: 2026-3-30        # YYYY-M-D
  effective_date: 2026-4-1

processes:                       # 1-16 道工序
  - name: 工序名                 # ≤ 12 汉字
    key: false                   # true 表关键工序，会加 ★
    operations:                  # 1-6 条
      - 单条 ≤ 30 汉字
    notes:                       # 0-4 条
      - 单条 ≤ 28 汉字
    images:                      # 1-2 张，文件须存在于 assets/images/<MODEL>/
      - 工序名.png
    tools:                       # 1-4 项
      - 单项 ≤ 10 汉字
    materials:                   # 1-4 项
      - 单项 ≤ 10 汉字
```

**字段约束（违反则校验失败）**：
| 字段 | 上限 |
|------|------|
| operations 条数 | 6 |
| notes 条数 | 4 |
| tools / materials 项数 | 4 各 |
| images 张数 | 2 |
| 单条 operations 长度 | 30 汉字（超长仅警告） |
| 单条 notes 长度 | 28 汉字（超长仅警告） |
| 单项 tools / materials 长度 | 10 汉字（超长仅警告） |

## 典型工作流

### 场景 1：新建产品

1. 询问/确认产品信息：型号、名称、工序清单
2. 复制 `products/XESA01.yaml` 作为模板 → `products/<新型号>.yaml`
3. 创建图片目录 `assets/images/<新型号>/`，提示用户放入图片
4. 按用户描述填充 `processes`，**严格遵守字段约束**
5. 跑校验：`.venv/bin/python gen.py products/<新型号>.yaml --check`
6. 校验通过后：`.venv/bin/python gen.py products/<新型号>.yaml --pdf`
7. 报告：HTML / PDF 输出路径

### 场景 2：修改现有产品

1. 读 `products/<MODEL>.yaml` 理解现状
2. 按用户描述精确修改 YAML（用 Edit 工具，不要重写整个文件）
3. 跑校验 + 重新生成 PDF
4. 报告修改了哪些工序、哪些字段

### 场景 3：批量生成

`.venv/bin/python gen.py products/*.yaml --pdf`

## 关键约束

1. **图片必须真实存在**。如果用户描述的工序对应图片未放入 `assets/images/<MODEL>/`，**先提示用户放图片**，再继续 YAML 填充。
2. **不要在模板（templates/*.j2）里硬编码产品信息**。所有产品差异都通过 YAML 表达。
3. **超长字段要主动缩短**而不是机械填入。例如用户说"M4×10 内六角螺钉、螺纹胶"，应缩为"M4×10 螺钉、螺纹胶"或拆成两条。
4. **关键工序**（涉及静电敏感器件、精密装配等）的 `key` 字段设为 `true`。
5. **如果校验报错，停下来报告给用户**，不要继续生成 PDF。

## 常见错误处理

| 错误 | 处理 |
|------|------|
| `images 张数应为 1-2，得到 0` | 提示用户提供图片，放到 `assets/images/<MODEL>/` |
| `name 长度超过上限 12` | 缩短工序名 |
| `operations 条数超过上限 6` | 合并相邻步骤，或拆成两道工序 |
| `图片不存在：...` | 检查文件名拼写，或提示用户补图 |
| PDF 导出失败 | 检查 Edge/Chrome 是否安装；可降级为仅生成 HTML，提示用户手动 ⌘P |

## 输出示例

完成后报告这样的信息：

```
✓ 已生成 XESA02 作业指导书
  - YAML:  products/XESA02.yaml（5 道工序，2 道为关键工序 ★）
  - HTML:  output/XESA02.html
  - PDF:   output/XESA02.pdf
  - 警告:  processes[2].notes[1] 偏长（29 > 28）— 建议缩短
```
