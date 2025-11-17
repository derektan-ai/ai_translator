"""
音频录制模块，提供音频设备检测、录音控制及音频数据处理功能。
使用sounddevice库进行音频捕获，结合PyQt5提供潜在的UI交互支持，
实现了设备自动检测、采样率选择、音频流处理等核心功能。
"""
import time
import queue
import threading
import numpy as np
import sounddevice as sd
from .config import Config
from .info import INFO
from .message_center import message_center
# pylint: disable=c-extension-no-member
class AudioRecorder:
    """实现设备自动检测、采样率选择、音频流处理等功能"""
    def __init__(self, config, logger=None):
        """初始化音频录制器，设置配置和初始状态"""
        self.config = config
        self.logger = logger  # 保存logger
        self.audio_queue = queue.Queue()
        self.recording = False
        self.thread = None
        # 合并设备相关属性为字典，减少实例属性数量
        self.audio_device = {
            'id': -1,
            'api': None
        }

        # 错误回调 - 添加类型注释明确为可选的可调用对象
        self.error_callback = None

        # 初始化音频设备
        self._initialize_audio_device()

    def _initialize_audio_device(self):
        """
        检测并选择合适的音频输入设备，优先选择立体声混音设备，
        同时检测并设置设备支持的最佳采样率
        """
        try:
            devices = sd.query_devices()
            valid_input_devices = [
                (i, device) for i, device in enumerate(devices)
                if device['max_input_channels'] > 0
            ]

            if not valid_input_devices:
                error_msg = INFO.get("no_input_devices", Config.load_language_setting())
                self.logger.error(error_msg)
                self.audio_device['id'] = -1
                return

            # 选择音频设备
            selected_id, selected_name = self._select_device(valid_input_devices)

            # 验证设备是否可用
            try:
                sd.check_input_settings(device=selected_id)
                self.audio_device['id'] = selected_id
                msg = (
                    INFO.get("found_sound_device", Config.load_language_setting())
                    + f": {selected_name} (ID: {selected_id})"
                )
                self.logger.info(msg)
            except OSError:
                error_msg = INFO.get("device_invalid", Config.load_language_setting())
                self.logger.error(error_msg)
                self.audio_device['id'] = -1
                return

            # 检测并设置采样率
            self._set_samplerate()

        except OSError as e:
            error_msg = INFO.get("error", Config.load_language_setting()) + f": {str(e)}"
            self.logger.error(error_msg)

            # 使用message_center发送错误消息
            try:
                message_center.show_warning(
                    INFO.get("warning", Config.load_language_setting()),
                    error_msg,
                    parent=None
                )
            except Exception as exception:  # pylint: disable=broad-exception-caught
                if self.logger:
                    self.logger.error(f"显示警告消息时出错: {str(exception)}")

    def _select_device(self, valid_input_devices):
        """选择合适的音频输入设备，优先立体声混音，其次默认设备"""
        # 选择立体声混音，使用info中的映射而非硬编码字符串
        stereo_mix_cn = INFO.get("stereo_mix", "zh")
        stereo_mix_en = INFO.get("stereo_mix", "en")

        stereo_mix_devices = [
            (i, device) for i, device in valid_input_devices
            if stereo_mix_cn in device['name'] or stereo_mix_en in device['name'].lower()
        ]

        if stereo_mix_devices:
            return stereo_mix_devices[0][0], stereo_mix_devices[0][1]['name']

        # 使用默认输入设备
        default_device = sd.default.device[0]
        for i, device in valid_input_devices:
            if i == default_device:
                return i, device['name']

        # 如果默认设备不在有效列表中，选择第一个有效设备
        return valid_input_devices[0][0], valid_input_devices[0][1]['name']

    def _switch_to_next_device(self):
        """切换到下一个可用的音频输入设备"""
        lang = Config.load_language_setting()
        try:
            devices = sd.query_devices()
            valid_input_devices = [
                i for i, device in enumerate(devices)
                if device['max_input_channels'] > 0
            ]

            if valid_input_devices:
                # 找到当前设备在有效列表中的位置
                try:
                    current_idx = valid_input_devices.index(self.audio_device['id'])
                except ValueError:
                    current_idx = -1

                # 计算下一个设备索引
                next_idx = (current_idx + 1) % len(valid_input_devices) if current_idx != -1 else 0

                new_device_id = valid_input_devices[next_idx]
                new_device_name = devices[new_device_id]['name']

                # 验证新设备
                try:
                    sd.check_input_settings(device=new_device_id)
                    self.audio_device['id'] = new_device_id
                    msg = INFO.get("switch_to_backup_device", lang).format(
                        name=new_device_name, id=new_device_id
                    )
                    self.logger.info(msg)
                    return True
                except OSError as e:
                    msg = INFO.get("backup_device_unavailable", lang).format(
                        name=new_device_name, error=str(e)
                    )
                    self.logger.error(msg)

            msg = INFO.get("no_backup_devices", lang)
            self.logger.warning(msg)
            return False
        except OSError as e:
            msg = INFO.get("device_switch_error", lang).format(error=str(e))
            self.logger.error(msg)
            return False

    def _select_audio_api(self):
        """选择最佳的音频API，优先使用WASAPI、DirectSound和MME"""
        lang = Config.load_language_setting()
        try:
            host_apis = sd.query_hostapis()
            api_names = [api.get('name', '').lower() for api in host_apis]

            preferred_apis = ['wasapi', 'directsound', 'mme']
            for api in preferred_apis:
                for idx, name in enumerate(api_names):
                    if api in name:
                        self.audio_device['api'] = name
                        self.logger.info(
                            INFO.get("select_audio_api", lang).format(
                                api=self.audio_device['api'], idx=idx
                            )
                        )
                        return

            self.audio_device['api'] = None
            self.logger.info(INFO.get("use_default_audio_api", lang))
        except OSError as e:
            msg = INFO.get("audio_api_selection_failed", lang).format(error=str(e))
            self.logger.warning(msg)
            self.audio_device['api'] = None

    def _set_samplerate(self):
        """检测并设置设备支持的最佳采样率"""
        lang = Config.load_language_setting()
        device_info = sd.query_devices(self.audio_device['id'])
        # 确保device_info是字典而不是列表
        if isinstance(device_info, list) and self.audio_device['id'] < len(device_info):
            device_info = device_info[self.audio_device['id']]

        default_sr = device_info.get('default_samplerate', None)
        if default_sr:
            self.config.SAMPLE_RATE = int(default_sr)
            self.logger.info(
                INFO.get("use_device_samplerate", lang).format(rate=self.config.SAMPLE_RATE)
            )
            return

        sample_rates = [16000, 44100, 48000, 22050, 11025, 8000]
        for sr in sample_rates:
            try:
                sd.check_input_settings(
                    device=self.audio_device['id'],
                    samplerate=sr,
                    channels=self.config.CHANNELS,
                    dtype=self.config.DTYPE
                )
                self.config.SAMPLE_RATE = sr
                self.logger.info(
                    INFO.get("use_samplerate", lang).format(rate=self.config.SAMPLE_RATE)
                )
                return
            except OSError:
                continue

        self.config.SAMPLE_RATE = 16000
        self.logger.info(
            INFO.get("use_default_samplerate", lang).format(rate=self.config.SAMPLE_RATE)
        )

    def _audio_callback(self, indata, _frames, _time_info, status):
        """
        音频流回调函数，处理并将音频数据放入队列

        参数:
            indata: 音频数据
            _frames: 帧数量（未使用）
            _time_info: 时间信息（未使用）
            status: 音频状态信息
        """
        if status:
            lang = Config.load_language_setting()
            self.logger.info(
                INFO.get("audio_status", lang).format(status=status)
            )
        if not self.recording:
            return

        # 将音频数据转换为int16格式
        indata_int16 = (indata * 32767).astype(np.int16)
        self.audio_queue.put(indata_int16.copy())

    def _record_audio(self):
        """音频录制的内部实现，处理音频流和重连逻辑"""
        lang = Config.load_language_setting()
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries and self.recording:
            try:
                # 检查设备是否有效，无效则重新初始化
                if self.audio_device['id'] == -1:
                    self._initialize_audio_device()
                    if self.audio_device['id'] == -1:
                        time.sleep(2)
                        retry_count += 1
                        continue

                stream_params = {
                    'samplerate': self.config.SAMPLE_RATE,
                    'device': self.audio_device['id'],
                    'channels': self.config.CHANNELS,
                    'dtype': self.config.DTYPE,
                    'callback': self._audio_callback,
                    'blocksize': int(self.config.SAMPLE_RATE * self.config.BLOCK_SIZE / 1000)
                }

                host_api_id = -1
                if self.audio_device['api']:
                    host_apis = sd.query_hostapis()
                    for api in host_apis:
                        if self.audio_device['api'].lower() in api.get('name', '').lower():
                            host_api_id = api.get('index', -1)
                            break

                if host_api_id != -1:
                    stream_params['host_api'] = host_api_id

                with sd.InputStream(** stream_params):
                    device_name = sd.query_devices(self.audio_device['id']).get(
                        'name', INFO.get("unknown_device", lang)
                    )
                    status_msg = INFO.get("audio_stream_info", lang).format(
                        name=device_name,
                        rate=self.config.SAMPLE_RATE,
                        channels=self.config.CHANNELS
                    )
                    self.logger.info(status_msg)
                    while self.recording:
                        time.sleep(0.1)
                    return
            except OSError as e:
                retry_count += 1
                error_msg = INFO.get("audio_stream_failed", lang).format(
                    retry=retry_count,
                    max=max_retries,
                    error=str(e)
                )
                self.logger.error(error_msg)

                # 尝试切换到下一个可用设备
                self._switch_to_next_device()
                time.sleep(2)

        error_msg = INFO.get("recording_failed_max_retries", lang)
        self.logger.error(error_msg)
        self.recording = False

    def start_recording(self):
        """开始录音"""
        if not self.recording:
            self.recording = True
            self.thread = threading.Thread(target=self._record_audio)
            self.thread.daemon = True
            self.thread.start()
            self.logger.info(INFO.get("start_recording", Config.load_language_setting()))

    def stop_recording(self):
        """停止录音并确保线程正确终止"""
        if self.recording:
            self.recording = False
            if self.thread and self.thread.is_alive():
                # 增加超时机制确保线程终止
                start_time = time.time()
                timeout = 3.0  # 延长超时时间
                while self.thread.is_alive() and time.time() - start_time < timeout:
                    time.sleep(0.1)

                # 调用join方法确保线程正确结束
                self.thread.join()

                # 如果线程仍在运行，记录错误并强制清理
                if self.thread.is_alive():
                    lang = Config.load_language_setting()
                    self.logger.error(INFO.get("recording_thread_timeout", lang))

                # 清除线程引用，帮助垃圾回收
                self.thread = None

            # 清空音频队列，释放资源
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            lang = Config.load_language_setting()
            self.logger.info(INFO.get("recording_stopped", lang))

    def get_audio_data(self, timeout=1.0):
        """从音频队列获取录制的音频数据"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
