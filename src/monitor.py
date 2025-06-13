#!/usr/bin/env python3
"""
VPS监控系统 v3.0 - 多用户智能监控版
作者: kure29
网站: https://kure29.com

功能特点：
- 多用户支持，所有人可添加监控
- 管理员权限控制
- 智能组合监控算法
- 用户行为统计和管理
"""

import os
import sys
from pathlib import Path

# ====== 路径自动检测和修复 ======
def setup_project_paths():
    """自动检测并设置项目路径"""
    current_file = Path(__file__).resolve()
    
    if current_file.parent.name == 'src':
        project_root = current_file.parent.parent
        print(f"🔍 检测到在src目录运行，项目根目录: {project_root}")
    else:
        project_root = current_file.parent
        print(f"🔍 检测到在项目根目录运行: {project_root}")
    
    os.chdir(project_root)
    print(f"📁 当前工作目录: {os.getcwd()}")
    
    # 检查必需文件
    required_files = ['config.json', 'requirements.txt']
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必需文件: {missing_files}")
        
        if 'config.json' in missing_files and Path('config/config.json.example').exists():
            import shutil
            shutil.copy('config/config.json.example', 'config.json')
            print("✅ 已从示例创建config.json，请编辑配置信息")
            missing_files.remove('config.json')
        
        if missing_files:
            print(f"❌ 仍缺少文件: {missing_files}")
            sys.exit(1)
    
    print("✅ 项目路径设置完成")
    return project_root

# 设置项目路径
if __name__ == '__main__':
    PROJECT_ROOT = setup_project_paths()

# ====== 主程序导入 ======
import asyncio
import aiosqlite
import cloudscraper
import time
import logging
import json
import random
import urllib.parse
import re
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# 尝试导入selenium（可选）
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
    print("✅ Selenium可用，支持DOM监控")
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium未安装，将使用基础监控模式")

# 导入数据库管理器
from database_manager import DatabaseManager, MonitorItem, CheckHistory, User

# ====== 数据类定义 ======
@dataclass
class Config:
    """配置数据类"""
    bot_token: str
    chat_id: str
    channel_id: Optional[str] = None
    check_interval: int = 180
    notification_aggregation_interval: int = 180
    notification_cooldown: int = 600
    request_timeout: int = 30
    retry_delay: int = 60
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    proxy: Optional[str] = None
    debug: bool = False
    log_level: str = "INFO"
    admin_ids: List[str] = None
    items_per_page: int = 10
    # 新增配置项
    enable_selenium: bool = True
    enable_api_discovery: bool = True
    enable_visual_comparison: bool = False
    confidence_threshold: float = 0.6
    chromium_path: Optional[str] = None
    daily_add_limit: int = 50  # 每日添加限制
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            raise ValueError("请配置正确的Telegram Bot Token")
        
        if not self.chat_id or self.chat_id == "YOUR_TELEGRAM_CHAT_ID":
            raise ValueError("请配置正确的Telegram Chat ID")
        
        if self.admin_ids is None:
            self.admin_ids = []

# ====== 配置管理器 ======
class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self._config = None
        self.logger = logging.getLogger(__name__)
    
    def load_config(self) -> Config:
        """加载配置"""
        try:
            if not self.config_file.exists():
                self.logger.error(f"配置文件 {self.config_file} 不存在")
                raise FileNotFoundError(f"配置文件 {self.config_file} 不存在")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                required_fields = ['bot_token', 'chat_id']
                missing_fields = [field for field in required_fields if not data.get(field)]
                
                if missing_fields:
                    raise ValueError(f"配置文件缺少必需字段: {missing_fields}")
                
                valid_fields = {field.name for field in Config.__dataclass_fields__.values()}
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                
                extra_fields = set(data.keys()) - valid_fields
                if extra_fields:
                    self.logger.warning(f"配置文件中包含未知字段，已忽略: {extra_fields}")
                
                self._config = Config(**filtered_data)
                self.logger.info("配置文件加载成功")
                return self._config
                
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            raise
    
    @property
    def config(self) -> Config:
        """获取当前配置"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

# ====== 页面指纹监控器 ======
class PageFingerprintMonitor:
    """页面指纹监控器"""
    
    def __init__(self):
        self.page_fingerprints = {}
        self.logger = logging.getLogger(__name__)
    
    def extract_important_content(self, html: str) -> str:
        """提取页面中重要的内容片段"""
        important_content = []
        html_lower = html.lower()
        
        # 提取价格相关内容
        price_patterns = [
            r'\$[\d,]+\.?\d*',
            r'¥[\d,]+\.?\d*',
            r'€[\d,]+\.?\d*',
            r'price[^>]*>[^<]*</[^>]*>',
            r'cost[^>]*>[^<]*</[^>]*>'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, html_lower)
            important_content.extend(matches)
        
        # 提取按钮文本
        button_pattern = r'<button[^>]*>(.*?)</button>'
        buttons = re.findall(button_pattern, html_lower, re.DOTALL)
        important_content.extend([btn.strip()[:50] for btn in buttons])
        
        # 提取关键状态文本
        status_patterns = [
            r'库存[^<]{0,20}',
            r'stock[^<]{0,20}',
            r'available[^<]{0,20}',
            r'sold out[^<]{0,20}',
            r'缺货[^<]{0,20}'
        ]
        
        for pattern in status_patterns:
            matches = re.findall(pattern, html_lower)
            important_content.extend(matches)
        
        return ''.join(important_content)
    
    def get_page_fingerprint(self, html: str, url: str) -> str:
        """生成页面指纹"""
        important_content = self.extract_important_content(html)
        content_hash = hashlib.md5(important_content.encode()).hexdigest()
        return content_hash
    
    async def check_page_changes(self, url: str, html: str) -> Tuple[bool, str]:
        """检查页面是否有变化"""
        try:
            current_fingerprint = self.get_page_fingerprint(html, url)
            
            if url not in self.page_fingerprints:
                self.page_fingerprints[url] = current_fingerprint
                return False, "首次检查，已记录指纹"
            
            if self.page_fingerprints[url] != current_fingerprint:
                self.page_fingerprints[url] = current_fingerprint
                return True, "页面内容发生变化，可能库存状态改变"
            
            return False, "页面内容无变化"
        except Exception as e:
            self.logger.error(f"页面指纹检查失败: {e}")
            return False, f"指纹检查失败: {str(e)}"

# ====== DOM元素监控器 ======
class DOMElementMonitor:
    """DOM元素监控器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.driver = None
        self.logger = logging.getLogger(__name__)
        if SELENIUM_AVAILABLE and config.enable_selenium:
            self.setup_driver()
    
    def setup_driver(self):
        """设置无头浏览器"""
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(f'--user-agent={self.config.user_agent}')
            
            # 禁用图片和CSS加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.stylesheets": 2
            }
            options.add_experimental_option("prefs", prefs)
            
            if self.config.chromium_path:
                options.binary_location = self.config.chromium_path
            
            # 使用webdriver-manager自动管理ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.logger.info("Chrome浏览器初始化成功")
            
        except Exception as e:
            self.logger.error(f"Chrome浏览器初始化失败: {e}")
            self.driver = None
    
    async def check_stock_by_elements(self, url: str) -> Tuple[Optional[bool], str, Dict]:
        """通过DOM元素检查库存状态"""
        if not self.driver:
            return None, "浏览器未初始化", {}
        
        try:
            # 访问页面
            self.driver.get(url)
            await asyncio.sleep(3)  # 等待页面加载
            
            # 等待页面完全加载
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                pass
            
            check_info = {
                'page_title': self.driver.title,
                'url': self.driver.current_url,
                'page_source_length': len(self.driver.page_source)
            }
            
            # 检查特定商家规则
            vendor_result = self._check_vendor_specific_rules(url)
            if vendor_result['status'] is not None:
                return vendor_result['status'], vendor_result['message'], check_info
            
            # 检查购买按钮
            buy_buttons = self._find_buy_buttons()
            if buy_buttons['enabled_count'] > 0:
                return True, f"发现{buy_buttons['enabled_count']}个可用购买按钮", check_info
            
            # 检查库存文本
            stock_info = self._check_stock_text()
            if stock_info['definitive']:
                return stock_info['status'], stock_info['message'], check_info
            
            # 检查价格信息
            price_info = self._check_price_elements()
            if price_info['has_price'] and price_info['has_form']:
                return True, f"发现价格信息和订单表单", check_info
            
            return None, "DOM检查无法确定库存状态", check_info
            
        except Exception as e:
            self.logger.error(f"DOM检查失败: {e}")
            return None, f"DOM检查失败: {str(e)}", {}
    
    def _check_vendor_specific_rules(self, url: str) -> Dict:
        """检查特定商家的规则"""
        url_lower = url.lower()
        
        try:
            # DMIT特殊处理
            if 'dmit' in url_lower:
                return self._check_dmit_specific()
            
            # RackNerd特殊处理
            elif 'racknerd' in url_lower:
                return self._check_racknerd_specific()
            
            # BandwagonHost特殊处理
            elif 'bandwagonhost' in url_lower or 'bwh' in url_lower:
                return self._check_bwh_specific()
            
            return {'status': None, 'message': '无特定商家规则'}
            
        except Exception as e:
            return {'status': None, 'message': f'商家规则检查失败: {str(e)}'}
    
    def _check_dmit_specific(self) -> Dict:
        """DMIT特定检查"""
        try:
            # DMIT特有的缺货标识
            dmit_out_selectors = [
                "//*[contains(text(), '缺货中')]",
                "//*[contains(text(), '刷新库存')]", 
                "//*[contains(text(), 'refresh stock')]",
                "//*[contains(text(), '暂无库存')]",
                ".out-of-stock",
                ".stock-refresh"
            ]
            
            for selector in dmit_out_selectors:
                try:
                    if selector.startswith('//'):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() for el in elements):
                        return {
                            'status': False,
                            'message': f'DMIT页面显示缺货: {elements[0].text}'
                        }
                except:
                    continue
            
            # DMIT有货检查
            dmit_in_selectors = [
                "//*[contains(text(), '立即订购')]",
                "//*[contains(text(), '配置选项')]",
                "button[type='submit']",
                ".btn-primary"
            ]
            
            for selector in dmit_in_selectors:
                try:
                    if selector.startswith('//'):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() and el.is_enabled() for el in elements):
                        return {
                            'status': True,
                            'message': 'DMIT页面显示可购买'
                        }
                except:
                    continue
            
            return {'status': None, 'message': 'DMIT页面状态不明确'}
            
        except Exception as e:
            return {'status': None, 'message': f'DMIT检查失败: {str(e)}'}
    
    def _check_racknerd_specific(self) -> Dict:
        """RackNerd特定检查"""
        try:
            # RackNerd缺货检查
            if self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Out of Stock')]"):
                return {'status': False, 'message': 'RackNerd显示缺货'}
            
            # RackNerd有货检查
            if self.driver.find_elements(By.CSS_SELECTOR, ".btn-order, .order-button"):
                return {'status': True, 'message': 'RackNerd显示可订购'}
            
            return {'status': None, 'message': 'RackNerd状态不明确'}
            
        except Exception as e:
            return {'status': None, 'message': f'RackNerd检查失败: {str(e)}'}
    
    def _check_bwh_specific(self) -> Dict:
        """BandwagonHost特定检查"""
        try:
            # BWH缺货检查
            if self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Out of stock')]"):
                return {'status': False, 'message': 'BWH显示缺货'}
            
            # BWH有货检查
            if self.driver.find_elements(By.CSS_SELECTOR, ".cart-add-button"):
                return {'status': True, 'message': 'BWH显示可购买'}
            
            return {'status': None, 'message': 'BWH状态不明确'}
            
        except Exception as e:
            return {'status': None, 'message': f'BWH检查失败: {str(e)}'}
    
    def _find_buy_buttons(self) -> Dict:
        """查找购买按钮"""
        button_selectors = [
            "//button[contains(text(), 'Buy')]",
            "//button[contains(text(), '购买')]",
            "//button[contains(text(), 'Order')]", 
            "//button[contains(text(), '订购')]",
            "//button[contains(text(), 'Add to Cart')]",
            "//button[contains(text(), '加入购物车')]",
            ".btn-buy", ".buy-button", ".order-button",
            "input[type='submit'][value*='buy']",
            "input[type='submit'][value*='order']"
        ]
        
        enabled_count = 0
        disabled_count = 0
        
        for selector in button_selectors:
            try:
                if selector.startswith('//'):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed():
                        if element.is_enabled():
                            enabled_count += 1
                        else:
                            disabled_count += 1
            except:
                continue
        
        return {
            'enabled_count': enabled_count,
            'disabled_count': disabled_count
        }
    
    def _check_stock_text(self) -> Dict:
        """检查库存相关文本"""
        out_of_stock_selectors = [
            "//*[contains(text(), 'Out of Stock')]",
            "//*[contains(text(), '缺货')]",
            "//*[contains(text(), 'Sold Out')]",
            "//*[contains(text(), '售罄')]",
            "//*[contains(text(), '缺货中')]",
            "//*[contains(text(), 'unavailable')]",
            "//*[contains(text(), '暂无库存')]"
        ]
        
        in_stock_selectors = [
            "//*[contains(text(), 'In Stock')]",
            "//*[contains(text(), '有货')]",
            "//*[contains(text(), 'Available')]",
            "//*[contains(text(), '现货')]",
            "//*[contains(text(), '立即购买')]"
        ]
        
        # 检查缺货文本
        for selector in out_of_stock_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements and any(el.is_displayed() for el in elements):
                    return {
                        'status': False,
                        'message': f'发现缺货文本: {elements[0].text}',
                        'definitive': True
                    }
            except:
                continue
        
        # 检查有货文本
        for selector in in_stock_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                if elements and any(el.is_displayed() for el in elements):
                    return {
                        'status': True,
                        'message': f'发现有货文本: {elements[0].text}',
                        'definitive': True
                    }
            except:
                continue
        
        return {
            'status': None,
            'message': '未发现明确库存文本',
            'definitive': False
        }
    
    def _check_price_elements(self) -> Dict:
        """检查价格元素"""
        price_selectors = [
            ".price", ".cost", ".amount", 
            "[class*='price']", "[class*='cost']",
            "//*[contains(text(), '$')]",
            "//*[contains(text(), '¥')]",
            "//*[contains(text(), '€')]"
        ]
        
        form_selectors = [
            "form", "input[type='submit']", "button[type='submit']",
            ".checkout", ".order-form", ".purchase-form"
        ]
        
        found_prices = []
        has_form = False
        
        # 检查价格
        for selector in price_selectors:
            try:
                if selector.startswith('//'):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed():
                        text = element.text.strip()
                        if text and any(symbol in text for symbol in ['$', '¥', '€']):
                            found_prices.append(text[:20])
            except:
                continue
        
        # 检查表单
        for selector in form_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(el.is_displayed() for el in elements):
                    has_form = True
                    break
            except:
                continue
        
        return {
            'has_price': len(found_prices) > 0,
            'has_form': has_form,
            'prices': found_prices[:3]
        }
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass

# ====== API监控器 ======
class APIMonitor:
    """API监控器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = cloudscraper.create_scraper()
        self.session.headers.update({
            'User-Agent': config.user_agent
        })
        self.logger = logging.getLogger(__name__)
    
    async def discover_api_endpoints(self, url: str) -> List[str]:
        """发现可能的API端点"""
        if not self.config.enable_api_discovery:
            return []
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(url, timeout=self.config.request_timeout)
            )
            content = response.text
            
            # 查找可能的API端点
            api_patterns = [
                r'/api/[^"\s]+',
                r'api\.[^/"\s]+/[^"\s]+',
                r'/ajax/[^"\s]+',
                r'\.php\?[^"\s]+action=[^"\s]*stock[^"\s]*',
                r'\.json[^"\s]*',
                r'/check[^"\s]*stock[^"\s]*',
                r'/inventory[^"\s]*'
            ]
            
            endpoints = []
            for pattern in api_patterns:
                matches = re.findall(pattern, content)
                endpoints.extend(matches)
            
            # 去重并补全URL
            base_url = '/'.join(url.split('/')[:3])
            full_endpoints = []
            for endpoint in set(endpoints):
                if not endpoint.startswith('http'):
                    endpoint = base_url + endpoint
                full_endpoints.append(endpoint)
            
            return full_endpoints[:5]  # 限制数量
            
        except Exception as e:
            self.logger.error(f"API发现失败: {e}")
            return []
    
    async def check_api_stock(self, api_url: str) -> Tuple[Optional[bool], str]:
        """检查API接口的库存信息"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(api_url, timeout=self.config.request_timeout)
            )
            
            if response.status_code != 200:
                return None, f"API请求失败: {response.status_code}"
            
            try:
                data = response.json()
                return self._analyze_api_response(data)
            except:
                # 如果不是JSON，尝试分析文本
                return self._analyze_text_response(response.text)
                
        except Exception as e:
            return None, f"API检查失败: {str(e)}"
    
    def _analyze_api_response(self, data: Dict) -> Tuple[Optional[bool], str]:
        """分析API JSON响应"""
        # 常见的库存字段
        stock_fields = ['stock', 'inventory', 'available', 'quantity', 'in_stock', 'inStock']
        status_fields = ['status', 'state', 'availability']
        
        def search_nested(obj, keys):
            """递归搜索嵌套字典"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if any(field in key.lower() for field in keys):
                        return value
                    if isinstance(value, (dict, list)):
                        result = search_nested(value, keys)
                        if result is not None:
                            return result
            elif isinstance(obj, list):
                for item in obj:
                    result = search_nested(item, keys)
                    if result is not None:
                        return result
            return None
        
        # 查找库存信息
        stock_value = search_nested(data, stock_fields)
        if stock_value is not None:
            if isinstance(stock_value, (int, float)):
                return stock_value > 0, f"API库存数量: {stock_value}"
            elif isinstance(stock_value, bool):
                return stock_value, f"API库存状态: {stock_value}"
            elif isinstance(stock_value, str):
                stock_lower = stock_value.lower()
                if any(word in stock_lower for word in ['out', 'unavailable', '缺货', 'false', '0']):
                    return False, f"API显示缺货: {stock_value}"
                elif any(word in stock_lower for word in ['available', 'in', '有货', 'true']):
                    return True, f"API显示有货: {stock_value}"
        
        return None, "无法从API响应中确定库存状态"
    
    def _analyze_text_response(self, text: str) -> Tuple[Optional[bool], str]:
        """分析文本响应"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['out of stock', 'sold out', '缺货', '售罄']):
            return False, "API文本显示缺货"
        elif any(word in text_lower for word in ['in stock', 'available', '有货', '现货']):
            return True, "API文本显示有货"
        
        return None, "无法从API文本中确定库存状态"

# ====== 智能组合监控器 ======
class SmartComboMonitor:
    """智能组合监控器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.fingerprint_monitor = PageFingerprintMonitor()
        self.dom_monitor = DOMElementMonitor(config) if SELENIUM_AVAILABLE else None
        self.api_monitor = APIMonitor(config)
        self.logger = logging.getLogger(__name__)
        
        # 简单的关键词检查器作为后备
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'custom': config.user_agent
            },
            debug=config.debug
        )
    
    async def check_stock(self, url: str) -> Tuple[Optional[bool], Optional[str], Dict[str, Any]]:
        """智能组合检查库存状态"""
        start_time = time.time()
        
        try:
            # 执行综合检查
            result = await self.comprehensive_check(url)
            
            check_info = {
                'response_time': time.time() - start_time,
                'http_status': 200,
                'content_length': 0,
                'method': 'SMART_COMBO',
                'confidence': result.get('confidence', 0),
                'methods_used': list(result.get('methods', {}).keys()),
                'final_status': result.get('final_status')
            }
            
            status = result.get('final_status')
            confidence = result.get('confidence', 0)
            
            if status is None:
                return None, "智能检查无法确定库存状态", check_info
            elif confidence < self.config.confidence_threshold:
                return None, f"置信度过低({confidence:.2f})", check_info
            else:
                return status, None, check_info
                
        except Exception as e:
            self.logger.error(f"智能检查失败 {url}: {e}")
            return None, f"智能检查失败: {str(e)}", {
                'response_time': time.time() - start_time,
                'http_status': 0,
                'content_length': 0,
                'method': 'SMART_COMBO_ERROR'
            }
    
    async def comprehensive_check(self, url: str) -> Dict[str, Any]:
        """综合检查库存状态"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'methods': {},
            'final_status': None,
            'confidence': 0
        }
        
        # 方法1: 获取页面内容用于指纹检查
        html_content = ""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.scraper.get(url, timeout=self.config.request_timeout)
            )
            
            if response and response.status_code == 200:
                html_content = response.text
                
                # 页面指纹检查
                fingerprint_changed, fp_message = await self.fingerprint_monitor.check_page_changes(url, html_content)
                results['methods']['fingerprint'] = {
                    'changed': fingerprint_changed,
                    'message': fp_message
                }
                
                # 简单关键词检查作为基准
                keyword_result = self._basic_keyword_check(html_content)
                results['methods']['keywords'] = keyword_result
                
        except Exception as e:
            results['methods']['basic'] = {'error': str(e)}
        
        # 方法2: DOM元素检查（如果可用）
        if self.dom_monitor and self.config.enable_selenium:
            try:
                dom_status, dom_message, dom_info = await self.dom_monitor.check_stock_by_elements(url)
                results['methods']['dom'] = {
                    'status': dom_status,
                    'message': dom_message,
                    'info': dom_info
                }
            except Exception as e:
                results['methods']['dom'] = {'error': str(e)}
        
        # 方法3: API检查
        if self.config.enable_api_discovery:
            try:
                api_endpoints = await self.api_monitor.discover_api_endpoints(url)
                if api_endpoints:
                    api_status, api_message = await self.api_monitor.check_api_stock(api_endpoints[0])
                    results['methods']['api'] = {
                        'status': api_status,
                        'message': api_message,
                        'endpoints': api_endpoints[:3]
                    }
            except Exception as e:
                results['methods']['api'] = {'error': str(e)}
        
        # 综合判断
        results['final_status'], results['confidence'] = self._make_final_decision(results['methods'])
        
        return results
    
    def _basic_keyword_check(self, content: str) -> Dict:
        """基础关键词检查"""
        content_lower = content.lower()
        
        # 扩展的关键词列表
        out_of_stock_keywords = [
            'sold out', 'out of stock', '缺货', '售罄', '补货中', '缺货中',
            'currently unavailable', 'not available', '暂时缺货',
            'temporarily out of stock', '已售完', '库存不足',
            'out-of-stock', 'unavailable', '无货', '断货',
            'not in stock', 'no stock', '无库存', 'stock: 0',
            '刷新库存', '库存刷新', '暂无库存', '等待补货'
        ]
        
        in_stock_keywords = [
            'add to cart', 'buy now', '立即购买', '加入购物车',
            'in stock', '有货', '现货', 'available', 'order now',
            'purchase', 'checkout', '订购', '下单', '继续', '繼續',
            'configure', 'select options', 'configure now', 'continue',
            '立即订购', '马上购买', '选择配置'
        ]
        
        out_count = sum(1 for keyword in out_of_stock_keywords if keyword in content_lower)
        in_count = sum(1 for keyword in in_stock_keywords if keyword in content_lower)
        
        if out_count > in_count and out_count > 0:
            return {'status': False, 'confidence': 0.7, 'out_count': out_count, 'in_count': in_count}
        elif in_count > out_count and in_count > 0:
            return {'status': True, 'confidence': 0.7, 'out_count': out_count, 'in_count': in_count}
        else:
            return {'status': None, 'confidence': 0.3, 'out_count': out_count, 'in_count': in_count}
    
    def _make_final_decision(self, methods: Dict) -> Tuple[Optional[bool], float]:
        """基于多种方法的结果做出最终判断"""
        votes = []
        confidence_scores = []
        
        # DOM检查权重最高
        if 'dom' in methods and 'status' in methods['dom']:
            status = methods['dom']['status']
            if status is not None:
                votes.append(status)
                confidence_scores.append(0.9)
        
        # API检查权重次之
        if 'api' in methods and 'status' in methods['api']:
            status = methods['api']['status']
            if status is not None:
                votes.append(status)
                confidence_scores.append(0.8)
        
        # 关键词检查
        if 'keywords' in methods and 'status' in methods['keywords']:
            status = methods['keywords']['status']
            if status is not None:
                votes.append(status)
                confidence_scores.append(methods['keywords'].get('confidence', 0.5))
        
        # 页面变化检测
        changes_detected = 0
        if methods.get('fingerprint', {}).get('changed'):
            changes_detected += 1
        
        if changes_detected > 0:
            confidence_scores.append(0.3)
        
        if not votes:
            return None, 0.0
        
        # 投票决定
        true_votes = sum(votes)
        total_votes = len(votes)
        
        if true_votes > total_votes / 2:
            final_status = True
        elif true_votes < total_votes / 2:
            final_status = False
        else:
            # 平票时，倾向于保守判断（无货）
            final_status = False
        
        # 计算置信度
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            # 如果投票一致性高，提高置信度
            vote_consistency = abs(true_votes - (total_votes - true_votes)) / total_votes
            final_confidence = min(avg_confidence * (0.5 + 0.5 * vote_consistency), 1.0)
        else:
            final_confidence = 0.0
        
        return final_status, final_confidence
    
    def close(self):
        """关闭监控器"""
        if self.dom_monitor:
            self.dom_monitor.close()

# ====== Telegram机器人（多用户版） ======
class TelegramBot:
    """Telegram机器人（多用户增强版）"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.app = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """初始化机器人"""
        try:
            self.app = Application.builder().token(self.config.bot_token).build()
            await self.app.initialize()
            bot_info = await self.app.bot.get_me()
            self.logger.info(f"Telegram Bot 初始化成功: @{bot_info.username}")
            print(f"✅ Telegram Bot连接成功: @{bot_info.username}")
            
            self._setup_handlers()
            await self.app.start()
            await self.app.updater.start_polling()
            
        except Exception as e:
            self.logger.error(f"Telegram Bot 初始化失败: {e}")
            raise
    
    def _setup_handlers(self) -> None:
        """设置命令处理器"""
        handlers = [
            CommandHandler("start", self._start_command),
            CommandHandler("help", self._help_command),
            CommandHandler("list", self._list_command),
            CommandHandler("add", self._add_command),
            CommandHandler("status", self._status_command),
            CommandHandler("stats", self._stats_command),
            CommandHandler("debug", self._debug_command),
            CommandHandler("admin", self._admin_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            CallbackQueryHandler(self._handle_callback)
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    def _escape_markdown(self, text: str) -> str:
        """转义Markdown特殊字符"""
        if not text:
            return text
        
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def _check_admin_permission(self, user_id: str) -> bool:
        """检查管理员权限"""
        if not self.config.admin_ids:
            return True
        return str(user_id) in self.config.admin_ids
    
    async def _get_user_info(self, update: Update) -> User:
        """获取用户信息并更新数据库"""
        user = update.effective_user
        return await self.db_manager.add_or_update_user(
            user_id=str(user.id),
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or ""
        )
    
    # ===== 基础命令处理器 =====
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        user_info = await self._get_user_info(update)
        
        if user_info.is_banned:
            await update.message.reply_text("❌ 您已被管理员禁用，无法使用此服务")
            return
        
        await self._show_main_menu(update.message, user_info, edit_message=False)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        help_text = (
            "🤖 **VPS监控机器人 v3.0 帮助**\n\n"
            
            "📱 **基础功能:**\n"
            "• `/start` - 显示主菜单\n"
            "• `/list` - 查看您的监控列表\n"
            "• `/add <URL>` - 添加监控项目\n"
            "• `/status` - 查看系统状态\n"
            "• `/stats` - 查看统计信息\n"
            "• `/help` - 显示此帮助信息\n\n"
            
            "🔍 **调试功能:**\n"
            "• `/debug <URL>` - 调试分析单个URL\n\n"
            
            "🚀 **v3.0 新特性:**\n"
            "• 🧠 智能组合监控算法\n"
            "• 🎯 多重检测方法验证\n"
            "• 📊 置信度评分系统\n"
            "• 👥 多用户支持\n"
            "• 🛡️ 主流VPS商家适配\n\n"
            
            "💡 **使用提示:**\n"
            "• 支持主流VPS商家（DMIT、RackNerd、BWH等）\n"
            "• 智能检测算法自动选择最佳方法\n"
            "• 所有用户都可以添加监控\n"
            "• 库存变化会推送给管理员\n"
            "• 每日添加限制：50个商品\n\n"
            
            "👨‍💻 **开发者信息:**\n"
            "作者: kure29\n"
            "网站: https://kure29.com"
        )
        
        if self._check_admin_permission(str(update.effective_user.id)):
            help_text += (
                "\n\n🧩 **管理员专用:**\n"
                "• `/admin` - 管理员控制面板\n"
                "• 全局监控管理\n"
                "• 用户行为统计\n"
                "• 系统配置管理"
            )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /list 命令"""
        user_info = await self._get_user_info(update)
        if user_info.is_banned:
            await update.message.reply_text("❌ 您已被禁用")
            return
        
        await self._show_monitor_list(update.message, user_info.id, 0, edit_message=False)
    
    async def _add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /add 命令"""
        user_info = await self._get_user_info(update)
        if user_info.is_banned:
            await update.message.reply_text("❌ 您已被禁用")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "📝 **添加监控使用方法:**\n\n"
                "`/add <URL> [名称]`\n\n"
                "例如:\n"
                "`/add https://example.com/vps 测试VPS`\n"
                "`/add https://example.com/product`\n\n"
                "💡 如果不指定名称，将自动提取页面标题",
                parse_mode='Markdown'
            )
            return
        
        url = context.args[0]
        name = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        await self._add_monitor_item(update.message, user_info.id, url, name)
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /status 命令"""
        user_info = await self._get_user_info(update)
        await self._show_system_status(update.message, user_info.id)
    
    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /stats 命令"""
        user_info = await self._get_user_info(update)
        await self._show_user_statistics(update.message, user_info.id)
    
    async def _debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /debug 命令"""
        user_info = await self._get_user_info(update)
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔍 **调试命令使用方法:**\n\n"
                "`/debug <URL>`\n\n"
                "例如: `/debug https://example.com/product`\n\n"
                "此命令会详细分析页面并显示各种检测方法的结果",
                parse_mode='Markdown'
            )
            return
        
        url = context.args[0]
        if not self._is_valid_url(url)[0]:
            await update.message.reply_text("❌ URL格式无效")
            return
        
        await self._debug_url(update.message, url)
    
    async def _admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /admin 命令"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            await update.message.reply_text("❌ 只有管理员才能使用此功能")
            return
        
        await self._show_admin_panel(update.message, user_id)
    
    # ===== 菜单和界面显示 =====
    
    async def _show_main_menu(self, message_or_query, user_info: User, edit_message: bool = False) -> None:
        """显示主菜单"""
        is_admin = self._check_admin_permission(user_info.id)
        
        keyboard = [
            [
                InlineKeyboardButton("📝 我的监控", callback_data=f'list_items_{user_info.id}_0'),
                InlineKeyboardButton("➕ 添加监控", callback_data='add_item')
            ],
            [
                InlineKeyboardButton("📊 系统状态", callback_data='status'),
                InlineKeyboardButton("📈 我的统计", callback_data='my_stats')
            ]
        ]
        
        if is_admin:
            keyboard.append([
                InlineKeyboardButton("🧩 管理员面板", callback_data='admin_panel'),
                InlineKeyboardButton("🔍 调试工具", callback_data='debug_tools')
            ])
        
        keyboard.append([InlineKeyboardButton("❓ 帮助", callback_data='help')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_display = user_info.username or user_info.first_name or "未知用户"
        
        welcome_text = (
            f"👋 欢迎，{user_display}！\n\n"
            "🤖 **VPS 监控机器人 v3.0**\n"
            "🧠 智能多重检测算法\n\n"
            
            f"📊 **您的统计:**\n"
            f"• 监控项目: {user_info.total_monitors} 个\n"
            f"• 通知次数: {user_info.total_notifications} 次\n"
            f"• 今日添加: {user_info.daily_add_count} 个\n\n"
            
            "🆕 **v3.0 特色:**\n"
            "• 🎯 高精度库存检测\n"
            "• 🧠 智能算法组合\n"
            "• 📊 置信度评分\n"
            "• 👥 多用户共享\n"
            "• 🛡️ 主流商家优化"
        )
        
        if is_admin:
            welcome_text += "\n\n🧩 您是管理员，可使用管理功能"
        
        if edit_message:
            await message_or_query.edit_message_text(welcome_text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _show_monitor_list(self, message_or_query, user_id: str, page: int = 0, edit_message: bool = True) -> None:
        """显示监控列表"""
        items = await self.db_manager.get_monitor_items(user_id=user_id, include_global=True)
        
        if not items:
            text = "📝 **您的监控列表**\n\n❌ 还没有监控项目\n\n💡 点击下方按钮添加您的第一个监控项目"
            keyboard = [[InlineKeyboardButton("➕ 添加监控", callback_data='add_item')]]
        else:
            items_list = list(items.values())
            total_pages = (len(items_list) + self.config.items_per_page - 1) // self.config.items_per_page
            start_idx = page * self.config.items_per_page
            end_idx = start_idx + self.config.items_per_page
            page_items = items_list[start_idx:end_idx]
            
            text = f"📝 **您的监控列表** (第 {page + 1}/{total_pages} 页)\n\n"
            
            keyboard = []
            for i, item in enumerate(page_items, start=start_idx + 1):
                status_emoji = "🟢" if item.status else "🔴" if item.status is False else "⚪"
                global_mark = "🌐" if item.is_global else ""
                name = item.name[:25] + "..." if len(item.name) > 25 else item.name
                
                text += f"{i}. {status_emoji} {global_mark}{name}\n"
                text += f"   📊 成功率: {self._calculate_success_rate(item)}\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{i}. {name[:15]}...", 
                        callback_data=f'item_detail_{item.id}'
                    )
                ])
            
            # 分页按钮
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ 上页", callback_data=f'list_items_{user_id}_{page-1}'))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️ 下页", callback_data=f'list_items_{user_id}_{page+1}'))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([
                InlineKeyboardButton("➕ 添加监控", callback_data='add_item'),
                InlineKeyboardButton("🔄 刷新", callback_data=f'list_items_{user_id}_{page}')
            ])
        
        keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await message_or_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(text, reply_markup=reply_markup)
    
    async def _show_admin_panel(self, message_or_query, admin_id: str, edit_message: bool = False) -> None:
        """显示管理员面板"""
        # 获取全局统计
        stats = await self.db_manager.get_global_statistics()
        
        text = (
            "🧩 **管理员控制面板**\n\n"
            
            f"👥 **用户统计:**\n"
            f"• 总用户数: {stats.get('users', {}).get('total', 0)}\n"
            f"• 活跃用户: {stats.get('users', {}).get('active', 0)}\n"
            f"• 被封用户: {stats.get('users', {}).get('banned', 0)}\n\n"
            
            f"📊 **监控统计:**\n"
            f"• 总监控项: {stats.get('monitor_items', {}).get('total', 0)}\n"
            f"• 启用项目: {stats.get('monitor_items', {}).get('enabled', 0)}\n"
            f"• 全局项目: {stats.get('monitor_items', {}).get('global', 0)}\n"
            f"• 有货项目: {stats.get('monitor_items', {}).get('in_stock', 0)}\n\n"
            
            f"🔍 **检查统计:**\n"
            f"• 总检查次数: {stats.get('checks', {}).get('total', 0)}\n"
            f"• 成功检查: {stats.get('checks', {}).get('successful', 0)}\n"
            f"• 平均响应: {stats.get('checks', {}).get('avg_response_time', 0)}s\n"
            f"• 平均置信度: {stats.get('checks', {}).get('avg_confidence', 0)}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👥 用户管理", callback_data='admin_users'),
                InlineKeyboardButton("📊 全局监控", callback_data='admin_monitors')
            ],
            [
                InlineKeyboardButton("📈 详细统计", callback_data='admin_stats'),
                InlineKeyboardButton("⚙️ 系统配置", callback_data='admin_config')
            ],
            [
                InlineKeyboardButton("🔧 维护工具", callback_data='admin_maintenance'),
                InlineKeyboardButton("📋 操作日志", callback_data='admin_logs')
            ],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await message_or_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(text, reply_markup=reply_markup)
    
    # ===== 核心功能实现 =====
    
    async def _add_monitor_item(self, message, user_id: str, url: str, name: str = "") -> None:
        """添加监控项目"""
        # 验证URL
        is_valid, error_msg = self._is_valid_url(url)
        if not is_valid:
            await message.reply_text(f"❌ {error_msg}")
            return
        
        # 检查用户状态
        user = await self.db_manager.get_user(user_id)
        if user and user.is_banned:
            await message.reply_text("❌ 您已被禁用，无法添加监控")
            return
        
        # 检查每日限制
        if user and user.daily_add_count >= self.config.daily_add_limit:
            today = datetime.now().date().isoformat()
            if user.last_add_date == today:
                await message.reply_text(f"❌ 今日添加数量已达上限 ({self.config.daily_add_limit})")
                return
        
        adding_msg = await message.reply_text("⏳ 正在添加监控项...")
        
        try:
            # 如果没有提供名称，尝试获取页面标题
            if not name:
                try:
                    smart_monitor = SmartComboMonitor(self.config)
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: smart_monitor.scraper.get(url, timeout=10)
                    )
                    
                    if response and response.status_code == 200:
                        title_match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
                        if title_match:
                            name = title_match.group(1).strip()[:50]
                    
                    smart_monitor.close()
                except:
                    pass
                
                if not name:
                    name = f"监控项目 {datetime.now().strftime('%m-%d %H:%M')}"
            
            # 添加到数据库
            item_id, success = await self.db_manager.add_monitor_item(
                user_id=user_id,
                name=name,
                url=url,
                config="",
                tags=[],
                is_global=False
            )
            
            if success:
                await adding_msg.edit_text(
                    f"✅ **监控添加成功**\n\n"
                    f"📝 名称: {name}\n"
                    f"🔗 URL: {url}\n"
                    f"🆔 ID: {item_id}\n\n"
                    f"🔍 系统将在下次检查周期中开始监控此项目\n"
                    f"📱 库存变化时会推送通知给管理员"
                )
                
                # 通知管理员
                for admin_id in self.config.admin_ids:
                    await self.send_notification(
                        message=f"📝 新增监控项\n\n"
                                f"👤 用户: {user.username or user.first_name or user_id}\n"
                                f"📝 名称: {name}\n"
                                f"🔗 URL: {url}",
                        chat_id=admin_id
                    )
            else:
                await adding_msg.edit_text("❌ 添加失败，可能URL已存在或达到限制")
                
        except Exception as e:
            await adding_msg.edit_text(f"❌ 添加失败: {str(e)}")
            self.logger.error(f"添加监控项失败: {e}")
    
    async def _debug_url(self, message, url: str) -> None:
        """调试URL分析"""
        checking_msg = await message.reply_text("🔍 正在进行详细分析...")
        
        try:
            smart_monitor = SmartComboMonitor(self.config)
            result = await smart_monitor.comprehensive_check(url)
            
            debug_text = f"🔍 **调试分析结果**\n\n"
            debug_text += f"🔗 **URL:** {url}\n"
            debug_text += f"📊 **最终状态:** {result.get('final_status')}\n"
            debug_text += f"🎯 **置信度:** {result.get('confidence', 0):.2f}\n\n"
            
            # 显示各种方法的结果
            methods = result.get('methods', {})
            
            for method_name, method_result in methods.items():
                debug_text += f"**{method_name.upper()}检查:**\n"
                
                if 'error' in method_result:
                    debug_text += f"❌ 错误: {method_result['error']}\n"
                elif 'status' in method_result:
                    status = method_result['status']
                    if status is True:
                        debug_text += "✅ 有货\n"
                    elif status is False:
                        debug_text += "❌ 无货\n"
                    else:
                        debug_text += "⚪ 未知\n"
                    
                    if 'message' in method_result:
                        debug_text += f"💬 详情: {method_result['message']}\n"
                else:
                    debug_text += f"📋 结果: {method_result}\n"
                
                debug_text += "\n"
            
            # 建议
            confidence = result.get('confidence', 0)
            if confidence < 0.3:
                debug_text += "💡 **建议:** 检测置信度很低，可能需要手动验证\n"
            elif confidence < 0.6:
                debug_text += "💡 **建议:** 检测置信度中等，建议观察多次检查结果\n"
            else:
                debug_text += "💡 **建议:** 检测置信度较高，结果相对可靠\n"
            
            smart_monitor.close()
            
            await checking_msg.edit_text(debug_text, parse_mode='Markdown')
            
        except Exception as e:
            await checking_msg.edit_text(f"❌ 调试分析失败: {str(e)}")
    
    # ===== 统计和状态显示 =====
    
    async def _show_system_status(self, message, user_id: str) -> None:
        """显示系统状态"""
        try:
            stats = await self.db_manager.get_global_statistics()
            
            status_text = (
                "📊 **系统运行状态**\n\n"
                
                f"🤖 **Bot状态:** ✅ 运行中\n"
                f"🧠 **监控算法:** v3.0 智能组合\n"
                f"⏱️ **检查间隔:** {self.config.check_interval}秒\n"
                f"🎯 **置信度阈值:** {self.config.confidence_threshold}\n\n"
                
                f"👥 **用户统计:**\n"
                f"• 总用户: {stats.get('users', {}).get('total', 0)}\n"
                f"• 活跃用户: {stats.get('users', {}).get('active', 0)}\n\n"
                
                f"📋 **监控统计:**\n"
                f"• 总监控项: {stats.get('monitor_items', {}).get('total', 0)}\n"
                f"• 启用项目: {stats.get('monitor_items', {}).get('enabled', 0)}\n"
                f"• 有货项目: {stats.get('monitor_items', {}).get('in_stock', 0)}\n\n"
                
                f"🔍 **检查统计:**\n"
                f"• 总检查: {stats.get('checks', {}).get('total', 0)}\n"
                f"• 成功率: {self._calculate_global_success_rate(stats)}\n"
                f"• 平均响应: {stats.get('checks', {}).get('avg_response_time', 0)}s\n"
                f"• 平均置信度: {stats.get('checks', {}).get('avg_confidence', 0):.2f}\n\n"
                
                f"🚀 **功能状态:**\n"
                f"• Selenium: {'✅' if SELENIUM_AVAILABLE and self.config.enable_selenium else '❌'}\n"
                f"• API发现: {'✅' if self.config.enable_api_discovery else '❌'}\n"
                f"• 视觉对比: {'✅' if self.config.enable_visual_comparison else '❌'}\n\n"
                
                f"⏰ 最后更新: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            keyboard = [[InlineKeyboardButton("🔄 刷新", callback_data='status')]]
            if self._check_admin_permission(user_id):
                keyboard[0].append(InlineKeyboardButton("🧩 管理面板", callback_data='admin_panel'))
            keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')])
            
            await message.reply_text(status_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            await message.reply_text(f"❌ 获取系统状态失败: {str(e)}")
    
    async def _show_user_statistics(self, message, user_id: str) -> None:
        """显示用户统计"""
        try:
            stats = await self.db_manager.get_user_statistics(user_id)
            
            user_info = stats.get('user_info', {})
            monitor_info = stats.get('monitor_items', {})
            activities = stats.get('recent_activities', {})
            
            stats_text = (
                f"📈 **个人统计信息**\n\n"
                
                f"👤 **基本信息:**\n"
                f"• 用户名: {user_info.get('username', '未设置')}\n"
                f"• 注册时间: {user_info.get('created_at', '').split('T')[0] if user_info.get('created_at') else '未知'}\n"
                f"• 总监控数: {user_info.get('total_monitors', 0)}\n"
                f"• 总通知数: {user_info.get('total_notifications', 0)}\n\n"
                
                f"📊 **监控项目:**\n"
                f"• 总数: {monitor_info.get('total', 0)}\n"
                f"• 启用: {monitor_info.get('enabled', 0)}\n"
                f"• 有货: {monitor_info.get('in_stock', 0)}\n"
                f"• 全局项目: {monitor_info.get('global_items', 0)}\n\n"
                
                "🎯 **近期活动:**\n"
            )
            
            if activities:
                for action, count in list(activities.items())[:5]:
                    action_name = {
                        'add_monitor': '添加监控',
                        'remove_monitor': '删除监控',
                        'user_login': '登录使用'
                    }.get(action, action)
                    stats_text += f"• {action_name}: {count} 次\n"
            else:
                stats_text += "• 暂无活动记录\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 刷新", callback_data='my_stats')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            
            await message.reply_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            await message.reply_text(f"❌ 获取统计信息失败: {str(e)}")
    
    # ===== 消息处理器 =====
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本消息"""
        user_info = await self._get_user_info(update)
        if user_info.is_banned:
            return
        
        text = update.message.text.strip()
        
        # 检查是否是URL
        if text.startswith(('http://', 'https://')):
            await self._add_monitor_item(update.message, user_info.id, text)
        else:
            # 提供帮助信息
            await update.message.reply_text(
                "💡 **快速添加监控:**\n"
                "直接发送URL即可添加监控\n\n"
                "📋 **其他操作:**\n"
                "• 使用 /start 查看菜单\n"
                "• 使用 /help 查看帮助\n"
                "• 使用 /list 查看监控列表"
            )
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理回调查询"""
        query = update.callback_query
        user_info = await self._get_user_info(update)
        
        if user_info.is_banned:
            await query.answer("您已被禁用")
            return
        
        data = query.data
        
        try:
            if data == 'main_menu':
                await self._show_main_menu(query, user_info, edit_message=True)
            
            elif data == 'add_item':
                await query.edit_message_text(
                    "📝 **添加监控项目**\n\n"
                    "请发送以下格式的消息:\n"
                    "`/add <URL> [名称]`\n\n"
                    "或者直接发送URL，系统会自动提取页面标题作为名称\n\n"
                    "例如:\n"
                    "`/add https://example.com/vps 测试VPS`\n"
                    "`https://example.com/product`",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')
                    ]])
                )
            
            elif data.startswith('list_items_'):
                parts = data.split('_')
                target_user_id = parts[2]
                page = int(parts[3])
                await self._show_monitor_list(query, target_user_id, page, edit_message=True)
            
            elif data == 'status':
                await self._show_system_status(query.message, user_info.id)
            
            elif data == 'my_stats':
                await self._show_user_statistics(query.message, user_info.id)
            
            elif data == 'help':
                await self._help_command(update, context)
            
            elif data == 'admin_panel':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_panel(query, user_info.id, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            await query.answer()
            
        except Exception as e:
            self.logger.error(f"处理回调查询失败: {e}")
            await query.answer("操作失败，请重试")
    
    # ===== 工具方法 =====
    
    def _is_valid_url(self, url: str) -> Tuple[bool, str]:
        """验证URL格式"""
        if not url:
            return False, "URL不能为空"
        
        if not url.startswith(('http://', 'https://')):
            return False, "URL必须以 http:// 或 https:// 开头"
        
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                return False, "URL格式无效，缺少域名"
            
            invalid_domains = ['localhost', '127.0.0.1', '0.0.0.0']
            if parsed.netloc.lower() in invalid_domains:
                return False, "不支持本地地址"
                
            return True, ""
        except Exception:
            return False, "URL格式无效"
    
    def _calculate_success_rate(self, item: MonitorItem) -> str:
        """计算成功率"""
        total = item.success_count + item.failure_count
        if total == 0:
            return "暂无数据"
        
        rate = (item.success_count / total) * 100
        return f"{rate:.1f}%"
    
    def _calculate_global_success_rate(self, stats: Dict) -> str:
        """计算全局成功率"""
        checks = stats.get('checks', {})
        total = checks.get('total', 0)
        successful = checks.get('successful', 0)
        
        if total == 0:
            return "暂无数据"
        
        rate = (successful / total) * 100
        return f"{rate:.1f}%"
    
    async def send_notification(self, message: str, parse_mode: str = None, chat_id: str = None) -> None:
        """发送通知"""
        try:
            if self.app and self.app.bot:
                target_chat_id = chat_id or self.config.channel_id or self.config.chat_id
                
                await self.app.bot.send_message(
                    chat_id=target_chat_id, 
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False
                )
                self.logger.info(f"通知发送成功到 {target_chat_id}")
        except Exception as e:
            self.logger.error(f"发送通知失败: {e}")
    
    async def shutdown(self) -> None:
        """关闭机器人"""
        try:
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                self.logger.info("Telegram Bot已关闭")
        except Exception as e:
            self.logger.error(f"关闭机器人失败: {e}")

# ====== 主监控类（多用户版） ======
class VPSMonitor:
    """主监控类（v3.0多用户版）"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.stock_checker = None
        self.telegram_bot = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._pending_notifications = []
        self._last_aggregation_time = datetime.now()
        self._last_notified = {}
    
    async def initialize(self) -> None:
        """初始化监控器"""
        try:
            print("🔧 初始化监控器 v3.0 (多用户版)...")
            
            # 加载配置
            config = self.config_manager.load_config()
            print("✅ 配置文件加载成功")
            
            # 初始化数据库
            await self.db_manager.initialize()
            print("✅ 多用户数据库初始化成功")
            
            # 初始化智能监控器
            self.stock_checker = SmartComboMonitor(config)
            self.telegram_bot = TelegramBot(config, self.db_manager)
            
            # 初始化Telegram Bot
            await self.telegram_bot.initialize()
            
            # 显示功能状态
            print(f"🤖 Selenium支持: {'✅' if SELENIUM_AVAILABLE and config.enable_selenium else '❌'}")
            print(f"🔍 API发现: {'✅' if config.enable_api_discovery else '❌'}")
            print(f"👁️ 视觉对比: {'✅' if config.enable_visual_comparison else '❌'}")
            print(f"👥 多用户支持: ✅")
            print(f"📊 每日添加限制: {config.daily_add_limit}")
            
            self.logger.info("多用户监控器v3.0初始化完成")
            print("✅ 多用户监控器v3.0初始化完成")
            
        except Exception as e:
            self.logger.error(f"监控器初始化失败: {e}")
            print(f"❌ 监控器初始化失败: {e}")
            raise
    
    async def _perform_startup_check(self) -> None:
        """执行启动检查"""
        # 获取所有启用的监控项（包括全局项目）
        items = await self.db_manager.get_monitor_items(enabled_only=True)
        if not items:
            await self.telegram_bot.send_notification("⚠️ 当前没有监控商品")
            print("⚠️ 当前没有监控商品")
            return
        
        print(f"🔍 开始智能检查 {len(items)} 个监控项...")
        await self.telegram_bot.send_notification("🧠 正在进行智能启动检查...")
        
        success_count = 0
        fail_count = 0
        low_confidence_count = 0
        
        for item in items.values():
            try:
                print(f"智能检查: {item.name} (用户: {item.user_id})")
                stock_available, error, check_info = await self.stock_checker.check_stock(item.url)
                
                # 记录检查历史
                await self.db_manager.add_check_history(
                    monitor_id=item.id,
                    status=stock_available,
                    response_time=check_info['response_time'],
                    error_message=error or '',
                    http_status=check_info['http_status'],
                    content_length=check_info['content_length'],
                    confidence=check_info.get('confidence', 0),
                    method_used=check_info.get('method', 'SMART_COMBO')
                )
                
                if error:
                    fail_count += 1
                    print(f"  ❌ 检查失败: {error}")
                else:
                    confidence = check_info.get('confidence', 0)
                    if confidence < self.config_manager.config.confidence_threshold:
                        low_confidence_count += 1
                        print(f"  ⚠️ 置信度过低: {confidence:.2f}")
                    else:
                        success_count += 1
                        status = "🟢 有货" if stock_available else "🔴 无货"
                        print(f"  ✅ 状态：{status} (置信度: {confidence:.2f})")
                    
                    await self.db_manager.update_monitor_item_status(item.id, stock_available, 0)
                
            except Exception as e:
                fail_count += 1
                self.logger.error(f"启动检查失败 {item.url}: {e}")
                print(f"  ❌ 检查异常: {e}")
        
        summary = (
            f"🧠 智能启动检查完成\n\n"
            f"✅ 成功: {success_count} 个\n"
            f"❌ 失败: {fail_count} 个\n"
            f"⚠️ 低置信度: {low_confidence_count} 个\n\n"
            f"🎯 多用户监控系统已就绪"
        )
        await self.telegram_bot.send_notification(summary)
        print(f"\n{summary}")
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._check_all_items()
                await self._process_notifications()
                
                # 等待下次检查
                await asyncio.sleep(self.config_manager.config.check_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟
    
    async def _check_all_items(self) -> None:
        """检查所有监控项"""
        items = await self.db_manager.get_monitor_items(enabled_only=True)
        
        if not items:
            return
        
        print(f"🔍 检查 {len(items)} 个监控项...")
        
        for item in items.values():
            try:
                stock_available, error, check_info = await self.stock_checker.check_stock(item.url)
                
                # 记录检查历史
                await self.db_manager.add_check_history(
                    monitor_id=item.id,
                    status=stock_available,
                    response_time=check_info['response_time'],
                    error_message=error or '',
                    http_status=check_info['http_status'],
                    content_length=check_info['content_length'],
                    confidence=check_info.get('confidence', 0),
                    method_used=check_info.get('method', 'SMART_COMBO')
                )
                
                # 检查是否需要通知
                if not error and stock_available is not None:
                    await self._check_for_notifications(item, stock_available, check_info)
                    await self.db_manager.update_monitor_item_status(item.id, stock_available, 0)
                
            except Exception as e:
                self.logger.error(f"检查项目失败 {item.url}: {e}")
    
    async def _check_for_notifications(self, item: MonitorItem, stock_available: bool, check_info: Dict) -> None:
        """检查是否需要发送通知"""
        # 只有状态变化或首次检查时才通知
        if item.status != stock_available:
            confidence = check_info.get('confidence', 0)
            
            if stock_available and confidence >= self.config_manager.config.confidence_threshold:
                # 有货通知
                notification = {
                    'type': 'stock_available',
                    'item': item,
                    'confidence': confidence,
                    'timestamp': datetime.now()
                }
                
                # 检查通知冷却
                cooldown_key = f"{item.id}_available"
                last_notified = self._last_notified.get(cooldown_key)
                
                if not last_notified or (datetime.now() - last_notified).seconds > self.config_manager.config.notification_cooldown:
                    self._pending_notifications.append(notification)
                    self._last_notified[cooldown_key] = datetime.now()
    
    async def _process_notifications(self) -> None:
        """处理待发送的通知"""
        if not self._pending_notifications:
            return
        
        # 检查是否到达聚合时间
        time_since_last = (datetime.now() - self._last_aggregation_time).seconds
        if time_since_last < self.config_manager.config.notification_aggregation_interval:
            return
        
        # 按类型分组通知
        available_notifications = [n for n in self._pending_notifications if n['type'] == 'stock_available']
        
        if available_notifications:
            await self._send_aggregated_notifications(available_notifications)
        
        # 清空待发送列表
        self._pending_notifications.clear()
        self._last_aggregation_time = datetime.now()
    
    async def _send_aggregated_notifications(self, notifications: List[Dict]) -> None:
        """发送聚合通知"""
        if len(notifications) == 1:
            # 单个通知
            item = notifications[0]['item']
            confidence = notifications[0]['confidence']
            
            user_info = await self.db_manager.get_user(item.user_id)
            user_display = "未知用户"
            if user_info:
                user_display = user_info.username or user_info.first_name or f"用户{item.user_id}"
            
            message = (
                f"🟢 **有货提醒**\n\n"
                f"📝 **商品:** {item.name}\n"
                f"👤 **添加者:** {user_display}\n"
                f"🔗 **链接:** {item.url}\n"
                f"🎯 **置信度:** {confidence:.2f}\n"
                f"🕐 **检测时间:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"🧠 **检测方法:** 智能组合算法"
            )
        else:
            # 批量通知
            message = f"🟢 **批量有货提醒** ({len(notifications)}个商品)\n\n"
            
            for i, notification in enumerate(notifications[:5], 1):
                item = notification['item']
                confidence = notification['confidence']
                user_info = await self.db_manager.get_user(item.user_id)
                user_display = user_info.username if user_info and user_info.username else f"用户{item.user_id}"
                
                message += f"{i}. **{item.name}**\n"
                message += f"   👤 {user_display} | 🎯 {confidence:.2f}\n"
                message += f"   🔗 {item.url}\n\n"
            
            if len(notifications) > 5:
                message += f"...还有 {len(notifications) - 5} 个商品有货\n\n"
            
            message += f"🕐 **检测时间:** {datetime.now().strftime('%H:%M:%S')}"
        
        # 发送给所有管理员
        for admin_id in self.config_manager.config.admin_ids:
            await self.telegram_bot.send_notification(message, parse_mode='Markdown', chat_id=admin_id)
        
        # 记录通知历史
        for notification in notifications:
            item = notification['item']
            await self.db_manager.add_notification_history(
                user_id=item.user_id,
                monitor_id=item.id,
                message=message,
                notification_type='stock_alert'
            )
    
    async def start(self) -> None:
        """启动监控"""
        try:
            print("🚀 启动VPS监控系统 v3.0 (多用户版)...")
            await self.initialize()
            
            # 发送启动通知
            config = self.config_manager.config
            startup_message = (
                "🚀 **VPS监控程序 v3.0 已启动** (多用户版)\n\n"
                "🆕 **v3.0新特性:**\n"
                "🧠 智能组合监控算法\n"
                "🎯 多重检测方法验证\n"
                "📊 置信度评分系统\n"
                "👥 多用户支持系统\n"
                "🛡️ 主流VPS商家适配\n\n"
                f"⚙️ **系统配置:**\n"
                f"⏰ 检查间隔：{config.check_interval}秒\n"
                f"📊 聚合间隔：{config.notification_aggregation_interval}秒\n"
                f"🕐 通知冷却：{config.notification_cooldown}秒\n"
                f"🎯 置信度阈值：{config.confidence_threshold}\n"
                f"📈 每日添加限制：{config.daily_add_limit}\n\n"
                f"👥 **多用户特性:**\n"
                f"• 所有用户都可添加监控\n"
                f"• 库存变化推送给管理员\n"
                f"• 用户行为统计和管理\n"
                f"• 智能防刷机制\n\n"
                "💡 使用 /start 开始操作\n"
                "🔍 使用 /debug <URL> 进行调试\n"
                "🧩 管理员可使用 /admin 管理\n\n"
                "👨‍💻 作者: kure29 | https://kure29.com"
            )
            await self.telegram_bot.send_notification(startup_message, parse_mode='Markdown')
            
            # 执行启动检查
            await self._perform_startup_check()
            
            # 开始监控循环
            self._running = True
            print("✅ 多用户智能监控系统启动成功，按Ctrl+C停止")
            await self._monitor_loop()
            
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号")
            self.logger.info("收到停止信号")
        except Exception as e:
            print(f"❌ 监控运行失败: {e}")
            self.logger.error(f"监控运行失败: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """停止监控"""
        print("🛑 正在停止监控系统...")
        self._running = False
        if self.stock_checker:
            self.stock_checker.close()
        if self.telegram_bot:
            await self.telegram_bot.shutdown()
        self.logger.info("监控程序已停止")
        print("✅ 监控程序已停止")


# ====== 日志设置 ======
def setup_logging() -> None:
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('monitor.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


# ====== 主函数 ======
async def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🤖 VPS监控系统 v3.0 - 多用户智能监控版")
    print("👨‍💻 作者: kure29")
    print("🌐 网站: https://kure29.com")
    print("🆕 新功能: 多用户+智能算法+多重验证+置信度评分")
    print("=" * 60)
    
    try:
        monitor = VPSMonitor()
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        print("\n✅ 程序已停止")
    except Exception as e:
        logger.error(f"程序发生错误: {e}")
        print(f"❌ 程序发生错误: {e}")
        print("\n💡 常见解决方案:")
        print("1. 检查config.json文件是否存在且配置正确")
        print("2. 确认Telegram Bot Token和Chat ID有效")
        print("3. 检查网络连接")
        print("4. 安装selenium: pip install selenium webdriver-manager")
        print("5. 查看monitor.log获取详细错误信息")
        print("6. 确保admin_ids配置正确（多用户版必需）")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"程序发生错误: {e}")
