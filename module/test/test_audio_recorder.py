import sys
import os
from PyQt5 import QtWidgets

# 确保有QApplication实例
app = QtWidgets.QApplication.instance()
if not app:
    app = QtWidgets.QApplication(sys.argv)

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import queue
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# 导入被测试的模块
from module.audio_recorder import AudioRecorder
from module.config import Config
from module.message_center import message_center
from module.info import INFO

class TestAudioRecorder(unittest.TestCase):
    """AudioRecorder类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建配置对象的模拟
        self.config_mock = Mock()
        self.config_mock.SAMPLE_RATE = 16000
        self.config_mock.CHANNELS = 1
        self.config_mock.DTYPE = 'float32'
        self.config_mock.BLOCK_SIZE = 100

        # 创建日志对象的模拟
        self.logger_mock = Mock()

        # 禁用警告和错误消息，避免测试时弹出窗口
        message_center.show_warning = Mock()
        message_center.show_critical = Mock()

        # 模拟WindowMessageBox以避免测试时弹出实际窗口
        from module.window_utils import WindowMessageBox
        WindowMessageBox.warning = Mock()
        WindowMessageBox.critical = Mock()

    @patch('module.audio_recorder.sd')  # 请替换为实际的模块名
    @patch('module.audio_recorder.Config')
    @patch('module.audio_recorder.INFO')
    def test_initialization(self, info_mock, config_mock, sd_mock):
        """测试初始化方法"""
        # 配置模拟返回值
        info_mock.get.return_value = "Test message"
        config_mock.load_language_setting.return_value = "en"
        sd_mock.query_devices.return_value = [
            {'max_input_channels': 2, 'name': 'Test Device', 'default_samplerate': 44100}
        ]
        sd_mock.default.device = [0]

        # 创建实例
        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        # 验证初始化结果
        self.assertEqual(recorder.audio_device['id'], 0)
        self.assertFalse(recorder.recording)
        self.assertIsInstance(recorder.audio_queue, queue.Queue)
        self.logger_mock.info.assert_called()

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.Config')
    @patch('module.audio_recorder.INFO')
    def test_initialize_audio_device_no_devices(self, info_mock, config_mock, sd_mock):
        """测试没有可用音频设备的情况"""
        info_mock.get.return_value = "No devices"
        config_mock.load_language_setting.return_value = "en"
        sd_mock.query_devices.return_value = []  # 没有设备

        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        self.assertEqual(recorder.audio_device['id'], -1)
        self.logger_mock.error.assert_called_with("No devices")

    @patch('module.audio_recorder.sd')
    def test_select_device(self, sd_mock):
        """测试设备选择逻辑"""
        # 创建测试实例
        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        # 测试立体声混音设备优先
        stereo_mix_device = {'max_input_channels': 2, 'name': 'Stereo Mix'}
        valid_devices = [(0, stereo_mix_device), (1, {'max_input_channels': 1, 'name': 'Mic'})]
        device_id, device_name = recorder._select_device(valid_devices)
        self.assertEqual(device_id, 0)
        self.assertEqual(device_name, 'Stereo Mix')

        # 测试默认设备选择
        sd_mock.default.device = [1]
        valid_devices = [(0, {'max_input_channels': 1, 'name': 'Mic 1'}),
                         (1, {'max_input_channels': 1, 'name': 'Mic 2'})]
        device_id, device_name = recorder._select_device(valid_devices)
        self.assertEqual(device_id, 1)
        self.assertEqual(device_name, 'Mic 2')

        # 测试默认设备不在有效列表中
        sd_mock.default.device = [2]  # 无效的设备ID
        valid_devices = [(0, {'max_input_channels': 1, 'name': 'Mic 1'}),
                         (1, {'max_input_channels': 1, 'name': 'Mic 2'})]
        device_id, device_name = recorder._select_device(valid_devices)
        self.assertEqual(device_id, 0)  # 应该选择第一个有效设备

    @patch('module.audio_recorder.sd')
    def test_switch_to_next_device(self, sd_mock):
        """测试切换到下一个设备"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0

        # 设置可用设备
        sd_mock.query_devices.return_value = [
            {'max_input_channels': 1, 'name': 'Device 0'},
            {'max_input_channels': 1, 'name': 'Device 1'},
            {'max_input_channels': 1, 'name': 'Device 2'}
        ]
        sd_mock.check_input_settings.return_value = True

        # 测试切换
        result = recorder._switch_to_next_device()
        self.assertTrue(result)
        self.assertEqual(recorder.audio_device['id'], 1)

        # 再次切换
        result = recorder._switch_to_next_device()
        self.assertTrue(result)
        self.assertEqual(recorder.audio_device['id'], 2)

        # 循环切换
        result = recorder._switch_to_next_device()
        self.assertTrue(result)
        self.assertEqual(recorder.audio_device['id'], 0)

    @patch('module.audio_recorder.sd')
    def test_select_audio_api(self, sd_mock):
        """测试音频API选择"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        # 测试优先选择WASAPI
        sd_mock.query_hostapis.return_value = [
            {'name': 'MME', 'index': 0},
            {'name': 'WASAPI', 'index': 1},
            {'name': 'DirectSound', 'index': 2}
        ]
        recorder._select_audio_api()
        self.assertEqual(recorder.audio_device['api'], 'wasapi')

        # 测试没有首选API的情况
        sd_mock.query_hostapis.return_value = [
            {'name': 'ALSA', 'index': 0}
        ]
        recorder._select_audio_api()
        self.assertIsNone(recorder.audio_device['api'])

    @patch('module.audio_recorder.sd')
    def test_set_samplerate(self, sd_mock):
        """测试采样率设置"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0

        # 测试使用设备默认采样率
        sd_mock.query_devices.return_value = {'default_samplerate': 48000}
        recorder._set_samplerate()
        self.assertEqual(recorder.config.SAMPLE_RATE, 48000)

        # 测试采样率检测
        sd_mock.query_devices.return_value = {'default_samplerate': None}
        sd_mock.check_input_settings.side_effect = [
            OSError,  # 16000失败
            None,     # 44100成功
        ]
        recorder._set_samplerate()
        self.assertEqual(recorder.config.SAMPLE_RATE, 44100)

        # 测试所有采样率都失败的情况
        sd_mock.check_input_settings.side_effect = OSError
        recorder._set_samplerate()
        self.assertEqual(recorder.config.SAMPLE_RATE, 16000)  # 默认值

    def test_audio_callback(self):
        """测试音频回调函数"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.recording = True

        # 创建测试数据
        test_data = np.array([[0.1], [0.2], [0.3]], dtype=np.float32)
        status_mock = Mock()

        # 调用回调函数
        recorder._audio_callback(test_data, None, None, status_mock)

        # 验证数据被正确处理并放入队列
        self.assertEqual(recorder.audio_queue.qsize(), 1)
        queued_data = recorder.audio_queue.get()
        self.assertEqual(queued_data.dtype, np.int16)
        self.assertTrue(np.array_equal(queued_data, (test_data * 32767).astype(np.int16)))

        # 测试录音停止状态下的回调
        recorder.recording = False
        recorder._audio_callback(test_data, None, None, status_mock)
        self.assertEqual(recorder.audio_queue.qsize(), 0)  # 不应添加新数据

    @patch('module.audio_recorder.sd')
    def test_record_audio_success(self, sd_mock):
        """测试录音成功的情况"""
        # 禁用time.sleep模拟，避免影响线程执行
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0
        recorder.audio_device['api'] = 'wasapi'  # 明确设置API

        # 配置模拟，确保录音流程能正常执行
        mock_input_stream = MagicMock()
        sd_mock.InputStream.return_value.__enter__.return_value = mock_input_stream
        sd_mock.query_devices.return_value = {
            'name': 'Test Device',
            'default_samplerate': 16000,
            'max_input_channels': 1
        }
        sd_mock.check_input_settings.return_value = None
        sd_mock.query_hostapis.return_value = [{'name': 'WASAPI', 'index': 0}]

        # 启动录音线程
        import threading
        recorder.recording = True
        test_thread = threading.Thread(target=recorder._record_audio)
        test_thread.start()

        # 给予足够时间确保InputStream被创建
        import time
        time.sleep(0.5)  # 延长等待时间

        # 停止录音
        recorder.recording = False
        test_thread.join(timeout=1.0)

        # 验证InputStream被正确调用
        self.assertTrue(sd_mock.InputStream.called, "InputStream未被调用")
        self.logger_mock.info.assert_called()

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.time.sleep')
    def test_record_audio_failure(self, sleep_mock, sd_mock):
        """测试录音失败的情况"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0
        recorder.recording = True

        # 配置模拟以抛出错误
        sd_mock.InputStream.side_effect = OSError("Device error")
        sd_mock.query_devices.return_value = {'name': 'Test Device'}
        recorder._switch_to_next_device = Mock(return_value=False)

        # 运行录音方法
        recorder._record_audio()

        # 验证
        self.logger_mock.error.assert_called()
        self.assertFalse(recorder.recording)  # 应该在失败后停止

    @patch('module.audio_recorder.threading.Thread')
    def test_start_recording(self, thread_mock):
        """测试开始录音方法"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.recording = False

        recorder.start_recording()

        self.assertTrue(recorder.recording)
        thread_mock.assert_called()
        thread_mock.return_value.daemon = True
        thread_mock.return_value.start.assert_called()
        self.logger_mock.info.assert_called_with("开始录音")

    @patch('module.audio_recorder.time.sleep')
    def test_stop_recording(self, sleep_mock):
        """测试停止录音方法"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.recording = True
        # 创建线程模拟并保存引用
        thread_mock = Mock()
        thread_mock.is_alive.return_value = True
        recorder.thread = thread_mock

        recorder.stop_recording()

        self.assertFalse(recorder.recording)
        # 使用保存的线程引用进行断言
        thread_mock.join.assert_called()
        # 使用INFO.get获取预期消息，与实际代码行为一致
        expected_message = INFO.get("recording_stopped", "zh")
        self.logger_mock.info.assert_called_with(expected_message)

    def test_get_audio_data(self):
        """测试获取音频数据方法"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        # 测试队列有数据的情况
        test_data = np.array([1, 2, 3], dtype=np.int16)
        recorder.audio_queue.put(test_data)

        data = recorder.get_audio_data()
        self.assertTrue(np.array_equal(data, test_data))
        self.assertEqual(recorder.audio_queue.qsize(), 0)

        # 测试队列为空的情况
        data = recorder.get_audio_data(timeout=0.1)
        self.assertIsNone(data)

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.Config')
    @patch('module.audio_recorder.INFO')
    def test_initialize_audio_device_validation_failure(self, info_mock, config_mock, sd_mock):
        """测试设备存在但验证失败的场景（覆盖行67-71）"""
        info_mock.get.return_value = "Device invalid"
        config_mock.load_language_setting.return_value = "en"

        # 模拟存在设备但验证失败
        sd_mock.query_devices.return_value = [
            {'max_input_channels': 2, 'name': 'Test Device', 'default_samplerate': 44100}
        ]
        sd_mock.default.device = [0]
        sd_mock.check_input_settings.side_effect = OSError("Validation failed")

        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        self.assertEqual(recorder.audio_device['id'], -1)
        # 保留原有的断言，因为mock已经设置了正确的返回值
        self.logger_mock.error.assert_called_with("Device invalid")

    @patch('module.audio_recorder.sd')
    def test_set_samplerate_with_list_device_info(self, sd_mock):
        """测试device_info为列表类型的场景（覆盖行76-81）"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0

        # 模拟device_info为列表
        sd_mock.query_devices.return_value = [
            {'default_samplerate': 48000},  # 索引0的设备
            {'default_samplerate': 44100}   # 索引1的设备
        ]

        recorder._set_samplerate()
        self.assertEqual(recorder.config.SAMPLE_RATE, 48000)

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.Config')
    def test_select_audio_api_exception(self, config_mock, sd_mock):
        """测试查询host_apis时抛出异常的场景（覆盖行124-125）"""
        config_mock.load_language_setting.return_value = "en"
        sd_mock.query_hostapis.side_effect = OSError("API query failed")

        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder._select_audio_api()

        self.assertIsNone(recorder.audio_device['api'])
        self.logger_mock.warning.assert_called()

    def test_audio_callback_with_status(self):
        """测试回调函数中status非空的场景（覆盖行177-180）"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.recording = True

        test_data = np.array([[0.1], [0.2]], dtype=np.float32)
        # 创建一个具有__str__方法的Mock对象
        status_mock = Mock()
        # 修改__str__方法的模拟方式，避免直接操作method-wrapper
        status_mock.__str__ = Mock(return_value="Input overflow")

        # 调用回调函数
        with patch('module.audio_recorder.Config') as config_mock:
            config_mock.load_language_setting.return_value = "en"
            with patch('module.audio_recorder.INFO') as info_mock:
                info_mock.get.return_value = "Audio status: {status}"
                recorder._audio_callback(test_data, None, None, status_mock)

                self.logger_mock.info.assert_called_with("Audio status: Input overflow")

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.time.sleep')
    def test_record_audio_with_invalid_device_retry(self, sleep_mock, sd_mock):
        """测试设备ID为-1时的重试流程（覆盖行252-256）"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = -1  # 初始设备无效
        recorder.recording = True

        # 使用计数器跟踪初始化调用次数
        init_count = 0

        def mock_initialize():
            nonlocal init_count
            init_count += 1
            if init_count == 1:
                recorder.audio_device['id'] = -1  # 第一次失败
            else:
                recorder.audio_device['id'] = 0   # 第二次成功

        # 替换实例方法
        recorder._initialize_audio_device = mock_initialize

        sd_mock.check_input_settings.return_value = None
        sd_mock.query_devices.return_value = {'name': 'Valid Device'}

        # 使用模拟的InputStream避免实际创建音频流
        with patch('module.audio_recorder.sd.InputStream') as stream_mock:
            stream_context = MagicMock()
            stream_mock.return_value.__enter__.return_value = stream_context

            # 添加超时控制，防止无限循环
            import threading
            test_thread = threading.Thread(target=recorder._record_audio)
            test_thread.start()
            # 增加超时时间并分两步join，确保线程有足够时间处理终止
            test_thread.join(timeout=3.0)  # 第一次等待

            # 明确停止录音并给线程处理时间
            recorder.recording = False
            test_thread.join(timeout=2.0)  # 第二次等待

            self.assertEqual(init_count, 2)  # 验证重试了一次
            self.assertFalse(test_thread.is_alive(), "测试线程未能正常结束")

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.Config')
    @patch('module.audio_recorder.INFO')
    def test_initialize_audio_device_oserror(self, info_mock, config_mock, sd_mock):
        """测试_initialize_audio_device方法中捕获OSError异常的情况（覆盖行76-81）"""
        info_mock.get.side_effect = lambda key, *args: {
            "error": "Error",
            "warning": "Warning"
        }.get(key, "Default")
        config_mock.load_language_setting.return_value = "en"
        sd_mock.query_devices.side_effect = OSError("Device error")

        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        self.logger_mock.error.assert_called()
        # 使用在setUp中已经模拟的message_center.show_warning来断言
        message_center.show_warning.assert_called()

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.Config')
    @patch('module.audio_recorder.INFO')
    def test_initialize_audio_device_show_warning_exception(self, info_mock, config_mock, sd_mock):
        """测试_initialize_audio_device方法中show_warning抛出异常的情况（覆盖行88-90）"""
        info_mock.get.return_value = "Warning message"
        config_mock.load_language_setting.return_value = "en"
        sd_mock.query_devices.side_effect = OSError("Device error")

        # 模拟message_center.show_warning抛出异常
        message_center.show_warning.side_effect = Exception("UI display error")

        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        # 验证logger_mock.error被调用，记录了show_warning抛出的异常
        self.logger_mock.error.assert_called_with("显示警告消息时出错: UI display error")

    @patch('module.audio_recorder.sd')
    def test_switch_to_next_device_value_error(self, sd_mock):
        """测试_switch_to_next_device方法中捕获ValueError异常的情况（覆盖行124-125）"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 999  # 一个不在有效列表中的设备ID

        sd_mock.query_devices.return_value = [
            {'max_input_channels': 1, 'name': 'Device 0'},
            {'max_input_channels': 1, 'name': 'Device 1'}
        ]
        sd_mock.check_input_settings.return_value = True

        result = recorder._switch_to_next_device()

        self.assertTrue(result)
        self.assertEqual(recorder.audio_device['id'], 0)  # 应该选择第一个设备

    @patch('module.audio_recorder.sd')
    @patch('module.audio_recorder.Config')
    @patch('module.audio_recorder.INFO')
    def test_switch_to_next_device_error_handling(self, info_mock, config_mock, sd_mock):
        """测试_switch_to_next_device方法中的错误处理（覆盖行142-154）"""
        info_mock.get.side_effect = lambda key, *args: {
            "backup_device_unavailable": "Device {name} unavailable: {error}",
            "no_backup_devices": "No backup devices",
            "device_switch_error": "Switch error: {error}"
        }.get(key, "Default")
        config_mock.load_language_setting.return_value = "en"

        # 测试设备验证失败的情况
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0

        sd_mock.query_devices.return_value = [
            {'max_input_channels': 1, 'name': 'Device 0'},
            {'max_input_channels': 1, 'name': 'Device 1'}
        ]
        sd_mock.check_input_settings.side_effect = OSError("Validation failed")

        result = recorder._switch_to_next_device()
        self.logger_mock.error.assert_called_with("Device Device 1 unavailable: Validation failed")

        # 测试没有备用设备的情况
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.audio_device['id'] = 0

        sd_mock.query_devices.return_value = []

        result = recorder._switch_to_next_device()
        self.logger_mock.warning.assert_called_with("No backup devices")

        # 测试方法抛出OSError的情况
        recorder = AudioRecorder(self.config_mock, self.logger_mock)

        sd_mock.query_devices.side_effect = OSError("API error")

        result = recorder._switch_to_next_device()
        self.logger_mock.error.assert_called_with("Switch error: API error")

    def test_stop_recording_queue_empty_exception(self):
        """测试stop_recording方法中清空队列时捕获queue.Empty异常的情况（覆盖行340-343）"""
        recorder = AudioRecorder(self.config_mock, self.logger_mock)
        recorder.recording = True
        recorder.thread = None  # 不需要线程来测试队列清空

        # 创建一个会在get_nowait()时抛出queue.Empty异常的队列
        original_get_nowait = queue.Queue.get_nowait

        def mock_get_nowait(self, *args, **kwargs):
            raise queue.Empty()

        try:
            # 替换方法
            queue.Queue.get_nowait = mock_get_nowait
            # 模拟队列不为空
            recorder.audio_queue.empty = Mock(side_effect=[False, True])

            recorder.stop_recording()
            # 如果没有抛出异常，则测试通过
            self.assertTrue(True)
        finally:
            # 恢复原始方法
            queue.Queue.get_nowait = original_get_nowait

if __name__ == '__main__':
    unittest.main()
