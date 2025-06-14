#!/usr/bin/env python3
"""
智能组合监控器（优化版）
VPS监控系统 v3.1
增强了判断逻辑和准确性
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
    """智能组合监控器（优化版）"""
    
    def __init__(self, config: Config):
        self.config = config
        self.fingerprint_monitor = PageFingerprintMonitor()
        self.dom_monitor = DOMElementMonitor(config)
        self.api_monitor = APIMonitor(config)
        self.logger = logging.getLogger(__name__)
        
        # 缓存机制，避免重复检查
        self.recent_checks = {}  # URL -> (timestamp, result)
        self.cache_duration = 60  # 60秒缓存
        
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
        
        # 检查缓存
        if url in self.recent_checks:
            cached_time, cached_result = self.recent_checks[url]
            if time.time() - cached_time < self.cache_duration:
                self.logger.debug(f"使用缓存结果: {url}")
                return cached_result
        
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
                'final_status': result.get('final_status'),
                'decision_reason': result.get('decision_reason', '')
            }
            
            status = result.get('final_status')
            confidence = result.get('confidence', 0)
            
            if status is None:
                response = (None, "智能检查无法确定库存状态", check_info)
            elif confidence < self.config.confidence_threshold:
                response = (None, f"置信度过低({confidence:.2f})", check_info)
            else:
                response = (status, None, check_info)
            
            # 缓存结果
            self.recent_checks[url] = (time.time(), response)
            
            return response
                
        except Exception as e:
            self.logger.error(f"智能检查失败 {url}: {e}")
            return None, f"智能检查失败: {str(e)}", {
                'response_time': time.time() - start_time,
                'http_status': 0,
                'content_length': 0,
                'method': 'SMART_COMBO_ERROR'
            }
    
    async def comprehensive_check(self, url: str) -> Dict[str, Any]:
        """综合检查库存状态（优化版）"""
        results = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'methods': {},
            'final_status': None,
            'confidence': 0,
            'decision_reason': ''
        }
        
        # 并行执行多种检查方法
        tasks = []
        
        # 方法1: 获取页面内容
        async def check_page_content():
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
                    
                    # 高级关键词检查
                    keyword_result = self._advanced_keyword_check_v2(html_content)
                    results['methods']['keywords'] = keyword_result
                    
                    # 检查页面结构
                    structure_result = self._analyze_page_structure(html_content)
                    results['methods']['structure'] = structure_result
                    
            except Exception as e:
                results['methods']['basic'] = {'error': str(e)}
        
        # 方法2: DOM检查
        async def check_dom():
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
        async def check_api():
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
        
        # 并行执行所有检查
        tasks = [check_page_content(), check_dom(), check_api()]
        await asyncio.gather(*tasks)
        
        # 综合判断（优化版）
        results['final_status'], results['confidence'], results['decision_reason'] = self._make_final_decision_v2(results['methods'])
        
        return results
    
    def _advanced_keyword_check_v2(self, content: str) -> Dict:
        """高级关键词检查（优化版）"""
        content_lower = content.lower()
        
        # 分层的关键词系统
        keyword_layers = {
            'critical_out_of_stock': {
                'keywords': [
                    ('out of stock', 1.0),
                    ('sold out', 1.0),
                    ('缺货', 1.0),
                    ('售罄', 1.0),
                    ('currently unavailable', 0.95),
                    ('temporarily unavailable', 0.95),
                    ('no longer available', 1.0),
                    ('discontinued', 1.0),
                    ('暂时缺货', 0.95),
                    ('暂无库存', 0.95),
                    ('库存不足', 0.9),
                    ('无货', 1.0),
                    ('断货', 1.0),
                ],
                'context_boost': ['title', 'h1', 'h2', 'alert', 'warning', 'error'],
                'context_penalty': ['maybe', 'previous', 'was', 'history']
            },
            'moderate_out_of_stock': {
                'keywords': [
                    ('not available', 0.8),
                    ('unavailable', 0.7),
                    ('coming soon', 0.7),
                    ('pre-order', 0.6),
                    ('notify me', 0.7),
                    ('waitlist', 0.7),
                    ('join waiting list', 0.8),
                    ('back in stock', 0.7),
                    ('restock', 0.6),
                    ('补货中', 0.7),
                    ('即将上架', 0.7),
                    ('敬请期待', 0.7),
                    ('到货通知', 0.7),
                ],
                'context_boost': ['product', 'item', 'plan'],
                'context_penalty': ['newsletter', 'blog', 'article']
            },
            'in_stock': {
                'keywords': [
                    ('add to cart', 0.9),
                    ('buy now', 0.95),
                    ('purchase now', 0.95),
                    ('order now', 0.9),
                    ('in stock', 0.95),
                    ('available now', 0.95),
                    ('立即购买', 0.95),
                    ('加入购物车', 0.9),
                    ('现在订购', 0.9),
                    ('有货', 0.95),
                    ('现货', 0.95),
                    ('立即订购', 0.9),
                    ('马上购买', 0.95),
                ],
                'context_boost': ['price', 'cost', '$', '¥', '€', 'plan', 'package'],
                'context_penalty': ['demo', 'trial', 'example', 'documentation']
            },
            'ambiguous': {
                'keywords': [
                    ('available', 0.5),
                    ('order', 0.4),
                    ('get started', 0.4),
                    ('configure', 0.4),
                    ('continue', 0.3),
                    ('create', 0.2),
                    ('选择', 0.3),
                    ('开始', 0.3),
                ],
                'context_boost': ['checkout', 'payment', 'billing'],
                'context_penalty': ['login', 'register', 'account', 'support']
            }
        }
        
        # 计算各层得分
        layer_scores = {}
        found_keywords = {}
        
        for layer_name, layer_config in keyword_layers.items():
            layer_score = 0
            layer_keywords = []
            
            for keyword, base_weight in layer_config['keywords']:
                if keyword in content_lower:
                    # 计算上下文权重
                    context_weight = self._calculate_context_weight(
                        content_lower, 
                        keyword, 
                        layer_config['context_boost'], 
                        layer_config['context_penalty']
                    )
                    
                    final_weight = base_weight * context_weight
                    layer_score += final_weight
                    layer_keywords.append((keyword, final_weight))
            
            layer_scores[layer_name] = layer_score
            found_keywords[layer_name] = layer_keywords
        
        # 决策逻辑（优化版）
        # 1. 如果有关键的缺货词且得分高
        if layer_scores['critical_out_of_stock'] > 0.8:
            # 检查是否同时有强烈的有货信号
            if layer_scores['in_stock'] > layer_scores['critical_out_of_stock'] * 1.5:
                # 可能是混合信号，需要更仔细判断
                return {
                    'status': None,
                    'confidence': 0.5,
                    'reason': 'mixed_signals',
                    'details': {
                        'out_score': layer_scores['critical_out_of_stock'],
                        'in_score': layer_scores['in_stock'],
                        'keywords': found_keywords
                    }
                }
            else:
                # 明确缺货
                return {
                    'status': False,
                    'confidence': min(0.95, layer_scores['critical_out_of_stock'] / 1.0),
                    'reason': 'critical_out_of_stock',
                    'details': {
                        'score': layer_scores['critical_out_of_stock'],
                        'keywords': found_keywords['critical_out_of_stock']
                    }
                }
        
        # 2. 如果有中等缺货信号
        if layer_scores['moderate_out_of_stock'] > 0.5:
            total_out = layer_scores['critical_out_of_stock'] + layer_scores['moderate_out_of_stock']
            if total_out > layer_scores['in_stock']:
                return {
                    'status': False,
                    'confidence': min(0.8, total_out / 2.0),
                    'reason': 'moderate_out_of_stock',
                    'details': {
                        'score': total_out,
                        'keywords': found_keywords['moderate_out_of_stock']
                    }
                }
        
        # 3. 如果有明确的有货信号
        if layer_scores['in_stock'] > 0.8:
            # 确保没有强烈的缺货信号
            total_out = layer_scores['critical_out_of_stock'] + layer_scores['moderate_out_of_stock']
            if total_out < layer_scores['in_stock'] * 0.5:
                return {
                    'status': True,
                    'confidence': min(0.9, layer_scores['in_stock'] / 1.0),
                    'reason': 'clear_in_stock',
                    'details': {
                        'score': layer_scores['in_stock'],
                        'keywords': found_keywords['in_stock']
                    }
                }
        
        # 4. 模糊情况
        if layer_scores['ambiguous'] > 0:
            # 需要其他方法辅助判断
            return {
                'status': None,
                'confidence': 0.3,
                'reason': 'ambiguous_keywords',
                'details': {
                    'scores': layer_scores,
                    'keywords': found_keywords
                }
            }
        
        # 5. 没有找到关键词
        return {
            'status': None,
            'confidence': 0.0,
            'reason': 'no_keywords',
            'details': {}
        }
    
    def _calculate_context_weight(self, content: str, keyword: str, 
                                boost_words: List[str], penalty_words: List[str]) -> float:
        """计算关键词的上下文权重"""
        keyword_pos = content.find(keyword)
        if keyword_pos == -1:
            return 1.0
        
        # 检查关键词前后100个字符的上下文
        context_start = max(0, keyword_pos - 100)
        context_end = min(len(content), keyword_pos + len(keyword) + 100)
        context = content[context_start:context_end]
        
        weight = 1.0
        
        # 检查增强词
        for boost_word in boost_words:
            if boost_word in context:
                weight *= 1.2
        
        # 检查惩罚词
        for penalty_word in penalty_words:
            if penalty_word in context:
                weight *= 0.7
        
        # 检查是否在重要标签中
        # 简单检查是否在标题等标签附近
        if any(tag in content[max(0, keyword_pos-50):keyword_pos] for tag in ['<h1', '<h2', '<title', '<alert']):
            weight *= 1.3
        
        return min(2.0, max(0.3, weight))  # 限制权重范围
    
    def _analyze_page_structure(self, html: str) -> Dict:
        """分析页面结构以辅助判断"""
        structure_info = {
            'is_product_page': False,
            'has_price_info': False,
            'has_buy_section': False,
            'has_notification_form': False,
            'page_type': 'unknown'
        }
        
        html_lower = html.lower()
        
        # 检查是否是产品页面
        product_indicators = [
            'product-detail', 'product-info', 'product-page',
            'item-detail', 'plan-detail', 'vps-plan',
            'pricing', 'specifications', 'features'
        ]
        structure_info['is_product_page'] = any(indicator in html_lower for indicator in product_indicators)
        
        # 检查价格信息
        price_patterns = [r'\$\d+', r'¥\d+', r'€\d+', r'/mo', r'/month', r'/year']
        structure_info['has_price_info'] = any(re.search(pattern, html) for pattern in price_patterns)
        
        # 检查购买区域
        buy_section_indicators = [
            'add-to-cart', 'buy-button', 'purchase-section',
            'order-form', 'checkout', 'shopping-cart'
        ]
        structure_info['has_buy_section'] = any(indicator in html_lower for indicator in buy_section_indicators)
        
        # 检查通知表单
        notification_indicators = [
            'notify-form', 'waitlist-form', 'email-notification',
            'stock-alert', 'availability-notification'
        ]
        structure_info['has_notification_form'] = any(indicator in html_lower for indicator in notification_indicators)
        
        # 判断页面类型
        if structure_info['has_notification_form']:
            structure_info['page_type'] = 'out_of_stock_notification'
        elif structure_info['is_product_page'] and structure_info['has_buy_section']:
            structure_info['page_type'] = 'active_product'
        elif structure_info['is_product_page']:
            structure_info['page_type'] = 'product_no_buy'
        
        return structure_info
    
    def _make_final_decision_v2(self, methods: Dict) -> Tuple[Optional[bool], float, str]:
        """基于多种方法的结果做出最终判断（优化版）"""
        decision_factors = []
        
        # 1. DOM检查结果（最高权重）
        if 'dom' in methods and 'status' in methods['dom']:
            dom_status = methods['dom']['status']
            if dom_status is not None:
                decision_factors.append({
                    'method': 'dom',
                    'status': dom_status,
                    'weight': 0.9,
                    'confidence': 0.9,
                    'message': methods['dom'].get('message', '')
                })
        
        # 2. API检查结果（次高权重）
        if 'api' in methods and 'status' in methods['api']:
            api_status = methods['api']['status']
            if api_status is not None:
                decision_factors.append({
                    'method': 'api',
                    'status': api_status,
                    'weight': 0.85,
                    'confidence': 0.85,
                    'message': methods['api'].get('message', '')
                })
        
        # 3. 关键词检查结果（动态权重）
        if 'keywords' in methods and 'status' in methods['keywords']:
            keyword_result = methods['keywords']
            if keyword_result['status'] is not None:
                # 根据原因调整权重
                weight = 0.6  # 默认权重
                if keyword_result['reason'] == 'critical_out_of_stock':
                    weight = 0.8
                elif keyword_result['reason'] == 'clear_in_stock':
                    weight = 0.7
                elif keyword_result['reason'] == 'ambiguous_keywords':
                    weight = 0.4
                
                decision_factors.append({
                    'method': 'keywords',
                    'status': keyword_result['status'],
                    'weight': weight,
                    'confidence': keyword_result['confidence'],
                    'message': keyword_result['reason']
                })
        
        # 4. 页面结构分析（辅助）
        if 'structure' in methods:
            structure = methods['structure']
            if structure['page_type'] == 'out_of_stock_notification':
                decision_factors.append({
                    'method': 'structure',
                    'status': False,
                    'weight': 0.7,
                    'confidence': 0.8,
                    'message': 'detected_notification_page'
                })
            elif structure['page_type'] == 'active_product':
                decision_factors.append({
                    'method': 'structure',
                    'status': True,
                    'weight': 0.5,
                    'confidence': 0.6,
                    'message': 'active_product_page'
                })
        
        # 如果没有任何判断因素
        if not decision_factors:
            return None, 0.0, 'no_detection_methods_succeeded'
        
        # 智能决策算法
        # 1. 检查是否有高置信度的一致结果
        high_confidence_factors = [f for f in decision_factors if f['confidence'] >= 0.8]
        if high_confidence_factors:
            # 检查是否一致
            statuses = [f['status'] for f in high_confidence_factors]
            if all(s == statuses[0] for s in statuses):
                # 高置信度一致结果
                total_weight = sum(f['weight'] * f['confidence'] for f in high_confidence_factors)
                avg_confidence = total_weight / sum(f['weight'] for f in high_confidence_factors)
                return statuses[0], min(0.95, avg_confidence), 'high_confidence_consensus'
        
        # 2. 加权投票
        in_stock_score = 0
        out_of_stock_score = 0
        total_weight = 0
        
        for factor in decision_factors:
            weight = factor['weight'] * factor['confidence']
            total_weight += factor['weight']
            
            if factor['status'] is True:
                in_stock_score += weight
            elif factor['status'] is False:
                out_of_stock_score += weight
        
        # 3. 特殊规则
        # 如果DOM明确说缺货，而其他方法说有货，倾向于相信DOM
        dom_factor = next((f for f in decision_factors if f['method'] == 'dom'), None)
        if dom_factor and dom_factor['status'] is False and dom_factor['confidence'] >= 0.8:
            if out_of_stock_score < in_stock_score:
                # DOM说缺货但其他说有货，提高缺货权重
                out_of_stock_score *= 1.5
        
        # 4. 最终决策
        if total_weight == 0:
            return None, 0.0, 'no_valid_weights'
        
        score_diff = abs(in_stock_score - out_of_stock_score)
        confidence = min(0.95, score_diff / total_weight)
        
        # 需要明显的差异才做出判断
        threshold = total_weight * 0.2  # 20%的差异阈值
        
        if out_of_stock_score > in_stock_score + threshold:
            return False, confidence, f'out_of_stock_score_higher({out_of_stock_score:.2f}>{in_stock_score:.2f})'
        elif in_stock_score > out_of_stock_score + threshold:
            return True, confidence, f'in_stock_score_higher({in_stock_score:.2f}>{out_of_stock_score:.2f})'
        else:
            # 分数接近，使用保守策略
            if out_of_stock_score > in_stock_score:
                return False, confidence * 0.7, 'scores_close_lean_out_of_stock'
            else:
                return None, confidence * 0.5, 'scores_too_close'
    
    def close(self):
        """关闭监控器"""
        if self.dom_monitor:
            self.dom_monitor.close()
        # 清理缓存
        self.recent_checks.clear()

    import re
