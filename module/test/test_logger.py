import unittest
import sys
import os
from unittest.mock import patch, mock_open, MagicMock
import datetime

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from module.logger import Logger
from module.info import INFO


class TestLogger(unittest.TestCase):
    """Logger类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        self.test_log_file = os.path.join(os.path.dirname(__file__), "test.log")
        # 确保文件初始状态是不存在的
        if os.path.exists(self.test_log_file):
            try:
                os.remove(self.test_log_file)
            except PermissionError:
                # 处理文件可能被锁定的情况
                pass

    def tearDown(self):
        """测试后的清理工作"""
        # 移除测试日志文件
        if os.path.exists(self.test_log_file):
            try:
                # 尝试多次删除，解决文件锁定问题
                for _ in range(3):
                    try:
                        os.remove(self.test_log_file)
                        break
                    except PermissionError:
                        import time
                        time.sleep(0.1)
            except Exception:
                pass

    @patch('module.logger.os.makedirs')
    @patch('module.logger.open', new_callable=mock_open)
    def test_init_default_log_file(self, mock_file, mock_makedirs):
        """测试使用默认日志文件路径初始化"""
        logger = Logger()
        self.assertIsNotNone(logger.log_file)
        # 修正默认路径检查，根据实际项目结构
        self.assertTrue(logger.log_file.endswith(os.path.join("video2text", "result", "system.log")))
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once()

    @patch('module.logger.os.makedirs')
    @patch('module.logger.open', new_callable=mock_open)
    def test_init_custom_log_file(self, mock_file, mock_makedirs):
        """测试使用自定义日志文件路径初始化"""
        logger = Logger(self.test_log_file)
        self.assertEqual(logger.log_file, self.test_log_file)
        mock_makedirs.assert_called_once()
        mock_file.assert_called_once_with(self.test_log_file, 'a', encoding='utf-8')

    @patch('module.logger.INFO.get')
    @patch('module.logger.open', new_callable=mock_open)
    def test_log_method(self, mock_file, mock_info_get):
        """测试log方法的基本功能"""
        mock_info_get.return_value = "Log started at {timestamp}"
        logger = Logger(self.test_log_file)

        test_message = "Test log message"
        logger.log(test_message, "INFO")

        # 验证文件写入
        handle = mock_file()
        self.assertTrue(any(test_message in call[0][0] for call in handle.write.call_args_list))

    def test_info_method(self):
        """测试info级别的日志记录"""
        with patch.object(Logger, 'log') as mock_log:
            logger = Logger(self.test_log_file)
            test_message = "Test info message"
            logger.info(test_message)
            # 允许log被调用多次，因为初始化时会写入日志头
            self.assertTrue(mock_log.call_count >= 1)
            mock_log.assert_called_with(test_message, "INFO")

    def test_warning_method(self):
        """测试warning级别的日志记录"""
        with patch.object(Logger, 'log') as mock_log:
            logger = Logger(self.test_log_file)
            test_message = "Test warning message"
            logger.warning(test_message)
            self.assertTrue(mock_log.call_count >= 1)
            mock_log.assert_called_with(test_message, "WARNING")

    def test_error_method(self):
        """测试error级别的日志记录"""
        with patch.object(Logger, 'log') as mock_log:
            logger = Logger(self.test_log_file)
            test_message = "Test error message"
            logger.error(test_message)
            self.assertTrue(mock_log.call_count >= 1)
            mock_log.assert_called_with(test_message, "ERROR")

    def test_debug_method(self):
        """测试debug级别的日志记录"""
        with patch.object(Logger, 'log') as mock_log:
            logger = Logger(self.test_log_file)
            test_message = "Test debug message"
            logger.debug(test_message)
            self.assertTrue(mock_log.call_count >= 1)
            mock_log.assert_called_with(test_message, "DEBUG")

    @patch('module.logger.INFO.get')
    @patch('module.logger.open', new_callable=mock_open)
    def test_close_method(self, mock_file, mock_info_get):
        """测试关闭日志文件"""
        mock_info_get.return_value = "Log ended at {timestamp}"
        logger = Logger(self.test_log_file)
        logger.close()

        # 验证文件已关闭
        handle = mock_file()
        handle.write.assert_called()  # 验证写入结束标记
        handle.flush.assert_called()
        handle.close.assert_called_once()
        self.assertIsNone(logger.file)

    @patch('module.logger.INFO.get')
    @patch('module.logger.open', new_callable=mock_open)
    def test_close_method_failure(self, mock_file, mock_info_get):
        """测试关闭日志文件时发生错误的情况"""
        # 设置INFO.get返回包含timestamp参数的格式字符串
        def mock_info_get_side_effect(key, default=""):
            if key == "log_end":
                return "Log ended at {timestamp}"
            elif key == "log_close_error":
                return "日志关闭错误: {error}"
            return default

        mock_info_get.side_effect = mock_info_get_side_effect

        logger = Logger(self.test_log_file)

        # 让close方法抛出异常
        handle = mock_file()
        handle.close.side_effect = IOError("Close error")

        with patch('module.logger.print') as mock_print:
            logger.close()
            # 验证文件对象被设置为None
            self.assertIsNone(logger.file)
            # 验证错误消息被打印
            self.assertTrue(mock_print.call_count >= 1)

    def test_clear_method_failure(self):
        """测试清空日志文件时发生错误的情况"""
        # 先创建一个正常的logger，然后模拟重新打开失败
        logger = Logger(self.test_log_file)
        logger.file = MagicMock()  # 确保file不为None

        # 模拟close方法
        with patch.object(logger, 'close') as mock_close:
            # 让重新打开文件时抛出异常
            with patch('module.logger.open', side_effect=OSError("Permission denied")):
                with patch('module.logger.print') as mock_print:
                    logger.clear()

                    # 验证close被调用
                    mock_close.assert_called_once()
                    # 验证错误消息被打印
                    self.assertTrue(mock_print.call_count >= 1)
                    # 验证文件对象被设置为None
                    self.assertIsNone(logger.file)

    def test_get_log_file_path(self):
        """测试获取日志文件路径"""
        logger = Logger(self.test_log_file)
        self.assertEqual(logger.get_log_file_path(), self.test_log_file)

    @patch('module.logger.os.makedirs')
    @patch('module.logger.open', side_effect=OSError("Permission denied"))
    @patch('module.logger.print')
    def test_init_log_file_error(self, mock_print, mock_open, mock_makedirs):
        """测试初始化日志文件时发生错误的情况"""
        Logger(self.test_log_file)
        # 允许print被调用多次，因为可能有日志结束信息
        self.assertTrue(mock_print.call_count >= 1)

    @patch('module.logger.INFO.get')
    @patch('module.logger.open', new_callable=mock_open)
    def test_log_write_error(self, mock_file, mock_info_get):
        """测试写入日志时发生错误的情况"""
        mock_info_get.return_value = "Log started at {timestamp}"
        logger = Logger(self.test_log_file)

        # 让write方法抛出异常
        handle = mock_file()
        handle.write.side_effect = IOError("Write error")

        with patch('module.logger.print') as mock_print:
            logger.log("Test error message", "INFO")
            # 验证print被调用至少一次（日志头可能也会调用一次）
            self.assertGreaterEqual(mock_print.call_count, 1)
            # 检查是否有包含错误信息的调用
            error_calls = [call for call in mock_print.call_args_list
                          if "error" in str(call).lower()]
            self.assertEqual(len(error_calls), 1)

    def test_init_with_none_log_file(self):
        """测试使用None作为log_file参数初始化"""
        with patch('os.makedirs') as mock_makedirs, \
             patch('module.logger.open', new_callable=mock_open), \
             patch('os.path.dirname') as mock_dirname, \
             patch('os.path.abspath', return_value='D:/video2text/module/logger.py'):
            # 模拟目录结构
            mock_dirname.side_effect = lambda path: {
                'D:/video2text/module/logger.py': 'D:/video2text/module',
                'D:/video2text/module': 'D:/video2text'
            }.get(path, path)

            logger = Logger(log_file=None)
            # 验证使用默认路径
            self.assertIsNotNone(logger.log_file)
            mock_makedirs.assert_called_once()

if __name__ == '__main__':
    unittest.main()
