#!/usr/bin/env python3
"""
供应商特定优化模块（增强版）
VPS监控系统 v3.1
支持更多供应商和更准确的检测
"""

import logging
import re
from typing import Dict, Optional, List
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


class VendorOptimizer:
    """供应商特定优化器（增强版）"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 扩展的供应商特定检查规则
        self.vendor_rules = {
            # 原有供应商
            'dmit.io': self._check_dmit,
            'racknerd.com': self._check_racknerd,
            'bandwagonhost.com': self._check_bandwagon,
            'virmach.com': self._check_virmach,
            'hostdare.com': self._check_hostdare,
            'hosthatch.com': self._check_hosthatch,
            'greencloudvps.com': self._check_greencloud,
            
            # 新增供应商
            'vultr.com': self._check_vultr,
            'digitalocean.com': self._check_digitalocean,
            'linode.com': self._check_linode,
            'ovh.com': self._check_ovh,
            'ovhcloud.com': self._check_ovh,
            'hetzner.com': self._check_hetzner,
            'hetzner.de': self._check_hetzner,
            'contabo.com': self._check_contabo,
            'hostwinds.com': self._check_hostwinds,
            'buyvm.net': self._check_buyvm,
            'nexusbytes.com': self._check_nexusbytes,
            'spartanhost.net': self._check_spartanhost,
            'cloudcone.com': self._check_cloudcone,
            'hosteons.com': self._check_hosteons,
            'alpharacks.com': self._check_alpharacks,
            'webhostingtalk.com': self._check_wht,  # WHT offers
        }
        
        # 通用的WHMCS检测规则
        self.whmcs_rules = {
            'out_of_stock_texts': [
                'out of stock', 'sold out', 'unavailable', 
                'currently unavailable', 'not available',
                '缺货', '售罄', '暂时缺货', '无货'
            ],
            'in_stock_texts': [
                'order now', 'add to cart', 'configure',
                'order', 'buy now', 'purchase',
                '立即订购', '加入购物车', '立即购买'
            ],
            'notification_texts': [
                'notify', 'email me', 'stock alert',
                'waiting list', 'waitlist',
                '到货通知', '缺货提醒'
            ]
        }
    
    def check_vendor_specific(self, driver, url: str) -> Dict:
        """执行供应商特定检查（增强版）"""
        domain = self._extract_domain(url)
        
        # 查找对应的检查函数
        for vendor_domain, check_func in self.vendor_rules.items():
            if vendor_domain in domain:
                try:
                    self.logger.info(f"执行供应商特定检查: {vendor_domain}")
                    result = check_func(driver)
                    
                    # 如果供应商检查没有明确结果，尝试通用WHMCS检查
                    if result['status'] is None and self._is_whmcs_site(driver):
                        whmcs_result = self._check_whmcs_generic(driver)
                        if whmcs_result['status'] is not None:
                            return whmcs_result
                    
                    return result
                except Exception as e:
                    self.logger.error(f"供应商检查失败 ({vendor_domain}): {e}")
                    # 失败时尝试通用检查
                    return self._check_generic(driver)
        
        # 没有找到特定规则，使用通用检查
        return self._check_generic(driver)
    
    def _extract_domain(self, url: str) -> str:
        """从URL提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return url.lower()
    
    def _is_whmcs_site(self, driver) -> bool:
        """检测是否是WHMCS网站"""
        try:
            # WHMCS特征
            whmcs_indicators = [
                "//link[contains(@href, 'whmcs')]",
                "//script[contains(@src, 'whmcs')]",
                "//meta[@name='generator'][contains(@content, 'WHMCS')]",
                "//*[contains(@class, 'whmcs')]",
                "//form[@action='cart.php']"
            ]
            
            for indicator in whmcs_indicators:
                elements = driver.find_elements(By.XPATH, indicator)
                if elements:
                    return True
            
            # 检查URL
            current_url = driver.current_url.lower()
            if any(path in current_url for path in ['cart.php', 'whmcs', 'clientarea']):
                return True
                
        except:
            pass
        
        return False
    
    def _check_generic(self, driver) -> Dict:
        """通用检查方法"""
        try:
            page_source = driver.page_source.lower()
            
            # 检查明确的缺货标识
            strong_out_indicators = [
                'out of stock', 'sold out', 'currently unavailable',
                '缺货', '售罄', '暂时缺货'
            ]
            
            for indicator in strong_out_indicators:
                if indicator in page_source:
                    # 验证不是在导航栏或页脚
                    elements = driver.find_elements(
                        By.XPATH, 
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{indicator}')]"
                    )
                    for element in elements:
                        if element.is_displayed() and not self._is_in_nav_or_footer(element):
                            return {
                                'status': False,
                                'message': f'通用检查发现缺货标识: {indicator}'
                            }
            
            # 检查购买按钮
            buy_button_found = self._check_buy_buttons_generic(driver)
            if buy_button_found:
                return {
                    'status': True,
                    'message': '通用检查发现可用的购买按钮'
                }
            
            return {'status': None, 'message': '通用检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'通用检查异常: {str(e)}'}
    
    def _check_buy_buttons_generic(self, driver) -> bool:
        """通用的购买按钮检查"""
        try:
            button_texts = [
                'order now', 'buy now', 'add to cart', 'purchase',
                'get started', 'configure', 'choose plan',
                '立即订购', '立即购买', '加入购物车'
            ]
            
            for text in button_texts:
                xpath = f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')] | //a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return True
                        
        except:
            pass
        
        return False
    
    def _is_in_nav_or_footer(self, element) -> bool:
        """检查元素是否在导航栏或页脚"""
        try:
            current = element
            for _ in range(5):
                tag = current.tag_name.lower()
                classes = (current.get_attribute('class') or '').lower()
                element_id = (current.get_attribute('id') or '').lower()
                
                if (tag in ['nav', 'header', 'footer'] or
                    any(x in classes for x in ['nav', 'header', 'footer', 'menu']) or
                    any(x in element_id for x in ['nav', 'header', 'footer', 'menu'])):
                    return True
                
                current = current.find_element(By.XPATH, "..")
        except:
            pass
        
        return False
    
    def _check_whmcs_generic(self, driver) -> Dict:
        """通用WHMCS检查"""
        try:
            # 检查产品状态
            status_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".product-status, .availability, .stock-info, .order-button"
            )
            
            for element in status_elements:
                if element.is_displayed():
                    text = element.text.lower()
                    
                    # 检查缺货
                    for out_text in self.whmcs_rules['out_of_stock_texts']:
                        if out_text in text:
                            return {
                                'status': False,
                                'message': f'WHMCS检测到缺货: {text}'
                            }
                    
                    # 检查通知
                    for notify_text in self.whmcs_rules['notification_texts']:
                        if notify_text in text:
                            return {
                                'status': False,
                                'message': f'WHMCS检测到通知表单: {text}'
                            }
            
            # 检查订购按钮
            for in_text in self.whmcs_rules['in_stock_texts']:
                elements = driver.find_elements(
                    By.XPATH,
                    f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{in_text}')] | //button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{in_text}')]"
                )
                
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return {
                            'status': True,
                            'message': 'WHMCS检测到可用的订购按钮'
                        }
            
            return {'status': None, 'message': 'WHMCS检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'WHMCS检查异常: {str(e)}'}
    
    # ===== 各供应商的具体检查方法 =====
    
    def _check_dmit(self, driver) -> Dict:
        """DMIT特定检查（优化版）"""
        try:
            # 检查页面标题
            if 'out of stock' in driver.title.lower():
                return {'status': False, 'message': 'DMIT标题显示缺货'}
            
            # 检查主要内容
            try:
                # DMIT特定的选择器
                content_selectors = [
                    ".product-content", ".main-content", 
                    "#content", "main", ".container"
                ]
                
                for selector in content_selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            text = element.text.lower()
                            
                            # 强缺货标识
                            if 'currently out of stock' in text and 'out of stock' in text:
                                return {'status': False, 'message': 'DMIT内容显示缺货'}
                            
                            # 检查是否有配置选项
                            if 'configure' in text and any(x in text for x in ['price', 'plan', 'order']):
                                config_elements = driver.find_elements(
                                    By.CSS_SELECTOR,
                                    "select, input[type='radio'], .config-option"
                                )
                                if config_elements and any(e.is_enabled() for e in config_elements):
                                    return {'status': True, 'message': 'DMIT有可配置选项'}
            except:
                pass
            
            # 检查购物车页面
            if 'cart.php' in driver.current_url:
                # 检查缺货消息
                out_messages = driver.find_elements(
                    By.XPATH,
                    "//*[contains(text(), 'out of stock') or contains(text(), 'currently out of stock')]"
                )
                
                if out_messages and any(msg.is_displayed() for msg in out_messages):
                    return {'status': False, 'message': 'DMIT购物车显示缺货'}
                
                # 检查产品配置表单
                form = driver.find_elements(By.ID, "frmConfigureProduct")
                if form:
                    return {'status': True, 'message': 'DMIT有产品配置表单'}
            
            # 检查Create按钮的上下文
            create_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Create')] | //a[contains(text(), 'Create')]"
            )
            
            for button in create_buttons:
                if button.is_displayed():
                    # 检查是否在产品配置区域
                    parent_text = ""
                    try:
                        parent = button.find_element(By.XPATH, "../..")
                        parent_text = parent.text.lower()
                    except:
                        pass
                    
                    if any(keyword in parent_text for keyword in ['configure', 'price', 'plan', 'server']):
                        if button.is_enabled():
                            return {'status': True, 'message': 'DMIT有产品配置区的Create按钮'}
            
            return {'status': None, 'message': 'DMIT检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'DMIT检查异常: {str(e)}'}
    
    def _check_vultr(self, driver) -> Dict:
        """Vultr特定检查"""
        try:
            # Vultr通常不会直接显示out of stock，而是不显示某些选项
            # 检查部署按钮
            deploy_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Deploy')] | //a[contains(text(), 'Deploy')]"
            )
            
            if deploy_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in deploy_buttons):
                return {'status': True, 'message': 'Vultr有可用的Deploy按钮'}
            
            # 检查产品选择
            product_cards = driver.find_elements(
                By.CSS_SELECTOR,
                ".product-card:not(.disabled), .instance-type:not(.unavailable)"
            )
            
            if product_cards:
                return {'status': True, 'message': 'Vultr有可选择的产品'}
            
            # 检查错误消息
            error_messages = driver.find_elements(
                By.CSS_SELECTOR,
                ".error-message, .alert-error, .unavailable-message"
            )
            
            for msg in error_messages:
                if msg.is_displayed() and 'unavailable' in msg.text.lower():
                    return {'status': False, 'message': 'Vultr显示不可用消息'}
            
            return {'status': None, 'message': 'Vultr检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'Vultr检查异常: {str(e)}'}
    
    def _check_digitalocean(self, driver) -> Dict:
        """DigitalOcean特定检查"""
        try:
            # DO通常总是有货，但某些地区可能缺货
            create_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Create')] | //button[contains(text(), 'Get Started')]"
            )
            
            if create_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in create_buttons):
                return {'status': True, 'message': 'DigitalOcean有可用的创建按钮'}
            
            # 检查地区选择
            region_unavailable = driver.find_elements(
                By.CSS_SELECTOR,
                ".region-unavailable, .datacenter-unavailable"
            )
            
            if region_unavailable:
                # 检查是否所有地区都不可用
                available_regions = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".region-available, .datacenter:not(.unavailable)"
                )
                if not available_regions:
                    return {'status': False, 'message': 'DigitalOcean所有地区都不可用'}
            
            return {'status': None, 'message': 'DigitalOcean检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'DigitalOcean检查异常: {str(e)}'}
    
    def _check_linode(self, driver) -> Dict:
        """Linode特定检查"""
        try:
            # Linode的创建按钮
            create_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Create')] | //button[contains(text(), 'Add a Linode')]"
            )
            
            if create_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in create_buttons):
                return {'status': True, 'message': 'Linode有可用的创建按钮'}
            
            # 检查计划选择
            plan_cards = driver.find_elements(
                By.CSS_SELECTOR,
                ".plan-card:not(.disabled), .linode-plan:not(.unavailable)"
            )
            
            if plan_cards:
                return {'status': True, 'message': 'Linode有可选择的计划'}
            
            return {'status': None, 'message': 'Linode检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'Linode检查异常: {str(e)}'}
    
    def _check_ovh(self, driver) -> Dict:
        """OVH/OVHCloud特定检查"""
        try:
            # OVH的订购按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Order')] | //a[contains(text(), 'Order')] | //button[contains(text(), 'Commander')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {'status': True, 'message': 'OVH有可用的订购按钮'}
            
            # 检查缺货标识
            out_of_stock = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'Out of stock')] | //*[contains(text(), 'Rupture de stock')]"
            )
            
            if out_of_stock and any(el.is_displayed() for el in out_of_stock):
                return {'status': False, 'message': 'OVH显示缺货'}
            
            return {'status': None, 'message': 'OVH检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'OVH检查异常: {str(e)}'}
    
    def _check_hetzner(self, driver) -> Dict:
        """Hetzner特定检查"""
        try:
            # Hetzner的订购按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Order')] | //a[contains(text(), 'Order')] | //button[contains(text(), 'Bestellen')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {'status': True, 'message': 'Hetzner有可用的订购按钮'}
            
            # 检查服务器拍卖（Server Auction）
            if 'serverborse' in driver.current_url or 'server-auction' in driver.current_url:
                available_servers = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".server-available, tr.available"
                )
                if available_servers:
                    return {'status': True, 'message': 'Hetzner拍卖有可用服务器'}
            
            # 检查缺货
            unavailable = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'nicht verfügbar')] | //*[contains(text(), 'not available')]"
            )
            
            if unavailable and any(el.is_displayed() for el in unavailable):
                return {'status': False, 'message': 'Hetzner显示不可用'}
            
            return {'status': None, 'message': 'Hetzner检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'Hetzner检查异常: {str(e)}'}
    
    def _check_contabo(self, driver) -> Dict:
        """Contabo特定检查"""
        try:
            # Contabo的订购按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Order')] | //a[contains(text(), 'Configure & Order')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {'status': True, 'message': 'Contabo有可用的订购按钮'}
            
            # 检查产品配置
            config_section = driver.find_elements(
                By.CSS_SELECTOR,
                ".product-configurator, .config-section"
            )
            
            if config_section and any(el.is_displayed() for el in config_section):
                return {'status': True, 'message': 'Contabo有产品配置选项'}
            
            return {'status': None, 'message': 'Contabo检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'Contabo检查异常: {str(e)}'}
    
    def _check_hostwinds(self, driver) -> Dict:
        """HostWinds特定检查"""
        try:
            # 标准WHMCS检查
            return self._check_whmcs_generic(driver)
            
        except Exception as e:
            return {'status': None, 'message': f'HostWinds检查异常: {str(e)}'}
    
    def _check_buyvm(self, driver) -> Dict:
        """BuyVM特定检查"""
        try:
            # BuyVM的库存检查
            stock_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".stock-status, .availability"
            )
            
            for element in stock_elements:
                if element.is_displayed():
                    text = element.text.lower()
                    if 'out of stock' in text or 'sold out' in text:
                        return {'status': False, 'message': 'BuyVM显示缺货'}
                    elif 'in stock' in text or 'available' in text:
                        return {'status': True, 'message': 'BuyVM显示有货'}
            
            # 检查订购链接
            order_links = driver.find_elements(
                By.XPATH,
                "//a[contains(@href, 'order')] | //a[contains(text(), 'Order')]"
            )
            
            if order_links and any(link.is_displayed() and link.is_enabled() for link in order_links):
                return {'status': True, 'message': 'BuyVM有可用的订购链接'}
            
            return {'status': None, 'message': 'BuyVM检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'BuyVM检查异常: {str(e)}'}
    
    def _check_nexusbytes(self, driver) -> Dict:
        """NexusBytes特定检查"""
        try:
            # 检查WHMCS风格的库存状态
            return self._check_whmcs_generic(driver)
            
        except Exception as e:
            return {'status': None, 'message': f'NexusBytes检查异常: {str(e)}'}
    
    def _check_spartanhost(self, driver) -> Dict:
        """SpartanHost特定检查"""
        try:
            # WHMCS系统
            result = self._check_whmcs_generic(driver)
            if result['status'] is not None:
                return result
            
            # 特定的库存检查
            stock_badges = driver.find_elements(
                By.CSS_SELECTOR,
                ".badge, .label, .stock-indicator"
            )
            
            for badge in stock_badges:
                if badge.is_displayed():
                    text = badge.text.lower()
                    if 'out of stock' in text:
                        return {'status': False, 'message': 'SpartanHost显示缺货标签'}
                    elif 'in stock' in text:
                        return {'status': True, 'message': 'SpartanHost显示有货标签'}
            
            return {'status': None, 'message': 'SpartanHost检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'SpartanHost检查异常: {str(e)}'}
    
    def _check_cloudcone(self, driver) -> Dict:
        """CloudCone特定检查"""
        try:
            # CloudCone特定的购买按钮
            buy_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Deploy')] | //a[contains(text(), 'Order Now')]"
            )
            
            if buy_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in buy_buttons):
                return {'status': True, 'message': 'CloudCone有可用的购买按钮'}
            
            # 检查缺货消息
            out_stock_msg = driver.find_elements(
                By.XPATH,
                "//*[contains(@class, 'alert')]//*[contains(text(), 'out of stock')]"
            )
            
            if out_stock_msg and any(msg.is_displayed() for msg in out_stock_msg):
                return {'status': False, 'message': 'CloudCone显示缺货警告'}
            
            return {'status': None, 'message': 'CloudCone检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'CloudCone检查异常: {str(e)}'}
    
    def _check_hosteons(self, driver) -> Dict:
        """HostEONS特定检查"""
        try:
            # WHMCS系统
            return self._check_whmcs_generic(driver)
            
        except Exception as e:
            return {'status': None, 'message': f'HostEONS检查异常: {str(e)}'}
    
    def _check_alpharacks(self, driver) -> Dict:
        """AlphaRacks特定检查"""
        try:
            # WHMCS系统，但有特定的缺货提示
            whmcs_result = self._check_whmcs_generic(driver)
            if whmcs_result['status'] is not None:
                return whmcs_result
            
            # AlphaRacks特定的缺货消息
            specific_messages = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'This product is currently unavailable')]"
            )
            
            if specific_messages and any(msg.is_displayed() for msg in specific_messages):
                return {'status': False, 'message': 'AlphaRacks显示产品不可用'}
            
            return {'status': None, 'message': 'AlphaRacks检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'AlphaRacks检查异常: {str(e)}'}
    
    def _check_wht(self, driver) -> Dict:
        """WebHostingTalk offers特定检查"""
        try:
            # WHT论坛的特价信息通常在帖子中
            post_content = driver.find_elements(
                By.CSS_SELECTOR,
                ".post-content, .message-content, article"
            )
            
            if post_content:
                text = post_content[0].text.lower() if post_content[0].is_displayed() else ""
                
                # 检查是否明确说缺货
                if any(phrase in text for phrase in ['sold out', 'out of stock', 'no longer available']):
                    return {'status': False, 'message': 'WHT帖子显示已售罄'}
                
                # 检查是否有订购链接
                order_links = post_content[0].find_elements(By.TAG_NAME, "a")
                for link in order_links:
                    link_text = link.text.lower()
                    if any(word in link_text for word in ['order', 'buy', 'purchase']):
                        if link.is_enabled():
                            return {'status': True, 'message': 'WHT帖子有订购链接'}
            
            return {'status': None, 'message': 'WHT检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'WHT检查异常: {str(e)}'}
