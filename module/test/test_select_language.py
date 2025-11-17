import unittest
import sys
import os
import time
from unittest.mock import patch, MagicMock, mock_open
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from module.select_language import LanguageSelectionDialog
from module.config import Config

class TestLanguageSelectionDialog(unittest.TestCase):
    """LanguageSelectionDialog类的单元测试"""

    def setUp(self):
        """测试前的准备工作，仅进行配置备份"""
        # 备份并移除已存在的配置文件
        self.config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'language_config.ini'
        )
        self.config_backup = None
        if os.path.exists(self.config_path):
            with open(self.config_path, 'rb') as f:
                self.config_backup = f.read()
            os.remove(self.config_path)

        # 确保只有一个QApplication实例
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

        self.dialog = None

    def tearDown(self):
        """测试后的清理工作，确保资源正确释放"""
        # 安全关闭对话框
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
            self.app.processEvents()

        # 恢复配置文件
        if self.config_backup is not None:
            with open(self.config_path, 'wb') as f:
                f.write(self.config_backup)

        # 清除所有事件
        self.app.processEvents()

    def test_get_selected_language(self):
        """测试获取选择的语言"""
        self.dialog = LanguageSelectionDialog()
        # 测试默认值
        self.assertEqual(self.dialog.get_selected_language(), Config.LANGUAGE_CHINESE)

        # 测试修改后的值
        self.dialog.selected_language = Config.LANGUAGE_ENGLISH
        self.assertEqual(self.dialog.get_selected_language(), Config.LANGUAGE_ENGLISH)
        self.app.processEvents()

    def test_radio_button_connections(self):
        """测试单选按钮连接是否正确，使用信号发射代替鼠标点击"""
        self.dialog = LanguageSelectionDialog()

        # 使用信号发射代替鼠标点击
        self.dialog.zh_radio.setChecked(True)
        self.app.processEvents()
        self.assertEqual(self.dialog.selected_language, Config.LANGUAGE_CHINESE)

        self.dialog.en_radio.setChecked(True)
        self.app.processEvents()
        self.assertEqual(self.dialog.selected_language, Config.LANGUAGE_ENGLISH)

        self.dialog.ja_radio.setChecked(True)
        self.app.processEvents()
        self.assertEqual(self.dialog.selected_language, Config.LANGUAGE_JAPANESE)

        self.dialog.ko_radio.setChecked(True)
        self.app.processEvents()
        self.assertEqual(self.dialog.selected_language, Config.LANGUAGE_KOREAN)

    def test_setup_font(self):
        """测试_setup_font方法，确保字体设置逻辑被覆盖"""
        # 创建对话框实例
        self.dialog = LanguageSelectionDialog()

        # 测试中文语言的字体设置
        self.dialog.selected_language = Config.LANGUAGE_CHINESE
        # 直接调用_setup_font方法，这将覆盖之前未测试的代码行
        self.dialog._setup_font()
        # 验证字体被正确设置
        font = self.dialog.font()
        self.assertEqual(font.pointSize(), 9)

        # 测试英文语言的字体设置
        self.dialog.selected_language = Config.LANGUAGE_ENGLISH
        self.dialog._setup_font()
        font = self.dialog.font()
        self.assertEqual(font.pointSize(), 9)

        # 测试日文语言的字体设置
        self.dialog.selected_language = Config.LANGUAGE_JAPANESE
        self.dialog._setup_font()
        font = self.dialog.font()
        self.assertEqual(font.pointSize(), 9)

        # 测试韩文语言的字体设置
        self.dialog.selected_language = Config.LANGUAGE_KOREAN
        self.dialog._setup_font()
        font = self.dialog.font()
        self.assertEqual(font.pointSize(), 9)

        # 测试其他语言的字体设置（默认情况）
        self.dialog.selected_language = "unknown_language"
        self.dialog._setup_font()
        font = self.dialog.font()
        self.assertEqual(font.pointSize(), 9)

        # 清理资源
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

if __name__ == '__main__':
    unittest.main()
