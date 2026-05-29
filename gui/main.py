"""sop_generate GUI 主窗口

启动：
    python -m gui.main
"""
from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSplitter,
    QStatusBar, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core import __version__, paths
from core.renderer import render_manual, ProductData, write_html
from core.validator import validate
from core.pdf_export import export_pdf, find_browser
from core.updater import check_latest, is_newer, is_release_configured
from core.user_config import get_current_user, set_current_user, is_user_set

paths.ensure_user_dirs()

from gui.editor import ProcessEditor, ProductMetaEditor
from gui.model import (
    DEFAULT_PROCESS, Product, clone_product, delete_product, import_legacy,
    list_products, new_product,
)
from gui.sopkg import export_sopkg, import_sopkg
from gui.archive import archive_product


PREVIEW_DELAY_MS = 600

SKIP_VERSION_FILE = paths.app_dir() / ".skip_version"   # 记录用户"跳过此版本"的 tag


class UpdateCheckWorker(QObject):
    """后台线程查最新版本"""
    found = Signal(object)   # ReleaseInfo or None
    def run(self) -> None:
        try:
            self.found.emit(check_latest())
        except Exception:
            self.found.emit(None)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._base_title = "SOP Generate"
        self.setWindowTitle(self._base_title)
        self.resize(1500, 900)

        self.current: Product | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_html_path = Path(tempfile.gettempdir()) / "sop_preview.html"

        self._build_toolbar()
        self._build_central()
        self._build_status()

        # 启动时强制要求用户名
        if not is_user_set():
            self._ask_user_name(force=True)
        else:
            self.setWindowTitle(f"{self._base_title}  ·  当前用户：{get_current_user()}")

        # 启动时检测老 v1.0.x 数据
        if paths.has_legacy_data():
            QTimer.singleShot(500, self._prompt_legacy_migration)

        self._reload_product_list()

        # 启动后延迟 2 秒后台查更新（不阻塞 UI）
        if is_release_configured():
            QTimer.singleShot(2000, self._start_update_check)

    # ---------- UI 构建 ----------
    def _build_toolbar(self) -> None:
        tb = QToolBar()
        self.addToolBar(tb)

        act_new = QAction("新建 SOP", self); act_new.triggered.connect(self.action_new_product); tb.addAction(act_new)
        act_delete = QAction("删除 SOP", self); act_delete.triggered.connect(self.action_delete_product); tb.addAction(act_delete)
        act_import = QAction("导入 SOP 包", self); act_import.triggered.connect(self.action_import_sopkg); tb.addAction(act_import)
        act_export = QAction("导出 SOP 包", self); act_export.triggered.connect(self.action_export_sopkg); tb.addAction(act_export)
        act_archive = QAction("📦 归档定稿", self); act_archive.triggered.connect(self.action_archive); tb.addAction(act_archive)
        act_save = QAction("保存", self); act_save.triggered.connect(self.action_save); tb.addAction(act_save)
        tb.addSeparator()
        act_user = QAction("设置用户名", self); act_user.triggered.connect(lambda: self._ask_user_name(force=False)); tb.addAction(act_user)
        act_update = QAction("检查更新", self); act_update.triggered.connect(self._start_update_check_manual); tb.addAction(act_update)
        tb.addSeparator()
        act_html = QAction("导出 HTML", self); act_html.triggered.connect(self.action_export_html); tb.addAction(act_html)
        act_pdf = QAction("导出 PDF", self); act_pdf.triggered.connect(self.action_export_pdf); tb.addAction(act_pdf)
        tb.addSeparator()
        act_clone = QAction("派生新产品", self); act_clone.triggered.connect(self.action_clone); tb.addAction(act_clone)
        act_open_img = QAction("打开图片目录", self); act_open_img.triggered.connect(self.action_open_image_dir); tb.addAction(act_open_img)
        act_refresh = QAction("刷新预览", self); act_refresh.triggered.connect(self._refresh_preview); tb.addAction(act_refresh)
        act_help = QAction("帮助", self); act_help.triggered.connect(self.action_help); tb.addAction(act_help)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        # ----- 左：产品 + 工序 -----
        left = QWidget(); left_v = QVBoxLayout(left); left_v.setContentsMargins(4, 4, 4, 4)
        left_v.addWidget(QLabel("产品"))
        self.product_list = QListWidget()
        self.product_list.currentItemChanged.connect(self._on_product_changed)
        left_v.addWidget(self.product_list, 1)

        left_v.addWidget(QLabel("工序"))
        self.proc_list = QListWidget()
        self.proc_list.setDragDropMode(QListWidget.InternalMove)
        self.proc_list.model().rowsMoved.connect(self._on_proc_reordered)
        self.proc_list.currentRowChanged.connect(self._on_proc_selected)
        left_v.addWidget(self.proc_list, 2)

        btn_row = QHBoxLayout()
        b_add = QPushButton("＋ 工序"); b_add.clicked.connect(self.action_add_proc)
        b_del = QPushButton("－ 工序"); b_del.clicked.connect(self.action_del_proc)
        btn_row.addWidget(b_add); btn_row.addWidget(b_del)
        left_v.addLayout(btn_row)
        splitter.addWidget(left)

        # ----- 中：编辑器（标签页：产品元信息 / 工序） -----
        center = QWidget(); cv = QVBoxLayout(center); cv.setContentsMargins(4, 4, 4, 4)
        self.tabs = QTabWidget()
        self.meta_editor = ProductMetaEditor()
        self.meta_editor.changed.connect(self._schedule_preview)
        self.proc_editor = ProcessEditor()
        self.proc_editor.changed.connect(self._on_proc_edited)
        self.proc_editor.set_product_image_dir_provider(self._current_image_dir)
        self.tabs.addTab(self.meta_editor, "产品信息")
        self.tabs.addTab(self.proc_editor, "工序编辑")
        cv.addWidget(self.tabs)
        splitter.addWidget(center)

        # ----- 右：预览 -----
        right = QWidget(); rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(QLabel("HTML 预览  (编辑后约 0.6s 自动刷新)"))
        self.preview = QWebEngineView()
        rv.addWidget(self.preview, 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([260, 520, 720])

    def _build_status(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

    # ---------- 列表 / 选择 ----------
    def _reload_product_list(self) -> None:
        self.product_list.clear()
        for model in list_products():
            item = QListWidgetItem(model)
            item.setData(Qt.UserRole, model)
            self.product_list.addItem(item)
        if self.product_list.count():
            self.product_list.setCurrentRow(0)

    def _on_product_changed(self, current, previous) -> None:
        if current is None:
            return
        model = current.data(Qt.UserRole)
        try:
            self.current = Product.load(model)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
            return
        self.meta_editor.load(self.current.product)
        self._reload_proc_list()
        self._schedule_preview()
        self.status.showMessage(f"已加载 SOP：{model}")

    def _reload_proc_list(self) -> None:
        self.proc_list.clear()
        if not self.current:
            return
        for i, p in enumerate(self.current.processes, start=1):
            star = " ★" if p.get("key") else ""
            meta = p.get("_meta") or {}
            modifier = meta.get("last_modified_by", "")
            modifier_part = f"  · {modifier}" if modifier else ""
            self.proc_list.addItem(f"{i}. {p.get('name', '<无名>')}{star}{modifier_part}")
        if self.proc_list.count():
            self.proc_list.setCurrentRow(0)

    def _on_proc_selected(self, row: int) -> None:
        if not self.current or row < 0 or row >= len(self.current.processes):
            return
        self.proc_editor.load(self.current.processes[row])
        self.tabs.setCurrentWidget(self.proc_editor)

    def _on_proc_edited(self) -> None:
        # 名称变化时同步左侧列表显示
        row = self.proc_list.currentRow()
        if self.current and 0 <= row < len(self.current.processes):
            p = self.current.processes[row]
            star = " ★" if p.get("key") else ""
            self.proc_list.item(row).setText(f"{row + 1}. {p.get('name', '<无名>')}{star}")
        self._schedule_preview()

    def _on_proc_reordered(self, *args) -> None:
        if not self.current:
            return
        new_order: list[dict] = []
        for i in range(self.proc_list.count()):
            text = self.proc_list.item(i).text()
            # 通过文本反查很脆弱，改用：拖动后重建顺序
            new_order.append(text)
        # 实际重排：用拖后列表当前顺序，按原 processes 名字匹配
        old = self.current.processes
        rebuilt = []
        used = set()
        for txt in new_order:
            # 去掉前缀序号
            name = txt.split(". ", 1)[-1].replace(" ★", "")
            for j, p in enumerate(old):
                if j in used:
                    continue
                if p.get("name") == name:
                    rebuilt.append(p)
                    used.add(j)
                    break
        if len(rebuilt) == len(old):
            self.current.processes = rebuilt
            self._reload_proc_list()
            self._schedule_preview()

    # ---------- 动作 ----------
    def _ask_user_name(self, force: bool = False) -> None:
        """弹窗要求填写用户名。force=True 时不允许取消。"""
        current = get_current_user()
        while True:
            name, ok = QInputDialog.getText(
                self, "设置用户名",
                "请输入你的名字（用于记录 SOP 修改人）：" if not current
                else "修改用户名：",
                text=current,
            )
            if ok and name.strip():
                set_current_user(name.strip())
                self.setWindowTitle(f"{self._base_title}  ·  当前用户：{name.strip()}")
                return
            if not force:
                return
            # 强制模式：必须填写
            QMessageBox.warning(
                self, "需要用户名",
                "必须设置用户名才能使用本软件。\n"
                "用户名会记录到每次保存的 SOP 中，用于追溯责任。"
            )

    def _prompt_legacy_migration(self) -> None:
        from gui.migration import migrate_legacy_data
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("检测到旧版本数据")
        box.setText("检测到 v1.0.x 的产品数据。是否一键迁移到新结构 sop_packages/？")
        box.setInformativeText(
            "迁移后老数据会备份到 _legacy_v1_backup/ 目录（保留 1 个月）。"
            "不迁移的话，老数据仍能用 v1.0.x 软件打开，但本版本不会显示。"
        )
        yes_btn = box.addButton("立即迁移", QMessageBox.AcceptRole)
        later   = box.addButton("稍后再说", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes_btn:
            try:
                result = migrate_legacy_data()
                QMessageBox.information(
                    self, "迁移完成",
                    f"已迁移 {len(result['migrated'])} 个产品到 sop_packages/\n\n"
                    f"老数据备份在：{result['backup_dir']}"
                )
                self._reload_product_list()
            except Exception as e:
                QMessageBox.critical(self, "迁移失败", str(e))

    def action_delete_product(self) -> None:
        if not self.current:
            QMessageBox.warning(self, "提示", "请先在左侧选择要删除的 SOP")
            return
        if not self._require_user():
            return

        model = self.current.model
        n_procs = len(self.current.processes)
        # 统计图片数
        img_dir = self.current.image_dir
        n_imgs = len(list(img_dir.glob("*"))) if img_dir.exists() else 0

        # 第一次确认（红色警告样式）
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("删除 SOP 工程")
        box.setText(f"<b>确定要删除 SOP「{model}」吗？</b>")
        box.setInformativeText(
            f"将永久删除以下内容：\n"
            f"  · 产品 YAML（{n_procs} 道工序）\n"
            f"  · {n_imgs} 张图片\n"
            f"  · 已生成的 HTML / PDF\n\n"
            f"⚠️ 此操作不可撤销，删除前如需保留请先「导出 SOP 包」备份。"
        )
        del_btn = box.addButton("删除", QMessageBox.DestructiveRole)
        cancel  = box.addButton("取消", QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        if box.clickedButton() is not del_btn:
            return

        # 第二次确认：要求输入产品型号
        text, ok = QInputDialog.getText(
            self, "再次确认",
            f"请输入产品型号「{model}」以确认删除：",
        )
        if not ok:
            return
        if text.strip() != model:
            QMessageBox.warning(self, "已取消", f"输入的内容与「{model}」不一致，未删除。")
            return

        # 执行删除
        try:
            delete_product(model)
        except Exception as e:
            QMessageBox.critical(self, "删除失败", str(e))
            return

        self.current = None
        self._reload_product_list()
        self.status.showMessage(f"已删除 SOP：{model}")
        QMessageBox.information(self, "已删除", f"SOP「{model}」已永久删除。")

    def action_help(self) -> None:
        """帮助对话框：显示版本 + 打开使用手册"""
        # 查找使用手册位置（打包态在 app_dir，开发态在 docs/）
        manual_candidates = [
            paths.app_dir() / "使用说明.html",
            paths.app_dir() / "docs" / "使用说明.html",
            paths.resource_dir() / "docs" / "使用说明.html",
        ]
        manual = next((p for p in manual_candidates if p.exists()), None)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("关于 SOP Generate")
        box.setText("<b>SOP Generate</b>")
        body_lines = [
            f"<p>标准化作业指导书生成器</p>",
            f"<p><b>当前版本：</b>v{__version__}</p>",
            f"<p><b>当前用户：</b>{get_current_user() or '未设置'}</p>",
        ]
        if manual:
            body_lines.append(f"<p><b>使用手册：</b>{manual.name}</p>")
        else:
            body_lines.append("<p><b>使用手册：</b>未找到 使用说明.html 文件</p>")
        box.setInformativeText("".join(body_lines))

        if manual:
            open_btn = box.addButton("打开使用手册", QMessageBox.ActionRole)
        else:
            open_btn = None
        check_update_btn = box.addButton("检查更新", QMessageBox.ActionRole)
        close_btn = box.addButton("关闭", QMessageBox.RejectRole)
        box.setDefaultButton(close_btn)
        box.exec()

        clicked = box.clickedButton()
        if open_btn is not None and clicked is open_btn:
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(manual)))
        elif clicked is check_update_btn:
            self._start_update_check_manual()

    def action_archive(self) -> None:
        """归档定稿：渲染 HTML+PDF（文件名带日期）+ 打包 .sopkg → 用户指定目录"""
        if not self.current:
            QMessageBox.warning(self, "提示", "请先在左侧选择要归档的 SOP")
            return
        if not self._require_user():
            return

        # 先校验
        if not self._ensure_valid_for_export():
            return

        # 先保存
        self.action_save()

        # 选目标文件夹
        dest = QFileDialog.getExistingDirectory(
            self, f"选择归档输出文件夹（{self.current.model}）",
            str(Path.home() / "Documents"),
        )
        if not dest:
            return

        # 弹进度对话框
        model = self.current.model
        self.status.showMessage(f"正在归档 {model}...")
        QApplication.processEvents()

        def progress_cb(stage: str, cur: int, total: int) -> None:
            self.status.showMessage(f"归档 {model}：{stage}（{cur}/{total}）")
            QApplication.processEvents()

        try:
            result = archive_product(model, Path(dest), progress=progress_cb)
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "归档失败",
                                 f"{type(e).__name__}: {e}\n\n{traceback.format_exc()[:600]}")
            self.status.showMessage("")
            return

        pdf_line = f"  · {result['pdf_path'].name}" if result["pdf_path"] else "  · （未生成 PDF — 需安装 Edge/Chrome）"
        QMessageBox.information(
            self, "归档完成",
            f"已归档 {result['archive_name']}\n\n"
            f"目标位置：{result['archive_dir'].parent}\n\n"
            f"产物：\n"
            f"  · {result['archive_dir'].name}/  （工程文件夹，含 HTML/PDF + 源文件）\n"
            f"  · {result['sopkg_path'].name}  （打包文件，可直接发送/邮寄）\n"
            f"  · {result['html_path'].name}\n"
            f"{pdf_line}"
        )
        self.status.showMessage(f"✓ 已归档：{result['archive_name']}")

    def action_export_sopkg(self) -> None:
        if not self.current:
            QMessageBox.warning(self, "提示", "请先选择产品")
            return
        if not self._require_user():
            return
        # 先保存
        self.action_save()

        default_name = f"{self.current.model}.sopkg"
        dst, _ = QFileDialog.getSaveFileName(
            self, "导出 SOP 包",
            str(Path.home() / default_name),
            "SOP 包 (*.sopkg)",
        )
        if not dst:
            return
        try:
            out = export_sopkg(self.current.model, Path(dst))
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
            return
        QMessageBox.information(
            self, "导出完成",
            f"已导出：{out}\n\n可以把这个 .sopkg 文件发给同事，让他用"
            f"\"导入 SOP 包\"按钮打开即可。"
        )

    def action_import_sopkg(self) -> None:
        if not self._require_user():
            return
        src, _ = QFileDialog.getOpenFileName(
            self, "导入 SOP 包",
            str(Path.home()),
            "SOP 包 (*.sopkg *.zip)",
        )
        if not src:
            return
        try:
            model, overwritten = import_sopkg(Path(src))
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
            return
        self._reload_product_list()
        # 选中刚导入的
        for i in range(self.product_list.count()):
            if self.product_list.item(i).data(Qt.UserRole) == model:
                self.product_list.setCurrentRow(i)
                break
        msg = f"已导入 SOP：{model}"
        if overwritten:
            msg += "\n\n（同名已存在，旧版本已备份为 .bak_<时间戳>）"
        QMessageBox.information(self, "导入完成", msg)

    def action_import_legacy(self) -> None:
        src = QFileDialog.getExistingDirectory(
            self, "选择老版本目录（应包含 products/ 子目录）",
            str(Path.home()),
        )
        if not src:
            return
        try:
            result = import_legacy(Path(src))
        except ValueError as e:
            QMessageBox.warning(self, "导入失败", str(e))
            return

        lines = [
            f"✓ 导入产品：{len(result['imported_products'])} 个",
            f"✓ 导入图片：{result['imported_images'][0]} 张",
        ]
        if result['skipped_products']:
            lines.append("")
            lines.append("跳过的产品（同名已存在，未覆盖）：")
            lines.extend(f"  · {n}" for n in result['skipped_products'])

        QMessageBox.information(self, "导入完成", "\n".join(lines))
        self._reload_product_list()
        self.status.showMessage(
            f"已从 {src} 导入 {len(result['imported_products'])} 个产品"
        )

    def action_new_product(self) -> None:
        if not self._require_user():
            return
        model, ok = QInputDialog.getText(
            self, "新建 SOP",
            "产品型号（用作文件夹名，建议简洁）：",
        )
        if not ok or not model.strip():
            return
        model = model.strip()
        try:
            prod = new_product(model)
        except ValueError as e:
            QMessageBox.warning(self, "无法创建", str(e))
            return
        prod.processes.append(copy.deepcopy(DEFAULT_PROCESS))
        prod.save(get_current_user())
        prod.ensure_image_dir()
        self._reload_product_list()
        self.status.showMessage(f"已创建 {model}（图片请放到 {prod.image_dir}）")

    def action_save(self) -> None:
        if not self.current:
            return
        if not self._require_user():
            return
        self.meta_editor.commit()
        self.proc_editor.commit()
        self.current.save(get_current_user())
        self.status.showMessage(f"已保存 {self.current.path.name}")

    def _require_user(self) -> bool:
        """检查是否已设置用户名；未设置则强制弹窗，返回最终是否有用户名。"""
        if is_user_set():
            return True
        self._ask_user_name(force=True)
        return is_user_set()

    def action_export_html(self) -> None:
        if not self._ensure_valid_for_export():
            return
        data = ProductData(self.current.product, self.current.processes, self.current.to_dict())
        path = write_html(data)
        self.status.showMessage(f"HTML 已导出：{path}")
        QMessageBox.information(self, "完成", f"HTML 已导出：\n{path}")

    def action_export_pdf(self) -> None:
        if not self._ensure_valid_for_export():
            return
        data = ProductData(self.current.product, self.current.processes, self.current.to_dict())
        html_path = write_html(data)
        try:
            pdf_path = export_pdf(html_path)
        except Exception as e:
            QMessageBox.critical(self, "PDF 导出失败", str(e))
            return
        self.status.showMessage(f"PDF 已导出：{pdf_path}")
        QMessageBox.information(self, "完成", f"HTML: {html_path}\nPDF:  {pdf_path}")

    def action_clone(self) -> None:
        if not self.current:
            return
        if not self._require_user():
            return
        new_model, ok = QInputDialog.getText(self, "派生新产品", "新型号：")
        if not ok or not new_model.strip():
            return
        try:
            new_prod = clone_product(self.current, new_model.strip())
        except ValueError as e:
            QMessageBox.warning(self, "无法派生", str(e))
            return
        new_prod.save(get_current_user())
        new_prod.ensure_image_dir()
        self._reload_product_list()
        QMessageBox.information(
            self, "派生完成",
            f"已生成 {new_prod.model}\n图片需重新放入：{new_prod.image_dir}"
        )

    def action_open_image_dir(self) -> None:
        if not self.current:
            return
        d = self.current.ensure_image_dir()
        if sys.platform == "darwin":
            import subprocess; subprocess.run(["open", str(d)])
        elif sys.platform == "win32":
            import os; os.startfile(str(d))  # type: ignore
        else:
            import subprocess; subprocess.run(["xdg-open", str(d)])

    def action_add_proc(self) -> None:
        if not self.current:
            return
        self.current.processes.append(copy.deepcopy(DEFAULT_PROCESS))
        self._reload_proc_list()
        self.proc_list.setCurrentRow(len(self.current.processes) - 1)
        self._schedule_preview()

    def action_del_proc(self) -> None:
        if not self.current:
            return
        row = self.proc_list.currentRow()
        if row < 0:
            return
        del self.current.processes[row]
        self._reload_proc_list()
        self._schedule_preview()

    # ---------- 校验 / 预览 ----------
    def _ensure_valid_for_export(self) -> bool:
        if not self.current:
            QMessageBox.warning(self, "提示", "请先选择产品")
            return False
        self.meta_editor.commit()
        self.proc_editor.commit()
        result = validate(self.current.to_dict(), yaml_path=self.current.path)
        if not result.ok:
            QMessageBox.critical(
                self, "校验失败",
                "请先修正以下问题：\n\n" + "\n".join(result.errors)
            )
            return False
        return True

    def _current_image_dir(self) -> Path | None:
        if not self.current:
            return None
        return self.current.ensure_image_dir()

    def _schedule_preview(self) -> None:
        self._preview_timer.start(PREVIEW_DELAY_MS)

    # ---------- 检查更新 ----------
    def _start_update_check(self, manual: bool = False) -> None:
        self._update_manual = manual
        self._update_thread = QThread(self)
        self._update_worker = UpdateCheckWorker()
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.found.connect(self._on_update_check_done)
        self._update_worker.found.connect(self._update_thread.quit)
        self._update_thread.start()

    def _start_update_check_manual(self) -> None:
        if not is_release_configured():
            QMessageBox.information(
                self, "暂未配置",
                "自动更新功能需要在 release.config.json 配置 Gitee 发版仓库。"
                "\n打包发布时由 CI 注入此配置。"
            )
            return
        self.status.showMessage("正在检查更新...")
        self._start_update_check(manual=True)

    def _on_update_check_done(self, info) -> None:
        manual = getattr(self, "_update_manual", False)
        if info is None:
            if manual:
                QMessageBox.warning(self, "检查失败", "无法连接到 Gitee，请检查网络。")
            self.status.showMessage("更新检查失败" if manual else "")
            return
        if not is_newer(info.tag, __version__):
            if manual:
                QMessageBox.information(self, "已是最新", f"当前版本 v{__version__} 已是最新。")
            self.status.showMessage(f"当前 v{__version__} 已是最新")
            return

        # 用户曾"跳过此版本"
        if SKIP_VERSION_FILE.exists():
            try:
                if SKIP_VERSION_FILE.read_text().strip() == info.tag and not manual:
                    return
            except OSError:
                pass

        # 弹窗询问
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("发现新版本")
        box.setText(f"<b>发现新版本 {info.tag}</b><br>当前版本 v{__version__}")
        body = (info.body or "").strip()
        if body:
            short = body[:300] + ("..." if len(body) > 300 else "")
            box.setInformativeText(short)
        update_btn = box.addButton("立即更新", QMessageBox.AcceptRole)
        later_btn = box.addButton("暂不更新", QMessageBox.RejectRole)
        skip_btn  = box.addButton("跳过此版本", QMessageBox.DestructiveRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is update_btn:
            self._launch_updater(info.tag)
        elif clicked is skip_btn:
            try:
                SKIP_VERSION_FILE.write_text(info.tag)
            except OSError:
                pass

    def _launch_updater(self, tag: str) -> None:
        """启动 updater 子进程，自身退出。"""
        import os
        import subprocess

        # 找 updater 可执行文件
        app_dir = paths.app_dir()
        if getattr(sys, "frozen", False):
            # 打包态：updater 在主程序旁
            if sys.platform == "win32":
                updater_exe = app_dir / "updater.exe"
            elif sys.platform == "darwin":
                updater_exe = app_dir / "updater.app" / "Contents" / "MacOS" / "updater"
            else:
                updater_exe = app_dir / "updater"
            if not updater_exe.exists():
                QMessageBox.critical(self, "升级失败", f"未找到 updater 可执行文件：{updater_exe}")
                return
            cmd = [str(updater_exe), "--pid", str(os.getpid()), "--tag", tag, "--app-dir", str(app_dir)]
            subprocess.Popen(cmd, cwd=str(app_dir))
        else:
            # 开发态：直接跑 python -m updater.main
            cmd = [sys.executable, "-m", "updater.main",
                   "--pid", str(os.getpid()), "--tag", tag, "--app-dir", str(app_dir)]
            subprocess.Popen(cmd, cwd=str(paths.resource_dir()))

        # 主程序立即退出，让 updater 接管
        QApplication.quit()

    def _refresh_preview(self) -> None:
        if not self.current:
            return
        self.meta_editor.commit()
        self.proc_editor.commit()
        try:
            data = ProductData(self.current.product, self.current.processes,
                              self.current.to_dict())
            # 用绝对路径让临时文件能正确加载图片
            model = self.current.model or "preview"
            img_dir = self.current.image_dir
            html = render_manual(data, image_base=img_dir.as_uri())
            self._preview_html_path.write_text(html, encoding="utf-8")
            self.preview.load(QUrl.fromLocalFile(str(self._preview_html_path)))
            self.status.showMessage(f"已刷新预览（{model}）")
        except Exception as e:
            self.status.showMessage(f"预览渲染失败：{e}")


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    if not find_browser():
        win.status.showMessage("⚠ 未找到 Chrome/Edge，PDF 导出将不可用；HTML 导出与预览仍可用")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
