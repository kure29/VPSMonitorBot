#!/usr/bin/env python3
"""
Telegram机器人模块
VPS监控系统 v3.1
"""

import re
import logging
import asyncio
import cloudscraper
import psutil
import os
from datetime import datetime
from typing import List, Dict, Any
from config import Config
from database_manager import DatabaseManager, User, MonitorItem
from utils import is_valid_url, calculate_success_rate, escape_markdown
from monitors import SmartComboMonitor

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)


class TelegramBot:
    """Telegram机器人（多用户增强版）"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self.app = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """初始化机器人"""
        try:
            self.app = Application.builder().token(self.config.bot_token).build()
            await self.app.initialize()
            bot_info = await self.app.bot.get_me()
            self.logger.info(f"Telegram Bot 初始化成功: @{bot_info.username}")
            print(f"✅ Telegram Bot连接成功: @{bot_info.username}")
            
            self._setup_handlers()
            await self.app.start()
            await self.app.updater.start_polling()
            
        except Exception as e:
            self.logger.error(f"Telegram Bot 初始化失败: {e}")
            raise
    
    def _setup_handlers(self) -> None:
        """设置命令处理器"""
        handlers = [
            CommandHandler("start", self._start_command),
            CommandHandler("help", self._help_command),
            CommandHandler("list", self._list_command),
            CommandHandler("add", self._add_command),
            CommandHandler("status", self._status_command),
            CommandHandler("stats", self._stats_command),
            CommandHandler("debug", self._debug_command),
            CommandHandler("admin", self._admin_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            CallbackQueryHandler(self._handle_callback)
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    def _check_admin_permission(self, user_id: str) -> bool:
        """检查管理员权限"""
        if not self.config.admin_ids:
            return True
        return str(user_id) in self.config.admin_ids
    
    async def _get_user_info(self, update: Update) -> User:
        """获取用户信息并更新数据库"""
        user = update.effective_user
        return await self.db_manager.add_or_update_user(
            user_id=str(user.id),
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or ""
        )
    
    # ===== 基础命令处理器 =====
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        user_info = await self._get_user_info(update)
        
        if user_info.is_banned:
            await update.message.reply_text("❌ 您已被管理员禁用，无法使用此服务")
            return
        
        await self._show_main_menu(update.message, user_info, edit_message=False)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        help_text = (
            "🤖 **VPS监控机器人 v3.1 帮助**\n\n"
            
            "📱 **基础功能:**\n"
            "• `/start` - 显示主菜单\n"
            "• `/list` - 查看您的监控列表\n"
            "• `/add <URL>` - 添加监控项目\n"
            "• `/help` - 显示此帮助信息\n\n"
            
            "🔍 **调试功能:**\n"
            "• `/debug <URL>` - 调试分析单个URL\n\n"
            
            "🚀 **v3.1 新特性:**\n"
            "• 🧠 智能组合监控算法\n"
            "• 🎯 多重检测方法验证\n"
            "• 📊 置信度评分系统\n"
            "• 👥 多用户支持\n"
            "• 🛡️ 主流VPS商家适配\n"
            "• 🧩 完整的管理员工具\n"
            "• 🔧 集成调试功能\n\n"
            
            "💡 **使用提示:**\n"
            "• 支持主流VPS商家自动优化\n"
            "• 智能检测算法自动选择最佳方法\n"
            "• 所有用户都可以添加监控\n"
            "• 库存变化会推送给管理员\n"
            "• 每日添加限制：50个商品\n\n"
            
            "👨‍💻 **开发者信息:**\n"
            "作者: kure29\n"
            "网站: https://kure29.com"
        )
        
        if self._check_admin_permission(str(update.effective_user.id)):
            help_text += (
                "\n\n🧩 **管理员专用:**\n"
                "• `/admin` - 管理员控制面板\n"
                "• 全局监控管理\n"
                "• 用户行为统计\n"
                "• 系统配置管理\n"
                "• 调试工具集成"
            )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def _list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /list 命令"""
        user_info = await self._get_user_info(update)
        if user_info.is_banned:
            await update.message.reply_text("❌ 您已被禁用")
            return
        
        await self._show_monitor_list(update.message, user_info.id, 0, edit_message=False)
    
    async def _add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /add 命令"""
        user_info = await self._get_user_info(update)
        if user_info.is_banned:
            await update.message.reply_text("❌ 您已被禁用")
            return
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "📝 **添加监控使用方法:**\n\n"
                "`/add <URL> [名称]`\n\n"
                "例如:\n"
                "`/add https://example.com/vps 测试VPS`\n"
                "`/add https://example.com/product`\n\n"
                "💡 如果不指定名称，将自动提取页面标题",
                parse_mode='Markdown'
            )
            return
        
        url = context.args[0]
        name = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        await self._add_monitor_item(update.message, user_info.id, url, name)
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /status 命令"""
        user_info = await self._get_user_info(update)
        await self._show_user_statistics(update.message, user_info.id)
    
    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /stats 命令"""
        user_info = await self._get_user_info(update)
        await self._show_user_statistics(update.message, user_info.id)
    
    async def _debug_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /debug 命令"""
        user_info = await self._get_user_info(update)
        
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔍 **调试命令使用方法:**\n\n"
                "`/debug <URL>`\n\n"
                "例如: `/debug https://example.com/product`\n\n"
                "此命令会详细分析页面并显示各种检测方法的结果",
                parse_mode='Markdown'
            )
            return
        
        url = context.args[0]
        if not is_valid_url(url)[0]:
            await update.message.reply_text("❌ URL格式无效")
            return
        
        await self._debug_url(update.message, url)
    
    async def _admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /admin 命令"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            await update.message.reply_text("❌ 只有管理员才能使用此功能")
            return
        
        await self._show_admin_panel(update.message)
    
    # ===== 菜单和界面显示 =====
    
    async def _show_main_menu(self, message_or_query, user_info: User, edit_message: bool = False) -> None:
        """显示主菜单"""
        is_admin = self._check_admin_permission(user_info.id)
        
        keyboard = [
            [
                InlineKeyboardButton("📝 我的监控", callback_data=f'list_items_{user_info.id}_0'),
                InlineKeyboardButton("➕ 添加监控", callback_data='add_item')
            ],
            [
                InlineKeyboardButton("📈 我的统计", callback_data='my_stats'),
                InlineKeyboardButton("❓ 帮助", callback_data='help')
            ]
        ]
        
        if is_admin:
            keyboard.append([
                InlineKeyboardButton("🧩 管理员工具", callback_data='admin_panel')
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_display = user_info.username or user_info.first_name or "未知用户"
        
        welcome_text = (
            f"👋 欢迎，{user_display}！\n\n"
            "🤖 **VPS 监控机器人 v3.1**\n"
            "🧠 智能多重检测算法\n\n"
            
            f"📊 **您的统计:**\n"
            f"• 监控项目: {user_info.total_monitors} 个\n"
            f"• 通知次数: {user_info.total_notifications} 次\n"
            f"• 今日添加: {user_info.daily_add_count} 个\n\n"
            
            "🆕 **v3.1 特色:**\n"
            "• 🎯 高精度库存检测\n"
            "• 🧠 智能算法组合\n"
            "• 📊 置信度评分\n"
            "• 👥 多用户共享\n"
            "• 🛡️ 服务商优化\n"
            "• 🧩 完整管理工具"
        )
        
        if is_admin:
            welcome_text += "\n\n🧩 您是管理员，可使用管理功能"
        
        if edit_message:
            await message_or_query.edit_message_text(welcome_text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _show_monitor_list(self, message_or_query, user_id: str, page: int = 0, edit_message: bool = True) -> None:
        """显示监控列表"""
        items = await self.db_manager.get_monitor_items(user_id=user_id, include_global=True)
        
        if not items:
            text = "📝 **您的监控列表**\n\n❌ 还没有监控项目\n\n💡 点击下方按钮添加您的第一个监控项目"
            keyboard = [[InlineKeyboardButton("➕ 添加监控", callback_data='add_item')]]
        else:
            items_list = list(items.values())
            total_pages = (len(items_list) + self.config.items_per_page - 1) // self.config.items_per_page
            start_idx = page * self.config.items_per_page
            end_idx = start_idx + self.config.items_per_page
            page_items = items_list[start_idx:end_idx]
            
            text = f"📝 **您的监控列表** (第 {page + 1}/{total_pages} 页)\n\n"
            
            keyboard = []
            for i, item in enumerate(page_items, start=start_idx + 1):
                status_emoji = "🟢" if item.status else "🔴" if item.status is False else "⚪"
                global_mark = "🌐" if item.is_global else ""
                name = item.name[:25] + "..." if len(item.name) > 25 else item.name
                
                text += f"{i}. {status_emoji} {global_mark}{name}\n"
                text += f"   📊 成功率: {calculate_success_rate(item)}\n"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{i}. {name[:15]}...", 
                        callback_data=f'item_detail_{item.id}'
                    )
                ])
            
            # 分页按钮
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ 上页", callback_data=f'list_items_{user_id}_{page-1}'))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️ 下页", callback_data=f'list_items_{user_id}_{page+1}'))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([
                InlineKeyboardButton("➕ 添加监控", callback_data='add_item'),
                InlineKeyboardButton("🔄 刷新", callback_data=f'list_items_{user_id}_{page}')
            ])
        
        keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await message_or_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(text, reply_markup=reply_markup)
    
    async def _show_admin_panel(self, message_or_query, edit_message: bool = False) -> None:
        """显示管理员面板"""
        # 获取全局统计
        stats = await self.db_manager.get_global_statistics()
        
        text = (
            "🧩 **管理员控制面板**\n\n"
            
            f"👥 **用户统计:**\n"
            f"• 总用户数: {stats.get('users', {}).get('total', 0)}\n"
            f"• 活跃用户: {stats.get('users', {}).get('active', 0)}\n"
            f"• 被封用户: {stats.get('users', {}).get('banned', 0)}\n\n"
            
            f"📊 **监控统计:**\n"
            f"• 总监控项: {stats.get('monitor_items', {}).get('total', 0)}\n"
            f"• 启用项目: {stats.get('monitor_items', {}).get('enabled', 0)}\n"
            f"• 全局项目: {stats.get('monitor_items', {}).get('global', 0)}\n"
            f"• 有货项目: {stats.get('monitor_items', {}).get('in_stock', 0)}\n\n"
            
            f"🔍 **检查统计:**\n"
            f"• 总检查次数: {stats.get('checks', {}).get('total', 0)}\n"
            f"• 成功检查: {stats.get('checks', {}).get('successful', 0)}\n"
            f"• 平均响应: {stats.get('checks', {}).get('avg_response_time', 0)}s\n"
            f"• 平均置信度: {stats.get('checks', {}).get('avg_confidence', 0)}\n"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👥 用户管理", callback_data='admin_users'),
                InlineKeyboardButton("📊 全局监控", callback_data='admin_monitors')
            ],
            [
                InlineKeyboardButton("📈 详细统计", callback_data='admin_stats'),
                InlineKeyboardButton("📊 系统状态", callback_data='admin_system_status')
            ],
            [
                InlineKeyboardButton("🔧 调试工具", callback_data='admin_debug'),
                InlineKeyboardButton("⚙️ 系统配置", callback_data='admin_config')
            ],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await message_or_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(text, reply_markup=reply_markup)
    
    # ===== 核心功能实现 =====
    
    async def _add_monitor_item(self, message, user_id: str, url: str, name: str = "") -> None:
        """添加监控项目"""
        # 验证URL
        is_valid, error_msg = is_valid_url(url)
        if not is_valid:
            await message.reply_text(f"❌ {error_msg}")
            return
        
        # 检查用户状态
        user = await self.db_manager.get_user(user_id)
        if user and user.is_banned:
            await message.reply_text("❌ 您已被禁用，无法添加监控")
            return
        
        # 检查每日限制
        if user and user.daily_add_count >= self.config.daily_add_limit:
            today = datetime.now().date().isoformat()
            if user.last_add_date == today:
                await message.reply_text(f"❌ 今日添加数量已达上限 ({self.config.daily_add_limit})")
                return
        
        adding_msg = await message.reply_text("⏳ 正在添加监控项...")
        
        try:
            # 如果没有提供名称，尝试获取页面标题
            if not name:
                try:
                    smart_monitor = SmartComboMonitor(self.config)
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: smart_monitor.scraper.get(url, timeout=10)
                    )
                    
                    if response and response.status_code == 200:
                        title_match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
                        if title_match:
                            name = title_match.group(1).strip()[:50]
                    
                    smart_monitor.close()
                except:
                    pass
                
                if not name:
                    name = f"监控项目 {datetime.now().strftime('%m-%d %H:%M')}"
            
            # 添加到数据库
            item_id, success = await self.db_manager.add_monitor_item(
                user_id=user_id,
                name=name,
                url=url,
                config="",
                tags=[],
                is_global=False
            )
            
            if success:
                await adding_msg.edit_text(
                    f"✅ **监控添加成功**\n\n"
                    f"📝 名称: {name}\n"
                    f"🔗 URL: {url}\n"
                    f"🆔 ID: {item_id}\n\n"
                    f"🔍 系统将在下次检查周期中开始监控此项目\n"
                    f"📱 库存变化时会推送通知给管理员"
                )
                
                # 通知管理员
                for admin_id in self.config.admin_ids:
                    await self.send_notification(
                        message=f"📝 新增监控项\n\n"
                                f"👤 用户: {user.username or user.first_name or user_id}\n"
                                f"📝 名称: {name}\n"
                                f"🔗 URL: {url}",
                        chat_id=admin_id
                    )
            else:
                await adding_msg.edit_text("❌ 添加失败，可能URL已存在或达到限制")
                
        except Exception as e:
            await adding_msg.edit_text(f"❌ 添加失败: {str(e)}")
            self.logger.error(f"添加监控项失败: {e}")
    
    async def _debug_url(self, message, url: str) -> None:
        """调试URL分析"""
        checking_msg = await message.reply_text("🔍 正在进行详细分析...")
        
        try:
            smart_monitor = SmartComboMonitor(self.config)
            result = await smart_monitor.comprehensive_check(url)
            
            debug_text = f"🔍 **调试分析结果**\n\n"
            debug_text += f"🔗 **URL:** {url}\n"
            debug_text += f"📊 **最终状态:** {result.get('final_status')}\n"
            debug_text += f"🎯 **置信度:** {result.get('confidence', 0):.2f}\n\n"
            
            # 显示各种方法的结果
            methods = result.get('methods', {})
            
            for method_name, method_result in methods.items():
                debug_text += f"**{method_name.upper()}检查:**\n"
                
                if 'error' in method_result:
                    debug_text += f"❌ 错误: {method_result['error']}\n"
                elif 'status' in method_result:
                    status = method_result['status']
                    if status is True:
                        debug_text += "✅ 有货\n"
                    elif status is False:
                        debug_text += "❌ 无货\n"
                    else:
                        debug_text += "⚪ 未知\n"
                    
                    if 'message' in method_result:
                        debug_text += f"💬 详情: {method_result['message']}\n"
                else:
                    debug_text += f"📋 结果: {method_result}\n"
                
                debug_text += "\n"
            
            # 建议
            confidence = result.get('confidence', 0)
            if confidence < 0.3:
                debug_text += "💡 **建议:** 检测置信度很低，可能需要手动验证\n"
            elif confidence < 0.6:
                debug_text += "💡 **建议:** 检测置信度中等，建议观察多次检查结果\n"
            else:
                debug_text += "💡 **建议:** 检测置信度较高，结果相对可靠\n"
            
            smart_monitor.close()
            
            await checking_msg.edit_text(debug_text, parse_mode='Markdown')
            
        except Exception as e:
            await checking_msg.edit_text(f"❌ 调试分析失败: {str(e)}")
    
    # ===== 统计和状态显示 =====
    
    async def _show_user_statistics(self, message, user_id: str) -> None:
        """显示用户统计"""
        try:
            stats = await self.db_manager.get_user_statistics(user_id)
            
            user_info = stats.get('user_info', {})
            monitor_info = stats.get('monitor_items', {})
            activities = stats.get('recent_activities', {})
            
            stats_text = (
                f"📈 **个人统计信息**\n\n"
                
                f"👤 **基本信息:**\n"
                f"• 用户名: {user_info.get('username', '未设置')}\n"
                f"• 注册时间: {user_info.get('created_at', '').split('T')[0] if user_info.get('created_at') else '未知'}\n"
                f"• 总监控数: {user_info.get('total_monitors', 0)}\n"
                f"• 总通知数: {user_info.get('total_notifications', 0)}\n\n"
                
                f"📊 **监控项目:**\n"
                f"• 总数: {monitor_info.get('total', 0)}\n"
                f"• 启用: {monitor_info.get('enabled', 0)}\n"
                f"• 有货: {monitor_info.get('in_stock', 0)}\n"
                f"• 全局项目: {monitor_info.get('global_items', 0)}\n\n"
                
                "🎯 **近期活动:**\n"
            )
            
            if activities:
                for action, count in list(activities.items())[:5]:
                    action_name = {
                        'add_monitor': '添加监控',
                        'remove_monitor': '删除监控',
                        'user_login': '登录使用'
                    }.get(action, action)
                    stats_text += f"• {action_name}: {count} 次\n"
            else:
                stats_text += "• 暂无活动记录\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 刷新", callback_data='my_stats')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            
            await message.reply_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            await message.reply_text(f"❌ 获取统计信息失败: {str(e)}")
    
    # ===== 消息处理器 =====
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本消息"""
        user_info = await self._get_user_info(update)
        if user_info.is_banned:
            return
        
        text = update.message.text.strip()
        
        # 检查是否是URL
        if text.startswith(('http://', 'https://')):
            await self._add_monitor_item(update.message, user_info.id, text)
        else:
            # 提供帮助信息
            await update.message.reply_text(
                "💡 **快速添加监控:**\n"
                "直接发送URL即可添加监控\n\n"
                "📋 **其他操作:**\n"
                "• 使用 /start 查看菜单\n"
                "• 使用 /help 查看帮助\n"
                "• 使用 /list 查看监控列表"
            )
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理回调查询"""
        query = update.callback_query
        user_info = await self._get_user_info(update)
        
        if user_info.is_banned:
            await query.answer("您已被禁用")
            return
        
        data = query.data
        
        try:
            if data == 'main_menu':
                await self._show_main_menu(query, user_info, edit_message=True)
            
            elif data == 'add_item':
                await query.edit_message_text(
                    "📝 **添加监控项目**\n\n"
                    "请发送以下格式的消息:\n"
                    "`/add <URL> [名称]`\n\n"
                    "或者直接发送URL，系统会自动提取页面标题作为名称\n\n"
                    "例如:\n"
                    "`/add https://example.com/vps 测试VPS`\n"
                    "`https://example.com/product`",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')
                    ]])
                )
            
            elif data.startswith('list_items_'):
                parts = data.split('_')
                target_user_id = parts[2]
                page = int(parts[3])
                await self._show_monitor_list(query, target_user_id, page, edit_message=True)
            
            elif data == 'my_stats':
                await self._show_user_statistics(query.message, user_info.id)
            
            elif data == 'help':
                await self._help_command(update, context)
            
            elif data == 'admin_panel':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_panel(query, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            # 处理管理员面板的子菜单
            elif data == 'admin_users':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_users(query, 0, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data == 'admin_monitors':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_monitors(query, 0, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data == 'admin_stats':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_detailed_stats(query, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data == 'admin_system_status':
                if self._check_admin_permission(user_info.id):
                    await self._show_system_status(query, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data == 'admin_debug':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_debug_tools(query, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data == 'admin_config':
                if self._check_admin_permission(user_info.id):
                    await self._show_admin_config(query, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            # 处理管理员分页
            elif data.startswith('admin_users_page_'):
                if self._check_admin_permission(user_info.id):
                    page = int(data.split('_')[3])
                    await self._show_admin_users(query, page, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data.startswith('admin_monitors_page_'):
                if self._check_admin_permission(user_info.id):
                    page = int(data.split('_')[3])
                    await self._show_admin_monitors(query, page, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            # 处理管理员操作
            elif data == 'admin_cleanup':
                if self._check_admin_permission(user_info.id):
                    cleanup_stats = await self.db_manager.cleanup_old_data(90)
                    await query.answer(f"清理完成！删除了 {sum(cleanup_stats.values())} 条旧记录", show_alert=True)
                    await self._show_admin_debug_tools(query, edit_message=True)
                else:
                    await query.answer("您没有管理员权限")
            
            elif data == 'admin_export_logs':
                if self._check_admin_permission(user_info.id):
                    await query.answer("日志导出功能开发中...", show_alert=True)
                else:
                    await query.answer("您没有管理员权限")
            
            await query.answer()
            
        except Exception as e:
            self.logger.error(f"处理回调查询失败: {e}")
            await query.answer("操作失败，请重试")
    
    # ===== 管理员功能实现 =====
    
    async def _show_admin_users(self, query, page: int = 0, edit_message: bool = True) -> None:
        """显示用户管理界面"""
        users = await self.db_manager.get_all_users(include_banned=True)
        
        if not users:
            text = "👥 **用户管理**\n\n❌ 暂无用户"
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin_panel')]]
        else:
            total_pages = (len(users) + 10 - 1) // 10
            start_idx = page * 10
            end_idx = start_idx + 10
            page_users = users[start_idx:end_idx]
            
            text = f"👥 **用户管理** (第 {page + 1}/{total_pages} 页)\n\n"
            
            for user in page_users:
                status = "🚫" if user.is_banned else ("👑" if user.is_admin else "👤")
                display_name = user.username or user.first_name or f"用户{user.id}"
                text += f"{status} {display_name}\n"
                text += f"   ID: `{user.id}` | 监控: {user.total_monitors}\n"
            
            keyboard = []
            
            # 分页按钮
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f'admin_users_page_{page-1}'))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f'admin_users_page_{page+1}'))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🔙 返回", callback_data='admin_panel')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _show_admin_monitors(self, query, page: int = 0, edit_message: bool = True) -> None:
        """显示全局监控管理"""
        items = await self.db_manager.get_monitor_items(enabled_only=False)
        
        if not items:
            text = "📊 **全局监控管理**\n\n❌ 暂无监控项目"
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='admin_panel')]]
        else:
            items_list = list(items.values())
            total_pages = (len(items_list) + 10 - 1) // 10
            start_idx = page * 10
            end_idx = start_idx + 10
            page_items = items_list[start_idx:end_idx]
            
            text = f"📊 **全局监控管理** (第 {page + 1}/{total_pages} 页)\n\n"
            
            for i, item in enumerate(page_items, start=start_idx + 1):
                status_emoji = "🟢" if item.status else "🔴" if item.status is False else "⚪"
                global_mark = "🌐" if item.is_global else ""
                enabled_mark = "✅" if item.enabled else "❌"
                
                # 获取用户信息
                user = await self.db_manager.get_user(item.user_id)
                user_display = user.username if user and user.username else f"用户{item.user_id}"
                
                text += f"{i}. {status_emoji}{enabled_mark} {global_mark}{item.name[:20]}\n"
                text += f"   👤 {user_display} | 📊 成功率: {calculate_success_rate(item)}\n"
            
            keyboard = []
            
            # 分页按钮
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f'admin_monitors_page_{page-1}'))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f'admin_monitors_page_{page+1}'))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            keyboard.append([InlineKeyboardButton("🔙 返回", callback_data='admin_panel')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await query.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _show_admin_detailed_stats(self, query, edit_message: bool = True) -> None:
        """显示详细统计"""
        stats = await self.db_manager.get_global_statistics(days=30)
        
        text = (
            "📈 **详细统计信息** (30天)\n\n"
            
            "👥 **用户统计:**\n"
            f"• 总用户数: {stats.get('users', {}).get('total', 0)}\n"
            f"• 活跃用户: {stats.get('users', {}).get('active', 0)}\n"
            f"• 管理员: {stats.get('users', {}).get('admin', 0)}\n"
            f"• 被封用户: {stats.get('users', {}).get('banned', 0)}\n\n"
            
            "📊 **监控统计:**\n"
            f"• 总监控项: {stats.get('monitor_items', {}).get('total', 0)}\n"
            f"• 启用项目: {stats.get('monitor_items', {}).get('enabled', 0)}\n"
            f"• 全局项目: {stats.get('monitor_items', {}).get('global', 0)}\n"
            f"• 有货项目: {stats.get('monitor_items', {}).get('in_stock', 0)}\n\n"
            
            "🔍 **检查统计:**\n"
            f"• 总检查次数: {stats.get('checks', {}).get('total', 0)}\n"
            f"• 成功检查: {stats.get('checks', {}).get('successful', 0)}\n"
            f"• 平均响应时间: {stats.get('checks', {}).get('avg_response_time', 0)}s\n"
            f"• 平均置信度: {stats.get('checks', {}).get('avg_confidence', 0)}\n\n"
            
            "🏆 **活跃用户TOP 5:**\n"
        )
        
        top_users = stats.get('top_users', [])[:5]
        for i, user in enumerate(top_users, 1):
            text += f"{i}. {user['username']} - {user['activity_count']}次活动\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 刷新", callback_data='admin_stats')],
            [InlineKeyboardButton("🔙 返回", callback_data='admin_panel')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await query.reply_text(text, reply_markup=reply_markup)
    
    async def _show_system_status(self, query, edit_message: bool = True) -> None:
        """显示系统状态"""
        # 获取系统信息
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 获取进程信息
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss / 1024 / 1024  # MB
        process_cpu = process.cpu_percent(interval=1)
        
        # 获取数据库大小
        db_size = 0
        if self.db_manager.db_path.exists():
            db_size = self.db_manager.db_path.stat().st_size / 1024 / 1024  # MB
        
        text = (
            "📊 **系统状态**\n\n"
            
            "🖥️ **系统资源:**\n"
            f"• CPU使用率: {cpu_percent}%\n"
            f"• 内存使用: {memory.percent}% ({memory.used // 1024 // 1024}MB / {memory.total // 1024 // 1024}MB)\n"
            f"• 磁盘使用: {disk.percent}% ({disk.used // 1024 // 1024 // 1024}GB / {disk.total // 1024 // 1024 // 1024}GB)\n\n"
            
            "🤖 **进程信息:**\n"
            f"• 进程CPU: {process_cpu}%\n"
            f"• 进程内存: {process_memory:.1f}MB\n"
            f"• 数据库大小: {db_size:.1f}MB\n\n"
            
            "⚙️ **配置信息:**\n"
            f"• 检查间隔: {self.config.check_interval}秒\n"
            f"• 通知聚合: {self.config.notification_aggregation_interval}秒\n"
            f"• 通知冷却: {self.config.notification_cooldown}秒\n"
            f"• 置信度阈值: {self.config.confidence_threshold}\n"
            f"• 每日添加限制: {self.config.daily_add_limit}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 刷新", callback_data='admin_system_status')],
            [InlineKeyboardButton("🔙 返回", callback_data='admin_panel')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await query.reply_text(text, reply_markup=reply_markup)
    
    async def _show_admin_debug_tools(self, query, edit_message: bool = True) -> None:
        """显示调试工具"""
        text = (
            "🔧 **调试工具**\n\n"
            
            "🔍 **可用工具:**\n"
            "• `/debug <URL>` - 调试分析单个URL\n"
            "• 显示各种检测方法的结果\n"
            "• 查看置信度评分\n"
            "• 分析失败原因\n\n"
            
            "📝 **使用说明:**\n"
            "1. 直接使用 `/debug` 命令\n"
            "2. 提供要测试的URL\n"
            "3. 系统会返回详细分析结果\n\n"
            
            "🛠️ **其他功能:**\n"
            "• 数据库清理\n"
            "• 日志查看\n"
            "• 性能分析\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("🗑️ 清理旧数据", callback_data='admin_cleanup')],
            [InlineKeyboardButton("📋 导出日志", callback_data='admin_export_logs')],
            [InlineKeyboardButton("🔙 返回", callback_data='admin_panel')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await query.reply_text(text, reply_markup=reply_markup)
    
    async def _show_admin_config(self, query, edit_message: bool = True) -> None:
        """显示系统配置"""
        text = (
            "⚙️ **系统配置**\n\n"
            
            "🔧 **当前配置:**\n"
            f"• Selenium: {'✅ 启用' if self.config.enable_selenium else '❌ 禁用'}\n"
            f"• API发现: {'✅ 启用' if self.config.enable_api_discovery else '❌ 禁用'}\n"
            f"• 视觉对比: {'✅ 启用' if self.config.enable_visual_comparison else '❌ 禁用'}\n"
            f"• 服务商优化: {'✅ 启用' if self.config.enable_vendor_optimization else '❌ 禁用'}\n\n"
            
            "📊 **限制设置:**\n"
            f"• 检查间隔: {self.config.check_interval}秒\n"
            f"• 通知聚合: {self.config.notification_aggregation_interval}秒\n"
            f"• 通知冷却: {self.config.notification_cooldown}秒\n"
            f"• 请求超时: {self.config.request_timeout}秒\n"
            f"• 重试延迟: {self.config.retry_delay}秒\n"
            f"• 每日添加限制: {self.config.daily_add_limit}个\n"
            f"• 置信度阈值: {self.config.confidence_threshold}\n\n"
            
            "💡 **提示:**\n"
            "配置文件位于: config.json\n"
            "重启程序后生效"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='admin_panel')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if edit_message:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await query.reply_text(text, reply_markup=reply_markup)
    
    # ===== 通知功能 =====
    
    async def send_notification(self, message: str, parse_mode: str = None, chat_id: str = None) -> None:
        """发送通知"""
        try:
            if self.app and self.app.bot:
                target_chat_id = chat_id or self.config.channel_id or self.config.chat_id
                
                await self.app.bot.send_message(
                    chat_id=target_chat_id, 
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False
                )
                self.logger.info(f"通知发送成功到 {target_chat_id}")
        except Exception as e:
            self.logger.error(f"发送通知失败: {e}")
    
    async def shutdown(self) -> None:
        """关闭机器人"""
        try:
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                self.logger.info("Telegram Bot已关闭")
        except Exception as e:
            self.logger.error(f"关闭机器人失败: {e}")
