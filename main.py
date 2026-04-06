#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片转PDF工具
支持选择多张图片，预览、排序，生成PDF（每页尺寸与图片比例一致）
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QFileDialog,
    QMessageBox, QAbstractItemView
)
from PyQt6.QtGui import QPixmap, QIcon, QImage
from PyQt6.QtCore import Qt, QSize, pyqtSignal
import img2pdf
from PIL import Image


class ThumbnailListWidget(QListWidget):
    """支持拖拽排序的缩略图列表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setIconSize(QSize(100, 100))
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setSpacing(5)


class ImageToPdfApp(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.image_paths = []  # 存储图片路径
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle('图片转PDF工具')
        self.setMinimumSize(800, 600)

        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 顶部按钮区域
        button_layout = QHBoxLayout()

        self.btn_select = QPushButton('选择图片')
        self.btn_select.clicked.connect(self.select_images)

        self.btn_clear = QPushButton('清空列表')
        self.btn_clear.clicked.connect(self.clear_list)

        self.btn_move_up = QPushButton('上移')
        self.btn_move_up.clicked.connect(self.move_up)

        self.btn_move_down = QPushButton('下移')
        self.btn_move_down.clicked.connect(self.move_down)

        self.btn_generate = QPushButton('生成PDF')
        self.btn_generate.clicked.connect(self.generate_pdf)

        button_layout.addWidget(self.btn_select)
        button_layout.addWidget(self.btn_clear)
        button_layout.addWidget(self.btn_move_up)
        button_layout.addWidget(self.btn_move_down)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_generate)

        main_layout.addLayout(button_layout)

        # 缩略图列表
        self.list_widget = ThumbnailListWidget()
        self.list_widget.itemClicked.connect(self.update_preview)
        self.list_widget.model().rowsMoved.connect(self.on_rows_moved)
        main_layout.addWidget(self.list_widget, stretch=1)

        # 预览区域
        preview_layout = QVBoxLayout()
        preview_label = QLabel('预览')
        preview_layout.addWidget(preview_label)

        self.preview_widget = QLabel('请选择图片')
        self.preview_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_widget.setStyleSheet('QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }')
        self.preview_widget.setMinimumHeight(300)
        self.preview_widget.setScaledContents(False)
        preview_layout.addWidget(self.preview_widget, stretch=2)

        main_layout.addLayout(preview_layout, stretch=2)

    def select_images(self):
        """选择图片文件"""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter('图片文件 (*.jpg *.jpeg *.png *.bmp *.gif *.webp)')

        if file_dialog.exec():
            files = file_dialog.selectedFiles()
            for file_path in files:
                if file_path not in self.image_paths:
                    self.add_image(file_path)

    def add_image(self, file_path):
        """添加图片到列表"""
        self.image_paths.append(file_path)

        # 创建缩略图
        thumbnail = self.create_thumbnail(file_path)
        item = QListWidgetItem()
        item.setIcon(QIcon(thumbnail))
        item.setToolTip(os.path.basename(file_path))
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.list_widget.addItem(item)

    def create_thumbnail(self, file_path):
        """创建缩略图"""
        try:
            with Image.open(file_path) as img:
                img.thumbnail((100, 100), Image.Resampling.LANCZOS)
                # 转换为Qt格式
                if img.mode == 'RGBA':
                    data = img.tobytes('raw', 'RGBA')
                    qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                else:
                    img = img.convert('RGB')
                    data = img.tobytes('raw', 'RGB')
                    qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGB888)
                return QPixmap.fromImage(qimage)
        except Exception as e:
            print(f"创建缩略图失败: {e}")
            return QPixmap()

    def update_preview(self, item):
        """更新预览图片"""
        file_path = item.data(Qt.ItemDataRole.UserRole)

        try:
            with Image.open(file_path) as img:
                # 获取预览区域大小
                preview_size = self.preview_widget.size()

                # 计算缩放比例
                img_ratio = img.width / img.height
                widget_ratio = preview_size.width() / preview_size.height()

                if img_ratio > widget_ratio:
                    new_width = preview_size.width() - 20
                    new_height = int(new_width / img_ratio)
                else:
                    new_height = preview_size.height() - 20
                    new_width = int(new_height * img_ratio)

                # 缩放图片
                img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)

                # 转换为Qt格式
                if img.mode == 'RGBA':
                    data = img.tobytes('raw', 'RGBA')
                    qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                else:
                    img = img.convert('RGB')
                    data = img.tobytes('raw', 'RGB')
                    qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGB888)

                pixmap = QPixmap.fromImage(qimage)
                self.preview_widget.setPixmap(pixmap)
        except Exception as e:
            self.preview_widget.setText(f'预览失败: {e}')

    def on_rows_moved(self):
        """拖拽排序后更新image_paths"""
        self.sync_image_paths()

    def sync_image_paths(self):
        """同步列表顺序到image_paths"""
        new_paths = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            new_paths.append(item.data(Qt.ItemDataRole.UserRole))
        self.image_paths = new_paths

    def move_up(self):
        """上移选中项"""
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, item)
            self.list_widget.setCurrentRow(current_row - 1)
            self.sync_image_paths()

    def move_down(self):
        """下移选中项"""
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row + 1, item)
            self.list_widget.setCurrentRow(current_row + 1)
            self.sync_image_paths()

    def clear_list(self):
        """清空列表"""
        self.list_widget.clear()
        self.image_paths.clear()
        self.preview_widget.clear()
        self.preview_widget.setText('请选择图片')

    def generate_pdf(self):
        """生成PDF文件"""
        if not self.image_paths:
            QMessageBox.warning(self, '警告', '请先选择图片！')
            return

        # 同步列表顺序
        self.sync_image_paths()

        # 选择保存路径
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            '保存PDF',
            '',
            'PDF文件 (*.pdf)'
        )

        if not save_path:
            return

        if not save_path.endswith('.pdf'):
            save_path += '.pdf'

        try:
            # 使用img2pdf生成PDF
            # img2pdf会自动处理每页尺寸与图片一致
            with open(save_path, 'wb') as f:
                f.write(img2pdf.convert(self.image_paths))

            QMessageBox.information(self, '成功', f'PDF已生成:\n{save_path}')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'生成PDF失败:\n{e}')


def main():
    app = QApplication(sys.argv)
    window = ImageToPdfApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()