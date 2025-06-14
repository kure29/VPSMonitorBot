#!/usr/bin/env python3
"""
API监控器（优化版）
VPS监控系统 v3.1
增强了API发现和库存判断能力
"""

import re
import json
import asyncio
import logging
import cloudscraper
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from config import Config


class APIMonitor:
    """API监控器（优化版）"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = cloudscraper.create_scraper()
        self.session.headers.update({
            'User-Agent': config.user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        self.logger = logging.getLogger(__name__)
        
        # API发现缓存
        self.api_cache = {}  # domain -> list of endpoints
    
    async def discover_api_endpoints(self, url: str) -> List[str]:
        """发现可能的API端点（增强版）"""
        if not self.config.enable_api_discovery:
            return []
        
        try:
            domain = urlparse(url).netloc
            
            # 检查缓存
            if domain in self.api_cache:
                self.logger.debug(f"使用缓存的API端点: {domain}")
                return self.api_cache[domain]
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(url, timeout=self.config.request_timeout)
            )
            
            if response.status_code != 200:
                return []
            
            content = response.text
            
            # 扩展的API端点发现
            endpoints = set()
            
            # 1. 从JavaScript中提取API端点
            js_endpoints = self._extract_from_javascript(content)
            endpoints.update(js_endpoints)
            
            # 2. 从HTML中提取
            html_endpoints = self._extract_from_html(content)
            endpoints.update(html_endpoints)
            
            # 3. 从内联脚本中提取
            inline_endpoints = self._extract_from_inline_scripts(content)
            endpoints.update(inline_endpoints)
            
            # 4. 尝试常见的API路径
            common_endpoints = self._try_common_api_paths(url)
            endpoints.update(common_endpoints)
            
            # 5. 从网络请求中学习（检查XHR请求模式）
            xhr_endpoints = self._detect_xhr_patterns(content)
            endpoints.update(xhr_endpoints)
            
            # 转换为完整URL
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            full_endpoints = []
            
            for endpoint in endpoints:
                if endpoint.startswith('http'):
                    full_url = endpoint
                elif endpoint.startswith('//'):
                    full_url = f"{urlparse(url).scheme}:{endpoint}"
                elif endpoint.startswith('/'):
                    full_url = urljoin(base_url, endpoint)
                else:
                    full_url = urljoin(url, endpoint)
                
                # 验证URL格式
                if self._is_valid_api_url(full_url):
                    full_endpoints.append(full_url)
            
            # 去重并限制数量
            unique_endpoints = list(set(full_endpoints))[:10]
            
            # 缓存结果
            self.api_cache[domain] = unique_endpoints
            
            self.logger.info(f"发现 {len(unique_endpoints)} 个API端点")
            return unique_endpoints
            
        except Exception as e:
            self.logger.error(f"API发现失败: {e}")
            return []
    
    def _extract_from_javascript(self, content: str) -> List[str]:
        """从JavaScript代码中提取API端点"""
        endpoints = []
        
        # 查找JavaScript文件链接
        js_patterns = [
            r'<script[^>]+src=["\']([^"\']+\.js)["\']',
            r'<script[^>]+src=["\']([^"\']+/js/[^"\']+)["\']'
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # 分析JS文件名，可能包含API相关信息
                if any(keyword in match.lower() for keyword in ['api', 'ajax', 'data', 'service']):
                    # 尝试推测相关的API端点
                    base_path = match.rsplit('/', 1)[0]
                    possible_apis = [
                        f"{base_path}/api/",
                        f"{base_path}/data/",
                        f"{base_path}/service/"
                    ]
                    endpoints.extend(possible_apis)
        
        return endpoints
    
    def _extract_from_html(self, content: str) -> List[str]:
        """从HTML中提取API端点"""
        endpoints = []
        
        # 扩展的API模式
        api_patterns = [
            # 标准API路径
            r'["\'](/api/[^"\'?\s]+)["\']',
            r'["\'](/v\d+/[^"\'?\s]+)["\']',
            r'["\'](/ajax/[^"\'?\s]+)["\']',
            r'["\'](/rest/[^"\'?\s]+)["\']',
            r'["\'](/graphql[^"\'?\s]*)["\']',
            r'["\'](/ws/[^"\'?\s]+)["\']',
            
            # 动作相关
            r'["\']([^"\']*?/check[^"\']*?stock[^"\'?\s]*)["\']',
            r'["\']([^"\']*?/inventory[^"\'?\s]*)["\']',
            r'["\']([^"\']*?/availability[^"\'?\s]*)["\']',
            r'["\']([^"\']*?/product[^"\']*?status[^"\'?\s]*)["\']',
            r'["\']([^"\']*?/get[^"\']*?stock[^"\'?\s]*)["\']',
            
            # 数据端点
            r'["\']([^"\']*?\.json[^"\'?\s]*)["\']',
            r'["\']([^"\']*?\.xml[^"\'?\s]*)["\']',
            
            # 后端脚本
            r'["\']([^"\']*?\.php\?[^"\']*?action=[^"\']*?stock[^"\'?\s]*)["\']',
            r'["\']([^"\']*?\.asp[x]?\?[^"\']*?)["\']',
            
            # API子域名
            r'["\'](https?://api\.[^"\'?\s]+/[^"\'?\s]+)["\']',
            r'["\'](https?://[^"\'?\s]+/api/[^"\'?\s]+)["\']',
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            endpoints.extend(matches)
        
        return endpoints
    
    def _extract_from_inline_scripts(self, content: str) -> List[str]:
        """从内联脚本中提取API端点"""
        endpoints = []
        
        # 查找script标签内的内容
        script_pattern = r'<script[^>]*>(.*?)</script>'
        scripts = re.findall(script_pattern, content, re.DOTALL | re.IGNORECASE)
        
        for script in scripts:
            # 查找API相关的变量和配置
            api_config_patterns = [
                r'api[Uu]rl\s*[:=]\s*["\']([^"\']+)["\']',
                r'api[Ee]ndpoint\s*[:=]\s*["\']([^"\']+)["\']',
                r'baseURL\s*[:=]\s*["\']([^"\']+)["\']',
                r'endpoint\s*[:=]\s*["\']([^"\']+)["\']',
                r'["\']url["\']\s*:\s*["\']([^"\']+)["\']',
                r'fetch\s*\(["\']([^"\']+)["\']',
                r'\$\.ajax\s*\(\s*["\']([^"\']+)["\']',
                r'axios\.[get|post|put|delete]+\s*\(["\']([^"\']+)["\']',
                r'XMLHttpRequest.*?open\s*\([^,]+,\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in api_config_patterns:
                matches = re.findall(pattern, script, re.IGNORECASE)
                endpoints.extend(matches)
        
        return endpoints
    
    def _try_common_api_paths(self, url: str) -> List[str]:
        """尝试常见的API路径"""
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        
        common_paths = [
            '/api/products/stock',
            '/api/inventory',
            '/api/availability',
            '/api/v1/products',
            '/api/v2/products',
            '/rest/products',
            '/data/products.json',
            '/products/api/stock',
            '/cart/api/check',
            '/ajax/product/availability',
            '/ajax/stock/check',
            '/wp-json/wp/v2/products',  # WordPress
            '/index.php/api/products',   # 某些PHP框架
        ]
        
        endpoints = []
        for path in common_paths:
            endpoints.append(urljoin(base_url, path))
        
        return endpoints
    
    def _detect_xhr_patterns(self, content: str) -> List[str]:
        """检测XHR请求模式"""
        endpoints = []
        
        # 查找数据属性中的API端点
        data_attr_patterns = [
            r'data-api-url=["\']([^"\']+)["\']',
            r'data-endpoint=["\']([^"\']+)["\']',
            r'data-source=["\']([^"\']+)["\']',
            r'data-fetch-url=["\']([^"\']+)["\']',
            r'data-ajax-url=["\']([^"\']+)["\']',
        ]
        
        for pattern in data_attr_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            endpoints.extend(matches)
        
        return endpoints
    
    def _is_valid_api_url(self, url: str) -> bool:
        """验证是否是有效的API URL"""
        try:
            parsed = urlparse(url)
            
            # 排除静态资源
            static_extensions = ['.css', '.js', '.jpg', '.png', '.gif', '.ico', '.svg', '.woff', '.ttf']
            if any(parsed.path.lower().endswith(ext) for ext in static_extensions):
                return False
            
            # 排除文档页面
            doc_keywords = ['docs', 'documentation', 'help', 'support', 'about', 'contact']
            if any(keyword in parsed.path.lower() for keyword in doc_keywords):
                return False
            
            return True
            
        except:
            return False
    
    async def check_api_stock(self, api_url: str) -> Tuple[Optional[bool], str]:
        """检查API接口的库存信息（增强版）"""
        try:
            loop = asyncio.get_event_loop()
            
            # 尝试不同的HTTP方法
            methods = ['GET', 'POST']
            
            for method in methods:
                try:
                    if method == 'GET':
                        response = await loop.run_in_executor(
                            None,
                            lambda: self.session.get(api_url, timeout=self.config.request_timeout)
                        )
                    else:
                        # POST请求可能需要一些参数
                        response = await loop.run_in_executor(
                            None,
                            lambda: self.session.post(
                                api_url, 
                                json={}, 
                                timeout=self.config.request_timeout
                            )
                        )
                    
                    if response.status_code in [200, 201]:
                        # 尝试解析响应
                        try:
                            data = response.json()
                            return self._analyze_api_response_enhanced(data, api_url)
                        except json.JSONDecodeError:
                            # 不是JSON，尝试分析文本
                            return self._analyze_text_response_enhanced(response.text)
                    
                except Exception as e:
                    self.logger.debug(f"{method} 请求失败: {e}")
                    continue
            
            return None, f"API请求失败"
                
        except Exception as e:
            return None, f"API检查失败: {str(e)}"
    
    def _analyze_api_response_enhanced(self, data: Any, api_url: str) -> Tuple[Optional[bool], str]:
        """分析API JSON响应（增强版）"""
        # 扩展的库存相关字段
        stock_fields = {
            'positive': ['stock', 'inventory', 'available', 'quantity', 'in_stock', 
                        'inStock', 'qty', 'count', 'remaining', 'units'],
            'negative': ['out_of_stock', 'outOfStock', 'sold_out', 'soldOut', 
                        'unavailable', 'noStock', 'stockOut'],
            'status': ['status', 'state', 'availability', 'stockStatus', 
                       'inventoryStatus', 'productStatus']
        }
        
        # 递归搜索函数
        def search_nested(obj, path=""):
            results = []
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    key_lower = key.lower()
                    
                    # 检查负面字段
                    for neg_field in stock_fields['negative']:
                        if neg_field.lower() in key_lower:
                            if isinstance(value, bool) and value:
                                results.append(('negative', value, current_path))
                            elif isinstance(value, str) and value.lower() in ['true', 'yes', '1']:
                                results.append(('negative', True, current_path))
                    
                    # 检查正面字段
                    for pos_field in stock_fields['positive']:
                        if pos_field.lower() in key_lower:
                            if isinstance(value, (int, float)):
                                results.append(('quantity', value, current_path))
                            elif isinstance(value, bool):
                                results.append(('boolean', value, current_path))
                            elif isinstance(value, str):
                                # 尝试解析字符串中的数字
                                numbers = re.findall(r'\d+', value)
                                if numbers:
                                    results.append(('quantity', int(numbers[0]), current_path))
                                else:
                                    value_lower = value.lower()
                                    if value_lower in ['true', 'yes', 'available', '有货']:
                                        results.append(('boolean', True, current_path))
                                    elif value_lower in ['false', 'no', 'unavailable', '无货']:
                                        results.append(('boolean', False, current_path))
                    
                    # 检查状态字段
                    for status_field in stock_fields['status']:
                        if status_field.lower() in key_lower and isinstance(value, str):
                            value_lower = value.lower()
                            if any(word in value_lower for word in ['out', 'sold', 'unavailable', '缺货', '售罄']):
                                results.append(('status', False, current_path))
                            elif any(word in value_lower for word in ['in', 'available', 'active', '有货', '现货']):
                                results.append(('status', True, current_path))
                    
                    # 递归搜索
                    if isinstance(value, (dict, list)):
                        results.extend(search_nested(value, current_path))
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_path = f"{path}[{i}]"
                    results.extend(search_nested(item, current_path))
            
            return results
        
        # 执行搜索
        findings = search_nested(data)
        
        # 分析结果
        if findings:
            # 优先处理明确的负面结果
            negative_findings = [f for f in findings if f[0] == 'negative']
            if negative_findings:
                return False, f"API显示明确缺货标识 ({negative_findings[0][2]})"
            
            # 处理数量信息
            quantity_findings = [f for f in findings if f[0] == 'quantity']
            if quantity_findings:
                quantities = [f[1] for f in quantity_findings]
                min_qty = min(quantities)
                max_qty = max(quantities)
                
                if max_qty == 0:
                    return False, f"API显示库存数量为0 ({quantity_findings[0][2]})"
                elif min_qty > 0:
                    return True, f"API显示库存数量: {min_qty} ({quantity_findings[0][2]})"
            
            # 处理布尔值
            boolean_findings = [f for f in findings if f[0] == 'boolean']
            if boolean_findings:
                # 如果所有布尔值都一致
                values = [f[1] for f in boolean_findings]
                if all(v == values[0] for v in values):
                    status = values[0]
                    return status, f"API库存状态: {'有货' if status else '缺货'} ({boolean_findings[0][2]})"
            
            # 处理状态字段
            status_findings = [f for f in findings if f[0] == 'status']
            if status_findings:
                # 优先相信缺货状态
                if any(not f[1] for f in status_findings):
                    return False, f"API状态显示缺货 ({status_findings[0][2]})"
                elif all(f[1] for f in status_findings):
                    return True, f"API状态显示有货 ({status_findings[0][2]})"
        
        # 特殊处理：如果是产品列表，检查是否为空
        if isinstance(data, list):
            if len(data) == 0:
                return False, "API返回空产品列表"
            elif all(isinstance(item, dict) for item in data):
                # 检查所有产品是否都缺货
                available_count = 0
                for item in data:
                    item_result = self._analyze_api_response_enhanced(item, api_url)
                    if item_result[0] is True:
                        available_count += 1
                
                if available_count > 0:
                    return True, f"API显示 {available_count}/{len(data)} 个产品有货"
                else:
                    return False, "API显示所有产品都缺货"
        
        return None, "无法从API响应中确定库存状态"
    
    def _analyze_text_response_enhanced(self, text: str) -> Tuple[Optional[bool], str]:
        """分析文本响应（增强版）"""
        text_lower = text.lower()
        
        # 检查是否是XML
        if text.strip().startswith('<?xml'):
            return self._analyze_xml_response(text)
        
        # 检查是否是CSV
        if '\n' in text and (',' in text or '\t' in text):
            return self._analyze_csv_response(text)
        
        # 扩展的关键词列表
        out_of_stock_keywords = [
            'out of stock', 'sold out', 'unavailable', 'not available',
            'no stock', 'stock: 0', 'quantity: 0', 'inventory: 0',
            '缺货', '售罄', '无货', '暂无库存', '库存不足',
            'temporarily unavailable', 'currently unavailable',
            'back order', 'pre-order only'
        ]
        
        in_stock_keywords = [
            'in stock', 'available', 'ready to ship', 'ships immediately',
            '有货', '现货', '库存充足', '可发货',
            'quantity available', 'items in stock',
            'add to cart', 'buy now'
        ]
        
        # 计算关键词匹配
        out_count = sum(1 for keyword in out_of_stock_keywords if keyword in text_lower)
        in_count = sum(1 for keyword in in_stock_keywords if keyword in text_lower)
        
        # 查找数字库存
        stock_numbers = re.findall(r'(?:stock|inventory|quantity|available)[\s:]*(\d+)', text_lower)
        if stock_numbers:
            numbers = [int(n) for n in stock_numbers]
            if all(n == 0 for n in numbers):
                return False, "API文本显示库存为0"
            elif any(n > 0 for n in numbers):
                return True, f"API文本显示库存数量: {max(numbers)}"
        
        # 基于关键词计数判断
        if out_count > in_count:
            return False, "API文本包含更多缺货关键词"
        elif in_count > out_count:
            return True, "API文本包含更多有货关键词"
        
        return None, "无法从API文本中确定库存状态"
    
    def _analyze_xml_response(self, xml_text: str) -> Tuple[Optional[bool], str]:
        """分析XML响应"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            
            # 查找库存相关元素
            stock_elements = ['stock', 'inventory', 'available', 'quantity']
            
            for elem_name in stock_elements:
                elements = root.findall(f".//{elem_name}")
                for elem in elements:
                    if elem.text:
                        try:
                            value = int(elem.text)
                            if value == 0:
                                return False, f"XML显示{elem_name}为0"
                            elif value > 0:
                                return True, f"XML显示{elem_name}为{value}"
                        except ValueError:
                            # 文本值
                            if elem.text.lower() in ['false', 'no', 'unavailable']:
                                return False, f"XML显示{elem_name}不可用"
                            elif elem.text.lower() in ['true', 'yes', 'available']:
                                return True, f"XML显示{elem_name}可用"
            
        except Exception as e:
            self.logger.error(f"XML解析失败: {e}")
        
        return None, "无法从XML中确定库存状态"
    
    def _analyze_csv_response(self, csv_text: str) -> Tuple[Optional[bool], str]:
        """分析CSV响应"""
        try:
            lines = csv_text.strip().split('\n')
            if len(lines) < 2:
                return None, "CSV数据不完整"
            
            # 假设第一行是标题
            headers = [h.lower().strip() for h in lines[0].split(',')]
            
            # 查找库存相关列
            stock_columns = []
            for i, header in enumerate(headers):
                if any(keyword in header for keyword in ['stock', 'inventory', 'available', 'quantity']):
                    stock_columns.append(i)
            
            if stock_columns:
                # 检查数据行
                total_stock = 0
                for line in lines[1:]:
                    values = line.split(',')
                    for col in stock_columns:
                        if col < len(values):
                            try:
                                stock_value = int(values[col].strip())
                                total_stock += stock_value
                            except ValueError:
                                pass
                
                if total_stock == 0:
                    return False, "CSV显示总库存为0"
                else:
                    return True, f"CSV显示总库存: {total_stock}"
            
        except Exception as e:
            self.logger.error(f"CSV解析失败: {e}")
        
        return None, "无法从CSV中确定库存状态"
