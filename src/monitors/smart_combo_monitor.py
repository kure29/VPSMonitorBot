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
from typing import Dict, Any, Tuple, Optional, List
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
                
                # 改进的关键词检查
                keyword_result = self._advanced_keyword_check(html_content)
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
    
    def _advanced_keyword_check(self, content: str) -> Dict:
        """改进的关键词检查，支持权重和优先级"""
        content_lower = content.lower()
        
        # 高优先级的缺货关键词（权重更高）
        high_priority_out_of_stock = [
            ('sold out', 1.0),
            ('out of stock', 1.0),
            ('缺货', 1.0),
            ('售罄', 1.0),
            ('currently unavailable', 0.9),
            ('not available', 0.9),
            ('暂时缺货', 0.9),
            ('temporarily out of stock', 0.9),
            ('已售完', 0.9),
            ('out-of-stock', 0.9),
            ('unavailable', 0.8),
            ('无货', 0.9),
            ('断货', 0.9),
            ('not in stock', 0.9),
            ('no stock', 0.9),
            ('无库存', 0.9),
            ('stock: 0', 1.0),
            ('库存: 0', 1.0),
            ('暂无库存', 0.9),
            ('等待补货', 0.8)
        ]
        
        # 中低优先级的缺货关键词
        low_priority_out_of_stock = [
            ('补货中', 0.7),
            ('缺货中', 0.7),
            ('库存不足', 0.6),
            ('刷新库存', 0.5),
            ('库存刷新', 0.5)
        ]
        
        # 有货关键词（带权重）
        in_stock_keywords = [
            ('add to cart', 0.8),
            ('buy now', 0.8),
            ('立即购买', 0.8),
            ('加入购物车', 0.8),
            ('in stock', 0.9),
            ('有货', 0.9),
            ('现货', 0.9),
            ('available', 0.7),
            ('order now', 0.8),
            ('purchase', 0.6),
            ('checkout', 0.6),
            ('订购', 0.7),
            ('下单', 0.7),
            ('continue', 0.4),  # 降低continue的权重
            ('繼續', 0.4),
            ('configure', 0.5),
            ('select options', 0.5),
            ('configure now', 0.5),
            ('create', 0.3),  # create权重很低
            ('立即订购', 0.8),
            ('马上购买', 0.8),
            ('选择配置', 0.6)
        ]
        
        # 上下文排除词（如果这些词出现在关键词附近，降低权重）
        context_exclusions = ['disabled', 'false', 'unavailable', '不可用', '已禁用', 'grayed out']
        
        # 计算缺货得分
        out_of_stock_score = 0
        out_keywords_found = []
        
        for keyword, weight in high_priority_out_of_stock + low_priority_out_of_stock:
            if keyword in content_lower:
                # 检查上下文
                context_penalty = self._check_context(content_lower, keyword, context_exclusions)
                actual_weight = weight * (1 - context_penalty)
                out_of_stock_score += actual_weight
                out_keywords_found.append((keyword, actual_weight))
        
        # 计算有货得分
        in_stock_score = 0
        in_keywords_found = []
        
        for keyword, weight in in_stock_keywords:
            if keyword in content_lower:
                # 检查上下文
                context_penalty = self._check_context(content_lower, keyword, context_exclusions)
                actual_weight = weight * (1 - context_penalty)
                in_stock_score += actual_weight
                in_keywords_found.append((keyword, actual_weight))
        
        # 特殊规则：如果同时存在高优先级缺货关键词，直接判断为缺货
        high_priority_out_found = any(
            keyword in content_lower 
            for keyword, _ in high_priority_out_of_stock
        )
        
        if high_priority_out_found:
            # 即使有"create"等关键词，也优先判断为缺货
            return {
                'status': False,
                'confidence': min(0.9, out_of_stock_score / max(out_of_stock_score + in_stock_score, 1)),
                'out_score': out_of_stock_score,
                'in_score': in_stock_score,
                'out_keywords': out_keywords_found,
                'in_keywords': in_keywords_found,
                'reason': 'high_priority_out_of_stock_found'
            }
        
        # 综合判断
        total_score = out_of_stock_score + in_stock_score
        
        if total_score == 0:
            return {
                'status': None,
                'confidence': 0.0,
                'out_score': 0,
                'in_score': 0,
                'reason': 'no_keywords_found'
            }
        
        # 计算置信度
        score_diff = abs(out_of_stock_score - in_stock_score)
        confidence = min(0.9, score_diff / total_score)
        
        # 如果缺货得分明显高于有货得分
        if out_of_stock_score > in_stock_score * 1.2:  # 1.2倍阈值
            return {
                'status': False,
                'confidence': confidence,
                'out_score': out_of_stock_score,
                'in_score': in_stock_score,
                'out_keywords': out_keywords_found,
                'in_keywords': in_keywords_found,
                'reason': 'out_score_higher'
            }
        elif in_stock_score > out_of_stock_score * 1.5:  # 有货需要更高的阈值
            return {
                'status': True,
                'confidence': confidence,
                'out_score': out_of_stock_score,
                'in_score': in_stock_score,
                'out_keywords': out_keywords_found,
                'in_keywords': in_keywords_found,
                'reason': 'in_score_higher'
            }
        else:
            # 分数接近时，倾向于判断为缺货（保守策略）
            return {
                'status': False,
                'confidence': confidence * 0.5,  # 降低置信度
                'out_score': out_of_stock_score,
                'in_score': in_stock_score,
                'out_keywords': out_keywords_found,
                'in_keywords': in_keywords_found,
                'reason': 'scores_close_default_out'
            }
    
    def _check_context(self, content: str, keyword: str, exclusions: List[str]) -> float:
        """检查关键词的上下文，返回惩罚系数（0-1）"""
        keyword_pos = content.find(keyword)
        if keyword_pos == -1:
            return 0
        
        # 检查关键词前后50个字符
        start = max(0, keyword_pos - 50)
        end = min(len(content), keyword_pos + len(keyword) + 50)
        context = content[start:end]
        
        # 如果上下文中包含排除词，返回惩罚
        for exclusion in exclusions:
            if exclusion in context:
                return 0.5  # 50%惩罚
        
        return 0
    
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
        
        # 改进的关键词检查
        if 'keywords' in methods and 'status' in methods['keywords']:
            status = methods['keywords']['status']
            if status is not None:
                # 如果是因为高优先级缺货关键词而判断的，提高权重
                if methods['keywords'].get('reason') == 'high_priority_out_of_stock_found':
                    confidence_scores.append(0.85)
                else:
                    confidence_scores.append(methods['keywords'].get('confidence', 0.5))
                votes.append(status)
        
        # 页面变化检测
        if methods.get('fingerprint', {}).get('changed'):
            # 页面变化只是辅助信号，不直接参与投票
            confidence_scores.append(0.2)
        
        if not votes:
            return None, 0.0
        
        # 特殊规则：如果关键词检查发现高优先级缺货词，且没有其他方法明确说有货
        if ('keywords' in methods and 
            methods['keywords'].get('reason') == 'high_priority_out_of_stock_found' and
            methods['keywords'].get('status') is False):
            
            # 检查是否有其他方法明确说有货
            other_in_stock = any(
                vote for i, vote in enumerate(votes)
                if vote and i < len(confidence_scores) and confidence_scores[i] > 0.8
            )
            
            if not other_in_stock:
                # 直接返回缺货
                return False, 0.85
        
        # 加权投票
        weighted_sum = sum(
            (1 if vote else -1) * confidence
            for vote, confidence in zip(votes, confidence_scores[:len(votes)])
        )
        
        total_confidence = sum(confidence_scores[:len(votes)])
        
        if weighted_sum > 0:
            final_status = True
        elif weighted_sum < 0:
            final_status = False
        else:
            # 平票时，倾向于保守判断（缺货）
            final_status = False
        
        # 计算最终置信度
        if total_confidence > 0:
            final_confidence = abs(weighted_sum) / total_confidence
            # 根据投票一致性调整置信度
            vote_consistency = sum(1 for v in votes if v == final_status) / len(votes)
            final_confidence = min(final_confidence * (0.5 + 0.5 * vote_consistency), 0.95)
        else:
            final_confidence = 0.0
        
        return final_status, final_confidence
    
    def close(self):
        """关闭监控器"""
        if self.dom_monitor:
            self.dom_monitor.close()
