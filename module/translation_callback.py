"""
翻译模型实时回调模块（翻译器底层）
用于接收和处理来自实时翻译模型的回调信息，并发送模型返回的翻译文本。
"""
import time
import queue
from dashscope.audio.asr import (
    TranslationRecognizerCallback,
    TranscriptionResult,
    TranslationResult,
)
from .info import INFO
from .config import Config

class TranslationCallback(TranslationRecognizerCallback):
    """用于接收和处理实时翻译回调的类"""
    def __init__(self, result_queue, logger=None, realtime_callback=None):
        self.result_queue = result_queue
        self.logger = logger
        self.realtime_callback = realtime_callback
        self.last_event_time = time.time()
        self.language = Config.load_language_setting()

        # 句子处理相关配置
        self.sentence_config = {
            'counter': {},  # 句子ID计数器
            'attack': Config.SENTENCE_ID_ATTACK  # 忽略前n个结果的配置
        }

        # 回调函数集合
        self.callbacks = {
            'error': None,  # 错误回调
            'warning': None  # 警告回调
        }

    def on_error(self, message):
        """处理错误响应，第一时间捕获网络相关错误"""
        try:
            # 提取错误信息
            if isinstance(message, dict):
                error_msg = message.get('message', str(message))
            else:
                error_msg = str(message)

            # 识别网络相关错误关键词
            network_errors = [
                'websocket', 'connection', 'network', 'timeout',
                'ClientConnectionResetError', 'Cannot write to closing transport'
            ]

            if any(keyword in error_msg.lower() for keyword in network_errors):
                # 使用多语言文本
                error_msg = INFO.get(
                    "network_connection_exception",
                    self.language
                ).format(type=type(message), message=error_msg)

                # 优先触发网络错误回调
                network_error_callback = self.callbacks.get('network_error')
                if network_error_callback and callable(network_error_callback):
                    network_error_callback(error_msg)
                    return  # 已处理网络错误，不再触发普通错误回调

            # 确保错误回调存在且可调用
            error_callback = self.callbacks.get('error')
            if error_callback and callable(error_callback):
                error_callback(error_msg)
            else:
                if self.logger:
                    # 使用多语言文本
                    log_msg = INFO.get(
                        "no_error_callback_set",
                        self.language
                    ).format(message=error_msg)
                    self.logger.error(log_msg)

        except Exception as e:  # pylint: disable=broad-exception-caught
            # 使用多语言文本
            error_details = INFO.get(
                "callback_processing_error",
                self.language
            ).format(error=str(e))
            if self.logger:
                self.logger.error(error_details)
            # 避免再次触发可能的None回调
            error_callback = self.callbacks.get('error')
            if error_callback and callable(error_callback):
                error_callback(error_details)

    def set_network_error_callback(self, callback):
        """设置网络错误回调函数"""
        self.callbacks['network_error'] = callback

    def on_event(
        self,
        request_id,
        transcription_result: TranscriptionResult,
        translation_result: TranslationResult,
        usage,
    ) -> None:
        """处理翻译事件回调"""
        try:
            self.last_event_time = time.time()

            original_text = ""
            translated_text = ""
            sentence_id = None

            if transcription_result and transcription_result.text:
                original_text = transcription_result.text
                sentence_id = getattr(transcription_result, 'sentence_id', None)

            if translation_result:
                target_translation = translation_result.get_translation(Config.TRANSLATE_TARGET)
                if target_translation and target_translation.text:
                    translated_text = target_translation.text

            # 处理实时回调
            has_text = original_text.strip() or translated_text.strip()
            if self.realtime_callback and has_text:
                if sentence_id is not None:
                    self.sentence_config['counter'].setdefault(sentence_id, 0)
                    self.sentence_config['counter'][sentence_id] += 1

                    # 检查是否超过攻击阈值
                    counter_value = self.sentence_config['counter'][sentence_id]
                    if counter_value > self.sentence_config['attack']:
                        self.realtime_callback(original_text, translated_text)
                else:
                    self.realtime_callback(original_text, translated_text)

            # 处理翻译任务
            if has_text:
                if sentence_id is None:
                    sentence_id = time.time()
                self.result_queue.put((sentence_id, original_text, translated_text))

        except (AttributeError, ValueError) as e:
            # 使用多语言文本
            error_msg = INFO.get(
                "error_processing_translation",
                self.language
            ).format(error=e)
            self.logger.error(error_msg)

    def close(self):
        """关闭处理逻辑"""
        self.logger.info(INFO.get("thread_process_stopped", self.language))

    def get_all_texts(self):
        """获取所有的原文和译文"""
        all_original = []
        all_translated = []

        # 从结果队列收集结果
        while not self.result_queue.empty():
            try:
                result = self.result_queue.get_nowait()
                _, original, translated = result
                all_original.append(original)
                all_translated.append(translated)
            except queue.Empty:
                break

        return all_original, all_translated
