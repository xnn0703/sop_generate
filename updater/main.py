"""sop_generate updater · 独立升级程序

用法（通常由主程序唤起）：
    updater[.exe] --pid <主程序PID> --tag <目标版本tag> --app-dir <主程序所在目录>

工作流程：
    1. 等待主程序 PID 退出
    2. 调 Gitee API 拿目标 release info
    3. 下载所有 .7z 分卷到临时目录
    4. 合并分卷 + py7zr 解压
    5. 覆盖 app-dir 内除 products/ assets/ output/ 外的所有文件
    6. 启动新版本主程序
    7. 自身退出
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import traceback
from pathlib import Path

# 确保能 import core
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout,
    QMessageBox,
)

from core.updater import (
    apply_update, check_latest, download_release, relaunch, wait_for_pid,
)


class UpdateWorker(QObject):
    """后台线程跑升级流程"""

    stage_changed = Signal(str)                # 当前阶段文字
    progress      = Signal(int, int)           # (current_bytes, total_bytes)
    finished_ok   = Signal(str)                # 新主程序路径
    failed        = Signal(str)                # 错误信息

    def __init__(self, pid: int, app_dir: Path) -> None:
        super().__init__()
        self.pid = pid
        self.app_dir = app_dir

    def run(self) -> None:
        try:
            self.stage_changed.emit("等待主程序退出...")
            wait_for_pid(self.pid, timeout=30.0)

            self.stage_changed.emit("查询最新版本...")
            info = check_latest()
            if info is None:
                self.failed.emit("无法获取最新版本信息（网络异常或仓库未配置）")
                return

            self.stage_changed.emit(f"下载 {info.tag}...")
            tmp_root = Path(tempfile.gettempdir()) / f"sop_generate_update_{info.tag}"
            tmp_root.mkdir(parents=True, exist_ok=True)

            def dl_progress(stage: str, cur: int, total: int) -> None:
                self.stage_changed.emit(stage)
                self.progress.emit(cur, total)

            parts = download_release(info, tmp_root, dl_progress)

            self.stage_changed.emit("解压并应用更新...")
            self.progress.emit(0, 0)   # 切到不确定进度
            new_exe = apply_update(parts, self.app_dir, dl_progress)

            self.finished_ok.emit(str(new_exe))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


class UpdaterDialog(QDialog):
    """升级进度对话框"""

    def __init__(self, pid: int, tag: str, app_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle(f"sop_generate 升级到 {tag}")
        self.setMinimumWidth(540)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.label = QLabel("准备中...")
        self.label.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)   # 不确定进度
        self.close_btn = QPushButton("取消")
        self.close_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>正在升级到 {tag}</b>"))
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addStretch()
        layout.addWidget(self.close_btn)

        self._new_exe: Path | None = None

        # 后台线程
        self.thread = QThread(self)
        self.worker = UpdateWorker(pid, app_dir)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.stage_changed.connect(self._on_stage)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.thread.start()

    def _on_stage(self, text: str) -> None:
        self.label.setText(text)

    def _on_progress(self, cur: int, total: int) -> None:
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(cur)
        else:
            self.bar.setRange(0, 0)

    def _on_done(self, new_exe: str) -> None:
        self._new_exe = Path(new_exe)
        self.label.setText(f"✓ 升级完成，正在启动新版本...")
        self.bar.setRange(0, 1); self.bar.setValue(1)
        self.close_btn.setText("启动并退出")
        self.close_btn.clicked.disconnect()
        self.close_btn.clicked.connect(self._launch_and_exit)
        # 自动启动（无需用户再点）
        self._launch_and_exit()

    def _on_failed(self, msg: str) -> None:
        self.bar.setRange(0, 1); self.bar.setValue(0)
        QMessageBox.critical(self, "升级失败", msg)
        self.close_btn.setText("关闭")

    def _launch_and_exit(self) -> None:
        if self._new_exe is not None:
            try:
                relaunch(self._new_exe)
            except Exception as e:
                QMessageBox.warning(self, "启动失败", f"无法启动新版本：{e}\n请手动打开：{self._new_exe}")
        self.accept()
        QApplication.quit()


def main() -> int:
    ap = argparse.ArgumentParser(description="sop_generate updater")
    ap.add_argument("--pid", type=int, required=True, help="主程序 PID")
    ap.add_argument("--tag", required=True, help="目标版本 tag，如 v1.1.0")
    ap.add_argument("--app-dir", type=Path, required=True, help="主程序所在目录")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    dlg = UpdaterDialog(args.pid, args.tag, args.app_dir.resolve())
    dlg.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
