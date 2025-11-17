"""
配置模块，包含应用程序的各种配置参数及相关操作方法。
涵盖路径设置、API密钥管理、语言配置、网络检测等功能。
"""
import os
import sys
import configparser
import base64
import re
import time
from .info import INFO

class Config:
    """获取工作目录 - 对于打包环境，使用可执行文件所在目录；对于开发环境，使用脚本所在目录"""
    if getattr(sys, 'frozen', False):
        # 打包环境下，使用sys.executable获取可执行文件路径，再取其父目录作为工作目录
        WORK_DIR = os.path.dirname(os.path.abspath(sys.executable))
        # 依赖包所在目录（PyInstaller创建的_MEIPASS临时目录）
        BASE_DIR = getattr(sys, '_MEIPASS', '')
    else:
        # 开发环境下，使用脚本所在目录作为工作目录和基础目录
        WORK_DIR = os.path.dirname(os.path.abspath(__file__))
        BASE_DIR = WORK_DIR

    # 安装语言常量配置
    LANGUAGE_CHINESE = "zh"
    LANGUAGE_ENGLISH = "en"
    LANGUAGE_JAPANESE = "ja"
    LANGUAGE_KOREAN = "ko"

    # 子目录 - 所有文件操作都基于工作目录，而不是父目录
    LOG_DIR = os.path.join(WORK_DIR, "log")
    RESULT_DIR = os.path.join(WORK_DIR, "result")

    # 创建目录
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(RESULT_DIR, exist_ok=True)  # 确保结果目录存在

    # 对于开发环境，设置项目根目录
    PROJECT_ROOT = None
    if not getattr(sys, 'frozen', False):
        # 项目根目录是模块目录的父目录
        PROJECT_ROOT = os.path.dirname(WORK_DIR)

    # 支持的API密钥文件扩展名列表
    API_KEY_FILE_EXTS = ['.txt', '.doc', '.docx']

    # API密钥正则表达式（以sk-开头，长度为35，仅包含字母和数字）
    API_KEY_REGEX = r'^sk-[a-zA-Z0-9]{32}$'

    # 网络检测配置
    NETWORK_CHECK_TIMEOUT = 10  # 网络检测超时时间(秒)
    CONNECTION_CHECK_RETRIES = 3  # 连接检测重试次数
    CONNECTION_CHECK_DELAY = 2  # 连接检测重试间隔(秒)

    # 记录程序启动时间，用于统一文件名时间戳
    START_TIMESTAMP = time.strftime('%Y%m%d_%H%M%S')

    # 日志文件
    LOG_FILE = os.path.join(LOG_DIR, f"translation_log_{START_TIMESTAMP}.txt")

    # 录音参数
    SAMPLE_RATE = 48000
    BLOCK_SIZE = 100
    CHANNELS = 2
    DTYPE = 'float32'

    # 音频API选择
    AUDIO_API = None

    # 语种配置 - 初始化为None，将在UI中设置
    ASR_LANGUAGE = None  # 语音识别语种
    TRANSLATE_SOURCE = None  # 翻译源语种
    TRANSLATE_TARGET = None  # 翻译目标语种

    # API密钥 - 初始化为None
    DASHSCOPE_API_KEY = None

    # 限制最大翻译器实例数量 - 【重要】不要修改！！
    MAX_RECOGNIZERS = 1

    # API请求超时时间
    API_REQUEST_TIMEOUT = 30  # API请求超时时间(秒)

    # 重连延迟时间(秒)
    RECONNECT_DELAY = 5  # 重连延迟(秒)
    MAX_RECONNECT_ATTEMPTS = 3  # 最大重连次数

    # 心跳检测间隔(秒)
    HEARTBEAT_INTERVAL = 5  # 心跳检测间隔

    # 空闲超时阈值(秒)
    IDLE_TIMEOUT_THRESHOLD = 20  # 空闲超时阈值

    # sentence_id_attack配置
    SENTENCE_ID_ATTACK = 2  # 忽略每个sentence_id的前n个结果

    # 语言配置
    LANGUAGE = LANGUAGE_CHINESE  # 默认中文
    # 语言配置文件放在工作目录下
    LANGUAGE_FILE = os.path.join(WORK_DIR, "language_config.ini")

    @staticmethod
    def _validate_api_key(api_key):
        """验证API密钥格式是否正确"""
        return re.match(Config.API_KEY_REGEX, api_key) is not None

    @staticmethod
    def _encrypt_api_key(api_key):
        """使用Base64加密API密钥"""
        return base64.b64encode(api_key.encode('utf-8')).decode('utf-8')

    @staticmethod
    def _decrypt_api_key(encrypted_api_key):
        """使用Base64解密API密钥"""
        if encrypted_api_key is None:
            return None
        try:
            return base64.b64decode(encrypted_api_key.encode('utf-8')).decode('utf-8')
        except (ValueError, TypeError, base64.binascii.Error):
            return None

    @staticmethod
    def _is_encrypted_api_key(content):
        """检查内容是否是加密的API密钥"""
        try:
            # 尝试解密，如果解密后是有效的API密钥格式，则认为是加密的API密钥
            decrypted = Config._decrypt_api_key(content.strip())
            return decrypted is not None and Config._validate_api_key(decrypted)
        except (ValueError, TypeError, AttributeError):
            return False

    @staticmethod
    def _process_file_for_api_key(file_path):
        """处理单个文件，查找API密钥"""
        try:
            print(f"正在检查文件: {file_path}")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # 尝试使用正则表达式匹配API密钥
                matches = re.findall(Config.API_KEY_REGEX, content)
                if matches:
                    # 使用第一个匹配的API密钥
                    api_key = matches[0]
                    Config.DASHSCOPE_API_KEY = api_key
                    print(f"从文件 {file_path} 中找到有效API密钥")
                    return True
        except (IOError, UnicodeDecodeError) as e:
            print(f"读取文件 {file_path} 失败: {e}")
        return False

    @staticmethod
    def _scan_directory_for_api_keys(search_dir):
        """扫描目录中的文件查找API密钥"""
        print(f"正在扫描目录: {search_dir}")
        try:
            for root, _, files in os.walk(search_dir):
                # 限制搜索深度，避免搜索过深
                current_depth = root[len(search_dir):].count(os.sep)
                if current_depth > 1:  # 只搜索当前目录和直接子目录
                    continue

                for file in files:
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in Config.API_KEY_FILE_EXTS:
                        file_path = os.path.join(root, file)
                        if Config._process_file_for_api_key(file_path):
                            return True
        except (OSError, PermissionError, FileNotFoundError) as e:
            print(f"扫描目录 {search_dir} 时出错: {e}")
        return False

    @staticmethod
    def load_api_key():
        """加载API密钥，支持从多个文件中查找有效的API密钥"""
        print("开始在所有可能的目录中扫描包含API密钥的文件...")

        # 确定搜索目录
        search_dirs = [Config.WORK_DIR]

        # 对于开发环境，额外搜索项目根目录
        if Config.PROJECT_ROOT is not None:
            search_dirs.append(Config.PROJECT_ROOT)

        print(f"搜索目录列表: {search_dirs}")

        # 遍历所有搜索目录中的文件
        for search_dir in search_dirs:
            if Config._scan_directory_for_api_keys(search_dir):
                return

        # 如果没有找到有效的API密钥
        print("未找到有效的API密钥")
        Config.DASHSCOPE_API_KEY = None
        return

        # 函数已完成，API密钥已设置或为None

    @classmethod
    def save_language_setting(cls, language):
        """保存语言设置到ini文件"""
        try:
            # 创建配置解析器
            config = configparser.ConfigParser()
            # 添加section和键值对
            config['Settings'] = {'language': language}

            # 写入文件
            with open(cls.LANGUAGE_FILE, 'w', encoding='utf-8') as f:
                config.write(f)

            cls.LANGUAGE = language
        except (OSError, configparser.Error) as e:
            print(f"{INFO.get('save_language_failed')}: {e}")
            # 尝试创建文件目录（无论是否存在）
            try:
                dir_name = os.path.dirname(cls.LANGUAGE_FILE)
                os.makedirs(dir_name, exist_ok=True)
                # 再次尝试保存
                config = configparser.ConfigParser()
                config['Settings'] = {'language': language}
                with open(cls.LANGUAGE_FILE, 'w', encoding='utf-8') as f:
                    config.write(f)
                cls.LANGUAGE = language
            except (OSError, configparser.Error) as e2:
                print(f"{INFO.get('save_language_retry_failed')}: {e2}")

    @classmethod
    def load_language_setting(cls):
        """从ini文件加载语言设置"""
        try:
            if os.path.exists(cls.LANGUAGE_FILE):
                # 创建配置解析器
                config = configparser.ConfigParser()
                # 读取文件
                config.read(cls.LANGUAGE_FILE, encoding='utf-8')
                # 获取语言设置
                cls.LANGUAGE = config.get('Settings', 'language', fallback=cls.LANGUAGE_CHINESE)
                return cls.LANGUAGE
        except (OSError, configparser.Error) as e:
            print(f"{INFO.get('load_language_failed')}: {e}")
        return cls.LANGUAGE
