#!/usr/bin/env python3
"""
页面指纹监控器
VPS监控系统 v3.1
"""

import re
import hashlib
import logging
from typing import Tuple


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
