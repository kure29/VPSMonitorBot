#!/usr/bin/env python3
"""
VPS监控系统测试套件
用于验证各组件功能的正确性
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import sqlite3
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入被测试的模块
try:
    from monitor import (
        ConfigManager, DataManager, StockChecker, TelegramBot, 
        VPSMonitor, MonitorItem, Config
    )
    from database_manager import DatabaseManager, CheckHistory
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有依赖已安装: pip install -r requirements.txt")
    sys.exit(1)


class TestConfigManager(unittest.TestCase):
    """配置管理器测试"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        self.config_manager = ConfigManager(self.config_file)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        os.rmdir(self.temp_dir)
    
    def test_save_and_load_config(self):
        """测试配置保存和加载"""
        test_config = Config(
            bot_token="test_token",
            chat_id="123456789",
            check_interval=300
        )
        
        # 保存配置
        self.config_manager.save_config(test_config)
        self.assertTrue(os.path.exists(self.config_file))
        
        # 加载配置
        loaded_config = self.config_manager.load_config()
        self.assertEqual(loaded_config.bot_token, test_config.bot_token)
        self.assertEqual(loaded_config.chat_id, test_config.chat_id)
        self.assertEqual(loaded_config.check_interval, test_config.check_interval)
    
    def test_load_nonexistent_config(self):
        """测试加载不存在的配置文件"""
        with self.assertRaises(FileNotFoundError):
            self.config_manager.load_config()


class TestDataManager(unittest.IsolatedAsyncioTestCase):
    """数据管理器测试"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.temp_dir, "test_urls.json")
        self.data_manager = DataManager(self.data_file)
        await self.data_manager.load_monitor_items()
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        if os.path.exists(self.data_file):
            os.remove(self.data_file)
        os.rmdir(self.temp_dir)
    
    async def test_add_and_get_monitor_item(self):
        """测试添加和获取监控项"""
        # 添加监控项
        item_id = self.data_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test",
            config="2GB RAM"
        )
        
        # 验证添加成功
        self.assertIsNotNone(item_id)
        items = self.data_manager.monitor_items
        self.assertEqual(len(items), 1)
        
        # 验证数据正确性
        item = items[item_id]
        self.assertEqual(item.name, "Test VPS")
        self.assertEqual(item.url, "https://example.com/test")
        self.assertEqual(item.config, "2GB RAM")
    
    async def test_remove_monitor_item(self):
        """测试删除监控项"""
        # 添加监控项
        self.data_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        # 删除监控项
        success = self.data_manager.remove_monitor_item("https://example.com/test")
        self.assertTrue(success)
        
        # 验证删除成功
        items = self.data_manager.monitor_items
        self.assertEqual(len(items), 0)
    
    async def test_update_monitor_item_status(self):
        """测试更新监控项状态"""
        # 添加监控项
        self.data_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        # 更新状态
        self.data_manager.update_monitor_item_status(
            "https://example.com/test", 
            True, 
            1
        )
        
        # 验证状态更新
        item = self.data_manager.get_monitor_item_by_url("https://example.com/test")
        self.assertTrue(item.status)
        self.assertEqual(item.notification_count, 1)
    
    async def test_save_and_load_monitor_items(self):
        """测试保存和加载监控项"""
        # 添加监控项
        self.data_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        # 保存数据
        await self.data_manager.save_monitor_items()
        self.assertTrue(os.path.exists(self.data_file))
        
        # 创建新的管理器实例并加载数据
        new_manager = DataManager(self.data_file)
        items = await new_manager.load_monitor_items()
        
        self.assertEqual(len(items), 1)
        item = list(items.values())[0]
        self.assertEqual(item.name, "Test VPS")
        self.assertEqual(item.url, "https://example.com/test")


class TestStockChecker(unittest.IsolatedAsyncioTestCase):
    """库存检查器测试"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        self.config = Config(
            bot_token="test_token",
            chat_id="123456789",
            request_timeout=10
        )
        self.stock_checker = StockChecker(self.config)
    
    def test_clean_url(self):
        """测试URL清理功能"""
        dirty_url = "https://example.com/product?__cf_chl_rt_tk=token123&other=param"
        clean_url = self.stock_checker._clean_url(dirty_url)
        self.assertNotIn("__cf_chl_rt_tk", clean_url)
        self.assertIn("other=param", clean_url)
    
    def test_analyze_content_out_of_stock(self):
        """测试缺货内容分析"""
        content = """
        <html>
            <body>
                <h1>Product Page</h1>
                <p>This item is currently sold out</p>
                <button disabled>Add to Cart</button>
            </body>
        </html>
        """
        result, error = self.stock_checker._analyze_content(content)
        self.assertFalse(result)
        self.assertIsNone(error)
    
    def test_analyze_content_in_stock(self):
        """测试有货内容分析"""
        content = """
        <html>
            <body>
                <h1>Product Page</h1>
                <p>This item is available now</p>
                <button>Add to Cart</button>
                <form>
                    <select name="quantity">
                        <option>1</option>
                        <option>2</option>
                    </select>
                    <input type="submit" value="Buy Now">
                </form>
            </body>
        </html>
        """
        result, error = self.stock_checker._analyze_content(content)
        self.assertTrue(result)
        self.assertIsNone(error)
    
    def test_analyze_content_cloudflare(self):
        """测试Cloudflare验证页面检测"""
        content = "Just a moment, checking if the site connection is secure..."
        result, error = self.stock_checker._analyze_content(content)
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertIn("Cloudflare", error)
    
    @patch('cloudscraper.CloudScraper.get')
    async def test_check_stock_success(self, mock_get):
        """测试成功的库存检查"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Available now <button>Add to Cart</button>"
        mock_get.return_value = mock_response
        
        result, error = await self.stock_checker.check_stock("https://example.com/test")
        self.assertTrue(result)
        self.assertIsNone(error)
    
    @patch('cloudscraper.CloudScraper.get')
    async def test_check_stock_http_error(self, mock_get):
        """测试HTTP错误的库存检查"""
        # 模拟HTTP错误响应
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result, error = await self.stock_checker.check_stock("https://example.com/test")
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertIn("404", error)


class TestDatabaseManager(unittest.IsolatedAsyncioTestCase):
    """数据库管理器测试"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db.name)
        await self.db_manager.initialize()
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        os.unlink(self.temp_db.name)
    
    async def test_add_and_get_monitor_items(self):
        """测试添加和获取监控项"""
        item_id = await self.db_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test",
            config="2GB RAM",
            tags=["vps", "test"]
        )
        
        items = await self.db_manager.get_monitor_items()
        self.assertEqual(len(items), 1)
        
        item = items[item_id]
        self.assertEqual(item.name, "Test VPS")
        self.assertEqual(item.url, "https://example.com/test")
    
    async def test_update_monitor_item_status(self):
        """测试更新监控项状态"""
        item_id = await self.db_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        await self.db_manager.update_monitor_item_status(
            item_id, True, 1, ""
        )
        
        items = await self.db_manager.get_monitor_items()
        item = items[item_id]
        self.assertTrue(item.status)
        self.assertEqual(item.notification_count, 1)
    
    async def test_add_check_history(self):
        """测试添加检查历史"""
        item_id = await self.db_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        await self.db_manager.add_check_history(
            monitor_id=item_id,
            status=True,
            response_time=1.5,
            http_status=200,
            content_length=5000
        )
        
        history = await self.db_manager.get_check_history(item_id)
        self.assertEqual(len(history), 1)
        
        record = history[0]
        self.assertEqual(record.monitor_id, item_id)
        self.assertTrue(record.status)
        self.assertEqual(record.response_time, 1.5)
    
    async def test_get_statistics(self):
        """测试获取统计信息"""
        # 添加监控项
        item_id = await self.db_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        # 添加检查历史
        await self.db_manager.add_check_history(
            monitor_id=item_id,
            status=True,
            response_time=1.5
        )
        
        stats = await self.db_manager.get_statistics(days=7)
        self.assertIn('total_checks', stats)
        self.assertIn('total_items', stats)
        self.assertEqual(stats['total_checks'], 1)
        self.assertEqual(stats['total_items'], 1)
    
    async def test_cleanup_old_history(self):
        """测试清理旧历史记录"""
        item_id = await self.db_manager.add_monitor_item(
            name="Test VPS",
            url="https://example.com/test"
        )
        
        # 添加一些历史记录
        for i in range(5):
            await self.db_manager.add_check_history(
                monitor_id=item_id,
                status=True,
                response_time=1.0
            )
        
        # 清理（这里用很短的时间来模拟旧记录）
        deleted_count = await self.db_manager.cleanup_old_history(days=0)
        self.assertEqual(deleted_count, 5)


class IntegrationTest(unittest.IsolatedAsyncioTestCase):
    """集成测试"""
    
    async def asyncSetUp(self):
        """异步测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试配置
        self.config_file = os.path.join(self.temp_dir, "config.json")
        self.data_file = os.path.join(self.temp_dir, "urls.json")
        
        test_config = {
            "bot_token": "test_token",
            "chat_id": "123456789",
            "check_interval": 60,
            "max_notifications": 3
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
    
    async def asyncTearDown(self):
        """异步测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @patch('monitor.TelegramBot')
    @patch('monitor.StockChecker')
    async def test_monitor_workflow(self, mock_stock_checker, mock_telegram_bot):
        """测试完整的监控工作流程"""
        # 模拟组件
        mock_checker_instance = AsyncMock()
        mock_checker_instance.check_stock.return_value = (True, None)
        mock_stock_checker.return_value = mock_checker_instance
        
        mock_bot_instance = AsyncMock()
        mock_telegram_bot.return_value = mock_bot_instance
        
        # 修改配置文件路径
        with patch('monitor.ConfigManager') as mock_config_manager:
            mock_config = Config(
                bot_token="test_token",
                chat_id="123456789",
                check_interval=1  # 快速测试
            )
            mock_config_manager.return_value.load_config.return_value = mock_config
            
            # 创建监控器
            monitor = VPSMonitor()
            
            # 手动设置文件路径
            monitor.data_manager.data_file = Path(self.data_file)
            
            # 添加监控项
            monitor.data_manager.add_monitor_item(
                name="Test VPS",
                url="https://example.com/test"
            )
            
            # 保存数据
            await monitor.data_manager.save_monitor_items()
            
            # 验证监控项已添加
            items = monitor.data_manager.monitor_items
            self.assertEqual(len(items), 1)


class PerformanceTest(unittest.IsolatedAsyncioTestCase):
    """性能测试"""
    
    async def test_bulk_operations_performance(self):
        """测试批量操作性能"""
        import time
        
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        try:
            db_manager = DatabaseManager(temp_db.name)
            await db_manager.initialize()
            
            # 测试批量添加
            start_time = time.time()
            item_ids = []
            
            for i in range(100):
                item_id = await db_manager.add_monitor_item(
                    name=f"Test VPS {i}",
                    url=f"https://example.com/test{i}"
                )
                item_ids.append(item_id)
            
            add_time = time.time() - start_time
            
            # 测试批量查询
            start_time = time.time()
            items = await db_manager.get_monitor_items()
            query_time = time.time() - start_time
            
            self.assertEqual(len(items), 100)
            self.assertLess(add_time, 10.0)  # 添加100个项目应该在10秒内完成
            self.assertLess(query_time, 1.0)  # 查询应该在1秒内完成
            
            print(f"添加100个监控项耗时: {add_time:.2f}秒")
            print(f"查询100个监控项耗时: {query_time:.2f}秒")
            
        finally:
            os.unlink(temp_db.name)


def run_network_tests():
    """运行网络相关测试（需要网络连接）"""
    async def test_real_website():
        """测试真实网站检查"""
        config = Config(
            bot_token="dummy",
            chat_id="dummy",
            request_timeout=10
        )
        
        checker = StockChecker(config)
        
        # 测试一个总是可访问的网站
        result, error = await checker.check_stock("https://httpbin.org/status/200")
        print(f"HTTP 200测试: 结果={result}, 错误={error}")
        
        # 测试404错误
        result, error = await checker.check_stock("https://httpbin.org/status/404")
        print(f"HTTP 404测试: 结果={result}, 错误={error}")
    
    try:
        asyncio.run(test_real_website())
        print("✓ 网络测试完成")
    except Exception as e:
        print(f"✗ 网络测试失败: {e}")


def main():
    """主测试函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.WARNING,  # 减少测试期间的日志输出
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("VPS监控系统测试套件")
    print("=" * 60)
    
    # 运行单元测试
    print("\n🧪 运行单元测试...")
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # 添加测试类
    test_classes = [
        TestConfigManager,
        TestDataManager,
        TestStockChecker,
        TestDatabaseManager,
        IntegrationTest,
        PerformanceTest
    ]
    
    for test_class in test_classes:
        tests = test_loader.loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 运行网络测试（可选）
    print("\n🌐 运行网络测试...")
    try:
        run_network_tests()
    except KeyboardInterrupt:
        print("网络测试被用户中断")
    except Exception as e:
        print(f"网络测试出现异常: {e}")
    
    # 总结
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print(f"运行测试: {result.testsRun}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ 所有测试通过!' if success else '❌ 部分测试失败'}")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
