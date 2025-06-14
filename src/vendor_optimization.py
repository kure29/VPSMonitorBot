#!/usr/bin/env python3
"""
供应商特定优化模块
VPS监控系统 v3.1
"""

import logging
from typing import Dict, Optional
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException


class VendorOptimizer:
    """供应商特定优化器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 供应商特定的检查规则
        self.vendor_rules = {
            'dmit.io': self._check_dmit,
            'racknerd.com': self._check_racknerd,
            'bandwagonhost.com': self._check_bandwagon,
            'virmach.com': self._check_virmach,
            'hostdare.com': self._check_hostdare,
            'hosthatch.com': self._check_hosthatch,
            'greencloudvps.com': self._check_greencloud
        }
    
    def check_vendor_specific(self, driver, url: str) -> Dict:
        """执行供应商特定检查"""
        # 从URL中提取域名
        domain = self._extract_domain(url)
        
        # 查找对应的检查函数
        for vendor_domain, check_func in self.vendor_rules.items():
            if vendor_domain in domain:
                try:
                    result = check_func(driver)
                    if result['status'] is not None:
                        self.logger.info(f"供应商优化检查 ({vendor_domain}): {result['message']}")
                    return result
                except Exception as e:
                    self.logger.error(f"供应商检查失败 ({vendor_domain}): {e}")
                    return {'status': None, 'message': f'供应商检查失败: {str(e)}'}
        
        # 没有找到特定规则
        return {'status': None, 'message': '无供应商特定规则'}
    
    def _extract_domain(self, url: str) -> str:
        """从URL提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return url.lower()
    
    def _check_dmit(self, driver) -> Dict:
        """DMIT特定检查"""
        try:
            # 检查页面标题
            page_title = driver.title.lower()
            
            # DMIT的缺货页面特征
            if 'out of stock' in page_title:
                return {
                    'status': False,
                    'message': 'DMIT页面标题显示缺货'
                }
            
            # 检查主要内容区域
            try:
                # 查找主要内容容器
                main_content_selectors = [
                    ".main-content", "#main", ".content", ".page-content",
                    "main", "article", ".container"
                ]
                
                for selector in main_content_selectors:
                    try:
                        if selector.startswith('.') or selector.startswith('#'):
                            content_element = driver.find_element(By.CSS_SELECTOR, selector)
                        else:
                            content_element = driver.find_element(By.TAG_NAME, selector)
                        
                        content_text = content_element.text.lower()
                        
                        # 检查是否包含明确的缺货信息
                        if ('out of stock' in content_text and 
                            'currently out of stock' in content_text):
                            return {
                                'status': False,
                                'message': 'DMIT内容区域显示缺货'
                            }
                        
                        # 检查是否是产品配置页面
                        if all(keyword in content_text for keyword in ['configure', 'price', 'order']):
                            # 检查是否有可选择的配置选项
                            config_selectors = [
                                "select", "input[type='radio']", ".config-option",
                                ".product-option", "[name='configoption']"
                            ]
                            
                            for config_sel in config_selectors:
                                config_elements = driver.find_elements(By.CSS_SELECTOR, config_sel)
                                if config_elements and any(el.is_enabled() for el in config_elements):
                                    return {
                                        'status': True,
                                        'message': 'DMIT产品配置页面，有可选配置项'
                                    }
                        
                        break  # 找到内容区域就停止
                    except:
                        continue
            except Exception as e:
                self.logger.debug(f"DMIT内容检查异常: {e}")
            
            # 检查购物车页面特定元素
            if 'cart.php' in driver.current_url:
                # 检查是否有"Continue"或"Create"按钮但同时有缺货提示
                out_of_stock_messages = driver.find_elements(
                    By.XPATH, 
                    "//*[contains(text(), 'out of stock') or contains(text(), 'currently out of stock')]"
                )
                
                if out_of_stock_messages and any(msg.is_displayed() for msg in out_of_stock_messages):
                    return {
                        'status': False,
                        'message': 'DMIT购物车页面显示缺货信息'
                    }
                
                # 检查是否有产品配置表单
                form_elements = driver.find_elements(By.CSS_SELECTOR, "form#frmConfigureProduct")
                if form_elements:
                    return {
                        'status': True,
                        'message': 'DMIT购物车有产品配置表单'
                    }
            
            return {'status': None, 'message': 'DMIT检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'DMIT检查异常: {str(e)}'}
    
    def _check_racknerd(self, driver) -> Dict:
        """RackNerd特定检查"""
        try:
            # RackNerd的缺货通常显示"Sold Out"按钮
            sold_out_buttons = driver.find_elements(
                By.XPATH, 
                "//button[contains(text(), 'Sold Out')] | //a[contains(text(), 'Sold Out')]"
            )
            
            if sold_out_buttons and any(btn.is_displayed() for btn in sold_out_buttons):
                return {
                    'status': False,
                    'message': 'RackNerd显示Sold Out按钮'
                }
            
            # 检查Order Now按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//a[contains(text(), 'Order Now')] | //button[contains(text(), 'Order Now')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {
                    'status': True,
                    'message': 'RackNerd有可用的Order Now按钮'
                }
            
            return {'status': None, 'message': 'RackNerd检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'RackNerd检查异常: {str(e)}'}
    
    def _check_bandwagon(self, driver) -> Dict:
        """搬瓦工特定检查"""
        try:
            # 搬瓦工缺货时会显示"Out of Stock"
            out_of_stock = driver.find_elements(
                By.XPATH,
                "//*[contains(@class, 'out-of-stock')] | //*[contains(text(), 'Out of Stock')]"
            )
            
            if out_of_stock and any(el.is_displayed() for el in out_of_stock):
                return {
                    'status': False,
                    'message': '搬瓦工显示Out of Stock'
                }
            
            # 检查"Order Now"链接
            order_links = driver.find_elements(
                By.XPATH,
                "//a[contains(@href, 'order')] | //a[contains(text(), 'Order')]"
            )
            
            if order_links and any(link.is_displayed() and link.is_enabled() for link in order_links):
                return {
                    'status': True,
                    'message': '搬瓦工有可用的订购链接'
                }
            
            return {'status': None, 'message': '搬瓦工检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'搬瓦工检查异常: {str(e)}'}
    
    def _check_virmach(self, driver) -> Dict:
        """VirMach特定检查"""
        try:
            # VirMach缺货时按钮会变成"Unavailable"
            unavailable = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Unavailable')] | //a[contains(text(), 'Unavailable')]"
            )
            
            if unavailable and any(el.is_displayed() for el in unavailable):
                return {
                    'status': False,
                    'message': 'VirMach显示Unavailable'
                }
            
            # 检查"Order"按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(text(), 'Order')] | //a[contains(@class, 'order')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {
                    'status': True,
                    'message': 'VirMach有可用的Order按钮'
                }
            
            return {'status': None, 'message': 'VirMach检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'VirMach检查异常: {str(e)}'}
    
    def _check_hostdare(self, driver) -> Dict:
        """HostDare特定检查"""
        try:
            # HostDare使用WHMCS，检查产品状态
            unavailable_text = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), '暂时缺货')] | //*[contains(text(), 'Currently Unavailable')]"
            )
            
            if unavailable_text and any(el.is_displayed() for el in unavailable_text):
                return {
                    'status': False,
                    'message': 'HostDare显示暂时缺货'
                }
            
            # 检查"立即订购"按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//a[contains(text(), '立即订购')] | //a[contains(text(), 'Order Now')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {
                    'status': True,
                    'message': 'HostDare有可用的订购按钮'
                }
            
            return {'status': None, 'message': 'HostDare检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'HostDare检查异常: {str(e)}'}
    
    def _check_hosthatch(self, driver) -> Dict:
        """HostHatch特定检查"""
        try:
            # HostHatch缺货时显示"Out of Stock"标签
            stock_badges = driver.find_elements(
                By.XPATH,
                "//*[contains(@class, 'badge')] | //*[contains(@class, 'label')]"
            )
            
            for badge in stock_badges:
                if badge.is_displayed() and 'out of stock' in badge.text.lower():
                    return {
                        'status': False,
                        'message': 'HostHatch显示Out of Stock标签'
                    }
            
            # 检查购买按钮
            buy_buttons = driver.find_elements(
                By.XPATH,
                "//a[contains(@href, 'billing')] | //button[contains(text(), 'Order')]"
            )
            
            if buy_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in buy_buttons):
                return {
                    'status': True,
                    'message': 'HostHatch有可用的购买按钮'
                }
            
            return {'status': None, 'message': 'HostHatch检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'HostHatch检查异常: {str(e)}'}
    
    def _check_greencloud(self, driver) -> Dict:
        """GreenCloudVPS特定检查"""
        try:
            # GreenCloud使用WHMCS，缺货显示"Out of Stock"
            out_of_stock = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'Out of Stock')] | //*[contains(@class, 'unavailable')]"
            )
            
            if out_of_stock and any(el.is_displayed() for el in out_of_stock):
                return {
                    'status': False,
                    'message': 'GreenCloudVPS显示Out of Stock'
                }
            
            # 检查"Order Now"按钮
            order_buttons = driver.find_elements(
                By.XPATH,
                "//a[contains(text(), 'Order Now')] | //button[contains(text(), 'Configure')]"
            )
            
            if order_buttons and any(btn.is_displayed() and btn.is_enabled() for btn in order_buttons):
                return {
                    'status': True,
                    'message': 'GreenCloudVPS有可用的订购按钮'
                }
            
            return {'status': None, 'message': 'GreenCloudVPS检查无法确定状态'}
            
        except Exception as e:
            return {'status': None, 'message': f'GreenCloudVPS检查异常: {str(e)}'}
