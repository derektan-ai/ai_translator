import unittest
import sys
import os
from unittest.mock import patch, MagicMock, mock_open
import requests
import dashscope
from PyQt5 import QtWidgets

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from module.network_checker import NetworkChecker
from module.info import INFO


class TestNetworkChecker(unittest.TestCase):
    """NetworkChecker类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建模拟对象
        self.mock_config = MagicMock()
        self.mock_config.api_key = "test_api_key"
        self.mock_logger = MagicMock()
        self.mock_language = "en"
        self.mock_callback = MagicMock()

        # 创建测试实例
        self.network_checker = NetworkChecker(
            self.mock_config,
            self.mock_logger,
            self.mock_language,
            self.mock_callback
        )

    def test_initialization(self):
        """测试NetworkChecker初始化"""
        self.assertEqual(self.network_checker.config, self.mock_config)
        self.assertEqual(self.network_checker.logger, self.mock_logger)
        self.assertEqual(self.network_checker.language, self.mock_language)
        self.assertEqual(self.network_checker.update_callback, self.mock_callback)
        self.assertFalse(self.network_checker._running)
        self.assertIsNone(self.network_checker._thread)

    @patch('module.network_checker.threading.Thread')
    def test_start_checking(self, mock_thread):
        """测试启动网络检查线程"""
        self.network_checker.start_checking(interval=5)

        self.assertTrue(self.network_checker._running)
        mock_thread.assert_called_once()
        self.assertIsNotNone(self.network_checker._thread)
        mock_thread.return_value.start.assert_called_once()

    @patch('module.network_checker.time.sleep')
    def test_stop_checking(self, mock_sleep):
        """测试停止网络检查线程"""
        # 创建一个模拟线程
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True  # 线程处于活动状态

        # 先启动线程并设置模拟线程
        self.network_checker.start_checking()
        self.network_checker._thread = mock_thread

        self.network_checker.stop_checking()

        self.assertFalse(self.network_checker._running)
        mock_thread.join.assert_called_once_with(timeout=5)

    @patch('module.network_checker.time.sleep')
    def test_stop_checking_thread_alive(self, mock_sleep):
        """测试停止仍在运行的网络检查线程"""
        # 创建一个模拟线程，第一次检查时活着，join后仍然活着
        mock_thread = MagicMock()
        mock_thread.is_alive.side_effect = [True, True]

        # 先启动线程并设置模拟线程
        self.network_checker.start_checking()
        self.network_checker._thread = mock_thread

        self.network_checker.stop_checking()

        # 验证警告日志被调用
        self.mock_logger.warning.assert_called_once_with(
            INFO.get("network_thread_exit_error", self.mock_language)
        )
        mock_thread.join.assert_called_once_with(timeout=5)

    @patch.object(NetworkChecker, 'check_network_status')
    @patch('module.network_checker.time.sleep')
    def test_check_loop(self, mock_sleep, mock_check_status):
        """测试网络检查循环"""
        mock_check_status.return_value = True
        self.network_checker._running = True

        # 使用线程运行检查循环并在短时间后停止
        def run_and_stop():
            # 限制循环执行次数，防止无限循环
            loop_count = 0
            while self.network_checker._running and loop_count < 2:
                self.network_checker._check_loop(0.1)
                loop_count += 1

        import threading
        test_thread = threading.Thread(target=run_and_stop)
        test_thread.start()
        # 给循环一些时间运行
        import time
        time.sleep(0.2)
        # 停止循环
        self.network_checker._running = False
        test_thread.join(timeout=1.0)  # 添加超时机制

        self.assertTrue(mock_check_status.called)
        self.assertTrue(self.mock_callback.called)
        self.assertTrue(mock_sleep.called)

    @patch.object(NetworkChecker, 'check_network_status')
    @patch('module.network_checker.time.sleep')
    def test_check_loop_exception(self, mock_sleep, mock_check_status):
        """测试网络检查循环中的异常处理"""
        # 创建异常实例
        exception = requests.exceptions.ConnectionError("Test error")
        mock_check_status.side_effect = exception

        # 使用计数器和事件控制执行次数
        error_handler_count = 0
        from threading import Event
        loop_event = Event()  # 用于控制循环执行次数的事件

        # 只允许执行一次异常处理
        def track_error(*args, **kwargs):
            nonlocal error_handler_count
            if not loop_event.is_set():
                error_handler_count += 1
                loop_event.set()  # 触发一次后标记事件

        self.mock_logger.error.side_effect = track_error

        # 启动检查线程
        self.network_checker.start_checking(interval=0.1)

        # 等待事件触发或超时
        loop_event.wait(timeout=0.1)

        # 立即停止检查
        self.network_checker.stop_checking()

        # 确保状态已停止
        self.assertFalse(self.network_checker._running)

        # 验证异常处理逻辑被正确调用一次
        self.assertEqual(error_handler_count, 1)
        self.assertTrue(mock_sleep.called)

    @patch('module.network_checker.requests.head')
    def test_check_internet_connection_success(self, mock_head):
        """测试网络连接检查成功的情况"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        result = self.network_checker.check_internet_connection(show_error=False)
        self.assertTrue(result)
        mock_head.assert_called_once()

    @patch('module.network_checker.requests.head')
    @patch('module.network_checker.message_center.show_critical')
    @patch('module.network_checker.QtWidgets.QApplication')
    def test_check_internet_connection_failure(self, mock_app, mock_message_center, mock_head):
        """测试网络连接检查失败的情况"""
        # 模拟所有请求都失败
        mock_head.side_effect = requests.exceptions.RequestException("Connection failed")

        result = self.network_checker.check_internet_connection()
        self.assertFalse(result)
        self.assertEqual(mock_head.call_count, 3)  # 测试三个网站
        mock_message_center.assert_called_once()

    @patch('module.network_checker.dashscope.Generation.call')
    def test_check_dashscope_connection_success(self, mock_generation_call):
        """测试Dashscope连接检查成功的情况"""
        # 模拟成功响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_generation_call.return_value = mock_response

        result = self.network_checker.check_dashscope_connection(
            "valid_api_key",
            show_error=False
        )
        self.assertTrue(result)
        mock_generation_call.assert_called_once()

    @patch('module.network_checker.message_center.show_critical')
    def test_check_dashscope_connection_no_api_key(self, mock_message_center):
        """测试API密钥缺失的情况"""
        result = self.network_checker.check_dashscope_connection("", show_error=False)
        self.assertFalse(result)
        mock_message_center.assert_not_called()  # 因为show_error=False

    @patch('module.network_checker.message_center.show_critical')
    @patch('module.network_checker.QtWidgets.QApplication')
    def test_check_dashscope_connection_no_api_key_with_error(self, mock_app, mock_message_center):
        """测试API密钥缺失且显示错误的情况"""
        # 模拟QApplication.instance()返回None
        mock_app.instance.return_value = None

        result = self.network_checker.check_dashscope_connection("", show_error=True)
        self.assertFalse(result)
        mock_message_center.assert_called_once()
        # 使用message_center后不再需要显式创建QApplication实例
        # 移除对QApplication创建的断言

    @patch('module.network_checker.message_center.show_critical')
    @patch('module.network_checker.QtWidgets.QApplication')
    def test_check_dashscope_connection_no_api_key_with_existing_ui(self, mock_app, mock_message_center):
        """测试API密钥缺失且QApplication已存在的情况"""
        # 模拟QApplication.instance()返回一个实例
        mock_instance = MagicMock()
        mock_app.instance.return_value = mock_instance

        result = self.network_checker.check_dashscope_connection("", show_error=True)
        self.assertFalse(result)
        mock_message_center.assert_called_once()
        # 确保没有创建新的QApplication实例
        mock_app.assert_not_called()

    @patch('module.network_checker.dashscope.Generation.call')
    @patch('module.network_checker.QtWidgets.QMessageBox.critical')
    def test_check_dashscope_connection_invalid_key(self, mock_message_center, mock_generation_call):
        """测试API密钥无效的情况"""
        # 模拟401错误（未授权）
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_generation_call.return_value = mock_response

        result = self.network_checker.check_dashscope_connection(
            "invalid_api_key",
            show_error=False
        )
        self.assertFalse(result)

    @patch('module.network_checker.dashscope.Generation.call')
    @patch('module.network_checker.QtWidgets.QMessageBox.critical')
    def test_check_dashscope_connection_other_error(self, mock_message_center, mock_generation_call):
        """测试API返回其他错误状态码的情况"""
        # 模拟500错误（服务器内部错误）
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_generation_call.return_value = mock_response

        result = self.network_checker.check_dashscope_connection(
            "test_api_key",
            show_error=False
        )
        self.assertFalse(result)

    @patch('module.network_checker.dashscope.Generation.call')
    @patch('module.network_checker.message_center.show_critical')
    @patch('module.network_checker.QtWidgets.QApplication')
    def test_check_dashscope_connection_error_with_new_ui(self, mock_app, mock_message_center, mock_generation_call):
        """测试Dashscope连接错误且QApplication不存在的情况"""
        # 模拟QApplication.instance()返回None
        mock_app.instance.return_value = None
        # 模拟500错误
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_generation_call.return_value = mock_response

        result = self.network_checker.check_dashscope_connection(
            "test_api_key",
            show_error=True
        )
        self.assertFalse(result)
        mock_message_center.assert_called_once()
        # 使用message_center后不再需要显式创建和退出QApplication实例
        # mock_app.assert_called_once()
        # mock_app.return_value.exit.assert_called_once()

    @patch('module.network_checker.dashscope.Generation.call')
    @patch('module.network_checker.QtWidgets.QMessageBox.critical')
    def test_check_dashscope_connection_request_exception(self, mock_msgbox, mock_generation_call):
        """测试Dashscope连接请求异常的情况"""
        mock_generation_call.side_effect = requests.exceptions.RequestException("Connection error")

        result = self.network_checker.check_dashscope_connection(
            "test_api_key",
            show_error=False
        )
        self.assertFalse(result)

    @patch('module.network_checker.dashscope.Generation.call')
    @patch('module.network_checker.QtWidgets.QMessageBox.critical')
    def test_check_dashscope_connection_value_error(self, mock_msgbox, mock_generation_call):
        """测试Dashscope连接值错误的情况"""
        # 模拟一般ValueError异常
        mock_generation_call.side_effect = ValueError("Value error")

        result = self.network_checker.check_dashscope_connection(
            "test_api_key",
            show_error=False
        )
        self.assertFalse(result)

    @patch('module.network_checker.dashscope.Generation.call')
    @patch('module.network_checker.QtWidgets.QMessageBox.critical')
    def test_check_dashscope_connection_api_key_value_error(self, mock_msgbox, mock_generation_call):
        """测试与API密钥相关的ValueError异常"""
        # 模拟包含API密钥相关短语的ValueError异常
        error_msg = "Invalid API key"
        mock_generation_call.side_effect = ValueError(error_msg)

        result = self.network_checker.check_dashscope_connection(
            "test_api_key",
            show_error=False
        )
        self.assertFalse(result)

    @patch('module.network_checker.requests.head')
    @patch('module.network_checker.message_center.show_critical')
    @patch('module.network_checker.QtWidgets.QApplication')
    def test_check_internet_connection_failure_with_ui(self, mock_app, mock_message_center, mock_head):
        """测试网络连接失败且显示UI错误的情况"""
        # 模拟QApplication.instance()返回None
        mock_app.instance.return_value = None
        # 模拟所有请求都失败
        mock_head.side_effect = requests.exceptions.RequestException("Connection failed")

        result = self.network_checker.check_internet_connection(show_error=True)
        self.assertFalse(result)
        mock_message_center.assert_called_once()
        # 使用message_center后不再需要显式创建QApplication实例
        # 移除对QApplication创建的断言

    @patch('module.network_checker.requests.head')
    @patch('module.network_checker.message_center.show_critical')
    @patch('module.network_checker.QtWidgets.QApplication')
    def test_check_internet_connection_failure_with_existing_ui(self, mock_app, mock_message_center, mock_head):
        """测试网络连接失败且QApplication已存在的情况"""
        # 模拟QApplication.instance()返回一个实例
        mock_instance = MagicMock()
        mock_app.instance.return_value = mock_instance
        # 模拟所有请求都失败
        mock_head.side_effect = requests.exceptions.RequestException("Connection failed")

        result = self.network_checker.check_internet_connection(show_error=True)
        self.assertFalse(result)
        mock_message_center.assert_called_once()
        # 确保没有创建新的QApplication实例
        mock_app.assert_not_called()

    @patch('module.network_checker.requests.head')
    def test_check_internet_connection_partial_success(self, mock_head):
        """测试部分网站连接失败但最终成功的情况"""
        # 模拟前两个请求失败，第三个请求成功
        mock_head.side_effect = [
            requests.exceptions.RequestException("Fail 1"),
            requests.exceptions.RequestException("Fail 2"),
            MagicMock(status_code=200)
        ]

        result = self.network_checker.check_internet_connection(show_error=False)
        self.assertTrue(result)
        self.assertEqual(mock_head.call_count, 3)

    @patch('module.network_checker.requests.head')
    def test_check_internet_connection_redirect_success(self, mock_head):
        """测试重定向后的连接成功情况"""
        # 模拟重定向后的成功响应
        mock_response = MagicMock()
        mock_response.status_code = 302  # 重定向
        mock_head.return_value = mock_response

        result = self.network_checker.check_internet_connection(show_error=False)
        self.assertTrue(result)

    @patch.object(NetworkChecker, 'check_network_status')
    @patch('module.network_checker.time.sleep')
    def test_check_loop_timeout_exception(self, mock_sleep, mock_check_status):
        """测试网络检查循环中超时异常的处理"""
        exception = requests.exceptions.Timeout("Test timeout")
        mock_check_status.side_effect = exception

        # 使用计数器和事件控制执行次数
        warning_handler_count = 0
        from threading import Event
        loop_event = Event()

        def track_warning(*args, **kwargs):
            nonlocal warning_handler_count
            if not loop_event.is_set():
                warning_handler_count += 1
                loop_event.set()

        self.mock_logger.warning.side_effect = track_warning

        self.network_checker.start_checking(interval=0.1)
        loop_event.wait(timeout=0.1)
        self.network_checker.stop_checking()

        self.assertEqual(warning_handler_count, 1)

    @patch.object(NetworkChecker, 'check_network_status')
    @patch('module.network_checker.time.sleep')
    def test_check_loop_other_exception(self, mock_sleep, mock_check_status):
        """测试网络检查循环中其他异常的处理"""
        exception = Exception("Other error")
        mock_check_status.side_effect = exception

        # 使用计数器和事件控制执行次数
        error_handler_count = 0
        from threading import Event
        loop_event = Event()

        def track_error(*args, **kwargs):
            nonlocal error_handler_count
            if not loop_event.is_set():
                error_handler_count += 1
                loop_event.set()

        self.mock_logger.error.side_effect = track_error

        self.network_checker.start_checking(interval=0.1)
        loop_event.wait(timeout=0.1)
        self.network_checker.stop_checking()

        self.assertEqual(error_handler_count, 1)

    @patch.object(NetworkChecker, 'check_dashscope_connection')
    @patch.object(NetworkChecker, 'check_internet_connection')
    def test_check_network_status_both_ok(self, mock_internet, mock_dashscope):
        """测试网络和API都正常的情况"""
        mock_internet.return_value = True
        mock_dashscope.return_value = True

        result = self.network_checker.check_network_status("test_api_key")
        self.assertTrue(result)
        mock_internet.assert_called_once()
        mock_dashscope.assert_called_once_with("test_api_key")

    @patch.object(NetworkChecker, 'check_dashscope_connection')
    @patch.object(NetworkChecker, 'check_internet_connection')
    def test_check_network_status_internet_failed(self, mock_internet, mock_dashscope):
        """测试网络不正常的情况"""
        mock_internet.return_value = False
        mock_dashscope.return_value = True  # 这个应该不会被调用

        result = self.network_checker.check_network_status("test_api_key")
        self.assertFalse(result)
        mock_internet.assert_called_once()
        mock_dashscope.assert_not_called()

    @patch.object(NetworkChecker, 'check_dashscope_connection')
    @patch.object(NetworkChecker, 'check_internet_connection')
    def test_check_network_status_internet_condition(self, mock_internet, mock_dashscope):
        """专门测试check_network_status方法中的互联网连接检查条件"""
        # 设置dashscope方法返回True，避免异常
        mock_dashscope.return_value = True

        # 测试互联网连接失败的情况（覆盖if条件为True的情况）
        mock_internet.return_value = False

        result = self.network_checker.check_network_status("any_api_key")

        self.assertFalse(result)
        mock_internet.assert_called_once()
        mock_dashscope.assert_not_called()  # 确认dashscope方法没有被调用

        # 重置mock
        mock_internet.reset_mock()
        mock_dashscope.reset_mock()

        # 测试互联网连接成功的情况（覆盖if条件为False的情况）
        mock_internet.return_value = True

        result = self.network_checker.check_network_status("any_api_key")

        # 验证if条件为False时的执行路径
        mock_internet.assert_called_once()
        mock_dashscope.assert_called_once_with("any_api_key")  # 确认dashscope方法被调用了
        self.assertTrue(result)

    @patch.object(NetworkChecker, 'check_dashscope_connection')
    @patch.object(NetworkChecker, 'check_internet_connection')
    def test_check_network_status_api_failed(self, mock_internet, mock_dashscope):
        """测试网络正常但API不正常的情况"""
        mock_internet.return_value = True
        mock_dashscope.return_value = False

        result = self.network_checker.check_network_status("test_api_key")
        self.assertFalse(result)
        mock_internet.assert_called_once()
        mock_dashscope.assert_called_once_with("test_api_key")

    @patch.object(NetworkChecker, 'check_dashscope_connection')
    @patch.object(NetworkChecker, 'check_internet_connection')
    def test_check_network_status_dashscope_verification(self, mock_internet, mock_dashscope):
        """专门测试check_network_status方法中的dashscope连接验证部分"""
        # 关键设置：确保互联网连接正常，这样才会执行到dashscope验证
        mock_internet.return_value = True
        # 设置dashscope返回True
        mock_dashscope.return_value = True

        # 调用被测方法
        api_key = "unique_test_api_key_123"
        result = self.network_checker.check_network_status(api_key)

        # 严格验证调用顺序和参数
        mock_internet.assert_called_once()
        mock_dashscope.assert_called_once_with(api_key)
        # 验证返回值
        self.assertTrue(result)

        # 测试dashscope返回False的情况
        mock_internet.reset_mock()
        mock_dashscope.reset_mock()
        mock_internet.return_value = True
        mock_dashscope.return_value = False

        result = self.network_checker.check_network_status(api_key)

        # 再次验证调用和结果
        mock_internet.assert_called_once()
        mock_dashscope.assert_called_once_with(api_key)
        self.assertFalse(result)

    @patch('builtins.print')
    @patch('module.network_checker.IN_TEST_ENV', False)
    @patch('module.network_checker.requests.head')
    @patch('module.network_checker.message_center.show_critical')
    def test_check_internet_connection_print_output(self, mock_message_center, mock_head, mock_print):
        """测试网络连接失败时的打印输出（非测试环境）"""
        # 模拟所有请求都失败
        mock_head.side_effect = requests.exceptions.RequestException("Connection failed")

        result = self.network_checker.check_internet_connection(show_error=False)
        self.assertFalse(result)
        # 验证打印函数被调用
        mock_print.assert_called_once()

    @patch('builtins.print')
    @patch('module.network_checker.IN_TEST_ENV', False)
    def test_check_dashscope_print_error(self, mock_print):
        """测试check_dashscope_connection方法中的print语句（覆盖第200行）"""
        # 测试无API密钥时的错误打印
        result = self.network_checker.check_dashscope_connection("", show_error=False)

        self.assertFalse(result)
        mock_print.assert_called_once()

        # 重置mock
        mock_print.reset_mock()

        # 测试无效API密钥时的错误打印（需要模拟dashscope调用失败）
        with patch('dashscope.Generation.call') as mock_call:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_call.return_value = mock_response

            result = self.network_checker.check_dashscope_connection("invalid_key", show_error=False)

            self.assertFalse(result)
            mock_print.assert_called_once()

# 单独测试check_network_status方法的类
class TestNetworkStatus(unittest.TestCase):
    """专门测试check_network_status方法的返回值"""

    def test_is_test_environment(self):
        """测试is_test_environment函数的各种场景"""
        # 导入network_checker模块
        import module.network_checker as network_checker

        # 场景1：模块名包含'test'
        test_modules = {'test_module': MagicMock(), 'normal_module': MagicMock()}
        self.assertTrue(network_checker.is_test_environment(module=test_modules, args=['script.py']))

        # 场景2：命令行参数包含'test'
        normal_modules = {'normal_module': MagicMock(), 'os': MagicMock()}
        self.assertTrue(network_checker.is_test_environment(module=normal_modules, args=['script.py', '--test']))

        # 场景3：既没有测试模块也没有测试参数
        self.assertFalse(network_checker.is_test_environment(module=normal_modules, args=['script.py']))

        # 场景4：空模块和空参数
        self.assertFalse(network_checker.is_test_environment(module={}, args=[]))

        # 场景5：测试名称在不同位置
        self.assertTrue(network_checker.is_test_environment(module={}, args=['script.py', 'run_test']))
        self.assertTrue(network_checker.is_test_environment(module={'my_test_module': MagicMock()}, args=[]))

        # 验证当前确实是测试环境（运行时的真实情况）
        self.assertTrue(network_checker.is_test_environment())

if __name__ == '__main__':
    unittest.main()
