#!/usr/bin/env python3
"""
VPS监控系统 - 服务商优化模块
作者: kure29
网站: https://kure29.com

专门针对各大VPS服务商的优化检测模块
支持的服务商：DMIT、RackNerd、BandwagonHost、CloudCone等
"""

import re
import logging
from typing import Dict, Optional, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class VendorInfo:
    """服务商信息"""
    
    # 支持的服务商信息
    VENDORS = {
        'dmit': {
            'name': 'DMIT',
            'full_name': 'DMIT Network',
            'website': 'https://www.dmit.io',
            'description': '高端网络服务提供商，专注亚洲优化线路',
            'keywords': ['dmit', 'dmit.io'],
            'out_of_stock_patterns': [
                '缺货中', '刷新库存', 'refresh stock', '暂无库存',
                'out of stock', 'sold out'
            ],
            'in_stock_patterns': [
                '立即订购', '配置选项', 'order now', 'configure',
                'add to cart', 'buy now'
            ]
        },
        'racknerd': {
            'name': 'RackNerd',
            'full_name': 'RackNerd LLC',
            'website': 'https://racknerd.com',
            'description': '美国VPS提供商，价格实惠',
            'keywords': ['racknerd', 'racknerd.com'],
            'out_of_stock_patterns': [
                'Out of Stock', 'Sold Out', 'unavailable',
                'not available', 'temporarily unavailable'
            ],
            'in_stock_patterns': [
                'Order Now', 'Add to Cart', 'Configure',
                'Select', 'Choose Plan'
            ]
        },
        'bandwagonhost': {
            'name': 'BandwagonHost',
            'full_name': 'BandwagonHost (BWH)',
            'website': 'https://bandwagonhost.com',
            'description': '知名VPS提供商，CN2线路',
            'keywords': ['bandwagonhost', 'bwh', 'justhost'],
            'out_of_stock_patterns': [
                'Out of stock', 'Sold out', 'Not available',
                'Currently unavailable'
            ],
            'in_stock_patterns': [
                'Add to cart', 'Order', 'Purchase',
                'Buy now', 'Select'
            ]
        },
        'cloudcone': {
            'name': 'CloudCone',
            'full_name': 'CloudCone LLC',
            'website': 'https://cloudcone.com',
            'description': '美西VPS提供商',
            'keywords': ['cloudcone', 'cloudcone.com'],
            'out_of_stock_patterns': [
                'Out of Stock', 'Sold Out', 'Unavailable'
            ],
            'in_stock_patterns': [
                'Order Now', 'Add to Cart', 'Deploy'
            ]
        },
        'vultr': {
            'name': 'Vultr',
            'full_name': 'Vultr Holdings LLC',
            'website': 'https://vultr.com',
            'description': '全球云服务提供商',
            'keywords': ['vultr', 'vultr.com'],
            'out_of_stock_patterns': [
                'Out of Stock', 'Unavailable', 'Not Available'
            ],
            'in_stock_patterns': [
                'Deploy', 'Deploy Now', 'Create Instance'
            ]
        },
        'linode': {
            'name': 'Linode',
            'full_name': 'Linode LLC',
            'website': 'https://linode.com',
            'description': 'Linux云服务提供商',
            'keywords': ['linode', 'linode.com'],
            'out_of_stock_patterns': [
                'Out of Stock', 'Unavailable'
            ],
            'in_stock_patterns': [
                'Create', 'Deploy', 'Launch'
            ]
        }
    }
    
    @classmethod
    def get_vendor_by_url(cls, url: str) -> Optional[str]:
        """根据URL识别服务商"""
        url_lower = url.lower()
        
        for vendor_key, vendor_info in cls.VENDORS.items():
            for keyword in vendor_info['keywords']:
                if keyword in url_lower:
                    return vendor_key
        
        return None
    
    @classmethod
    def get_vendor_info(cls, vendor_key: str) -> Optional[Dict]:
        """获取服务商信息"""
        return cls.VENDORS.get(vendor_key)
    
    @classmethod
    def get_all_vendors(cls) -> Dict:
        """获取所有服务商信息"""
        return cls.VENDORS


class VendorOptimizer:
    """服务商优化检测器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def check_vendor_specific(self, driver, url: str) -> Dict:
        """服务商特定检查"""
        vendor_key = VendorInfo.get_vendor_by_url(url)
        
        if not vendor_key:
            return {'status': None, 'message': '未识别的服务商，使用通用检测'}
        
        vendor_info = VendorInfo.get_vendor_info(vendor_key)
        self.logger.info(f"检测到服务商: {vendor_info['name']}")
        
        try:
            # 根据服务商类型调用相应的检查方法
            if vendor_key == 'dmit':
                return self._check_dmit(driver, vendor_info)
            elif vendor_key == 'racknerd':
                return self._check_racknerd(driver, vendor_info)
            elif vendor_key == 'bandwagonhost':
                return self._check_bandwagonhost(driver, vendor_info)
            elif vendor_key == 'cloudcone':
                return self._check_cloudcone(driver, vendor_info)
            elif vendor_key == 'vultr':
                return self._check_vultr(driver, vendor_info)
            elif vendor_key == 'linode':
                return self._check_linode(driver, vendor_info)
            else:
                return self._check_generic(driver, vendor_info)
                
        except Exception as e:
            self.logger.error(f"服务商特定检查失败: {e}")
            return {'status': None, 'message': f'检查失败: {str(e)}'}
    
    def _check_dmit(self, driver, vendor_info: Dict) -> Dict:
        """DMIT特定检查"""
        try:
            # DMIT特有的缺货标识
            out_selectors = [
                "//*[contains(text(), '缺货中')]",
                "//*[contains(text(), '刷新库存')]", 
                "//*[contains(text(), 'refresh stock')]",
                "//*[contains(text(), '暂无库存')]",
                ".out-of-stock",
                ".stock-refresh",
                "//*[contains(@class, 'stock-status') and contains(text(), '缺货')]"
            ]
            
            for selector in out_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() for el in elements):
                        return {
                            'status': False,
                            'message': f'DMIT页面显示缺货: {elements[0].text}',
                            'vendor': vendor_info['name']
                        }
                except:
                    continue
            
            # DMIT有货检查
            in_selectors = [
                "//*[contains(text(), '立即订购')]",
                "//*[contains(text(), '配置选项')]",
                "//*[contains(text(), 'order now')]",
                "//*[contains(text(), 'configure')]",
                "button[type='submit']:not([disabled])",
                ".btn-primary:not([disabled])",
                ".order-button:not([disabled])"
            ]
            
            for selector in in_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() and el.is_enabled() for el in elements):
                        return {
                            'status': True,
                            'message': f'DMIT页面显示可购买: {elements[0].text}',
                            'vendor': vendor_info['name']
                        }
                except:
                    continue
            
            return {
                'status': None, 
                'message': 'DMIT页面状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None, 
                'message': f'DMIT检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _check_racknerd(self, driver, vendor_info: Dict) -> Dict:
        """RackNerd特定检查"""
        try:
            # RackNerd缺货检查
            out_selectors = [
                "//*[contains(text(), 'Out of Stock')]",
                "//*[contains(text(), 'Sold Out')]",
                "//*[contains(text(), 'Unavailable')]",
                ".out-of-stock",
                ".sold-out"
            ]
            
            for selector in out_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() for el in elements):
                        return {
                            'status': False,
                            'message': f'RackNerd显示缺货: {elements[0].text}',
                            'vendor': vendor_info['name']
                        }
                except:
                    continue
            
            # RackNerd有货检查
            in_selectors = [
                "//*[contains(text(), 'Order Now')]",
                "//*[contains(text(), 'Add to Cart')]",
                "//*[contains(text(), 'Configure')]",
                ".btn-order",
                ".order-button",
                ".add-to-cart"
            ]
            
            for selector in in_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() and el.is_enabled() for el in elements):
                        return {
                            'status': True,
                            'message': f'RackNerd显示可订购: {elements[0].text}',
                            'vendor': vendor_info['name']
                        }
                except:
                    continue
            
            return {
                'status': None,
                'message': 'RackNerd状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None,
                'message': f'RackNerd检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _check_bandwagonhost(self, driver, vendor_info: Dict) -> Dict:
        """BandwagonHost特定检查"""
        try:
            # BWH缺货检查
            out_selectors = [
                "//*[contains(text(), 'Out of stock')]",
                "//*[contains(text(), 'Sold out')]",
                "//*[contains(text(), 'Not available')]",
                ".out-of-stock",
                ".sold-out"
            ]
            
            for selector in out_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() for el in elements):
                        return {
                            'status': False,
                            'message': f'BWH显示缺货: {elements[0].text}',
                            'vendor': vendor_info['name']
                        }
                except:
                    continue
            
            # BWH有货检查
            in_selectors = [
                "//*[contains(text(), 'Add to cart')]",
                "//*[contains(text(), 'Order')]",
                "//*[contains(text(), 'Purchase')]",
                ".cart-add-button",
                ".order-button"
            ]
            
            for selector in in_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements and any(el.is_displayed() and el.is_enabled() for el in elements):
                        return {
                            'status': True,
                            'message': f'BWH显示可购买: {elements[0].text}',
                            'vendor': vendor_info['name']
                        }
                except:
                    continue
            
            return {
                'status': None,
                'message': 'BWH状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None,
                'message': f'BWH检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _check_cloudcone(self, driver, vendor_info: Dict) -> Dict:
        """CloudCone特定检查"""
        try:
            # CloudCone缺货检查
            if self._find_text_elements(driver, vendor_info['out_of_stock_patterns']):
                return {
                    'status': False,
                    'message': 'CloudCone显示缺货',
                    'vendor': vendor_info['name']
                }
            
            # CloudCone有货检查
            if self._find_text_elements(driver, vendor_info['in_stock_patterns']):
                return {
                    'status': True,
                    'message': 'CloudCone显示可订购',
                    'vendor': vendor_info['name']
                }
            
            return {
                'status': None,
                'message': 'CloudCone状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None,
                'message': f'CloudCone检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _check_vultr(self, driver, vendor_info: Dict) -> Dict:
        """Vultr特定检查"""
        try:
            # Vultr缺货检查
            if self._find_text_elements(driver, vendor_info['out_of_stock_patterns']):
                return {
                    'status': False,
                    'message': 'Vultr显示缺货',
                    'vendor': vendor_info['name']
                }
            
            # Vultr有货检查
            if self._find_text_elements(driver, vendor_info['in_stock_patterns']):
                return {
                    'status': True,
                    'message': 'Vultr显示可部署',
                    'vendor': vendor_info['name']
                }
            
            return {
                'status': None,
                'message': 'Vultr状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None,
                'message': f'Vultr检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _check_linode(self, driver, vendor_info: Dict) -> Dict:
        """Linode特定检查"""
        try:
            # Linode缺货检查
            if self._find_text_elements(driver, vendor_info['out_of_stock_patterns']):
                return {
                    'status': False,
                    'message': 'Linode显示缺货',
                    'vendor': vendor_info['name']
                }
            
            # Linode有货检查
            if self._find_text_elements(driver, vendor_info['in_stock_patterns']):
                return {
                    'status': True,
                    'message': 'Linode显示可创建',
                    'vendor': vendor_info['name']
                }
            
            return {
                'status': None,
                'message': 'Linode状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None,
                'message': f'Linode检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _check_generic(self, driver, vendor_info: Dict) -> Dict:
        """通用检查（基于服务商信息中的关键词）"""
        try:
            # 检查缺货
            if self._find_text_elements(driver, vendor_info['out_of_stock_patterns']):
                return {
                    'status': False,
                    'message': f'{vendor_info["name"]}显示缺货',
                    'vendor': vendor_info['name']
                }
            
            # 检查有货
            if self._find_text_elements(driver, vendor_info['in_stock_patterns']):
                return {
                    'status': True,
                    'message': f'{vendor_info["name"]}显示可购买',
                    'vendor': vendor_info['name']
                }
            
            return {
                'status': None,
                'message': f'{vendor_info["name"]}状态不明确',
                'vendor': vendor_info['name']
            }
            
        except Exception as e:
            return {
                'status': None,
                'message': f'{vendor_info["name"]}检查失败: {str(e)}',
                'vendor': vendor_info['name']
            }
    
    def _find_text_elements(self, driver, patterns: List[str]) -> bool:
        """查找包含特定文本的元素"""
        for pattern in patterns:
            try:
                xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern.lower()}')]"
                elements = driver.find_elements(By.XPATH, xpath)
                if elements and any(el.is_displayed() for el in elements):
                    return True
            except:
                continue
        return False
    
    def get_vendor_info_from_url(self, url: str) -> Optional[Dict]:
        """从URL获取服务商信息"""
        vendor_key = VendorInfo.get_vendor_by_url(url)
        if vendor_key:
            return VendorInfo.get_vendor_info(vendor_key)
        return None
    
    def get_supported_vendors(self) -> Dict:
        """获取所有支持的服务商"""
        return VendorInfo.get_all_vendors()


# 使用示例
if __name__ == "__main__":
    # 示例：获取服务商信息
    optimizer = VendorOptimizer()
    
    # 测试URL识别
    test_urls = [
        "https://www.dmit.io/cart.php?a=add&pid=123",
        "https://racknerd.com/cart/",
        "https://bandwagonhost.com/cart.php",
        "https://cloudcone.com/",
        "https://unknown-provider.com/"
    ]
    
    print("=== 服务商识别测试 ===")
    for url in test_urls:
        vendor_info = optimizer.get_vendor_info_from_url(url)
        if vendor_info:
            print(f"URL: {url}")
            print(f"服务商: {vendor_info['full_name']}")
            print(f"描述: {vendor_info['description']}")
            print(f"网站: {vendor_info['website']}")
            print("-" * 40)
        else:
            print(f"URL: {url} - 未识别的服务商")
            print("-" * 40)
    
    print("\n=== 支持的服务商列表 ===")
    vendors = optimizer.get_supported_vendors()
    for key, info in vendors.items():
        print(f"{info['full_name']} ({info['name']})")
        print(f"  网站: {info['website']}")
        print(f"  描述: {info['description']}")
        print(f"  关键词: {', '.join(info['keywords'])}")
        print()
