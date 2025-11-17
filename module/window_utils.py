"""
UI工具类模块，提供统一的UI组件样式和工具方法
"""
# pylint: disable=E0611
from PyQt5.QtWidgets import QMessageBox, QPushButton
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class WindowMessageBox(QMessageBox):
    """自定义消息框类，提供统一的样式和行为"""

    @staticmethod
    def _create_message_box(icon_type, title, text, buttons=None):
        """内部方法：创建并配置消息框"""
        # 创建消息框实例
        msg_box = WindowMessageBox()

        # 设置基本属性
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon_type)

        # 设置字体大小
        font = QFont()
        font.setPointSize(10)
        msg_box.setFont(font)

        # 设置最小窗口大小
        msg_box.setMinimumWidth(400)
        msg_box.setMinimumHeight(200)

        # 添加按钮
        if buttons is None:
            # 创建自定义按钮并居中
            ok_button = QPushButton("OK")
            ok_button.setFont(font)
            msg_box.addButton(ok_button, WindowMessageBox.AcceptRole)
        else:
            # 使用标准按钮
            msg_box.setStandardButtons(buttons)

        # 居中显示
        msg_box.setWindowFlag(Qt.WindowStaysOnTopHint)

        return msg_box

    @staticmethod
    def critical(_parent, title, text):
        """显示统一风格的错误消息框"""
        msg_box = WindowMessageBox._create_message_box(
            WindowMessageBox.Critical, title, text
        )
        msg_box.exec_()

    @staticmethod
    def warning(_parent, title, text):
        """显示统一风格的警告消息框"""
        msg_box = WindowMessageBox._create_message_box(
            WindowMessageBox.Warning, title, text
        )
        msg_box.exec_()

    @staticmethod
    def information(_parent, title, text):
        """显示统一风格的信息消息框"""
        msg_box = WindowMessageBox._create_message_box(
            WindowMessageBox.Information, title, text
        )
        msg_box.exec_()

    @staticmethod
    def question(_parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No):
        """显示统一风格的问题消息框"""
        msg_box = WindowMessageBox._create_message_box(
            WindowMessageBox.Question, title, text, buttons
        )
        return msg_box.exec_()
