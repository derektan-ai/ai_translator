"""
用于检查网络连接、DNS 与 Dashscope 服务可用性。
"""
import sys
import time
import threading
import requests
import dashscope
from PyQt5 import QtWidgets
from .message_center import message_center
from .info import INFO

# 检测是否在测试环境中运行
def is_test_environment(module=None, args=None):
    """检查当前是否在测试环境中运行

    Args:
        module: 可选，用于测试的模块字典
        args: 可选，用于测试的命令行参数列表
    """
    # 使用传入的参数或默认值
    check_modules = module if module is not None else sys.modules
    check_args = args if args is not None else sys.argv

    # 检查模块名称是否包含test
    for module_name in check_modules:
        if 'test' in module_name.lower():
            return True
    # 检查命令行参数是否包含test
    for arg in check_args:
        if 'test' in arg.lower():
            return True
    return False

# 全局标志，表示是否在测试环境中
IN_TEST_ENV = is_test_environment()
# pylint: disable=c-extension-no-member
class NetworkChecker:
    """用于检查网络连接、DNS与Dashscope服务可用性的类"""
    def __init__(self, config, logger, language, update_callback):
        """初始化网络检查器

        Args:
            config: 配置对象
            logger: 日志对象
            language: 语言设置
            update_callback: 更新回调函数
        """
        self.config = config
        self.logger = logger
        self.language = language
        self.update_callback = update_callback
        self._running = False
        self._thread = None

    def start_checking(self, interval=10):
        """启动网络检查线程"""
        self._running = True
        self._thread = threading.Thread(
            target=self._check_loop,
            args=(interval,),
            daemon=True
        )
        self._thread.start()

    def stop_checking(self):
        """停止网络检查线程"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                self.logger.warning(INFO.get("network_thread_exit_error", self.language))

    def _check_loop(self, interval):
        """网络检查循环"""
        while self._running:
            try:
                # 执行网络检查
                status = self.check_network_status(self.config.api_key)
                if self.update_callback:
                    self.update_callback(status)
                time.sleep(interval)
            except requests.exceptions.ConnectionError as e:
                self.logger.error(
                    INFO.get("network_connection_error", self.language).format(error=str(e))
                )
                time.sleep(interval)
            except requests.exceptions.Timeout as e:
                self.logger.warning(
                    INFO.get("network_check_timeout", self.language).format(error=str(e))
                )
                time.sleep(interval)
            # 捕获dashscope相关异常（dashscope未明确定义公共异常类）
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.error(
                    INFO.get("dashscope_unknown_error", self.language).format(error=str(e))
                )
                time.sleep(interval)

    def check_internet_connection(self, timeout=5, show_error=True):
        """检查网络连接状态"""
        test_sites = [
            ("https://www.baidu.com", INFO.get("baidu", self.language)),
            ("https://www.aliyun.com", INFO.get("aliyun", self.language)),
            ("https://www.bing.com", INFO.get("bing", self.language))
        ]

        for url, _ in test_sites:  # 使用下划线代替未使用的'name'变量
            try:
                response = requests.head(url, timeout=timeout, allow_redirects=True)
                if response.status_code < 400:
                    return True
            except requests.exceptions.RequestException:
                continue

        error_msg = INFO.get("network_error", self.language)
        if show_error:
            # 在UI启动前使用弹窗显示错误
            # 直接使用消息中心，它会自动处理QApplication实例的创建和线程问题
            message_center.show_critical(
                INFO.get("connection_failed", self.language),
                error_msg,
                parent=None
            )
        # 在测试环境中完全禁用打印，避免测试输出污染
        if not IN_TEST_ENV:
            print(error_msg)
        return False

    def check_dashscope_connection(self, api_key, timeout=5, show_error=True):
        """检查与Dashscope的连接状态"""
        if not api_key:
            error_msg = (
                f"{INFO.get('api_key_missing', self.language)}\n"
                f"{INFO.get('check_api_key', self.language)}"
            )
            if show_error:
                # 处理未使用的app变量
                # 直接使用消息中心，它会自动处理QApplication实例的创建和线程问题
                message_center.show_critical(
                    INFO.get("check_api_key", self.language),
                    error_msg,
                    parent=None
                )
            # 在测试环境中完全禁用打印，避免测试输出污染
            if not IN_TEST_ENV:
                print(error_msg)
            return False

        try:
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': 'Who are you？'}
            ]

            response = dashscope.Generation.call(
                api_key=api_key,
                model="qwen-turbo",
                messages=messages,
                result_format="message",
                timeout=timeout
            )

            if response.status_code == 200:
                return True

            # 合并状态码检查分支
            error_msg = (
                INFO.get('api_key_invalid', self.language)
                if response.status_code == 401
                else (
                    f"{INFO.get('api_connection_error', self.language)}: "
                    f"HTTP {response.status_code}")
                )

        except requests.exceptions.RequestException as e:
            error_msg = f"{INFO.get('api_connection_error', self.language)}: {str(e)}"

        except ValueError as e:
            error_msg = f"{INFO.get('connection_failed', self.language)}: {str(e)}"
            api_key_phrase = INFO.get("api_key_phrase", self.language)
            api_key_lower_phrase = INFO.get("api_key_lower_phrase", self.language)
            if api_key_phrase in str(e) or api_key_lower_phrase in str(e).lower():
                error_msg += f" {INFO.get('check_api_key', self.language)}"

        if show_error:
            # 合并错误弹窗显示逻辑
            parent = None
            title = INFO.get("connection_failed", self.language)
            if QtWidgets.QApplication.instance() is None:
                # 直接使用消息中心，它会自动处理QApplication实例的创建和线程问题
                message_center.show_critical(
                    title,
                    error_msg,
                    parent=parent
                )

        # 在测试环境中完全禁用打印，避免测试输出污染
        if not IN_TEST_ENV:
            print(error_msg)
        return False

    def check_network_status(self, api_key):
        """综合检查网络和API连接状态"""
        # 检查互联网连接
        if not self.check_internet_connection():
            return False

        # 检查dashscope连接并直接返回结果
        return self.check_dashscope_connection(api_key)
