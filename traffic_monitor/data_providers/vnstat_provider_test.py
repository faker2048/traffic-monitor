#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import logging
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

# 设置日志输出
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 导入VnStatDataProvider
sys.path.append('.')
from .vnstat_provider import VnStatDataProvider

# vnstat -m 的标准输出样例（基于实际系统输出）
VNSTAT_MONTHLY_SAMPLE = """
 ens5  /  monthly

        month        rx      |     tx      |    total    |   avg. rate
     ------------------------+-------------+-------------+---------------
       2025-04     51.47 GiB |   50.73 GiB |  102.20 GiB |  841.36 kbit/s
     ------------------------+-------------+-------------+---------------
     estimated    127.87 GiB |  126.01 GiB |  253.88 GiB |

"""

# 带有MiB单位的样例
VNSTAT_MONTHLY_SAMPLE_MIB = """
 ens5  /  monthly

        month        rx      |     tx      |    total    |   avg. rate
     ------------------------+-------------+-------------+---------------
       2025-04    506.10 MiB |  498.40 MiB | 1004.50 MiB |   8.28 kbit/s
     ------------------------+-------------+-------------+---------------
     estimated   1259.40 MiB | 1240.40 MiB | 2499.80 MiB |

"""

# 日数据样例
VNSTAT_DAILY_SAMPLE = """
 ens5  /  daily

         day         rx      |     tx      |    total    |   avg. rate
     ------------------------+-------------+-------------+---------------
     2025-04-11    4.83 GiB |    4.76 GiB |    9.59 GiB |    975 kbit/s
     2025-04-12    4.17 GiB |    4.11 GiB |    8.28 GiB |    842 kbit/s
          today    2.34 GiB |    2.30 GiB |    4.64 GiB |    793 kbit/s
     ------------------------+-------------+-------------+---------------
          total   11.34 GiB |   11.17 GiB |   22.51 GiB |

"""

class TestVnStatDataProvider(unittest.TestCase):
    
    def setUp(self):
        # 初始化VnStatDataProvider并mock _verify_vnstat方法避免检查vnstat是否安装
        with patch.object(VnStatDataProvider, '_verify_vnstat'):
            self.provider = VnStatDataProvider(interface='eth0')
    
    def test_parse_size_to_gb(self):
        """测试大小字符串解析函数"""
        test_cases = [
            ("10.5 GiB", 10.5),
            ("800 MiB", 800/1024),
            ("1024 KiB", 1024/(1024*1024)),
            ("2.5 TiB", 2.5*1024),
            ("0 GiB", 0),
        ]
        
        for size_str, expected_gb in test_cases:
            with self.subTest(size_str=size_str):
                result = self.provider._parse_size_to_gb(size_str)
                self.assertAlmostEqual(result, expected_gb, places=5)
                print(f"解析 {size_str} 为 {result} GB")
    
    @patch('subprocess.run')
    def test_get_current_month_usage(self, mock_run):
        """测试月度使用量解析（GiB单位）"""
        # 模拟当前月份是2025-04
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 4, 13)
            
            # 模拟vnstat命令输出
            mock_process = MagicMock()
            mock_process.stdout = VNSTAT_MONTHLY_SAMPLE
            mock_run.return_value = mock_process
            
            # 测试
            result = self.provider.get_current_month_usage()
            self.assertAlmostEqual(result, 102.20, places=2)
            print(f"月度使用量解析结果: {result} GB")
    
    @patch('subprocess.run')
    def test_get_current_month_usage_mib(self, mock_run):
        """测试月度使用量解析（MiB单位）"""
        # 模拟当前月份是2025-04
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 4, 13)
            
            # 模拟vnstat命令输出
            mock_process = MagicMock()
            mock_process.stdout = VNSTAT_MONTHLY_SAMPLE_MIB
            mock_run.return_value = mock_process
            
            # 测试
            result = self.provider.get_current_month_usage()
            expected = 1004.50/1024  # 转换为GB
            self.assertAlmostEqual(result, expected, places=2)
            print(f"MiB单位解析结果: {result} GB")
    
    @patch('subprocess.run')
    def test_get_daily_usage(self, mock_run):
        """测试每日使用量解析"""
        # 模拟vnstat命令输出
        mock_process = MagicMock()
        mock_process.stdout = VNSTAT_DAILY_SAMPLE
        mock_run.return_value = mock_process
        
        # 测试
        result = self.provider.get_daily_usage()
        
        # 验证结果
        expected = {
            "2025-04-11": 9.59,
            "2025-04-12": 8.28,
            datetime.now().strftime("%Y-%m-%d"): 4.64
        }
        
        for date, expected_value in expected.items():
            with self.subTest(date=date):
                self.assertIn(date, result)
                self.assertAlmostEqual(result[date], expected_value, places=2)
                
        print(f"每日使用量解析结果: {result}")


if __name__ == '__main__':
    print("\n开始测试 VnStatDataProvider 类的解析功能...")
    unittest.main(verbosity=2) 