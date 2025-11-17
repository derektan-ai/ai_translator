"""
日志记录模块，提供Logger类用于系统日志的管理与记录。
支持日志文件初始化、多级别日志（INFO、WARNING、ERROR、DEBUG）记录、
日志文件关闭及清空等功能，日志可同时输出到控制台和指定文件。
"""
import os
import datetime
from .info import INFO
# pylint: disable=consider-using-with
class Logger:
    """
    日志记录器类，负责记录系统日志
    """
    def __init__(self, log_file=None):
        """初始化日志记录器，默认日志文件位于父目录的result文件夹"""
        # 如果未提供日志文件路径或为空字符串，设置默认路径到父目录的result文件夹
        if log_file is None or log_file == '':
            # 获取当前文件所在目录的父目录（D:\video2text）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            result_dir = os.path.join(parent_dir, "result")
            log_file = os.path.join(result_dir, "system.log")

        self.log_file = log_file
        self.file = None

        # 初始化日志文件
        if self.log_file:
            self._init_log_file()

    def _init_log_file(self):
        """初始化日志文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

            # 打开日志文件（追加模式）
            self.file = open(self.log_file, 'a', encoding='utf-8')

            # 写入日志头
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_start = INFO.get("log_start").format(timestamp=timestamp)
            # 直接写入而不调用log方法，避免触发级联调用
            self.file.write(f"{log_start}\n")
            self.file.flush()
        except OSError as e:
            error_msg = INFO.get("log_init_failed").format(error=str(e))
            print(error_msg)
            self.file = None

    def log(self, message, level="INFO"):
        """记录一条日志"""
        # 生成带时间戳的日志消息
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}"

        # 打印到控制台
        print(log_message)

        # 写入文件
        if self.file:
            try:
                self.file.write(log_message + '\n')
                self.file.flush()
            except IOError as e:
                # 添加timestamp参数，修复KeyError
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                error_msg = INFO.get("log_write_failed").format(
                    timestamp=timestamp,
                    error=str(e)
                )
                print(error_msg)

    def info(self, message):
        """记录信息级别的日志"""
        self.log(message, "INFO")

    def warning(self, message):
        """记录警告级别的日志"""
        self.log(message, "WARNING")

    def error(self, message):
        """记录错误级别的日志"""
        self.log(message, "ERROR")

    def debug(self, message):
        """记录调试级别的日志"""
        self.log(message, "DEBUG")

    def close(self):
        """关闭日志文件"""
        if self.file:
            try:
                # 写入日志尾
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_end = INFO.get("log_end").format(timestamp=timestamp)
                # 直接写入而不调用log方法，避免触发级联调用
                self.file.write(f"{log_end}\n")
                self.file.flush()
                self.file.close()
            except IOError as e:
                error_msg = INFO.get("log_close_error").format(error=str(e))
                print(error_msg)
            finally:
                self.file = None

    def __del__(self):
        """析构函数，确保日志文件被关闭"""
        self.close()

    def get_log_file_path(self):
        """获取日志文件路径"""
        return self.log_file

    def clear(self):
        """清空日志文件"""
        if self.file:
            self.close()

        if self.log_file:
            try:
                # 重新打开文件（覆盖模式）
                self.file = open(self.log_file, 'w', encoding='utf-8')
            except OSError as e:
                error_msg = INFO.get("log_clear_failed").format(error=str(e))
                print(error_msg)
                self.file = None
