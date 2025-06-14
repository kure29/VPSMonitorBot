#!/usr/bin/env python3
"""
API监控器
VPS监控系统 v3.1
"""

import re
import asyncio
import logging
import cloudscraper
from typing import List, Tuple, Optional, Dict
from config import Config


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
