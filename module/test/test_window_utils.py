"""
window_utils模块的测试用例
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from module.window_utils import WindowMessageBox

class TestWindowUtils(unittest.TestCase):
    """测试window_utils模块"""

    def test_window_message_box_question_method_exists(self):
        """测试question方法存在"""
        self.assertTrue(hasattr(WindowMessageBox, 'question'))

    @patch('module.window_utils.WindowMessageBox.__init__', return_value=None)
    @patch('module.window_utils.WindowMessageBox.setWindowTitle')
    @patch('module.window_utils.WindowMessageBox.setText')
    @patch('module.window_utils.WindowMessageBox.setIcon')
    @patch('module.window_utils.WindowMessageBox.setFont')
    @patch('module.window_utils.WindowMessageBox.setMinimumWidth')
    @patch('module.window_utils.WindowMessageBox.setMinimumHeight')
    @patch('module.window_utils.WindowMessageBox.addButton')
    @patch('module.window_utils.WindowMessageBox.setWindowFlag')
    @patch('module.window_utils.WindowMessageBox.setStandardButtons')
    @patch('module.window_utils.QPushButton')
    @patch('module.window_utils.QFont')
    @patch('module.window_utils.Qt.WindowStaysOnTopHint')
    def test_create_message_box_method_no_buttons(self, mock_stays_on_top, mock_font_class, mock_push_button,
                                     mock_set_standard_buttons, mock_set_window_flag, mock_add_button, mock_set_min_height,
                                     mock_set_min_width, mock_set_font, mock_set_icon, mock_set_text,
                                     mock_set_title, mock_init):
        """测试_create_message_box内部方法（无自定义按钮）"""
        # 创建模拟对象
        mock_push_button_instance = MagicMock()
        mock_push_button.return_value = mock_push_button_instance
        mock_font_instance = MagicMock()
        mock_font_class.return_value = mock_font_instance

        # 直接测试内部方法
        result = WindowMessageBox._create_message_box(WindowMessageBox.Critical, "Test Title", "Test Text")

        # 验证各种方法调用
        mock_init.assert_called_once()
        mock_set_title.assert_called_once_with("Test Title")
        mock_set_text.assert_called_once_with("Test Text")
        mock_set_icon.assert_called_once_with(WindowMessageBox.Critical)
        mock_font_class.assert_called_once()
        mock_font_instance.setPointSize.assert_called_once_with(10)
        mock_set_font.assert_called_once_with(mock_font_instance)
        mock_set_min_width.assert_called_once_with(400)
        mock_set_min_height.assert_called_once_with(200)
        mock_push_button.assert_called_once_with("OK")
        mock_push_button_instance.setFont.assert_called_once_with(mock_font_instance)
        mock_add_button.assert_called_once_with(mock_push_button_instance, WindowMessageBox.AcceptRole)
        mock_set_window_flag.assert_called_once_with(mock_stays_on_top)
        # 验证setStandardButtons没有被调用
        mock_set_standard_buttons.assert_not_called()
        # 验证返回值
        self.assertIsNotNone(result)

    @patch('module.window_utils.WindowMessageBox.__init__', return_value=None)
    @patch('module.window_utils.WindowMessageBox.setWindowTitle')
    @patch('module.window_utils.WindowMessageBox.setText')
    @patch('module.window_utils.WindowMessageBox.setIcon')
    @patch('module.window_utils.WindowMessageBox.setFont')
    @patch('module.window_utils.WindowMessageBox.setMinimumWidth')
    @patch('module.window_utils.WindowMessageBox.setMinimumHeight')
    @patch('module.window_utils.WindowMessageBox.addButton')
    @patch('module.window_utils.WindowMessageBox.setWindowFlag')
    @patch('module.window_utils.WindowMessageBox.setStandardButtons')
    @patch('module.window_utils.QFont')
    @patch('module.window_utils.Qt.WindowStaysOnTopHint')
    def test_create_message_box_method_with_buttons(self, mock_stays_on_top, mock_font_class,
                                     mock_set_standard_buttons, mock_set_window_flag, mock_add_button, mock_set_min_height,
                                     mock_set_min_width, mock_set_font, mock_set_icon, mock_set_text,
                                     mock_set_title, mock_init):
        """测试_create_message_box内部方法（有自定义按钮）"""
        # 创建模拟对象
        mock_font_instance = MagicMock()
        mock_font_class.return_value = mock_font_instance
        test_buttons = WindowMessageBox.Yes | WindowMessageBox.No

        # 直接测试内部方法
        result = WindowMessageBox._create_message_box(WindowMessageBox.Question, "Test Title", "Test Text", test_buttons)

        # 验证各种方法调用
        mock_init.assert_called_once()
        mock_set_title.assert_called_once_with("Test Title")
        mock_set_text.assert_called_once_with("Test Text")
        mock_set_icon.assert_called_once_with(WindowMessageBox.Question)
        mock_font_class.assert_called_once()
        mock_font_instance.setPointSize.assert_called_once_with(10)
        mock_set_font.assert_called_once_with(mock_font_instance)
        mock_set_min_width.assert_called_once_with(400)
        mock_set_min_height.assert_called_once_with(200)
        mock_set_standard_buttons.assert_called_once_with(test_buttons)
        # 验证addButton没有被调用
        mock_add_button.assert_not_called()
        mock_set_window_flag.assert_called_once_with(mock_stays_on_top)
        # 验证返回值
        self.assertIsNotNone(result)

    @patch('module.window_utils.WindowMessageBox._create_message_box')
    @patch('module.window_utils.WindowMessageBox.exec_')
    def test_critical_method(self, mock_exec, mock_create_message_box):
        """测试critical方法"""
        # 设置模拟对象
        mock_msg_box = MagicMock()
        mock_create_message_box.return_value = mock_msg_box

        # 调用方法
        WindowMessageBox.critical(None, "Error", "Something went wrong")

        # 验证_create_message_box被正确调用
        mock_create_message_box.assert_called_once_with(
            WindowMessageBox.Critical, "Error", "Something went wrong"
        )
        # 验证exec_被调用
        mock_msg_box.exec_.assert_called_once()

    @patch('module.window_utils.WindowMessageBox._create_message_box')
    @patch('module.window_utils.WindowMessageBox.exec_')
    def test_warning_method(self, mock_exec, mock_create_message_box):
        """测试warning方法"""
        # 设置模拟对象
        mock_msg_box = MagicMock()
        mock_create_message_box.return_value = mock_msg_box

        # 调用方法
        WindowMessageBox.warning(None, "Warning", "This is a warning")

        # 验证调用
        mock_create_message_box.assert_called_once_with(
            WindowMessageBox.Warning, "Warning", "This is a warning"
        )
        mock_msg_box.exec_.assert_called_once()

    @patch('module.window_utils.WindowMessageBox._create_message_box')
    @patch('module.window_utils.WindowMessageBox.exec_')
    def test_information_method(self, mock_exec, mock_create_message_box):
        """测试information方法"""
        # 设置模拟对象
        mock_msg_box = MagicMock()
        mock_create_message_box.return_value = mock_msg_box

        # 调用方法
        WindowMessageBox.information(None, "Info", "This is information")

        # 验证调用
        mock_create_message_box.assert_called_once_with(
            WindowMessageBox.Information, "Info", "This is information"
        )
        mock_msg_box.exec_.assert_called_once()

    @patch('module.window_utils.WindowMessageBox._create_message_box')
    def test_question_method(self, mock_create_message_box):
        """测试question方法"""
        # 设置模拟对象
        mock_msg_box = MagicMock()
        mock_msg_box.exec_.return_value = WindowMessageBox.Yes
        mock_create_message_box.return_value = mock_msg_box

        # 调用方法
        result = WindowMessageBox.question(None, "Question", "Do you want to proceed?")

        # 验证调用
        mock_create_message_box.assert_called_once_with(
            WindowMessageBox.Question, "Question", "Do you want to proceed?",
            WindowMessageBox.Yes | WindowMessageBox.No
        )
        mock_msg_box.exec_.assert_called_once()
        self.assertEqual(result, WindowMessageBox.Yes)


if __name__ == '__main__':
    unittest.main()
