#!/usr/bin/env python3
"""
主监控器模块
VPS监控系统 v3.1
"""

import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from config import Config, ConfigManager
from database_manager import DatabaseManager
from telegram_bot import TelegramBot
from monitors import SmartComboMonitor
from utils import check_dependencies


class VPSMonitor:
    """主监控类（v3.1多用户版）"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.stock_checker = None
        self.telegram_bot = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._pending_notifications = []
        self._last_aggregation_time = datetime.now()
        self._last_notified = {}
    
    async def initialize(self) -> None:
        """初始化监控器"""
        try:
            print("🔧 初始化监控器 v3.1 (多用户版)...")
            
            # 检查依赖
            dependencies = check_dependencies()
            
            # 加载配置
            config = self.config_manager.load_config()
            print("✅ 配置文件加载成功")
            
            # 初始化数据库
            await self.db_manager.initialize()
            print("✅ 多用户数据库初始化成功")
            
            # 初始化智能监控器
            self.stock_checker = SmartComboMonitor(config)
            self.telegram_bot = TelegramBot(config, self.db_manager)
            
            # 初始化Telegram Bot
            await self.telegram_bot.initialize()
            
            # 显示功能状态
            print(f"🤖 Selenium支持: {'✅' if dependencies.get('selenium') and config.enable_selenium else '❌'}")
            print(f"🔍 API发现: {'✅' if config.enable_api_discovery else '❌'}")
            print(f"👁️ 视觉对比: {'✅' if config.enable_visual_comparison else '❌'}")
            print(f"🛡️ 服务商优化: {'✅' if dependencies.get('vendor_optimization') and config.enable_vendor_optimization else '❌'}")
            print(f"👥 多用户支持: ✅")
            print(f"📊 每日添加限制: {config.daily_add_limit}")
            
            self.logger.info("多用户监控器v3.1初始化完成")
            print("✅ 多用户监控器v3.1初始化完成")
            
        except Exception as e:
            self.logger.error(f"监控器初始化失败: {e}")
            print(f"❌ 监控器初始化失败: {e}")
            raise
    
    async def start(self) -> None:
        """启动监控"""
        try:
            print("🚀 启动VPS监控系统 v3.1 (多用户版)...")
            await self.initialize()
            
            # 发送启动通知
            config = self.config_manager.config
            startup_message = (
                "🚀 **VPS监控程序 v3.1 已启动** (多用户版)\n\n"
                "🆕 **v3.1新特性:**\n"
                "🧠 智能组合监控算法\n"
                "🎯 多重检测方法验证\n"
                "📊 置信度评分系统\n"
                "👥 多用户支持系统\n"
                "🛡️ 服务商优化模块\n"
                "🧩 完整管理员工具\n"
                "🔧 集成调试功能\n\n"
                f"⚙️ **系统配置:**\n"
                f"⏰ 检查间隔：{config.check_interval}秒\n"
                f"📊 聚合间隔：{config.notification_aggregation_interval}秒\n"
                f"🕐 通知冷却：{config.notification_cooldown}秒\n"
                f"🎯 置信度阈值：{config.confidence_threshold}\n"
                f"📈 每日添加限制：{config.daily_add_limit}\n\n"
                f"👥 **多用户特性:**\n"
                f"• 所有用户都可添加监控\n"
                f"• 库存变化推送给管理员\n"
                f"• 用户行为统计和管理\n"
                f"• 智能防刷机制\n"
                f"• 完整的管理员工具\n\n"
                "💡 使用 /start 开始操作\n"
                "🔍 使用 /debug <URL> 进行调试\n"
                "🧩 管理员可使用 /admin 管理\n\n"
                "👨‍💻 作者: kure29 | https://kure29.com"
            )
            await self.telegram_bot.send_notification(startup_message, parse_mode='Markdown')
            
            # 执行启动检查
            await self._perform_startup_check()
            
            # 开始监控循环
            self._running = True
            print("✅ 多用户智能监控系统启动成功，按Ctrl+C停止")
            await self._monitor_loop()
            
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号")
            self.logger.info("收到停止信号")
        except Exception as e:
            print(f"❌ 监控运行失败: {e}")
            self.logger.error(f"监控运行失败: {e}")
            raise
        finally:
            await self.stop()
    
    async def _perform_startup_check(self) -> None:
        """执行启动检查"""
        # 获取所有启用的监控项（包括全局项目）
        items = await self.db_manager.get_monitor_items(enabled_only=True)
        if not items:
            await self.telegram_bot.send_notification("⚠️ 当前没有监控商品")
            print("⚠️ 当前没有监控商品")
            return
        
        print(f"🔍 开始智能检查 {len(items)} 个监控项...")
        await self.telegram_bot.send_notification("🧠 正在进行智能启动检查...")
        
        success_count = 0
        fail_count = 0
        low_confidence_count = 0
        
        for item in items.values():
            try:
                print(f"智能检查: {item.name} (用户: {item.user_id})")
                stock_available, error, check_info = await self.stock_checker.check_stock(item.url)
                
                # 记录检查历史
                await self.db_manager.add_check_history(
                    monitor_id=item.id,
                    status=stock_available,
                    response_time=check_info['response_time'],
                    error_message=error or '',
                    http_status=check_info['http_status'],
                    content_length=check_info['content_length'],
                    confidence=check_info.get('confidence', 0),
                    method_used=check_info.get('method', 'SMART_COMBO')
                )
                
                if error:
                    fail_count += 1
                    print(f"  ❌ 检查失败: {error}")
                else:
                    confidence = check_info.get('confidence', 0)
                    if confidence < self.config_manager.config.confidence_threshold:
                        low_confidence_count += 1
                        print(f"  ⚠️ 置信度过低: {confidence:.2f}")
                    else:
                        success_count += 1
                        status = "🟢 有货" if stock_available else "🔴 无货"
                        print(f"  ✅ 状态：{status} (置信度: {confidence:.2f})")
                    
                    # 更新项目状态
                    await self._update_item_status(item.id, stock_available)
                
            except Exception as e:
                fail_count += 1
                self.logger.error(f"启动检查失败 {item.url}: {e}")
                print(f"  ❌ 检查异常: {e}")
        
        summary = (
            f"🧠 智能启动检查完成\n\n"
            f"✅ 成功: {success_count} 个\n"
            f"❌ 失败: {fail_count} 个\n"
            f"⚠️ 低置信度: {low_confidence_count} 个\n\n"
            f"🎯 多用户监控系统已就绪"
        )
        await self.telegram_bot.send_notification(summary)
        print(f"\n{summary}")
    
    async def _update_item_status(self, item_id: str, status: bool) -> None:
        """更新监控项状态"""
        try:
            async with aiosqlite.connect(self.db_manager.db_path) as db:
                await db.execute(
                    "UPDATE monitor_items SET status = ?, last_checked = ? WHERE id = ?",
                    (1 if status else 0, datetime.now().isoformat(), item_id)
                )
                await db.commit()
        except Exception as e:
            self.logger.error(f"更新项目状态失败: {e}")
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._check_all_items()
                await self._process_notifications()
                
                # 等待下次检查
                await asyncio.sleep(self.config_manager.config.check_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟
    
    async def _check_all_items(self) -> None:
        """检查所有监控项"""
        items = await self.db_manager.get_monitor_items(enabled_only=True)
        
        if not items:
            return
        
        print(f"🔍 检查 {len(items)} 个监控项...")
        
        for item in items.values():
            try:
                stock_available, error, check_info = await self.stock_checker.check_stock(item.url)
                
                # 记录检查历史
                await self.db_manager.add_check_history(
                    monitor_id=item.id,
                    status=stock_available,
                    response_time=check_info['response_time'],
                    error_message=error or '',
                    http_status=check_info['http_status'],
                    content_length=check_info['content_length'],
                    confidence=check_info.get('confidence', 0),
                    method_used=check_info.get('method', 'SMART_COMBO')
                )
                
                # 检查是否需要通知
                if not error and stock_available is not None:
                    await self._check_for_notifications(item, stock_available, check_info)
                    await self._update_item_status(item.id, stock_available)
                
            except Exception as e:
                self.logger.error(f"检查项目失败 {item.url}: {e}")
    
    async def _check_for_notifications(self, item, stock_available: bool, check_info: Dict) -> None:
        """检查是否需要发送通知"""
        # 只有状态变化或首次检查时才通知
        if item.status != stock_available:
            confidence = check_info.get('confidence', 0)
            
            if stock_available and confidence >= self.config_manager.config.confidence_threshold:
                # 有货通知
                notification = {
                    'type': 'stock_available',
                    'item': item,
                    'confidence': confidence,
                    'timestamp': datetime.now()
                }
                
                # 检查通知冷却
                cooldown_key = f"{item.id}_available"
                last_notified = self._last_notified.get(cooldown_key)
                
                if not last_notified or (datetime.now() - last_notified).seconds > self.config_manager.config.notification_cooldown:
                    self._pending_notifications.append(notification)
                    self._last_notified[cooldown_key] = datetime.now()
    
    async def _process_notifications(self) -> None:
        """处理待发送的通知"""
        if not self._pending_notifications:
            return
        
        # 检查是否到达聚合时间
        time_since_last = (datetime.now() - self._last_aggregation_time).seconds
        if time_since_last < self.config_manager.config.notification_aggregation_interval:
            return
        
        # 按类型分组通知
        available_notifications = [n for n in self._pending_notifications if n['type'] == 'stock_available']
        
        if available_notifications:
            await self._send_aggregated_notifications(available_notifications)
        
        # 清空待发送列表
        self._pending_notifications.clear()
        self._last_aggregation_time = datetime.now()
    
    async def _send_aggregated_notifications(self, notifications: List[Dict]) -> None:
        """发送聚合通知"""
        if len(notifications) == 1:
            # 单个通知
            item = notifications[0]['item']
            confidence = notifications[0]['confidence']
            
            user_info = await self.db_manager.get_user(item.user_id)
            user_display = "未知用户"
            if user_info:
                user_display = user_info.username or user_info.first_name or f"用户{item.user_id}"
            
            message = (
                f"🟢 **有货提醒**\n\n"
                f"📝 **商品:** {item.name}\n"
                f"👤 **添加者:** {user_display}\n"
                f"🔗 **链接:** {item.url}\n"
                f"🎯 **置信度:** {confidence:.2f}\n"
                f"🕐 **检测时间:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"🧠 **检测方法:** 智能组合算法"
            )
        else:
            # 批量通知
            message = f"🟢 **批量有货提醒** ({len(notifications)}个商品)\n\n"
            
            for i, notification in enumerate(notifications[:5], 1):
                item = notification['item']
                confidence = notification['confidence']
                user_info = await self.db_manager.get_user(item.user_id)
                user_display = user_info.username if user_info and user_info.username else f"用户{item.user_id}"
                
                message += f"{i}. **{item.name}**\n"
                message += f"   👤 {user_display} | 🎯 {confidence:.2f}\n"
                message += f"   🔗 {item.url}\n\n"
            
            if len(notifications) > 5:
                message += f"...还有 {len(notifications) - 5} 个商品有货\n\n"
            
            message += f"🕐 **检测时间:** {datetime.now().strftime('%H:%M:%S')}"
        
        # 发送给所有管理员
        for admin_id in self.config_manager.config.admin_ids:
            await self.telegram_bot.send_notification(message, parse_mode='Markdown', chat_id=admin_id)
        
        # 记录通知历史
        for notification in notifications:
            item = notification['item']
            await self.db_manager.add_notification_history(
                user_id=item.user_id,
                monitor_id=item.id,
                message=message,
                notification_type='stock_alert'
            )
    
    async def stop(self) -> None:
        """停止监控"""
        print("🛑 正在停止监控系统...")
        self._running = False
        if self.stock_checker:
            self.stock_checker.close()
        if self.telegram_bot:
            await self.telegram_bot.shutdown()
        self.logger.info("监控程序已停止")
        print("✅ 监控程序已停止")
