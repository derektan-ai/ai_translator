"""
统一消息中心模块
负责管理和分发应用程序中的所有消息提示，提供单例访问点
实现消息去重、冷却机制和来源追踪
"""
import time
import inspect
import sys
# 移除未使用的Qt导入以避免警告

# 延迟导入WindowMessageBox以避免循环依赖
# 将在需要时动态导入


class MessageCenter:
    """消息中心类 - 使用单例模式"""
    _instance = None
    _lock = False

    def __new__(cls):
        """确保只有一个实例被创建"""
        if cls._instance is None:
            cls._instance = super(MessageCenter, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    def __init__(self):
        """初始化消息中心属性"""
        # 消息去重和冷却机制 - 在__init__中初始化所有属性
        self.message_deduplication = {
            'critical': {'last_message': '', 'last_time': 0, 'cooldown': 2.0},
            'warning': {'last_message': '', 'last_time': 0, 'cooldown': 2.0},
            'information': {'last_message': '', 'last_time': 0, 'cooldown': 1.0},
            'question': {'last_message': '', 'last_time': 0, 'cooldown': 0.5}
        }

        # 日志和回调函数
        self.logger = None
        self.callbacks = {
            'critical': None,
            'warning': None,
            'information': None,
            'question': None
        }

        # 语言设置
        self.language = 'zh'

    def _initialize(self):
        """初始化消息中心（保持兼容性）"""
        # 所有初始化现在在__init__中完成

    def set_language(self, language):
        """设置语言"""
        # 在__init__中已经初始化了language属性
        self.language = language

    def set_logger(self, logger):
        """设置日志记录器"""
        # 在__init__中已经初始化了logger属性
        self.logger = logger

    def set_callbacks(self, callbacks):
        """设置回调函数字典"""
        self.callbacks.update(callbacks)

    def _get_source_info(self):
        """获取消息来源信息"""
        # 获取调用栈信息
        stack = inspect.stack()
        # 跳过当前方法和show_xxx方法，获取实际调用者
        if len(stack) >= 3:
            caller_frame = stack[2]
            file_path = caller_frame.filename
            line_no = caller_frame.lineno
            function_name = caller_frame.function
            # 获取相对路径
            module_name = file_path.replace('\\', '/')
            if '/module/' in module_name:
                module_name = module_name.split('/module/')[1]
            return f"[{module_name}:{line_no}@{function_name}]"
        return "[Unknown Source]"

    def _should_display_message(self, msg_type, message):
        """检查消息是否应该显示（去重和冷却）"""
        current_time = time.time()
        msg_info = self.message_deduplication[msg_type]

        # 检查是否是重复消息且在冷却期内
        if (message == msg_info['last_message'] and
                current_time - msg_info['last_time'] < msg_info['cooldown']):
            return False

        # 更新消息状态
        msg_info['last_message'] = message
        msg_info['last_time'] = current_time
        return True

    def _ensure_ui_thread(self, func, *args, **kwargs):
        """确保在UI线程中执行函数"""
        # pylint: disable=import-outside-toplevel
        # 延迟导入是必要的以避免循环依赖
        try:
            # 使用动态导入避免E0611错误
            qtwidgets = __import__('PyQt5.QtWidgets', fromlist=['QApplication'])
            app_instance = qtwidgets.QApplication.instance()

            if not app_instance:
                # 如果没有QApplication实例，创建一个临时实例
                qtwidgets.QApplication(sys.argv)
                return func(*args, **kwargs)

            # 检查当前线程是否是UI线程
            # 动态导入QThread以避免E0611错误
            qtcore = __import__('PyQt5.QtCore', fromlist=['QThread'])
            if app_instance.thread() == qtcore.QThread.currentThread():
                # 直接在当前线程执行
                return func(*args, **kwargs)

            # 在UI线程中执行 - 使用更可靠的方式
            # 动态导入QMetaObject以避免E0611错误
            qtcore = __import__('PyQt5.QtCore', fromlist=['QMetaObject'])
            qt_meta_object = qtcore.QMetaObject

            # 动态获取Qt常量以避免E0611错误和命名规范问题
            qt_constants = __import__('PyQt5.QtCore', fromlist=['Qt'])
            blocking_queued_conn = qt_constants.Qt.BlockingQueuedConnection

            # 使用可重入的方式执行
            result = []

            def execute_in_ui_thread():
                try:
                    result.append(func(*args, **kwargs))
                except Exception as exception:  # pylint: disable=broad-exception-caught
                    # 捕获异常并记录 - 需要捕获所有异常以确保UI线程不崩溃
                    print(f"Error in UI thread execution: {str(exception)}")
                return True

            # 使用BlockingQueuedConnection确保执行完成后再返回
            qt_meta_object.invokeMethod(
                app_instance,
                execute_in_ui_thread,
                blocking_queued_conn
            )

            return result[0] if result else None
        except Exception as exception:  # pylint: disable=broad-exception-caught
            # 如果Qt导入失败，直接执行函数
            print(f"Failed to use Qt UI thread: {str(exception)}")
            return func(*args, **kwargs)

    def show_critical(self, title, message, parent=None):
        """显示错误消息"""
        if not self._should_display_message('critical', message):
            return None

        # 获取来源信息
        source_info = self._get_source_info()

        # 记录日志（如果有logger）
        if self.logger:
            log_msg = f"[CRITICAL] {source_info} {title}: {message}"
            self.logger.error(log_msg)

        # 执行回调（如果有且可调用）
        callback = self.callbacks.get('critical')
        if callback and callable(callback):
            callback(title, message)
            return None

        # 显示消息框 - 延迟导入以避免循环依赖
        # pylint: disable=import-outside-toplevel
        from .window_utils import WindowMessageBox
        def display_message():
            return WindowMessageBox.critical(parent, title, message)

        return self._ensure_ui_thread(display_message)

    def show_warning(self, title, message, parent=None):
        """显示警告消息"""
        if not self._should_display_message('warning', message):
            return None

        # 获取来源信息
        source_info = self._get_source_info()

        # 记录日志（如果有logger）
        if self.logger:
            log_msg = f"[WARNING] {source_info} {title}: {message}"
            self.logger.warning(log_msg)

        # 执行回调（如果有且可调用）
        callback = self.callbacks.get('warning')
        if callback and callable(callback):
            callback(title, message)
            return None

        # 显示消息框 - 延迟导入以避免循环依赖
        # pylint: disable=import-outside-toplevel
        from .window_utils import WindowMessageBox
        def display_message():
            return WindowMessageBox.warning(parent, title, message)

        return self._ensure_ui_thread(display_message)

    def show_information(self, title, message, parent=None):
        """显示信息消息"""
        if not self._should_display_message('information', message):
            return None

        # 获取来源信息
        source_info = self._get_source_info()

        # 记录日志（如果有logger）
        if self.logger:
            log_msg = f"[INFO] {source_info} {title}: {message}"
            self.logger.info(log_msg)

        # 执行回调（如果有且可调用）
        callback = self.callbacks.get('information')
        if callback and callable(callback):
            callback(title, message)
            return None

        # 显示消息框 - 延迟导入以避免循环依赖
        # pylint: disable=import-outside-toplevel
        from .window_utils import WindowMessageBox
        def display_message():
            return WindowMessageBox.information(parent, title, message)

        return self._ensure_ui_thread(display_message)

    def show_question(self, title, message, parent=None, buttons=None):
        """显示问题消息"""
        if not self._should_display_message('question', message):
            return None

        # 获取来源信息
        source_info = self._get_source_info()

        # 记录日志（如果有logger）
        if self.logger:
            log_msg = f"[QUESTION] {source_info} {title}: {message}"
            self.logger.info(log_msg)

        # 执行回调（如果有且可调用）
        callback = self.callbacks.get('question')
        if callback and callable(callback):
            callback(title, message, buttons)
            return None

        # 显示消息框 - 延迟导入以避免循环依赖
        # pylint: disable=import-outside-toplevel
        from .window_utils import WindowMessageBox
        # 如果buttons参数为None，使用默认值
        if buttons is None:
            buttons = WindowMessageBox.Yes | WindowMessageBox.No

        def display_message():
            return WindowMessageBox.question(parent, title, message, buttons)

        return self._ensure_ui_thread(display_message)


# 创建全局消息中心实例
message_center = MessageCenter()

__all__ = ['MessageCenter', 'message_center']
