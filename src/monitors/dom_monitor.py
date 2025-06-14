#!/usr/bin/env python3
"""
DOM元素监控器（优化版）
VPS监控系统 v3.1
增强了库存判断的准确性
"""

import asyncio
import logging
import re
from typing import Dict, Tuple, Optional, List
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
    """DOM元素监控器（优化版）"""
    
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
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.logger.info("Chrome浏览器初始化成功")
            
        except Exception as e:
            self.logger.error(f"Chrome浏览器初始化失败: {e}")
            self.driver = None
    
    async def check_stock_by_elements(self, url: str) -> Tuple[Optional[bool], str, Dict]:
        """通过DOM元素检查库存状态（优化版）"""
        if not self.driver:
            return None, "浏览器未初始化", {}
        
        try:
            # 访问页面
            self.driver.get(url)
            await asyncio.sleep(3)
            
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
            
            # 使用服务商优化检查
            try:
                from vendor_optimization import VendorOptimizer
                if self.config.enable_vendor_optimization:
                    vendor_optimizer = VendorOptimizer()
                    vendor_result = vendor_optimizer.check_vendor_specific(self.driver, url)
                    if vendor_result['status'] is not None:
                        return vendor_result['status'], vendor_result['message'], check_info
            except ImportError:
                pass
            
            # 优化的检查流程
            # 1. 检查明确的缺货标识
            out_of_stock_result = self._check_explicit_out_of_stock()
            if out_of_stock_result['found']:
                return False, out_of_stock_result['message'], check_info
            
            # 2. 检查库存数量
            stock_quantity = self._check_stock_quantity()
            if stock_quantity['found']:
                if stock_quantity['quantity'] == 0:
                    return False, f"库存数量为0", check_info
                elif stock_quantity['quantity'] > 0:
                    return True, f"库存数量: {stock_quantity['quantity']}", check_info
            
            # 3. 检查购买按钮状态（改进版）
            button_analysis = self._analyze_purchase_buttons()
            
            # 4. 检查价格和配置选项
            product_info = self._analyze_product_page()
            
            # 5. 综合判断
            return self._make_dom_decision(
                out_of_stock_result,
                stock_quantity,
                button_analysis,
                product_info,
                check_info
            )
            
        except Exception as e:
            self.logger.error(f"DOM检查失败: {e}")
            return None, f"DOM检查失败: {str(e)}", {}
    
    def _check_explicit_out_of_stock(self) -> Dict:
        """检查明确的缺货标识（优化版）"""
        # 扩展的缺货标识列表
        out_of_stock_indicators = [
            # 英文
            {'text': 'out of stock', 'weight': 1.0, 'case_sensitive': False},
            {'text': 'sold out', 'weight': 1.0, 'case_sensitive': False},
            {'text': 'currently unavailable', 'weight': 0.95, 'case_sensitive': False},
            {'text': 'temporarily unavailable', 'weight': 0.95, 'case_sensitive': False},
            {'text': 'not available', 'weight': 0.9, 'case_sensitive': False},
            {'text': 'no longer available', 'weight': 1.0, 'case_sensitive': False},
            {'text': 'discontinued', 'weight': 1.0, 'case_sensitive': False},
            {'text': 'suspended', 'weight': 0.9, 'case_sensitive': False},
            {'text': 'coming soon', 'weight': 0.8, 'case_sensitive': False},
            {'text': 'pre-order', 'weight': 0.7, 'case_sensitive': False},
            {'text': 'waitlist', 'weight': 0.8, 'case_sensitive': False},
            {'text': 'notify me', 'weight': 0.8, 'case_sensitive': False},
            {'text': 'back in stock', 'weight': 0.8, 'case_sensitive': False},
            {'text': 'restock', 'weight': 0.7, 'case_sensitive': False},
            
            # 中文
            {'text': '缺货', 'weight': 1.0, 'case_sensitive': False},
            {'text': '售罄', 'weight': 1.0, 'case_sensitive': False},
            {'text': '暂时缺货', 'weight': 0.95, 'case_sensitive': False},
            {'text': '暂无库存', 'weight': 0.95, 'case_sensitive': False},
            {'text': '无货', 'weight': 1.0, 'case_sensitive': False},
            {'text': '断货', 'weight': 1.0, 'case_sensitive': False},
            {'text': '补货中', 'weight': 0.8, 'case_sensitive': False},
            {'text': '即将上架', 'weight': 0.8, 'case_sensitive': False},
            {'text': '敬请期待', 'weight': 0.8, 'case_sensitive': False},
            {'text': '到货通知', 'weight': 0.8, 'case_sensitive': False},
        ]
        
        # 重要元素选择器（这些位置的文本权重更高）
        important_selectors = [
            "h1", "h2", "h3", ".title", ".heading", ".product-title",
            ".availability", ".stock-status", ".product-status",
            ".alert", ".warning", ".error", ".notice"
        ]
        
        found_indicators = []
        
        for indicator in out_of_stock_indicators:
            try:
                # 构建XPath
                if indicator['case_sensitive']:
                    xpath = f"//*[contains(text(), '{indicator['text']}')]"
                else:
                    xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{indicator['text'].lower()}')]"
                
                elements = self.driver.find_elements(By.XPATH, xpath)
                
                for element in elements:
                    if not element.is_displayed():
                        continue
                    
                    # 检查是否在导航栏中
                    if self._is_in_navigation(element):
                        continue
                    
                    # 计算权重
                    weight = indicator['weight']
                    
                    # 如果在重要位置，增加权重
                    parent = element
                    for _ in range(3):  # 向上查找3层
                        try:
                            parent = parent.find_element(By.XPATH, "..")
                            for selector in important_selectors:
                                if parent.tag_name.lower() == selector.replace(".", ""):
                                    weight *= 1.2
                                    break
                                if selector.startswith(".") and selector[1:] in (parent.get_attribute("class") or ""):
                                    weight *= 1.2
                                    break
                        except:
                            break
                    
                    found_indicators.append({
                        'text': element.text,
                        'weight': weight,
                        'tag': element.tag_name
                    })
            except:
                continue
        
        if found_indicators:
            # 按权重排序
            found_indicators.sort(key=lambda x: x['weight'], reverse=True)
            best_indicator = found_indicators[0]
            
            if best_indicator['weight'] >= 0.9:
                return {
                    'found': True,
                    'message': f"发现明确缺货标识: {best_indicator['text'][:50]}",
                    'confidence': best_indicator['weight']
                }
        
        return {'found': False}
    
    def _check_stock_quantity(self) -> Dict:
        """检查库存数量显示"""
        quantity_patterns = [
            # 数字形式
            r'stock:\s*(\d+)',
            r'inventory:\s*(\d+)',
            r'available:\s*(\d+)',
            r'quantity:\s*(\d+)',
            r'(\d+)\s*in stock',
            r'(\d+)\s*available',
            
            # 中文
            r'库存[：:]\s*(\d+)',
            r'剩余[：:]\s*(\d+)',
            r'可用[：:]\s*(\d+)',
            r'数量[：:]\s*(\d+)',
        ]
        
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            for pattern in quantity_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    # 获取第一个匹配的数量
                    quantity = int(matches[0])
                    return {
                        'found': True,
                        'quantity': quantity
                    }
        except:
            pass
        
        return {'found': False}
    
    def _analyze_purchase_buttons(self) -> Dict:
        """分析购买按钮（改进版）"""
        # 购买相关按钮的关键词和权重
        button_keywords = [
            # 高权重购买词
            {'words': ['buy now', 'purchase now', 'order now'], 'weight': 1.0, 'type': 'buy'},
            {'words': ['add to cart', 'add to basket'], 'weight': 0.9, 'type': 'buy'},
            {'words': ['立即购买', '马上购买', '立即订购'], 'weight': 1.0, 'type': 'buy'},
            {'words': ['加入购物车', '添加到购物车'], 'weight': 0.9, 'type': 'buy'},
            
            # 中等权重
            {'words': ['configure', 'select options', 'choose plan'], 'weight': 0.7, 'type': 'config'},
            {'words': ['get started', 'start now'], 'weight': 0.6, 'type': 'action'},
            {'words': ['选择配置', '选择套餐'], 'weight': 0.7, 'type': 'config'},
            
            # 低权重或需要上下文
            {'words': ['continue', 'proceed'], 'weight': 0.4, 'type': 'action'},
            {'words': ['create'], 'weight': 0.3, 'type': 'action'},
            
            # 缺货相关按钮
            {'words': ['notify me', 'email when available'], 'weight': -1.0, 'type': 'notify'},
            {'words': ['join waitlist', 'waiting list'], 'weight': -1.0, 'type': 'notify'},
            {'words': ['到货通知', '缺货登记'], 'weight': -1.0, 'type': 'notify'},
        ]
        
        analysis = {
            'buy_buttons': [],
            'notify_buttons': [],
            'total_score': 0,
            'has_form': False,
            'has_price': False
        }
        
        # 检查所有按钮和链接
        elements = self.driver.find_elements(By.CSS_SELECTOR, "button, a.btn, a.button, input[type='submit'], input[type='button']")
        
        for element in elements:
            if not element.is_displayed():
                continue
            
            element_text = element.text.lower().strip()
            if not element_text:
                element_text = element.get_attribute('value') or ''
                element_text = element_text.lower().strip()
            
            # 跳过导航栏中的元素
            if self._is_in_navigation(element):
                continue
            
            for keyword_group in button_keywords:
                for keyword in keyword_group['words']:
                    if keyword in element_text:
                        button_info = {
                            'text': element_text,
                            'enabled': element.is_enabled(),
                            'weight': keyword_group['weight'],
                            'type': keyword_group['type']
                        }
                        
                        # 检查按钮周围的上下文
                        context_boost = self._analyze_button_context(element)
                        button_info['weight'] *= context_boost
                        
                        if keyword_group['type'] == 'notify':
                            analysis['notify_buttons'].append(button_info)
                        else:
                            analysis['buy_buttons'].append(button_info)
                        
                        if button_info['enabled']:
                            analysis['total_score'] += button_info['weight']
                        
                        break
        
        # 检查是否有表单
        forms = self.driver.find_elements(By.CSS_SELECTOR, "form.product-form, form.order-form, form[action*='cart'], form[action*='order']")
        analysis['has_form'] = len(forms) > 0
        
        # 检查是否有价格
        analysis['has_price'] = self._check_for_price()
        
        return analysis
    
    def _analyze_button_context(self, element) -> float:
        """分析按钮的上下文，返回权重倍数"""
        try:
            # 获取按钮周围的文本
            parent = element.find_element(By.XPATH, "..")
            context_text = parent.text.lower()
            
            # 正面上下文（表明是购买相关）
            positive_context = [
                'price', 'cost', '价格', '费用',
                'plan', 'package', '套餐', '方案',
                'monthly', 'yearly', '月付', '年付',
                'specifications', 'features', '配置', '规格',
                'checkout', 'payment', '结账', '支付'
            ]
            
            # 负面上下文（表明不是购买按钮）
            negative_context = [
                'login', 'register', 'account', 'sign',
                '登录', '注册', '账户',
                'learn more', 'read more', '了解更多',
                'documentation', 'support', '文档', '支持'
            ]
            
            positive_count = sum(1 for word in positive_context if word in context_text)
            negative_count = sum(1 for word in negative_context if word in context_text)
            
            if negative_count > positive_count:
                return 0.5  # 降低权重
            elif positive_count > 0:
                return 1.0 + (positive_count * 0.1)  # 提升权重
            
            return 1.0
            
        except:
            return 1.0
    
    def _check_for_price(self) -> bool:
        """检查页面是否包含价格信息"""
        price_patterns = [
            r'\$\d+',  # $99
            r'\$\d+\.\d{2}',  # $99.99
            r'¥\d+',  # ¥99
            r'€\d+',  # €99
            r'\d+\s*/\s*mo',  # 99/mo
            r'\d+\s*/\s*month',  # 99/month
            r'\d+\s*/\s*year',  # 99/year
            r'USD\s*\d+',  # USD 99
            r'CNY\s*\d+',  # CNY 99
        ]
        
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            for pattern in price_patterns:
                if re.search(pattern, page_text, re.IGNORECASE):
                    return True
        except:
            pass
        
        return False
    
    def _analyze_product_page(self) -> Dict:
        """分析是否是产品详情页"""
        indicators = {
            'has_product_info': False,
            'has_specifications': False,
            'has_configuration_options': False,
            'page_type': 'unknown'
        }
        
        try:
            # 检查产品信息
            product_selectors = [
                ".product-info", ".product-details", ".product-description",
                ".specifications", ".features", ".pricing-table",
                "#product", "#product-details"
            ]
            
            for selector in product_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(e.is_displayed() for e in elements):
                    indicators['has_product_info'] = True
                    break
            
            # 检查配置选项
            config_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                "select.product-option, input[type='radio'].product-option, .config-option, .plan-selector")
            if config_elements:
                indicators['has_configuration_options'] = True
            
            # 判断页面类型
            current_url = self.driver.current_url.lower()
            if any(keyword in current_url for keyword in ['product', 'plan', 'vps', 'server', 'hosting']):
                indicators['page_type'] = 'product'
            elif any(keyword in current_url for keyword in ['cart', 'checkout', 'order']):
                indicators['page_type'] = 'checkout'
            
        except:
            pass
        
        return indicators
    
    def _make_dom_decision(self, out_of_stock, stock_quantity, button_analysis, product_info, check_info) -> Tuple[Optional[bool], str, Dict]:
        """基于所有信息做出最终判断（优化版）"""
        confidence_score = 0
        evidence = []
        
        # 1. 如果有明确的缺货标识，直接判断缺货
        if out_of_stock['found']:
            confidence_score = out_of_stock.get('confidence', 0.9)
            evidence.append(f"明确缺货标识 (置信度: {confidence_score:.2f})")
            return False, f"DOM检测到缺货: {'; '.join(evidence)}", check_info
        
        # 2. 如果有库存数量信息
        if stock_quantity['found']:
            if stock_quantity['quantity'] == 0:
                confidence_score = 0.95
                evidence.append(f"库存数量为0")
                return False, f"DOM检测到缺货: {'; '.join(evidence)}", check_info
            else:
                confidence_score = 0.9
                evidence.append(f"库存数量: {stock_quantity['quantity']}")
                return True, f"DOM检测到有货: {'; '.join(evidence)}", check_info
        
        # 3. 如果有通知类按钮，可能缺货
        if button_analysis['notify_buttons']:
            confidence_score = 0.8
            evidence.append(f"发现到货通知按钮")
            return False, f"DOM检测到缺货: {'; '.join(evidence)}", check_info
        
        # 4. 基于购买按钮和页面信息的综合判断
        if button_analysis['buy_buttons']:
            enabled_buttons = [b for b in button_analysis['buy_buttons'] if b['enabled']]
            
            if enabled_buttons:
                # 有可用的购买按钮
                max_weight = max(b['weight'] for b in enabled_buttons)
                
                # 如果是高权重购买按钮
                if max_weight >= 0.8:
                    if button_analysis['has_price'] or product_info['has_product_info']:
                        confidence_score = 0.85
                        evidence.append(f"高权重购买按钮 + 产品信息")
                        return True, f"DOM检测到有货: {'; '.join(evidence)}", check_info
                
                # 中等权重按钮需要更多证据
                elif max_weight >= 0.5:
                    if button_analysis['has_price'] and button_analysis['has_form']:
                        confidence_score = 0.75
                        evidence.append(f"中等权重按钮 + 价格 + 表单")
                        return True, f"DOM检测到有货: {'; '.join(evidence)}", check_info
                    else:
                        evidence.append(f"中等权重按钮但缺少其他证据")
                        return None, f"DOM无法确定: {'; '.join(evidence)}", check_info
                
                # 低权重按钮
                else:
                    evidence.append(f"仅发现低权重按钮")
                    return None, f"DOM无法确定: {'; '.join(evidence)}", check_info
            
            else:
                # 所有按钮都被禁用
                confidence_score = 0.7
                evidence.append(f"所有购买按钮被禁用")
                return False, f"DOM检测到缺货: {'; '.join(evidence)}", check_info
        
        # 5. 如果是产品页但没有任何购买相关元素
        if product_info['has_product_info'] and not button_analysis['buy_buttons']:
            confidence_score = 0.6
            evidence.append(f"产品页面但无购买选项")
            return False, f"DOM检测到可能缺货: {'; '.join(evidence)}", check_info
        
        # 无法确定
        evidence.append("缺少足够的判断依据")
        return None, f"DOM无法确定: {'; '.join(evidence)}", check_info
    
    def _is_in_navigation(self, element) -> bool:
        """检查元素是否在导航区域"""
        try:
            # 向上遍历检查
            current = element
            for _ in range(5):
                # 检查常见的导航标签和类名
                tag = current.tag_name.lower()
                classes = current.get_attribute('class') or ''
                element_id = current.get_attribute('id') or ''
                role = current.get_attribute('role') or ''
                
                nav_indicators = [
                    tag in ['nav', 'header', 'footer'],
                    'nav' in classes.lower(),
                    'menu' in classes.lower(),
                    'header' in classes.lower(),
                    'footer' in classes.lower(),
                    'sidebar' in classes.lower(),
                    role == 'navigation',
                    'nav' in element_id.lower(),
                    'menu' in element_id.lower()
                ]
                
                if any(nav_indicators):
                    return True
                
                # 向上遍历
                current = current.find_element(By.XPATH, "..")
        except:
            pass
        
        return False
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
