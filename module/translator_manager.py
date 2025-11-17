"""
翻译器线程管理模块（翻译器中层）
负责管理其下的translation_callback模块
"""
import time
import queue
import threading
import dashscope
import numpy as np
from dashscope.audio.asr import TranslationRecognizerRealtime
from dashscope.common.error import InvalidParameter
from .message_center import message_center
from .info import INFO
from .logger import Logger
from .translation_callback import TranslationCallback
# pylint: disable=c-extension-no-member
# pylint: disable=R0902
class TranslatorManager:
    """
    基于 DashScope API 的实时语音翻译器类。
    该类管理翻译器实例，处理音频数据的接收与翻译。
    """
    def __init__(self, config, logger=None, realtime_callback=None):
        """
        初始化翻译器管理器
        Args:
            config: 配置对象
            logger: 日志记录器
            realtime_callback: 实时翻译结果回调函数
        """
        def empty_callback(*_, **__):
            """空函数作为回调函数默认值"""
            pass  # pylint: disable=unnecessary-pass

        self.config = config
        self.logger = logger or Logger()  # 确保logger存在
        self.translator = None
        self.callback = None
        self.audio_buffer = queue.Queue(maxsize=1024)
        self.result_queue = queue.PriorityQueue()
        self._stop_event = threading.Event()

        # 分组管理相关属性
        self.callbacks = {
            'realtime': realtime_callback,
            'error': empty_callback,
            'warning': empty_callback
        }

        self.threads = {
            'processing': None,
            'heartbeat': None,
            'network_check': None
        }

        self.state = {
            'running': False,
            'translator_status': "initialized",
            'network_status': True,
            'audio_processing_paused': False
        }

        self.message_deduplication = {
            'last_error_message': "",
            'last_warning_message': "",
            'error_cooldown': 5,
            'warning_cooldown': 5,
            'last_error_time': 0,
            'last_warning_time': 0
        }

        self.components = {
            'recorder': None
        }

        # 初始化翻译器
        dashscope.api_key = self.config.DASHSCOPE_API_KEY
        self.callback = TranslationCallback(
            self.result_queue,
            self.logger,
            realtime_callback=self.callbacks['realtime']
        )
        # 给Callback设置错误回调（接收网络错误并传递给TranslatorUnit）
        self.callback.set_network_error_callback(self._on_network_error)
        self.translator = self._create_translator(self.callback)

    def _on_network_error(self, message):
        error_msg = INFO.get("severe_network_error", self.config.LANGUAGE).format(message=message)
        self.logger.error(error_msg)

        # 检查是否已经停止，避免重复调用stop()
        if not self.state['running'] or self._stop_event.is_set():
            self.logger.info(INFO.get("already_stopped_state", self.config.LANGUAGE))
            return

        # 立即停止所有操作
        try:
            self.stop()
        except (RuntimeError, IOError) as e:
            log_msg = INFO.get("stop_process_error", self.config.LANGUAGE).format(error=str(e))
            self.logger.error(log_msg)

        # 通知UI
        if callable(self.callbacks['error']):
            notify_msg = INFO.get("network_disconnected", self.config.LANGUAGE)\
                .format(message=message)
            self.callbacks['error'](notify_msg)

    def _on_callback_warning(self, message):
        """处理来自回调的警告消息"""
        self.send_warning_notification(message)

    def send_error_notification(self, message):
        """发送错误通知，带冷却和去重机制"""
        current_time = time.time()

        # 检查是否是重复消息且在冷却期内
        if (message == self.message_deduplication['last_error_message'] and
                current_time - self.message_deduplication['last_error_time'] <
                self.message_deduplication['error_cooldown']):
            return

        # 更新错误状态
        self.message_deduplication['last_error_message'] = message
        self.message_deduplication['last_error_time'] = current_time

        # 记录日志
        log_msg = INFO.get("error_prefix", self.config.LANGUAGE).format(message=message)
        self.logger.error(log_msg)

        # 通过回调通知UI
        if callable(self.callbacks['error']):
            self.callbacks['error'](message)
        else:
            # 如果没有回调，使用消息中心
            message_center.show_critical(
                INFO.get("error", self.config.LANGUAGE),
                message
            )

    def send_warning_notification(self, message):
        """发送警告通知，带冷却和去重机制"""
        current_time = time.time()

        # 检查是否是重复消息且在冷却期内
        if (message == self.message_deduplication['last_warning_message'] and
                current_time - self.message_deduplication['last_warning_time'] <
                self.message_deduplication['warning_cooldown']):
            return

        # 更新警告状态
        self.message_deduplication['last_warning_message'] = message
        self.message_deduplication['last_warning_time'] = current_time

        # 记录日志
        log_msg = INFO.get("warning_prefix", self.config.LANGUAGE).format(message=message)
        self.logger.warning(log_msg)

        # 通过回调通知UI
        if callable(self.callbacks['warning']):
            self.callbacks['warning'](message)
        else:
            # 如果没有回调，使用消息中心
            message_center.show_warning(
                INFO.get("warning", self.config.LANGUAGE),
                message
            )

    def _create_translator(self, callback):
        """创建翻译器实例，使用配置中的动态语种参数"""
        translator = TranslationRecognizerRealtime(
            model="gummy-realtime-v1",
            format="pcm",
            sample_rate=self.config.SAMPLE_RATE,
            transcription_enabled=True,
            translation_enabled=True,
            transcription_source_language=self.config.ASR_LANGUAGE,
            translation_target_languages=[self.config.TRANSLATE_TARGET],
            callback=callback,
            enable_punctuation=True
        )
        return translator

    def start(self):
        """启动翻译过程，包括翻译器初始化和相关线程"""
        self.state['running'] = True
        self._stop_event.clear()  # 重置停止事件

        # 尝试启动翻译器
        if self.state['translator_status'] == "initialized" and self.translator:
            try:
                self.translator.start()
                self.state['translator_status'] = "running"
                self.logger.info(INFO.get("translator_started", self.config.LANGUAGE))
            except RuntimeError as e:
                self._handle_translator_start_error(e)
                return

        # 启动单个处理线程
        self.threads['processing'] = threading.Thread(target=self._consume_audio_buffer)
        self.threads['processing'].daemon = True
        self.threads['processing'].start()
        self.logger.info(INFO.get("processing_thread_started", self.config.LANGUAGE))

    def stop(self):
        """停止所有翻译器、线程及相关资源"""
        # 防止重复调用stop
        if not self.state['running'] and self._stop_event.is_set():
            return

        # 设置停止事件
        self._stop_event.set()
        self.state['running'] = False

        # 暂停音频处理
        self.state['audio_processing_paused'] = True

        # 停止录音（如果有录音器引用）
        if (hasattr(self, 'components') and self.components['recorder'] and
                self.components['recorder'].recording):
            try:
                self.components['recorder'].stop_recording()
                self.logger.info(INFO.get("recording_stopped", self.config.LANGUAGE))
            except (IOError, RuntimeError, OSError) as e:
                self.logger.error(f"{INFO.get(
                    'recording_stop_error',
                    self.config.LANGUAGE
                )}{e}")

        # 停止翻译器，增加更严格的状态检查
        if self.translator and self.state['translator_status'] not in ("stopped", "stopping"):
            try:
                # 先检查翻译器是否还在运行（如果有相关方法）
                if hasattr(self.translator, 'is_running') and not self.translator.is_running(): # pylint: disable=E1101
                    self.logger.warning(
                        INFO.get("translator_already_stopped", self.config.LANGUAGE)
                    )
                    self.state['translator_status'] = "stopped"
                    return

                self.state['translator_status'] = "stopping"  # 标记为正在停止
                self.translator.stop()
                self.logger.info(INFO.get("translator_stopped_success", self.config.LANGUAGE))
                self.state['translator_status'] = "stopped"
            except InvalidParameter as e:
                # 专门捕获"已停止"的异常
                self.logger.warning(
                    f"{INFO.get('translator_already_stopped', self.config.LANGUAGE)}: {e}"
                )
                self.state['translator_status'] = "stopped"
            except (RuntimeError, IOError) as e:
                error_msg = INFO.get("translator_stop_error", self.config.LANGUAGE)\
                    .format(error=str(e))
                self.logger.error(error_msg)
                self.state['translator_status'] = "error"

        # 停止处理线程
        self._stop_thread(
            INFO.get("processing_thread", self.config.LANGUAGE),
            self.threads['processing']
        )

        # 关闭回调
        if self.callback:
            self.callback.close()
            self.callback = None

        # 清空缓冲区
        self._clear_audio_buffer()

    def process_audio(self, audio_data):
        """
        处理原始音频数据并放入缓冲区（生产者方法）
        由录音线程调用，负责音频预处理和入队
        Args:
            audio_data: 原始音频数据
        """
        if (not self.state['running'] or audio_data is None or
                self._stop_event.is_set() or not self.state['network_status']):
            return

        try:
            # 转换为单声道（音频预处理）
            if audio_data.ndim == 2 and audio_data.shape[1] == 2:
                audio_data = np.mean(audio_data, axis=1, dtype=np.int16).reshape(-1, 1)

            # 放入缓冲区
            self.audio_buffer.put(audio_data, block=True, timeout=0.5)
        except queue.Full:
            warning_msg = INFO.get("audio_buffer_full", self.config.LANGUAGE)
            # 强制记录警告，不应用去重机制
            self.logger.warning(warning_msg)
            if callable(self.callbacks['warning']):
                self.callbacks['warning'](warning_msg)
        except (ValueError, TypeError, RuntimeError) as e:
            error_msg = INFO.get("audio_processing_error", self.config.LANGUAGE)\
                .format(error=str(e))
            self.logger.error(error_msg)

    def _consume_audio_buffer(self):
        """
        从缓冲区取出音频数据并发送给翻译器
        在独立线程中运行，负责音频数据的实际处理和发送
        """
        while self.state['running'] and not self._stop_event.is_set():
            try:
                if (self.state['audio_processing_paused'] or
                        not self.state['network_status']):
                    time.sleep(0.1)
                    continue

                # 获取音频数据
                try:
                    audio_data = self.audio_buffer.get(timeout=0.5)
                except queue.Empty:
                    # 无音频数据时检查翻译器状态
                    if self.state['translator_status'] == "initialized":
                        try:
                            self.translator.start()
                            # 直接执行成功处理逻辑，避免额外的方法调用层级
                            self.state['translator_status'] = "running"
                            self.logger.info(INFO.get("translator_started", "翻译器已成功启动"))
                        except RuntimeError as e:
                            # 调用单独的错误处理方法
                            self._handle_translator_start_error(e)
                    continue

                # 处理翻译器状态
                if (self.state['translator_status'] != "running" or
                        not self.translator):
                    if self.state['translator_status'] == "initialized":
                        try:
                            self.translator.start()
                            # 内联的状态更新和日志记录
                            self.state['translator_status'] = "running"
                            self.logger.info(INFO.get("translator_started", "翻译器已成功启动"))
                        except RuntimeError as e:
                            # 调用单独的错误处理方法
                            self._handle_translator_start_error(e)
                    else:
                        continue

                # 发送音频数据
                try:
                    self.translator.send_audio_frame(audio_data.tobytes())
                except (ConnectionError, IOError, RuntimeError) as e:
                    error_msg = INFO.get("send_audio_failed", self.config.LANGUAGE)\
                        .format(error=str(e))
                    self.logger.error(error_msg)
                    notify_msg = INFO.get("audio_transmission_error", self.config.LANGUAGE)\
                        .format(error=str(e))
                    self.send_error_notification(notify_msg)
                    self.stop()

            except (IOError, ConnectionError) as e:
                error_msg = INFO.get("audio_buffer_process_error", self.config.LANGUAGE)\
                    .format(error=str(e))
                self.logger.error(error_msg)
                self.stop()
            except (RuntimeError, TypeError) as e:
                error_msg = INFO.get("unexpected_audio_error", self.config.LANGUAGE)\
                    .format(error=str(e))
                self.logger.error(error_msg)
                self.stop()

    def _notify_connection_lost(self):
        """通知用户连接已断开"""
        error_msg = INFO.get("connection_failed", self.config.LANGUAGE)
        details = INFO.get("network_error", self.config.LANGUAGE)
        full_msg = f"{error_msg}\n{details}"
        self.logger.error(error_msg)
        self.logger.error(details)

        # 通过回调通知UI
        if callable(self.callbacks['error']):
            self.callbacks['error'](f"{error_msg}\n{details}")
        else:
            message_center.show_critical(
                INFO.get("error", self.config.LANGUAGE),
                full_msg
            )

        # 如果正在运行，停止录音
        if (hasattr(self, 'components') and self.components['recorder'] and
                self.components['recorder'].recording):
            self.components['recorder'].stop_recording()

    def _check_connection(self):
        """检查连接状态，网络中断时停止翻译"""
        while self.state['running'] and not self._stop_event.is_set():
            # 短间隔检查，便于快速响应停止事件
            remaining_sleep = self.config.HEARTBEAT_INTERVAL
            while remaining_sleep > 0 and not self._stop_event.is_set():
                sleep_time = min(0.5, remaining_sleep)
                time.sleep(sleep_time)
                remaining_sleep -= sleep_time

            if self._stop_event.is_set():
                break

            # 只检查状态，不进行重连
            if (self.state['translator_status'] == "running" and
                    self.translator):
                try:
                    self.translator.send_audio_frame(b'')
                except (ConnectionError, IOError, RuntimeError) as e:
                    error_msg = str(e)
                    log_msg = INFO.get("connection_check_failed", self.config.LANGUAGE)\
                        .format(error=error_msg)
                    self.logger.error(log_msg)

                    # 先更新状态
                    self.state['translator_status'] = "disconnected"
                    self.state['running'] = False
                    self.state['network_status'] = False

                    # 发送通知
                    self.send_error_notification(
                        INFO.get("translation_connection_lost", self.config.LANGUAGE)
                    )

                    # 停止时保持disconnected状态
                    self._stop_translator()

                    # 连接失败后退出检查循环
                    return

    def _handle_network_recovery(self):
        """处理网络恢复（仅记录，不重连）"""
        msg = INFO.get("network_recovered", self.config.LANGUAGE)
        self.logger.info(msg)
        self.callbacks['warning'](msg)

    def _handle_network_disconnection(self):
        """处理网络断开，停止翻译过程"""
        error_msg = INFO.get("network_error", self.config.LANGUAGE)
        self.logger.error(error_msg)

        # 通知UI并停止翻译（stop()方法中已包含停止录音的逻辑）
        self.send_error_notification(error_msg)
        self.stop()

    def _stop_thread(self, thread_name, thread, timeout=2.0):
        """停止指定线程并等待其退出"""
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                warning_msg = INFO.get("warning_prefix", self.config.LANGUAGE).format(
                    message=INFO.get("thread_not_exited", self.config.LANGUAGE).\
                        format(thread_name=thread_name)
                )
                self.logger.warning(warning_msg)
            else:
                info_msg = INFO.get("thread_stopped", self.config.LANGUAGE).\
                    format(thread_name=thread_name)
                self.logger.info(info_msg)

    def _handle_translator_start_error(self, error):
        """处理翻译器启动错误的单独方法"""
        error_msg = f"翻译器启动失败: {str(error)}"
        self.logger.error(error_msg)
        self.state['translator_status'] = "error"

    def _clear_audio_buffer(self):
        """清空音频缓冲区"""
        while not self.audio_buffer.empty():
            try:
                self.audio_buffer.get_nowait()
            except queue.Empty:
                pass

    def _stop_translator(self):
        """仅停止翻译器而不改变其当前状态（用于连接断开情况）"""
        # 保存当前状态，避免被stop()覆盖
        current_status = self.state['translator_status']

        # 停止翻译器但保持disconnected状态
        if self.translator and self.state['translator_status'] not in ("stopped", "stopping"):
            try:
                # pylint: disable=no-member
                if hasattr(self.translator, 'is_running') and not self.translator.is_running():
                    self.logger.warning(
                        INFO.get("translator_already_stopped", self.config.LANGUAGE)
                    )
                    return

                self.translator.stop()
                self.logger.info(INFO.get("translator_stopped_success", self.config.LANGUAGE))
            except InvalidParameter as e:
                self.logger.warning(
                    f"{INFO.get('translator_already_stopped', self.config.LANGUAGE)}: {e}"
                )
            except (RuntimeError, IOError) as e:
                error_msg = INFO.get("translator_stop_error",
                                     self.config.LANGUAGE).format(error=str(e))
                self.logger.error(error_msg)
                self.state['translator_status'] = "error"

        # 清空音频缓冲区
        self._clear_audio_buffer()

        # 恢复原始状态（例如disconnected）
        if current_status == "disconnected":
            self.state['translator_status'] = "disconnected"

    def set_recorder(self, recorder):
        """
        设置录音器引用
        Args:
            recorder: 录音器实例
        """
        self.components['recorder'] = recorder

    def get_result(self, timeout=0.1):
        """
        获取翻译结果
        Args:
            timeout: 超时时间
        Returns:
            翻译结果元组 (sentence_id, original, translated)
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None, None, None
