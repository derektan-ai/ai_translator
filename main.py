"""
AI Translator: Provides translation functionality based on the
Tong Yi real-time ASR/Translation model (gummy-realtime-v1),
featuring a concise PyQt5-based graphical user interface.
It supports various audio inputs such as microphone sources,
audio streams, and local voice file playback. The module can display
transcripts and INFO in real-time, supports window resizing,
transparency management, and save all results when translation is finished.
You only need to apply for a Dashscope API to use this program.
"""
import os
import sys
import traceback
import ctypes
import configparser
import matplotlib
# pylint: disable=no-name-in-module
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
# pylint: enable=no-name-in-module
# 导入拆分后的模块
from module.config import Config
from module.ui import UI
from module.info import INFO
from module.network_checker import NetworkChecker
# 授权验证已移除，简化为绿色版
from module.message_center import message_center

# 添加模块目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置中文字体支持
matplotlib.use('Agg')  # 使用非交互式后端，避免与PyQt冲突
plt_font = {'family': 'SimHei'}
matplotlib.rcParams["font.family"] = plt_font['family']

LANGUAGE_CHINESE = "zh"
LANGUAGE_ENGLISH = "en"


class InitializationThread(QThread):
    """初始化线程，用于在后台执行耗时的初始化操作"""
    initialized = pyqtSignal(bool, str)

    def stop(self):
        """停止线程执行"""
        self.terminate()
        self.wait()

    def run(self):
        """在线程中执行初始化操作"""
        try:
            # 绿色版移除授权验证

            # 检查API密钥是否存在
            Config.load_api_key()
            if not Config.DASHSCOPE_API_KEY:
                msg_title = INFO.get("api_key_error_title", Config.LANGUAGE)
                msg_content = INFO.get("api_key_error_message", Config.LANGUAGE)
                self.initialized.emit(False, msg_title + ": " + msg_content)
                return

            # 创建实例并检查网络连接
            network_checker = NetworkChecker(
                config=Config,
                logger=None,  # 假设此处暂时没有logger实例，可根据实际情况修改
                language=Config.LANGUAGE,
                update_callback=None
            )

            if not network_checker.check_internet_connection(show_error=False):
                msg_title = INFO.get("network_error", Config.LANGUAGE)
                msg_content = INFO.get("network_error_message", Config.LANGUAGE)
                self.initialized.emit(False, msg_title + ": " + msg_content)
                return

            # 检查API连接
            if not network_checker.check_dashscope_connection(
                Config.DASHSCOPE_API_KEY,
                show_error=False
            ):
                msg_title = INFO.get("api_connection_error", Config.LANGUAGE)
                msg_content = INFO.get("api_support_message", Config.LANGUAGE)
                self.initialized.emit(False, msg_title + ": " + msg_content)
                return

            # 初始化成功
            self.initialized.emit(True, "")

        except (IOError, OSError, configparser.Error, TimeoutError, RuntimeError, ValueError) as e:
            error_msg = f"{INFO.get('initialization_error', Config.LANGUAGE)}: {str(e)}"
            self.initialized.emit(False, error_msg)


def main():
    """主程序"""
    # 隐藏命令行窗口（仅Windows有效）
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    # 抑制PyInstaller临时目录删除警告
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, message="Failed to remove temporary directory")

    # 添加异常捕获，确保错误信息能显示在命令行窗口
    try:
        app = QApplication(sys.argv)

        # 设置应用程序图标（适用于任务栏和弹窗）
        # 确定图标路径，考虑打包和开发环境
        if hasattr(sys, 'frozen'):
            # 打包后的环境
            icon_path = os.path.join(os.path.dirname(sys.executable), 'ai_translator.ico')
        else:
            # 开发环境
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_translator.ico')

        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        # 加载语言设置
        Config.load_language_setting()

        # 根据语言设置选择合适的字体
        if Config.LANGUAGE == LANGUAGE_CHINESE:
            font = QFont("微软雅黑")
        else:
            font = QFont("Arial")
        app.setFont(font)

        # 创建UI实例
        ex = UI()
        ex.show()

        # 创建并启动初始化线程
        init_thread = InitializationThread()

        def on_initialization_completed(success, message):
            """初始化完成后的回调函数"""
            if not success:
                print(message)
                # 只在有异常发生时才打印堆栈跟踪
                if sys.exc_info()[0] is not None:
                    traceback.print_exc()
                message_center.show_critical(
                    INFO.get("initialization_error", Config.LANGUAGE),
                    f"{message}\n\n{INFO.get('check_console_log', Config.LANGUAGE)}",
                    parent=ex
                )
                # 延迟退出，让用户有时间看到错误信息
                QTimer.singleShot(2000, app.quit)

        # 连接信号
        init_thread.initialized.connect(on_initialization_completed)
        init_thread.start()

        sys.exit(app.exec_())
    except (IOError, OSError, configparser.Error, TimeoutError, RuntimeError, ValueError) as e:
        error_msg = f"{INFO.get('initialization_error', 'zh')}: {str(e)}"
        print(error_msg)
        traceback.print_exc()

        # 显示错误消息框
        if QApplication.instance() is None:
            app = QApplication(sys.argv)

        message_center.show_critical(
            INFO.get("initialization_error", "zh"),
            f"{error_msg}\n\n{INFO.get('check_console_log', 'zh')}",
            parent=None
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
