import unittest
import sys
import os
import base64
import re
from unittest.mock import patch, MagicMock, mock_open, call
import configparser

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from module.config import Config
from module.info import INFO


class TestConfig(unittest.TestCase):
    """Config类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始配置，以便测试后恢复
        self.original_language = Config.LANGUAGE
        self.original_api_key = getattr(Config, 'DASHSCOPE_API_KEY', None)
        self.original_work_dir = Config.WORK_DIR
        self.original_base_dir = Config.BASE_DIR

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始配置
        Config.LANGUAGE = self.original_language
        Config.WORK_DIR = self.original_work_dir
        Config.BASE_DIR = self.original_base_dir
        if self.original_api_key is not None:
            Config.DASHSCOPE_API_KEY = self.original_api_key
        else:
            if hasattr(Config, 'DASHSCOPE_API_KEY'):
                delattr(Config, 'DASHSCOPE_API_KEY')

    def test_decrypt_api_key_invalid(self):
        """测试解密无效的API密钥"""
        # 测试无效base64
        result = Config._decrypt_api_key("invalid_base64")
        self.assertIsNone(result)

        # 测试有效的base64但解密后不是有效的API密钥格式 (解密为"test")
        result = Config._decrypt_api_key("dGVzdA==")
        self.assertEqual(result, "test")

        # 测试None情况
        result = Config._decrypt_api_key(None)
        self.assertIsNone(result)

    def test_is_encrypted_api_key_invalid(self):
        """测试检查无效的加密API密钥"""
        invalid_keys = [
            "sk-1234567890abcdef1234567890abcdef",  # 未加密的API密钥
            "invalid_key",
            "",
            "dGVzdA==",  # 有效的base64但解密后不是有效的API密钥格式
        ]
        for key in invalid_keys:
            self.assertFalse(Config._is_encrypted_api_key(key))

    @patch('module.config.os.walk')
    @patch('module.config.open', new_callable=mock_open, read_data='sk-1234567890abcdef1234567890abcdef')
    def test_load_api_key_from_txt_file(self, mock_file, mock_walk):
        """测试从txt文件加载API密钥"""
        # 配置模拟
        mock_walk.return_value = [
            (Config.WORK_DIR, [], ['api_key.txt'])
        ]

        # 执行测试
        Config.load_api_key()

        # 验证结果
        self.assertEqual(Config.DASHSCOPE_API_KEY, "sk-1234567890abcdef1234567890abcdef")

    @patch('module.config.os.walk')
    @patch('module.config.open', new_callable=mock_open, read_data='sk-1234567890abcdef1234567890abcdef')
    def test_load_api_key_from_doc_file(self, mock_file, mock_walk):
        """测试从doc文件加载API密钥"""
        # 配置模拟
        mock_walk.return_value = [
            (Config.WORK_DIR, [], ['api_key.doc'])
        ]

        # 执行测试
        Config.load_api_key()

        # 验证结果
        self.assertEqual(Config.DASHSCOPE_API_KEY, "sk-1234567890abcdef1234567890abcdef")

    def test_load_api_key_from_file_with_multiple_keys(self):
        """测试从包含多个API密钥的文件中加载"""
        # 测试正则表达式匹配多个密钥
        test_content = 'sk-1234567890abcdef1234567890abcdef\nsk-abcdef1234567890abcdef1234567890'
        matches = re.findall(Config.API_KEY_REGEX, test_content, re.MULTILINE)

        # 验证匹配了2个密钥
        self.assertEqual(len(matches), 2)
        # 验证第一个密钥
        self.assertEqual(matches[0], 'sk-1234567890abcdef1234567890abcdef')
        # 验证第二个密钥
        self.assertEqual(matches[1], 'sk-abcdef1234567890abcdef1234567890')

    @patch('module.config.os.walk')
    @patch('module.config.open', side_effect=IOError("File not found"))
    def test_load_api_key_file_read_error(self, mock_file, mock_walk):
        """测试读取文件时发生错误"""
        # 配置模拟
        mock_walk.return_value = [
            (Config.WORK_DIR, [], ['api_key.txt'])
        ]

        # 保存原始API密钥
        original_api_key = getattr(Config, 'DASHSCOPE_API_KEY', None)

        # 执行测试
        Config.load_api_key()

        # 验证结果
        self.assertIsNone(Config.DASHSCOPE_API_KEY)

    @patch('module.config.os.walk')
    @patch('module.config.open', new_callable=mock_open, read_data='invalid_api_key_format')
    def test_load_api_key_no_valid_key_found(self, mock_file, mock_walk):
        """测试没有找到有效的API密钥"""
        # 配置模拟
        mock_walk.return_value = [
            (Config.WORK_DIR, [], ['config.txt'])
        ]

        # 执行测试
        Config.load_api_key()

        # 验证结果
        self.assertIsNone(Config.DASHSCOPE_API_KEY)

    def test_load_api_key_with_encrypted_key(self):
        """测试加载加密的API密钥"""
        # 创建一个有效的API密钥
        api_key = "sk-1234567890abcdef1234567890abcdef"
        encrypted_key = Config._encrypt_api_key(api_key)

        # 加密密钥不会被正则表达式匹配，所以我们需要测试加密密钥识别功能
        self.assertTrue(Config._is_encrypted_api_key(encrypted_key))
        self.assertEqual(Config._decrypt_api_key(encrypted_key), api_key)

    @patch('module.config.open', new_callable=mock_open)
    @patch('module.config.configparser.ConfigParser')
    def test_save_language_setting_success(self, mock_config, mock_file):
        """测试成功保存语言设置"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        # 执行测试
        Config.save_language_setting(Config.LANGUAGE_ENGLISH)

        # 验证结果
        self.assertEqual(Config.LANGUAGE, Config.LANGUAGE_ENGLISH)
        mock_config_instance.__setitem__.assert_called_once_with('Settings', {'language': Config.LANGUAGE_ENGLISH})
        mock_config_instance.write.assert_called_once()

    @patch('module.config.os.makedirs')
    @patch('module.config.open', new_callable=mock_open)
    @patch('module.config.configparser.ConfigParser')
    def test_save_language_setting_retry_success(self, mock_config, mock_file, mock_makedirs):
        """测试保存语言设置失败后重试成功"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        # 第一次写入失败，第二次成功
        mock_file.side_effect = [OSError("Permission denied"), mock_file()]

        # 执行测试
        Config.save_language_setting(Config.LANGUAGE_ENGLISH)

        # 验证结果
        self.assertEqual(Config.LANGUAGE, Config.LANGUAGE_ENGLISH)
        mock_makedirs.assert_called_once()
        self.assertEqual(mock_config_instance.write.call_count, 1)

    @patch('module.config.os.makedirs')
    @patch('module.config.open', side_effect=OSError("Permission denied"))
    @patch('module.config.configparser.ConfigParser')
    def test_save_language_setting_failure(self, mock_config, mock_file, mock_makedirs):
        """测试保存语言设置失败"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        # 保存原始语言设置
        original_language = Config.LANGUAGE

        # 执行测试
        Config.save_language_setting(Config.LANGUAGE_ENGLISH)

        # 验证结果 - 语言设置应保持不变
        self.assertEqual(Config.LANGUAGE, original_language)

    @patch('module.config.os.path.exists', return_value=True)
    @patch('module.config.open', new_callable=mock_open, read_data='[Settings]\nlanguage = en')
    @patch('module.config.configparser.ConfigParser')
    def test_load_language_setting_success(self, mock_config, mock_file, mock_exists):
        """测试成功加载语言设置"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.get.return_value = Config.LANGUAGE_ENGLISH

        # 执行测试
        result = Config.load_language_setting()

        # 验证结果
        self.assertEqual(result, Config.LANGUAGE_ENGLISH)
        self.assertEqual(Config.LANGUAGE, Config.LANGUAGE_ENGLISH)
        mock_config_instance.read.assert_called_once()

    @patch('module.config.os.path.exists', return_value=False)
    def test_load_language_setting_file_not_found(self, mock_exists):
        """测试配置文件不存在时加载语言设置"""
        # 保存原始语言设置
        original_language = Config.LANGUAGE

        # 执行测试
        result = Config.load_language_setting()

        # 验证结果 - 应返回默认语言
        self.assertEqual(result, original_language)

    @patch('module.config.os.path.exists', return_value=True)
    @patch('module.config.open', new_callable=mock_open)
    @patch('module.config.configparser.ConfigParser')
    def test_load_language_setting_error(self, mock_config, mock_file, mock_exists):
        """测试加载语言设置时发生错误"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.read.side_effect = configparser.Error("Parse error")

        # 保存原始语言设置
        original_language = Config.LANGUAGE

        # 执行测试
        result = Config.load_language_setting()

        # 验证结果 - 应返回默认语言
        self.assertEqual(result, original_language)

    @patch('module.config.os.path.exists', return_value=True)
    @patch('module.config.open', new_callable=mock_open, read_data='[Settings]')
    @patch('module.config.configparser.ConfigParser')
    def test_load_language_setting_missing_key(self, mock_config, mock_file, mock_exists):
        """测试语言设置文件缺少language键"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance
        mock_config_instance.get.side_effect = configparser.NoOptionError('language', 'Settings')

        # 保存原始语言设置
        original_language = Config.LANGUAGE

        # 执行测试
        result = Config.load_language_setting()

        # 验证结果 - 应返回默认语言
        self.assertEqual(result, original_language)

    def test_directory_creation(self):
        """测试目录创建功能"""
        # 验证LOG_DIR和RESULT_DIR已创建
        self.assertTrue(os.path.exists(Config.LOG_DIR))
        self.assertTrue(os.path.exists(Config.RESULT_DIR))

    @patch('module.config.os.makedirs')
    @patch('module.config.open', side_effect=[OSError("Permission denied"), mock_open()()])
    @patch('module.config.configparser.ConfigParser')
    def test_save_language_setting_with_makedirs_success(self, mock_config, mock_file, mock_makedirs):
        """测试保存语言设置时创建目录并成功重试"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        # 执行测试
        Config.save_language_setting(Config.LANGUAGE_ENGLISH)

        # 验证结果
        self.assertEqual(Config.LANGUAGE, Config.LANGUAGE_ENGLISH)
        mock_makedirs.assert_called_once_with(os.path.dirname(Config.LANGUAGE_FILE), exist_ok=True)
        self.assertEqual(mock_config_instance.write.call_count, 1)

    @patch('module.config.os.makedirs')
    @patch('module.config.open', side_effect=[OSError("Permission denied"), OSError("Still no permission")])
    @patch('module.config.configparser.ConfigParser')
    def test_save_language_setting_with_makedirs_failure(self, mock_config, mock_file, mock_makedirs):
        """测试保存语言设置时创建目录但重试仍然失败"""
        # 配置模拟
        mock_config_instance = MagicMock()
        mock_config.return_value = mock_config_instance

        # 保存原始语言设置
        original_language = Config.LANGUAGE

        # 执行测试
        Config.save_language_setting(Config.LANGUAGE_ENGLISH)

        # 验证结果 - 语言设置应保持不变
        self.assertEqual(Config.LANGUAGE, original_language)
        mock_makedirs.assert_called_once_with(os.path.dirname(Config.LANGUAGE_FILE), exist_ok=True)

    def test_is_encrypted_api_key_with_invalid_input(self):
        """测试_is_encrypted_api_key方法处理无效输入"""
        # 测试None输入
        result = Config._is_encrypted_api_key(None)
        self.assertFalse(result)
        
        # 测试空字符串
        result = Config._is_encrypted_api_key("")
        self.assertFalse(result)
        
        # 测试包含异常字符的输入
        result = Config._is_encrypted_api_key("invalid!@#$%")
        self.assertFalse(result)

    def test_process_file_for_api_key_with_invalid_file(self):
        """测试_process_file_for_api_key处理无效文件"""
        # 测试不存在的文件
        result = Config._process_file_for_api_key("nonexistent_file.txt")
        self.assertFalse(result)
        
        # 测试空文件路径
        result = Config._process_file_for_api_key("")
        self.assertFalse(result)

    def test_load_api_key_with_project_root(self):
        """测试load_api_key使用PROJECT_ROOT目录"""
        # 临时设置PROJECT_ROOT
        original_project_root = Config.PROJECT_ROOT
        test_root = os.path.join(Config.WORK_DIR, "test_project_root")
        Config.PROJECT_ROOT = test_root
        
        try:
            # 创建测试文件
            test_file = os.path.join(Config.PROJECT_ROOT, "api_key.txt")
            os.makedirs(Config.PROJECT_ROOT, exist_ok=True)
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("sk-1234567890abcdef1234567890abcdef")
            
            # 执行测试
            Config.load_api_key()
            
            # 验证结果
            self.assertEqual(Config.DASHSCOPE_API_KEY, "sk-1234567890abcdef1234567890abcdef")
        finally:
            # 清理
            Config.PROJECT_ROOT = original_project_root
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(test_root):
                try:
                    os.rmdir(test_root)
                except PermissionError:
                    # 如果无法删除，设置为空以避免影响后续测试
                    pass

    def test_scan_directory_with_os_error(self):
        """测试_scan_directory_for_api_keys处理os.walk异常"""
        # 测试os.walk抛出异常的情况
        with patch('module.config.os.walk', side_effect=OSError("Permission denied")):
            result = Config._scan_directory_for_api_keys(Config.WORK_DIR)
            self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
