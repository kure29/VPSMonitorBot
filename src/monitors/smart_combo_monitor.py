#!/usr/bin/env python3
"""
智能组合监控器
VPS监控系统 v3.1
"""

import time
import asyncio
import logging
import cloudscraper
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from config import Config
from .fingerprint_monitor import PageFingerprintMonitor
from .dom_monitor import DOMElementMonitor
from .api_monitor import APIMonitor


class SmartComboMonitor:
    """智能组合监控器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.fingerprint_monitor = PageFingerprintMonitor()
        self.dom_monitor = DOMElementMonitor(config)
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
