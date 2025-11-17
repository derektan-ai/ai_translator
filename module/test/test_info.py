import unittest
import sys
import os
from unittest.mock import patch

# 添加上级目录到系统路径，以便正确导入module包
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from module.info import INFO
from module.config import Config


class TestINFO(unittest.TestCase):
    """INFO类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        # 保存原始配置，以便测试后恢复
        self.original_language = Config.LANGUAGE

    def tearDown(self):
        """测试后的清理工作"""
        # 恢复原始配置
        Config.LANGUAGE = self.original_language

    def test_get_with_invalid_key(self):
        """测试获取不存在的键时返回键本身"""
        invalid_key = "non_existent_key"
        self.assertEqual(INFO.get(invalid_key), invalid_key)

if __name__ == '__main__':
    unittest.main()
