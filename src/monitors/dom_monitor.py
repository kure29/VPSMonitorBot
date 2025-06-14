#!/usr/bin/env python3
"""
DOM元素监控器
VPS监控系统 v3.1
"""

import asyncio
import logging
from typing import Dict, Tuple, Optional
from config import Config

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
except ImportError:
    SELENIUM_AVAILABLE = False


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
            
            # 使用服务商优化检查（如果可用且启用）
            try:
                from vendor_optimization import VendorOptimizer
                if self.config.enable_vendor_optimization:
                    vendor_optimizer = VendorOptimizer()
                    vendor_result = vendor_optimizer.check_vendor_specific(self.driver, url)
                    if vendor_result['status'] is not None:
                        return vendor_result['status'], vendor_result['message'], check_info
            except ImportError:
                pass
            
            # 通用检查逻辑
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
