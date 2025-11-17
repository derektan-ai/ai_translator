import unittest
import sys
import os
import queue
import time
from unittest.mock import patch, Mock, MagicMock
from dashscope.audio.asr import TranscriptionResult, TranslationResult

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from module.translation_callback import TranslationCallback
from module.info import INFO
from module.config import Config


class TestTranslationCallback(unittest.TestCase):
    """TranslationCallback类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建模拟队列
        self.result_queue = queue.Queue()
        # 创建模拟日志器
        self.logger = Mock()
        # 创建模拟实时回调
        self.realtime_callback = Mock()

        # 保存原始配置，以便测试后恢复
        self.original_language = Config.LANGUAGE
        self.original_translate_target = Config.TRANSLATE_TARGET
        self.original_sentence_id_attack = Config.SENTENCE_ID_ATTACK

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始配置
        Config.LANGUAGE = self.original_language
        Config.TRANSLATE_TARGET = self.original_translate_target
        Config.SENTENCE_ID_ATTACK = self.original_sentence_id_attack

    def test_on_error_network_error(self):
        """测试处理网络错误的情况"""
        callback = TranslationCallback(self.result_queue, self.logger)
        mock_network_callback = Mock()
        callback.set_network_error_callback(mock_network_callback)

        # 测试网络相关错误
        network_error_message = {'message': 'WebSocket connection failed'}
        callback.on_error(network_error_message)

        mock_network_callback.assert_called_once()
        self.logger.error.assert_not_called()

    def test_on_error_no_callback(self):
        """测试没有错误回调的情况"""
        callback = TranslationCallback(self.result_queue, self.logger)

        # 测试没有设置错误回调时的情况
        error_message = {'message': 'Test error without callback'}
        callback.on_error(error_message)

        self.logger.error.assert_called_once()

    @patch('module.config.Config.TRANSLATE_TARGET', 'en')
    @patch('module.config.Config.SENTENCE_ID_ATTACK', 0)
    def test_on_event_with_translation(self):
        """测试处理带有翻译结果的事件"""
        callback = TranslationCallback(
            self.result_queue,
            self.logger,
            self.realtime_callback
        )

        # 创建模拟转录结果
        transcription_result = MagicMock(spec=TranscriptionResult)
        transcription_result.text = "Hello world"
        transcription_result.sentence_id = 1

        # 创建模拟翻译结果
        translation_result = MagicMock(spec=TranslationResult)
        translation_result.get_translation.return_value.text = "你好世界"

        # 调用on_event方法
        callback.on_event(
            request_id="test_id",
            transcription_result=transcription_result,
            translation_result=translation_result,
            usage=None
        )

        # 验证实时回调被调用
        self.realtime_callback.assert_called_once_with("Hello world", "你好世界")

        # 验证结果被放入队列
        self.assertFalse(self.result_queue.empty())
        result = self.result_queue.get()
        self.assertEqual(result[1], "Hello world")
        self.assertEqual(result[2], "你好世界")

    def test_on_error_non_dict_message(self):
        """测试处理非字典类型的错误消息"""
        callback = TranslationCallback(self.result_queue, self.logger)
        mock_error_callback = Mock()
        callback.callbacks['error'] = mock_error_callback

        # 测试非字典类型的错误消息
        string_error = "String error message"
        callback.on_error(string_error)

        mock_error_callback.assert_called_once()

    def test_on_error_exception_handling(self):
        """测试on_error方法中的异常处理"""
        callback = TranslationCallback(self.result_queue, self.logger)
        mock_error_callback = Mock()
        callback.callbacks['error'] = mock_error_callback

        # 创建一个会在处理时抛出异常的自定义对象
        class ExceptionRaisingObject:
            def __str__(self):
                raise Exception('Test exception')

        # 传递这个对象给on_error方法
        exception_obj = ExceptionRaisingObject()
        callback.on_error(exception_obj)

        self.logger.error.assert_called_once()
        mock_error_callback.assert_called_once()

    def test_on_event_no_sentence_id(self):
        """测试sentence_id为None的情况"""
        callback = TranslationCallback(
            self.result_queue,
            self.logger,
            self.realtime_callback
        )

        # 创建模拟转录结果（无sentence_id）
        transcription_result = MagicMock(spec=TranscriptionResult)
        transcription_result.text = "Hello world"
        transcription_result.sentence_id = None

        # 创建模拟翻译结果
        translation_result = MagicMock(spec=TranslationResult)
        translation_result.get_translation.return_value.text = "你好世界"

        # 调用on_event方法
        callback.on_event(
            request_id="test_id",
            transcription_result=transcription_result,
            translation_result=translation_result,
            usage=None
        )

        # 验证实时回调被调用
        self.realtime_callback.assert_called_once_with("Hello world", "你好世界")

        # 验证结果被放入队列
        self.assertFalse(self.result_queue.empty())

    def test_on_event_exception_handling(self):
        """测试on_event方法中的异常处理"""
        callback = TranslationCallback(self.result_queue, self.logger)

        # 创建一个会在任何操作时抛出ValueError的对象
        # 这更可能触发on_event方法中的异常处理
        class ExceptionObject:
            def __getattr__(self, name):
                raise ValueError("Mock value error")

        # 使用这个异常对象作为transcription_result
        # 这样在尝试访问任何属性时都会抛出异常
        exception_obj = ExceptionObject()

        # 调用on_event方法，应该捕获异常并记录日志
        callback.on_event(
            request_id="test_id",
            transcription_result=exception_obj,  # 这会在访问.text或.sentence_id时抛出异常
            translation_result=None,
            usage=None
        )

        # 验证logger.error被调用
        self.logger.error.assert_called_once()

    def test_get_all_texts_with_queue_empty_exception(self):
        """测试get_all_texts方法中的队列异常处理"""
        callback = TranslationCallback(self.result_queue, self.logger)

        # 模拟队列操作抛出queue.Empty异常
        with patch.object(self.result_queue, 'empty', return_value=False):
            with patch.object(self.result_queue, 'get_nowait', side_effect=queue.Empty):
                result = callback.get_all_texts()

        # 验证结果是空列表
        self.assertEqual(result, ([], []))

    def test_close(self):
        """测试关闭方法"""
        callback = TranslationCallback(self.result_queue, self.logger)

        callback.close()
        self.logger.info.assert_called_once()

    def test_get_all_texts(self):
        """测试获取所有文本的方法"""
        callback = TranslationCallback(self.result_queue, self.logger)

        # 向队列中添加一些测试数据
        self.result_queue.put((1, "Original 1", "Translated 1"))
        self.result_queue.put((2, "Original 2", "Translated 2"))

        original_texts, translated_texts = callback.get_all_texts()

        self.assertEqual(original_texts, ["Original 1", "Original 2"])
        self.assertEqual(translated_texts, ["Translated 1", "Translated 2"])
        self.assertTrue(self.result_queue.empty())

if __name__ == '__main__':
    unittest.main()
