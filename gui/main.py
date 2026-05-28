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

paths.ensure_user_dirs()

from gui.editor import ProcessEditor, ProductMetaEditor
from gui.model import (
    DEFAULT_PROCESS, Product, clone_product, import_legacy, list_products,
    new_product,
)


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
        self.setWindowTitle(f"sop_generate v{__version__} · 作业指导书生成器")
        self.resize(1500, 900)

        self.current: Product | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._preview_html_path = Path(tempfile.gettempdir()) / "sop_preview.html"

        self._build_toolbar()
        self._build_central()
        self._build_status()

        self._reload_product_list()

        # 启动后延迟 2 秒后台查更新（不阻塞 UI）
        if is_release_configured():
            QTimer.singleShot(2000, self._start_update_check)

    # ---------- UI 构建 ----------
    def _build_toolbar(self) -> None:
        tb = QToolBar()
        self.addToolBar(tb)

        act_new = QAction("新建产品", self); act_new.triggered.connect(self.action_new_product); tb.addAction(act_new)
        act_import = QAction("导入旧数据", self); act_import.triggered.connect(self.action_import_legacy); tb.addAction(act_import)
        act_save = QAction("保存", self); act_save.triggered.connect(self.action_save); tb.addAction(act_save)
        tb.addSeparator()
        act_update = QAction("检查更新", self); act_update.triggered.connect(self._start_update_check_manual); tb.addAction(act_update)
        tb.addSeparator()
        act_html = QAction("导出 HTML", self); act_html.triggered.connect(self.action_export_html); tb.addAction(act_html)
        act_pdf = QAction("导出 PDF", self); act_pdf.triggered.connect(self.action_export_pdf); tb.addAction(act_pdf)
        tb.addSeparator()
        act_clone = QAction("派生新产品", self); act_clone.triggered.connect(self.action_clone); tb.addAction(act_clone)
        act_open_img = QAction("打开图片目录", self); act_open_img.triggered.connect(self.action_open_image_dir); tb.addAction(act_open_img)
        act_refresh = QAction("刷新预览", self); act_refresh.triggered.connect(self._refresh_preview); tb.addAction(act_refresh)

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
        for p in list_products():
            item = QListWidgetItem(p.stem)
            item.setData(Qt.UserRole, str(p))
            self.product_list.addItem(item)
        if self.product_list.count():
            self.product_list.setCurrentRow(0)

    def _on_product_changed(self, current, previous) -> None:
        if current is None:
            return
        path = Path(current.data(Qt.UserRole))
        try:
            self.current = Product.load(path)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))
            return
        self.meta_editor.load(self.current.product)
        self._reload_proc_list()
        self._schedule_preview()
        self.status.showMessage(f"已加载 {path.name}")

    def _reload_proc_list(self) -> None:
        self.proc_list.clear()
        if not self.current:
            return
        for i, p in enumerate(self.current.processes, start=1):
            star = " ★" if p.get("key") else ""
            self.proc_list.addItem(f"{i}. {p.get('name', '<无名>')}{star}")
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
            f"✓ 导入 YAML：{len(result['imported_yaml'])} 个",
            f"✓ 导入图片：{len(result['imported_images'])} 张",
        ]
        if result['skipped_yaml']:
            lines.append("")
            lines.append("跳过的 YAML（同名已存在，未覆盖）：")
            lines.extend(f"  · {n}" for n in result['skipped_yaml'])
        if result['skipped_images']:
            lines.append("")
            lines.append(f"跳过 {len(result['skipped_images'])} 张图片（同名已存在）")

        QMessageBox.information(self, "导入完成", "\n".join(lines))
        self._reload_product_list()
        self.status.showMessage(
            f"已从 {src} 导入 {len(result['imported_yaml'])} 个产品"
        )

    def action_new_product(self) -> None:
        model, ok = QInputDialog.getText(self, "新建产品", "产品型号（仅字母数字/下划线）：")
        if not ok or not model.strip():
            return
        model = model.strip()
        prod = new_product(model)
        prod.processes.append(copy.deepcopy(DEFAULT_PROCESS))
        prod.save()
        prod.ensure_image_dir()
        self._reload_product_list()
        self.status.showMessage(f"已创建 {prod.path.name}（请补充图片到 {prod.image_dir}）")

    def action_save(self) -> None:
        if not self.current:
            return
        self.meta_editor.commit()
        self.proc_editor.commit()
        self.current.save()
        self.status.showMessage(f"已保存 {self.current.path.name}")

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
        new_model, ok = QInputDialog.getText(self, "派生新产品", "新型号：")
        if not ok or not new_model.strip():
            return
        new_prod = clone_product(self.current, new_model.strip())
        new_prod.save()
        new_prod.ensure_image_dir()
        self._reload_product_list()
        QMessageBox.information(
            self, "派生完成",
            f"已生成 {new_prod.path.name}\n图片需重新放入：{new_prod.image_dir}"
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
