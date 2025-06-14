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
            
            # 通用检查逻辑 - 改进顺序，先检查缺货标识
            
            # 优先检查缺货文本
            stock_info = self._check_stock_text()
            if stock_info['definitive'] and stock_info['status'] is False:
                # 如果明确显示缺货，直接返回
                return False, stock_info['message'], check_info
            
            # 检查页面标题是否包含缺货信息
            title_check = self._check_page_title()
            if title_check['is_out_of_stock']:
                return False, title_check['message'], check_info
            
            # 只有在没有发现明确缺货标识的情况下，才检查购买按钮
            buy_buttons = self._find_buy_buttons()
            
            # 如果有明确的有货文本
            if stock_info['definitive'] and stock_info['status'] is True:
                # 并且有可用的购买按钮
                if buy_buttons['enabled_count'] > 0:
                    return True, f"发现有货文本和{buy_buttons['enabled_count']}个可用购买按钮", check_info
            
            # 如果只有购买按钮，没有其他明确标识，需要更谨慎
            if buy_buttons['enabled_count'] > 0 and buy_buttons['disabled_count'] == 0:
                # 检查是否是通用导航按钮
                if not self._is_generic_navigation_button():
                    # 检查价格信息
                    price_info = self._check_price_elements()
                    if price_info['has_price'] and price_info['has_form']:
                        return True, f"发现价格信息、订单表单和{buy_buttons['enabled_count']}个购买按钮", check_info
                    elif price_info['has_price']:
                        return None, f"发现价格和按钮但无明确库存信息", check_info
                else:
                    return None, "发现的可能是导航按钮而非购买按钮", check_info
            
            # 如果按钮被禁用
            if buy_buttons['disabled_count'] > 0 and buy_buttons['enabled_count'] == 0:
                return False, f"发现{buy_buttons['disabled_count']}个被禁用的购买按钮", check_info
            
            return None, "DOM检查无法确定库存状态", check_info
            
        except Exception as e:
            self.logger.error(f"DOM检查失败: {e}")
            return None, f"DOM检查失败: {str(e)}", {}
    
    def _check_page_title(self) -> Dict:
        """检查页面标题中的库存信息"""
        try:
            title = self.driver.title.lower()
            
            out_of_stock_keywords = [
                'out of stock', 'sold out', '缺货', '售罄',
                'unavailable', '无货', '断货'
            ]
            
            for keyword in out_of_stock_keywords:
                if keyword in title:
                    return {
                        'is_out_of_stock': True,
                        'message': f'页面标题显示缺货: {self.driver.title}'
                    }
            
            return {
                'is_out_of_stock': False,
                'message': ''
            }
        except:
            return {
                'is_out_of_stock': False,
                'message': ''
            }
    
    def _is_generic_navigation_button(self) -> bool:
        """检查是否是通用导航按钮（如Create账户按钮）"""
        try:
            # 检查是否在导航栏、侧边栏或头部
            nav_selectors = [
                "nav", "header", ".nav", ".navbar", ".sidebar", 
                ".menu", "[role='navigation']", ".navigation"
            ]
            
            for nav_selector in nav_selectors:
                nav_elements = self.driver.find_elements(By.CSS_SELECTOR, nav_selector)
                for nav in nav_elements:
                    # 检查导航区域内是否有Create等按钮
                    buttons_in_nav = nav.find_elements(By.TAG_NAME, "button")
                    links_in_nav = nav.find_elements(By.TAG_NAME, "a")
                    
                    for element in buttons_in_nav + links_in_nav:
                        text = element.text.lower()
                        if any(word in text for word in ['create', 'login', 'register', 'account']):
                            return True
            
            # 检查URL是否包含特定路径
            current_url = self.driver.current_url.lower()
            if any(path in current_url for path in ['/cart', '/basket', '/checkout']):
                # 在购物车页面，Create可能是创建订单按钮
                return False
            
            return False
        except:
            return False
    
    def _find_buy_buttons(self) -> Dict:
        """查找购买按钮"""
        button_selectors = [
            "//button[contains(translate(text(), 'BUY', 'buy'), 'buy')]",
            "//button[contains(text(), '购买')]",
            "//button[contains(translate(text(), 'ORDER', 'order'), 'order')]", 
            "//button[contains(text(), '订购')]",
            "//button[contains(translate(text(), 'ADD TO CART', 'add to cart'), 'add to cart')]",
            "//button[contains(text(), '加入购物车')]",
            "//button[contains(text(), 'Purchase')]",
            "//button[contains(text(), 'Get Started')]",
            "//button[contains(text(), 'Continue')]",
            "//button[contains(text(), '继续')]",
            "//button[contains(text(), 'Create')]",  # 保留但需要额外检查
            ".btn-buy", ".buy-button", ".order-button", ".purchase-button",
            "input[type='submit'][value*='buy' i]",
            "input[type='submit'][value*='order' i]",
            "input[type='submit'][value*='purchase' i]",
            "a.btn[href*='cart']", "a.btn[href*='order']"
        ]
        
        enabled_count = 0
        disabled_count = 0
        found_buttons = []
        
        for selector in button_selectors:
            try:
                if selector.startswith('//'):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if element.is_displayed():
                        button_text = element.text.strip()
                        
                        # 特殊处理Create按钮
                        if 'create' in button_text.lower():
                            # 检查是否在导航区域
                            if self._is_element_in_navigation(element):
                                continue  # 跳过导航区的Create按钮
                            
                            # 检查上下文是否与购买相关
                            if not self._is_purchase_context(element):
                                continue
                        
                        if element.is_enabled():
                            enabled_count += 1
                            found_buttons.append({
                                'text': button_text,
                                'enabled': True
                            })
                        else:
                            disabled_count += 1
                            found_buttons.append({
                                'text': button_text,
                                'enabled': False
                            })
            except:
                continue
        
        return {
            'enabled_count': enabled_count,
            'disabled_count': disabled_count,
            'buttons': found_buttons[:5]  # 返回前5个按钮的信息
        }
    
    def _is_element_in_navigation(self, element) -> bool:
        """检查元素是否在导航区域内"""
        try:
            # 向上遍历父元素
            current = element
            for _ in range(5):  # 最多向上查找5层
                current = current.find_element(By.XPATH, "..")
                tag_name = current.tag_name.lower()
                class_name = current.get_attribute('class') or ''
                id_name = current.get_attribute('id') or ''
                
                if (tag_name in ['nav', 'header'] or 
                    any(nav_class in class_name.lower() for nav_class in ['nav', 'menu', 'sidebar']) or
                    any(nav_id in id_name.lower() for nav_id in ['nav', 'menu', 'sidebar'])):
                    return True
            return False
        except:
            return False
    
    def _is_purchase_context(self, element) -> bool:
        """检查元素周围是否有购买相关的上下文"""
        try:
            # 获取元素周围的文本
            parent = element.find_element(By.XPATH, "..")
            context_text = parent.text.lower()
            
            # 购买相关的上下文关键词
            purchase_keywords = [
                'price', 'cost', 'plan', 'package', 'subscription',
                '价格', '费用', '套餐', '订阅', 'billing', 'payment',
                'monthly', 'yearly', '月付', '年付', 'configure'
            ]
            
            return any(keyword in context_text for keyword in purchase_keywords)
        except:
            return False
    
    def _check_stock_text(self) -> Dict:
        """检查库存相关文本"""
        # 高优先级缺货选择器
        high_priority_out_selectors = [
            "//h1[contains(translate(text(), 'OUT OF STOCK', 'out of stock'), 'out of stock')]",
            "//h2[contains(translate(text(), 'OUT OF STOCK', 'out of stock'), 'out of stock')]",
            "//h3[contains(translate(text(), 'OUT OF STOCK', 'out of stock'), 'out of stock')]",
            "//*[contains(@class, 'title')][contains(translate(text(), 'OUT OF STOCK', 'out of stock'), 'out of stock')]",
            "//*[contains(@class, 'heading')][contains(translate(text(), 'OUT OF STOCK', 'out of stock'), 'out of stock')]",
        ]
        
        # 普通缺货选择器
        out_of_stock_selectors = [
            "//*[contains(translate(text(), 'OUT OF STOCK', 'out of stock'), 'out of stock')]",
            "//*[contains(text(), '缺货')]",
            "//*[contains(translate(text(), 'SOLD OUT', 'sold out'), 'sold out')]",
            "//*[contains(text(), '售罄')]",
            "//*[contains(text(), '缺货中')]",
            "//*[contains(translate(text(), 'UNAVAILABLE', 'unavailable'), 'unavailable')]",
            "//*[contains(text(), '暂无库存')]",
            "//*[contains(text(), '库存不足')]",
            "//*[contains(text(), 'currently out of stock')]",
            "//*[contains(text(), 'suspended')]"
        ]
        
        in_stock_selectors = [
            "//*[contains(translate(text(), 'IN STOCK', 'in stock'), 'in stock')]",
            "//*[contains(text(), '有货')]",
            "//*[contains(translate(text(), 'AVAILABLE', 'available'), 'available')]",
            "//*[contains(text(), '现货')]",
            "//*[contains(text(), '立即购买')]"
        ]
        
        # 优先检查高优先级缺货文本（标题级别）
        for selector in high_priority_out_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                visible_elements = [el for el in elements if el.is_displayed()]
                if visible_elements:
                    element_text = visible_elements[0].text.strip()
                    return {
                        'status': False,
                        'message': f'页面标题显示缺货: {element_text}',
                        'definitive': True
                    }
            except:
                continue
        
        # 检查普通缺货文本
        for selector in out_of_stock_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                visible_elements = [el for el in elements if el.is_displayed()]
                
                # 过滤掉可能的误判（如菜单项）
                for element in visible_elements:
                    if not self._is_element_in_navigation(element):
                        element_text = element.text.strip()[:100]  # 限制文本长度
                        return {
                            'status': False,
                            'message': f'发现缺货文本: {element_text}',
                            'definitive': True
                        }
            except:
                continue
        
        # 检查有货文本
        for selector in in_stock_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                visible_elements = [el for el in elements if el.is_displayed()]
                
                for element in visible_elements:
                    if not self._is_element_in_navigation(element):
                        element_text = element.text.strip()[:100]
                        return {
                            'status': True,
                            'message': f'发现有货文本: {element_text}',
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
            ".price", ".cost", ".amount", ".pricing",
            "[class*='price']", "[class*='cost']", "[class*='pricing']",
            "//*[contains(text(), '$')]",
            "//*[contains(text(), '¥')]",
            "//*[contains(text(), '€')]",
            "//*[contains(text(), '/mo')]",
            "//*[contains(text(), '/month')]",
            "//*[contains(text(), '/年')]"
        ]
        
        form_selectors = [
            "form[action*='cart']", "form[action*='order']", 
            "input[type='submit']", "button[type='submit']",
            ".checkout", ".order-form", ".purchase-form",
            ".product-options", ".configuration"
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
                    if element.is_displayed() and not self._is_element_in_navigation(element):
                        text = element.text.strip()
                        # 验证是否包含数字
                        if text and any(char.isdigit() for char in text):
                            if any(symbol in text for symbol in ['$', '¥', '€', '/mo', '/month', '/年']):
                                found_prices.append(text[:30])
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
