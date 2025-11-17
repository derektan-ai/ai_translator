"""
翻译器单元模块（翻译器顶层）
翻译器的顶层模块，负责管理其下的translator_manager线程管理模块并对接ui
"""
import threading
import queue
import os
import time
from dataclasses import dataclass

# 系统导入
# pylint: disable=c-extension-no-member
# PyQt5是C扩展模块，pylint无法静态分析其成员
from PyQt5 import QtCore, QtWidgets

# 项目内部导入
from .message_center import message_center
from .result_recorder import ResultRecorder
from .audio_recorder import AudioRecorder
from .logger import Logger
from .config import Config
from .network_checker import NetworkChecker
from .info import INFO
from .translator_manager import TranslatorManager
# pylint: disable=too-many-instance-attributes
class Signal(QtCore.QObject):
    """信号类，用于跨线程通信"""
    # pylint: disable=too-few-public-methods
    # 信号类只需要一个公共方法，这是设计意图
    emit_subtitle_signal = QtCore.pyqtSignal(str, str)  # 新增字幕更新信号

    def emit_subtitle(self, original, translated):
        """发射更新字幕信号"""
        self.emit_subtitle_signal.emit(original, translated)

@dataclass
class UIState:
    """UI相关状态封装，包含UI实例、消息状态和错误标记"""
    app_instance: QtWidgets.QApplication = None
    subtitle_window: QtWidgets.QWidget = None
    message_state: dict = None
    network_error_stopped: bool = False
    connection_error_shown: bool = False


@dataclass
class ThreadState:
    """线程相关状态封装，包含线程管理、停止事件和运行状态"""
    threads: dict = None
    stop_event: threading.Event = None
    is_running: bool = False
    audio_processed: int = 0


@dataclass
class ComponentState:
    """组件依赖封装，包含配置、日志、录音器等核心组件"""
    config: Config = None
    logger: Logger = None
    recorder: AudioRecorder = None
    translator: TranslatorManager = None
    result_recorder: ResultRecorder = None
    signal: Signal = None
    language: str = None
    has_result: bool = False


class TranslatorUnit:
    """单个翻译器实现"""
    def __init__(self, config: Config, subtitle_window: QtWidgets.QWidget, output_format):
        """初始化翻译器单元，使用状态类封装实例属性"""
        # 初始化三大状态类，减少实例属性数量
        self.component_state = ComponentState(
            config=config,
            language=Config.load_language_setting(),
            has_result=False,
            signal=Signal()
        )

        # 初始化连接状态以避免W0201警告
        self.component_state.is_connected = False

        # UI状态
        self.ui_state = UIState(
            app_instance=QtWidgets.QApplication.instance(),
            subtitle_window=subtitle_window,
            message_state={
                'last_error': "",
                'last_warning': "",
                'error_cooldown': 5,  # UI错误消息冷却时间(秒)
                'warning_cooldown': 5,  # UI警告消息冷却时间(秒)
                'last_error_time': 0,
                'last_warning_time': 0
            },
            network_error_stopped=False,
            connection_error_shown=False
        )
        self.thread_state = ThreadState(
            threads={
                'process': None,  # 处理线程
                'result': None,   # 结果处理线程
                'network_check': None  # 网络检查线程
            },
            stop_event=threading.Event()
        )

        # 初始化核心组件
        self.component_state.logger = Logger(config.LOG_FILE)
        self.component_state.recorder = AudioRecorder(
            config,
            self.component_state.logger
        )

        # 连接信号到字幕窗口更新方法（如果字幕窗口存在）
        if self.ui_state.subtitle_window:
            self.component_state.signal.emit_subtitle_signal.connect(
                self.ui_state.subtitle_window.update_subtitle
            )

        # 设置录音器错误回调
        self.component_state.recorder.error_callback = self._on_error

        # 初始化翻译器管理器
        self.component_state.translator = TranslatorManager(
            config,
            self.component_state.logger,
            realtime_callback=self._realtime_update
        )

        # 配置翻译器回调
        self.component_state.translator.error_callback = self._on_error
        self.component_state.translator.warning_callback = self._on_warning
        self.component_state.translator.set_recorder(self.component_state.recorder)

        # 初始化结果记录器
        self.component_state.result_recorder = ResultRecorder(
            config.ASR_LANGUAGE,
            config.TRANSLATE_TARGET,
            logger=self.component_state.logger,
            format_config={'output_format': output_format}
        )

        # 记录程序启动信息
        self.component_state.logger.info(INFO.get("program_start", config.LANGUAGE))
        self.component_state.logger.info(
            INFO.get("source_target_languages", config.LANGUAGE).format(
                source=config.ASR_LANGUAGE,
                target=config.TRANSLATE_TARGET
            )
        )

        # 初始化时检查服务器连接
        self._check_initial_connection()

    def _realtime_update(self, original, translated):
        """实时更新字幕，不进行去重和过滤"""
        clean_original = original.strip().replace('\n', ' ')
        clean_translated = translated.strip().replace('\n', ' ')
        self.update_subtitle(clean_original, clean_translated)

    def _check_initial_connection(self):
        """检查初始连接状态，优化错误提示和重试机制，避免直接退出程序"""
        self.update_subtitle(
            INFO.get("api_checking", self.component_state.language),
            ""
        )

        # 添加连接状态标志
        self.component_state.is_connected = False

        # 创建NetworkChecker实例
        network_checker = NetworkChecker(
            config=self.component_state.config,
            logger=self.component_state.logger,
            language=self.component_state.language,
            update_callback=None
        )

        # 记录上次错误消息，用于去重
        last_error = ""

        for attempt in range(Config.CONNECTION_CHECK_RETRIES):
            # 先检查网络连接
            if not network_checker.check_internet_connection(
                timeout=Config.NETWORK_CHECK_TIMEOUT,
                show_error=False
            ):
                error_msg = INFO.get("network_error", self.component_state.language)
                self.update_subtitle(error_msg, "")
                self.component_state.logger.error(error_msg)
                self._on_error(error_msg)

            # 检查Dashscope连接
            if network_checker.check_dashscope_connection(
                self.component_state.config.DASHSCOPE_API_KEY,
                timeout=Config.NETWORK_CHECK_TIMEOUT,
                show_error=False
            ):
                self.update_subtitle(
                    INFO.get("api_ok", self.component_state.language),
                    ""
                )
                self.component_state.logger.info(
                    INFO.get("dashscope_connected", self.component_state.language)
                )
                self.component_state.is_connected = True
                return True

            error_msg = (
                INFO.get("api_reconnect", self.component_state.language)
                + f" ({attempt+1}/{Config.CONNECTION_CHECK_RETRIES})..."
            )
            if error_msg != last_error:  # 仅在消息不同时更新
                self.update_subtitle(error_msg, "")
                self.component_state.logger.error(error_msg)
                last_error = error_msg
            time.sleep(Config.CONNECTION_CHECK_DELAY)

        # 所有重试都失败
        error_msg = (
            f"{INFO.get('api_connection_error', self.component_state.language)}\n"
            f"{INFO.get('contact_for_help', self.component_state.language)}"
        )
        self.update_subtitle(error_msg, "")
        self.component_state.logger.error(error_msg)
        self._on_error(error_msg)

        # 确保只显示一次错误弹窗
        if not self.ui_state.connection_error_shown:
            self.ui_state.connection_error_shown = True
            # 使用message_center显示错误消息，它会自动处理UI线程问题
            try:
                message_center.show_critical(
                    INFO.get("connection_failed", self.component_state.language),
                    error_msg,
                    parent=None
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                # 保留广泛异常捕获以确保UI操作不会中断核心功能
                self.component_state.logger.error(
                    f"显示连接错误消息时出错: {str(e)}"
                )

        # 不直接退出程序，而是设置状态为未连接
        self.component_state.is_connected = False
        return False

    def _process_audio(self):
        """处理音频数据的线程"""
        while not self.thread_state.stop_event.is_set():
            try:
                # 从音频队列获取数据
                audio_data = self.component_state.recorder.audio_queue.get(timeout=1.0)

                if audio_data is not None:
                    try:
                        # 处理音频数据
                        self.component_state.translator.process_audio(audio_data)
                        self.thread_state.audio_processed += 1
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        # 保留广泛异常捕获以确保音频处理线程不会崩溃
                        error_msg = f"{INFO.get('audio_processing_error',
                                     self.component_state.language)}{e}"
                        self.component_state.logger.error(error_msg)

            except queue.Empty:
                continue
            except (IOError, ValueError, RuntimeError) as e:
                error_msg = (
                    f"{INFO.get('process_error', self.component_state.language)}{e}"
                )
                self.component_state.logger.error(error_msg)
                self.update_subtitle("", error_msg)

    def _record_and_display_translation(self, sentence_id, last_original, last_translated,
                                        set_has_result=False):
        """记录并显示翻译结果的公共方法

        Args:
            sentence_id: 用于显示的句子ID
            last_original: 原始文本
            last_translated: 翻译文本
            set_has_result: 是否设置has_result标志
        """
        # 记录翻译结果
        self.component_state.result_recorder.record_translation(last_original, last_translated)

        # 如果需要，设置has_result标志
        if set_has_result:
            self.component_state.has_result = True

        # 显示结果
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n【Sentence_ID: {sentence_id}】 {timestamp}")
        print(f"{INFO.get('original_prefix', self.component_state.language)}{last_original}")
        print(f"{INFO.get('translated_prefix', self.component_state.language)}{last_translated}")

        # 更新字幕窗口（带异常处理）
        try:
            self.update_subtitle(last_original, last_translated)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # 保留广泛异常捕获以确保字幕更新失败不会中断程序
            self._handle_subtitle_update_error(e)

    def _process_result(self):
        """处理翻译结果的线程，只记录每个sentence_id的最后一个结果"""
        # 用于缓存每个sentence_id的最新结果
        sentence_cache = {}
        # 记录当前处理的sentence_id
        current_sentence_id = None

        while not self.thread_state.stop_event.is_set():
            try:
                # 获取翻译结果
                result = self.component_state.translator.get_result(timeout=0.1)

                # 检查结果是否有效
                if not result or len(result) != 3:
                    continue

                sentence_id, original, translated = result

                if original and translated and sentence_id is not None:
                    # 更新缓存中该sentence_id的最新结果
                    sentence_cache[sentence_id] = (original, translated)

                    # 检查是否是新的sentence_id
                    if sentence_id != current_sentence_id:
                        # 如果有上一个sentence_id的结果，记录它
                        if current_sentence_id is not None \
                           and current_sentence_id in sentence_cache:
                            last_original, last_translated = sentence_cache[current_sentence_id]
                            # 使用公共方法处理结果
                            self._record_and_display_translation(
                                sentence_id, last_original, last_translated, set_has_result=True)

                        # 更新当前sentence_id
                        current_sentence_id = sentence_id
            except queue.Empty:
                continue
            except Exception as e:  # pylint: disable=broad-exception-caught
                # 保留广泛异常捕获以确保结果处理线程不会崩溃
                self.component_state.logger.error(
                    INFO.get("error_processing_result",
                             self.component_state.language).format(error=str(e))
                )
                continue

        # 处理最后一个sentence_id的结果
        if current_sentence_id is not None and current_sentence_id in sentence_cache:
            last_original, last_translated = sentence_cache[current_sentence_id]
            # 使用公共方法处理结果
            self._record_and_display_translation(
                current_sentence_id, last_original, last_translated)

    def _save_all_results(self):
        """保存所有翻译结果"""
        # 从队列中获取所有剩余结果
        while True:
            try:
                result = self.component_state.translator.get_result(timeout=0.1)

                # 检查结果是否有效
                if not result or len(result) != 3:
                    error_msg = INFO.get(
                        "error_processing_translation",
                        self.component_state.language
                    )
                    self.component_state.logger.warning(error_msg)
                    break

                _, original, translated = result
                if not original and not translated:
                    break

                if original and translated:
                    self.component_state.result_recorder.record_translation(
                        original,
                        translated
                    )
            except (queue.Empty, RuntimeError, IOError):
                break

        # 报告结果状态（会自动处理空文件和日志输出）
        self.component_state.result_recorder.report_result_status()

        # 保存结果
        result_file = self.component_state.result_recorder.get_file_path()
        file_exists = os.path.exists(result_file)

        if file_exists and self.component_state.has_result:
            # 移除重复的日志输出，因为report_result_status()已经输出了
            self.update_subtitle(
                INFO.get("translation_complete", self.component_state.language),
                f"{INFO.get(
                    'have_result',
                    self.component_state.language
                )}{os.path.basename(result_file)}"
            )
        else:
            # 移除重复的日志输出，因为report_result_status()已经输出了
            self.update_subtitle(
                INFO.get("translation_complete", self.component_state.language),
                INFO.get("no_result", self.component_state.language)
            )



    def _on_error(self, message):
        """处理错误消息，使用中文关键词检测网络错误"""
        try:
            # 检查冷却期和去重
            if self._should_ignore_duplicate_error(message):
                return

            # 更新错误状态
            self._update_error_state(message)

            # 检查是否是网络错误
            is_network_error = self._check_is_network_error(message)

            # 根据错误类型进行处理
            if is_network_error and not self.ui_state.network_error_stopped:
                self._handle_network_error(message)
            else:
                self._update_subtitle_or_show_error(message)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # 保留广泛异常捕获以确保错误处理本身不会失败
            self.component_state.logger.error(
                f"{INFO.get("unknown_error", self.component_state.language)}: {e}")

    def _should_ignore_duplicate_error(self, message):
        """检查是否应该忽略重复的错误消息"""
        current_time = time.time()
        msg_state = self.ui_state.message_state
        return (message == msg_state['last_error'] and
                (current_time - msg_state['last_error_time'] < msg_state['error_cooldown']))

    def _update_error_state(self, message):
        """更新错误状态"""
        msg_state = self.ui_state.message_state
        msg_state['last_error'] = message
        msg_state['last_error_time'] = time.time()

    def _check_is_network_error(self, message):
        """检查是否是网络错误"""
        network_error_keywords = INFO.get("network_error_keywords", self.component_state.language)
        return any(keyword in message for keyword in network_error_keywords)

    def _handle_network_error(self, message):
        """处理网络错误"""
        self.ui_state.network_error_stopped = True  # 标记已停止，防止重复调用
        error_title = INFO.get("connection_failed", self.component_state.language)
        error_content = (
            f"{message}\n{INFO.get('network_error', self.component_state.language)}"
        )

        # 在UI主线程显示错误提示
        self._show_network_error_dialog(error_title, error_content)

        # 自动停止所有组件
        try:
            self.stop()
        except (RuntimeError, IOError) as e:
            self.component_state.logger.error(
                f"{INFO.get('stop_process_error', self.component_state.language)}{str(e)}"
            )

    def _show_network_error_dialog(self, title, content):
        """显示网络错误对话框 - 使用统一消息中心"""
        # message_center会自动处理UI线程问题，不需要手动invokeMethod
        try:
            message_center.show_critical(
                title,
                content,
                parent=None
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            # 保留广泛异常捕获以确保UI操作不会中断核心功能
            self.component_state.logger.error(
                INFO.get("dialog_error", self.component_state.language).format(error=str(e))
            )

    def _handle_subtitle_update_error(self, error):
        """处理字幕更新错误"""
        self.component_state.logger.error(
            INFO.get("subtitle_update_error", self.component_state.language)\
                .format(error=str(error))
        )

    def _update_subtitle_or_show_error(self, message):
        """更新字幕或显示错误"""
        if self.ui_state.subtitle_window:
            self.ui_state.subtitle_window.update_subtitle(
                INFO.get("error", self.component_state.language),
                message
            )
        else:
            self._show_general_error_dialog(message)

    def _show_general_error_dialog(self, message):
        """显示通用错误对话框"""
        try:
            message_center.show_critical(
                INFO.get("error", self.component_state.language),
                message
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            # 保留广泛异常捕获以确保UI操作不会中断核心功能
            self.component_state.logger.error(
                INFO.get("general_dialog_error", self.component_state.language).format(error=str(e))
            )

    def _on_warning(self, message):
        """处理警告消息，带去重机制"""
        current_time = time.time()
        msg_state = self.ui_state.message_state

        # 检查是否是重复消息且在冷却期内
        if (message == msg_state['last_warning'] and
            (current_time - msg_state['last_warning_time'] < msg_state['warning_cooldown'])):
            return

        # 更新警告状态
        msg_state['last_warning'] = message
        msg_state['last_warning_time'] = current_time

        warning_title = INFO.get("warning", self.component_state.language)
        if self.ui_state.subtitle_window:
            try:
                self.ui_state.subtitle_window.update_subtitle(warning_title, message)
            except Exception as e:  # pylint: disable=broad-exception-caught
                # 保留广泛异常捕获以确保UI更新失败不会中断程序
                self.component_state.logger.error(
                    INFO.get("subtitle_update_error", self.component_state.language)\
                        .format(error=str(e))
                )
        else:
            # 简化实现，避免复杂的Qt线程调用以减少测试中的访问冲突
            try:
                # 只记录警告日志，不显示消息框
                self.component_state.logger.warning(f"{warning_title}: {message}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                # 保留广泛异常捕获以确保日志记录失败不会影响程序
                print(f"警告日志记录失败: {str(e)}")

    def start(self):
        """启动翻译器，包括录音、翻译器及相关处理线程的初始化和启动"""
        try:
            self.thread_state.is_running = True

            # 启动录音
            self.component_state.recorder.start_recording()

            # 等待录音线程启动
            time.sleep(0.5)
            if not self.component_state.recorder.recording:
                warning_msg = INFO.get("cannot_start_recording", self.component_state.language)
                self.component_state.logger.warning(warning_msg)
                self.component_state.logger.close()
                return

            # 调用翻译器启动方法，翻译器管理器内部会记录启动日志
            self.component_state.translator.start()

            # 启动处理线程
            self.thread_state.threads['process'] = threading.Thread(target=self._process_audio)
            self.thread_state.threads['process'].daemon = True
            self.thread_state.threads['process'].start()

            # 启动结果处理线程
            self.thread_state.threads['result'] = threading.Thread(target=self._process_result)
            self.thread_state.threads['result'].daemon = True
            self.thread_state.threads['result'].start()

            self.component_state.signal.emit_subtitle(
                INFO.get("translation_started", self.component_state.language),
                INFO.get("wait_audio", self.component_state.language)
            )
        except (RuntimeError, ConnectionError) as e:
            error_msg = f"{INFO.get('error_starting_translator', self.component_state.language)}{e}"
            self.component_state.logger.error(error_msg)

    def stop(self):
        """停止翻译器所有组件，确保资源释放顺序合理，避免句柄无效错误"""
        # 防止重复调用stop导致的资源重复释放
        if not self.thread_state.is_running:
            self.component_state.logger.warning(INFO.get(
                "stop_non_running_translator",
                self.component_state.language
            ))
            return

        # 只记录一次程序停止信息
        self.component_state.logger.info(INFO.get(
            "stopping_program",
            self.component_state.language
        ))

        # 1. 首先标记运行状态为停止，阻止新任务生成
        self.thread_state.is_running = False
        self.thread_state.stop_event.set()  # 触发所有等待停止事件的逻辑

        # 2. 先等待处理线程结束（它们依赖录音和翻译器资源）
        # 等待音频处理线程
        if self.thread_state.threads['process'] and self.thread_state.threads['process'].is_alive():
            self.thread_state.threads['process'].join(timeout=2.0)
            if self.thread_state.threads['process'].is_alive():
                self.component_state.logger.warning(INFO.get(
                    "audio_thread_not_exited",
                    self.component_state.language
                ))

        # 等待结果处理线程
        if self.thread_state.threads['result'] and self.thread_state.threads['result'].is_alive():
            self.thread_state.threads['result'].join(timeout=2.0)
            if self.thread_state.threads['result'].is_alive():
                self.component_state.logger.warning(INFO.get(
                    "result_thread_not_exited",
                    self.component_state.language
                ))

        # 3. 显式停止录音
        if hasattr(self.component_state.recorder, 'stop_recording') \
           and self.component_state.recorder.recording:
            try:
                self.component_state.recorder.stop_recording()
            except (IOError, RuntimeError, OSError) as e:
                self.component_state.logger.error(
                    f"{INFO.get('recording_stop_error',
                               self.component_state.language)}{e}")

        # 4. 停止翻译器
        if hasattr(self.component_state.translator, 'stop'):
            try:
                self.component_state.translator.stop()
            except (IOError, RuntimeError, OSError) as e:
                self.component_state.logger.error(f"{INFO.get(
                    'translator_stop_error',
                    self.component_state.language
                )}{e}")

        # 5. 保存结果和清理日志
        self._save_all_results()
        self.component_state.logger.info(INFO.get(
            "program_stopped",
            self.component_state.language
        ))
        self.component_state.logger.close()

    def update_subtitle(self, original, translated):
        """更新字幕窗口内容"""
        if self.ui_state.subtitle_window:
            try:
                self.ui_state.subtitle_window.update_subtitle(original, translated)
            except Exception as e:  # pylint: disable=broad-exception-caught
                # 保留广泛异常捕获以确保UI更新失败不会中断程序
                self._handle_subtitle_update_error(e)

    # _handle_subtitle_update_error方法已在460-470行定义，支持国际化处理
