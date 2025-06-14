"""
多用户版本的数据库管理器
支持用户管理、权限控制、统计分析
"""

import sqlite3
import asyncio
import aiosqlite
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class User:
    """用户数据类"""
    id: str
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    is_admin: bool = False
    is_banned: bool = False
    created_at: str = ""
    last_active: str = ""
    total_monitors: int = 0
    total_notifications: int = 0
    daily_add_count: int = 0
    last_add_date: str = ""


@dataclass
class MonitorItem:
    """监控项数据类"""
    id: str
    user_id: str
    name: str
    url: str
    config: str = ""
    created_at: str = ""
    last_checked: str = ""
    status: Optional[bool] = None
    notification_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: str = ""
    tags: str = ""  # JSON格式的标签
    enabled: bool = True
    is_global: bool = False  # 管理员添加的全局监控项


@dataclass
class CheckHistory:
    """检查历史记录"""
    id: int
    monitor_id: str
    check_time: str
    status: Optional[bool]
    response_time: float
    error_message: str = ""
    http_status: int = 0
    content_length: int = 0
    confidence: float = 0.0
    method_used: str = ""


class DatabaseManager:
    """多用户数据库管理器"""
    
    def __init__(self, db_path: str = "vps_monitor.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> None:
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await self._create_indexes(db)
            await self._migrate_old_data(db)
            await db.commit()
        
        self.logger.info("多用户数据库初始化完成")
    
    async def _create_tables(self, db: aiosqlite.Connection) -> None:
        """创建数据表"""
        
        # 用户表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                is_admin INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_active TEXT DEFAULT '',
                total_monitors INTEGER DEFAULT 0,
                total_notifications INTEGER DEFAULT 0,
                daily_add_count INTEGER DEFAULT 0,
                last_add_date TEXT DEFAULT ''
            )
        """)
        
        # 监控项表（增加用户ID和全局标记）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitor_items (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                config TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_checked TEXT DEFAULT '',
                status INTEGER DEFAULT NULL,
                notification_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1,
                is_global INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # 检查历史表（增加置信度和方法字段）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                monitor_id TEXT NOT NULL,
                check_time TEXT NOT NULL,
                status INTEGER DEFAULT NULL,
                response_time REAL DEFAULT 0,
                error_message TEXT DEFAULT '',
                http_status INTEGER DEFAULT 0,
                content_length INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0,
                method_used TEXT DEFAULT '',
                FOREIGN KEY (monitor_id) REFERENCES monitor_items (id)
            )
        """)
        
        # 通知历史表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                monitor_id TEXT NOT NULL,
                message TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                notification_type TEXT DEFAULT 'stock_alert',
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (monitor_id) REFERENCES monitor_items (id)
            )
        """)
        
        # 用户行为日志表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_data TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # 系统配置表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT DEFAULT ''
            )
        """)
        
        # 统计表（按日期和用户）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_statistics (
                date TEXT NOT NULL,
                user_id TEXT NOT NULL,
                checks_performed INTEGER DEFAULT 0,
                successful_checks INTEGER DEFAULT 0,
                failed_checks INTEGER DEFAULT 0,
                notifications_sent INTEGER DEFAULT 0,
                items_added INTEGER DEFAULT 0,
                items_removed INTEGER DEFAULT 0,
                PRIMARY KEY (date, user_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection) -> None:
        """创建索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_monitor_items_user_id ON monitor_items(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_monitor_items_url ON monitor_items(url)",
            "CREATE INDEX IF NOT EXISTS idx_monitor_items_enabled ON monitor_items(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_monitor_items_global ON monitor_items(is_global)",
            "CREATE INDEX IF NOT EXISTS idx_check_history_monitor_id ON check_history(monitor_id)",
            "CREATE INDEX IF NOT EXISTS idx_check_history_check_time ON check_history(check_time)",
            "CREATE INDEX IF NOT EXISTS idx_notification_history_user_id ON notification_history(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_user_actions_timestamp ON user_actions(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_daily_statistics_date ON daily_statistics(date)"
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
    
    async def _migrate_old_data(self, db: aiosqlite.Connection) -> None:
        """迁移旧版本数据"""
        try:
            # 检查是否有旧的monitor_items表结构
            cursor = await db.execute("PRAGMA table_info(monitor_items)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'user_id' not in column_names:
                self.logger.info("检测到旧版本数据结构，开始迁移...")
                
                # 添加缺失的列
                await db.execute("ALTER TABLE monitor_items ADD COLUMN user_id TEXT DEFAULT 'system'")
                await db.execute("ALTER TABLE monitor_items ADD COLUMN is_global INTEGER DEFAULT 1")
                
                # 将所有现有数据标记为系统全局项目
                await db.execute("UPDATE monitor_items SET user_id = 'system', is_global = 1 WHERE user_id IS NULL")
                
                self.logger.info("数据迁移完成")
        except Exception as e:
            self.logger.warning(f"数据迁移过程中的警告: {e}")
    
    # ===== 用户管理方法 =====
    
    async def add_or_update_user(self, user_id: str, username: str = "", 
                               first_name: str = "", last_name: str = "") -> User:
        """添加或更新用户"""
        now = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            # 检查用户是否存在
            async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                # 更新用户信息
                await db.execute("""
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, last_active = ?
                    WHERE id = ?
                """, (username, first_name, last_name, now, user_id))
                
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=bool(existing[4]),
                    is_banned=bool(existing[5]),
                    created_at=existing[6],
                    last_active=now,
                    total_monitors=existing[8],
                    total_notifications=existing[9],
                    daily_add_count=existing[10],
                    last_add_date=existing[11]
                )
            else:
                # 创建新用户
                await db.execute("""
                    INSERT INTO users 
                    (id, username, first_name, last_name, created_at, last_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, now, now))
                
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    created_at=now,
                    last_active=now
                )
            
            await db.commit()
            
        await self._log_user_action(user_id, "user_login", f"用户活跃: {username}")
        return user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return User(
                        id=row[0],
                        username=row[1],
                        first_name=row[2],
                        last_name=row[3],
                        is_admin=bool(row[4]),
                        is_banned=bool(row[5]),
                        created_at=row[6],
                        last_active=row[7],
                        total_monitors=row[8],
                        total_notifications=row[9],
                        daily_add_count=row[10],
                        last_add_date=row[11]
                    )
        return None
    
    async def set_user_admin(self, user_id: str, is_admin: bool, admin_user_id: str = "") -> bool:
        """设置用户管理员状态"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?", 
                (1 if is_admin else 0, user_id)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                action_data = f"设置管理员权限: {is_admin}"
                await self._log_user_action(admin_user_id, "admin_set_user_admin", action_data)
                return True
        return False
    
    async def ban_user(self, user_id: str, is_banned: bool, admin_user_id: str = "") -> bool:
        """封禁/解封用户"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE users SET is_banned = ? WHERE id = ?", 
                (1 if is_banned else 0, user_id)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                action_data = f"用户封禁状态: {is_banned}"
                await self._log_user_action(admin_user_id, "admin_ban_user", action_data)
                return True
        return False
    
    async def update_user_ban_status(self, user_id: str, is_banned: bool) -> bool:
        """更新用户封禁状态（简化版本，供 telegram_bot 调用）"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "UPDATE users SET is_banned = ? WHERE id = ?",
                    (1 if is_banned else 0, user_id)
                )
                await db.commit()
                
                if cursor.rowcount > 0:
                    # 记录操作日志
                    action_data = f"用户封禁状态更新: {'封禁' if is_banned else '解封'}"
                    await self._log_user_action("system", "update_ban_status", action_data)
                    return True
                else:
                    self.logger.warning(f"未找到用户 {user_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"更新用户封禁状态失败: {e}")
            return False
    
    async def get_all_users(self, include_banned: bool = False) -> List[User]:
        """获取所有用户"""
        users = []
        sql = "SELECT * FROM users"
        if not include_banned:
            sql += " WHERE is_banned = 0"
        sql += " ORDER BY created_at DESC"
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql) as cursor:
                async for row in cursor:
                    users.append(User(
                        id=row[0],
                        username=row[1],
                        first_name=row[2],
                        last_name=row[3],
                        is_admin=bool(row[4]),
                        is_banned=bool(row[5]),
                        created_at=row[6],
                        last_active=row[7],
                        total_monitors=row[8],
                        total_notifications=row[9],
                        daily_add_count=row[10],
                        last_add_date=row[11]
                    ))
        return users
    
    # ===== 监控项管理方法 =====
    async def update_monitor_item_status(self, item_id: str, enabled: bool) -> bool:
        """更新监控项启用状态"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "UPDATE monitor_items SET enabled = ? WHERE id = ?",
                    (1 if enabled else 0, item_id)
                )
                await db.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"监控项 {item_id} 状态更新为: {'启用' if enabled else '禁用'}")
                    return True
                else:
                    self.logger.warning(f"未找到监控项 {item_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"更新监控项状态失败: {e}")
            return False
    
    async def add_monitor_item(self, user_id: str, name: str, url: str, 
                             config: str = "", tags: List[str] = None, 
                             is_global: bool = False) -> Tuple[str, bool]:
        """添加监控项"""
        # 检查用户是否被封禁
        user = await self.get_user(user_id)
        if user and user.is_banned:
            return "", False
        
        # 检查每日添加限制
        if not await self._check_daily_add_limit(user_id):
            return "", False
        
        item_id = str(int(datetime.now().timestamp() * 1000))
        created_at = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])
        
        async with aiosqlite.connect(self.db_path) as db:
            # 检查URL是否已存在（对于该用户）
            if not is_global:
                async with db.execute(
                    "SELECT id FROM monitor_items WHERE url = ? AND user_id = ?", 
                    (url, user_id)
                ) as cursor:
                    if await cursor.fetchone():
                        return "", False  # URL已存在
            
            await db.execute("""
                INSERT INTO monitor_items 
                (id, user_id, name, url, config, created_at, tags, is_global)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_id, user_id, name, url, config, created_at, tags_json, 1 if is_global else 0))
            
            # 更新用户统计
            await db.execute(
                "UPDATE users SET total_monitors = total_monitors + 1 WHERE id = ?", 
                (user_id,)
            )
            
            await db.commit()
        
        await self._update_daily_add_count(user_id)
        await self._log_user_action(user_id, "add_monitor", f"添加监控: {name} - {url}")
        
        self.logger.info(f"用户 {user_id} 添加监控项: {name} - {url}")
        return item_id, True
    
    async def get_monitor_items(self, user_id: str = None, enabled_only: bool = True, 
                          include_global: bool = True) -> Dict[str, MonitorItem]:
        """获取监控项"""
        items = {}
        
        sql = "SELECT * FROM monitor_items WHERE 1=1"
        params = []
        
        if enabled_only:
            sql += " AND enabled = 1"
        
        if user_id:
            if include_global:
                sql += " AND (user_id = ? OR is_global = 1)"
                params.append(user_id)
            else:
                sql += " AND user_id = ?"
                params.append(user_id)
        
        # 修改这里：改为升序排序（ASC），先添加的在前
        sql += " ORDER BY created_at ASC"
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, params) as cursor:
                async for row in cursor:
                    item = MonitorItem(
                        id=row[0],
                        user_id=row[1],
                        name=row[2],
                        url=row[3],
                        config=row[4],
                        created_at=row[5],
                        last_checked=row[6],
                        status=None if row[7] is None else bool(row[7]),
                        notification_count=row[8],
                        success_count=row[9],
                        failure_count=row[10],
                        last_error=row[11],
                        tags=row[12],
                        enabled=bool(row[13]),
                        is_global=bool(row[14])
                    )
                    items[item.id] = item
        
        return items
    
    async def remove_monitor_item(self, item_id: str, user_id: str, 
                                is_admin: bool = False) -> bool:
        """删除监控项"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查权限
            if is_admin:
                # 管理员可以删除任何项目
                async with db.execute("SELECT user_id FROM monitor_items WHERE id = ?", (item_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    original_user_id = row[0]
            else:
                # 普通用户只能删除自己的项目
                async with db.execute(
                    "SELECT user_id FROM monitor_items WHERE id = ? AND user_id = ?", 
                    (item_id, user_id)
                ) as cursor:
                    if not await cursor.fetchone():
                        return False
                    original_user_id = user_id
            
            # 删除相关记录
            await db.execute("DELETE FROM check_history WHERE monitor_id = ?", (item_id,))
            await db.execute("DELETE FROM notification_history WHERE monitor_id = ?", (item_id,))
            await db.execute("DELETE FROM monitor_items WHERE id = ?", (item_id,))
            
            # 更新用户统计
            await db.execute(
                "UPDATE users SET total_monitors = total_monitors - 1 WHERE id = ?", 
                (original_user_id,)
            )
            
            await db.commit()
        
        await self._log_user_action(user_id, "remove_monitor", f"删除监控项: {item_id}")
        return True
    
    # ===== 检查历史和统计方法 =====
    
    async def add_check_history(self, monitor_id: str, status: Optional[bool],
                              response_time: float, error_message: str = "",
                              http_status: int = 0, content_length: int = 0,
                              confidence: float = 0.0, method_used: str = "") -> None:
        """添加检查历史记录（增强版）"""
        check_time = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO check_history 
                (monitor_id, check_time, status, response_time, error_message, 
                 http_status, content_length, confidence, method_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (monitor_id, check_time, status, response_time, error_message, 
                  http_status, content_length, confidence, method_used))
            await db.commit()
    
    async def add_notification_history(self, user_id: str, monitor_id: str, 
                                     message: str, notification_type: str = "stock_alert") -> None:
        """添加通知历史"""
        sent_at = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO notification_history 
                (user_id, monitor_id, message, sent_at, notification_type)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, monitor_id, message, sent_at, notification_type))
            
            # 更新用户通知统计
            await db.execute(
                "UPDATE users SET total_notifications = total_notifications + 1 WHERE id = ?",
                (user_id,)
            )
            
            await db.commit()
    
    async def _log_user_action(self, user_id: str, action_type: str, action_data: str = "") -> None:
        """记录用户行为"""
        timestamp = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO user_actions (user_id, action_type, action_data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, action_type, action_data, timestamp))
            await db.commit()
    
    async def _check_daily_add_limit(self, user_id: str, limit: int = 50) -> bool:
        """检查每日添加限制"""
        today = datetime.now().date().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT daily_add_count, last_add_date FROM users WHERE id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return True
                
                daily_count, last_date = row[0], row[1]
                
                if last_date != today:
                    # 新的一天，重置计数
                    return True
                
                return daily_count < limit
    
    async def _update_daily_add_count(self, user_id: str) -> None:
        """更新每日添加计数"""
        today = datetime.now().date().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT daily_add_count, last_add_date FROM users WHERE id = ?
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    daily_count, last_date = row[0], row[1]
                    
                    if last_date == today:
                        new_count = daily_count + 1
                    else:
                        new_count = 1
                    
                    await db.execute("""
                        UPDATE users 
                        SET daily_add_count = ?, last_add_date = ? 
                        WHERE id = ?
                    """, (new_count, today, user_id))
                    await db.commit()
    
    # ===== 统计和分析方法 =====
    
    async def get_user_statistics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """获取用户统计信息"""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        stats = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            # 用户基本信息
            async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cursor:
                user_row = await cursor.fetchone()
                if user_row:
                    stats['user_info'] = {
                        'username': user_row[1],
                        'created_at': user_row[6],
                        'total_monitors': user_row[8],
                        'total_notifications': user_row[9]
                    }
            
            # 监控项统计
            async with db.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN enabled = 1 THEN 1 END) as enabled,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as in_stock,
                    COUNT(CASE WHEN is_global = 1 THEN 1 END) as global_items
                FROM monitor_items 
                WHERE user_id = ? OR is_global = 1
            """, (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats['monitor_items'] = {
                        'total': row[0],
                        'enabled': row[1],
                        'in_stock': row[2],
                        'global_items': row[3]
                    }
            
            # 最近活动统计
            async with db.execute("""
                SELECT 
                    action_type,
                    COUNT(*) as count
                FROM user_actions 
                WHERE user_id = ? AND timestamp >= ?
                GROUP BY action_type
                ORDER BY count DESC
            """, (user_id, since_date)) as cursor:
                activities = {}
                async for row in cursor:
                    activities[row[0]] = row[1]
                stats['recent_activities'] = activities
        
        return stats
    
    async def get_global_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取全局统计信息"""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        stats = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            # 用户统计
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN is_admin = 1 THEN 1 END) as admin_users,
                    COUNT(CASE WHEN is_banned = 1 THEN 1 END) as banned_users,
                    COUNT(CASE WHEN last_active >= ? THEN 1 END) as active_users
                FROM users
            """, (since_date,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats['users'] = {
                        'total': row[0],
                        'admin': row[1],
                        'banned': row[2],
                        'active': row[3]
                    }
            
            # 监控项统计
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_items,
                    COUNT(CASE WHEN enabled = 1 THEN 1 END) as enabled_items,
                    COUNT(CASE WHEN is_global = 1 THEN 1 END) as global_items,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as items_in_stock
                FROM monitor_items
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats['monitor_items'] = {
                        'total': row[0],
                        'enabled': row[1],
                        'global': row[2],
                        'in_stock': row[3]
                    }
            
            # 检查统计
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_checks,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as successful_checks,
                    AVG(response_time) as avg_response_time,
                    AVG(confidence) as avg_confidence
                FROM check_history 
                WHERE check_time >= ?
            """, (since_date,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats['checks'] = {
                        'total': row[0],
                        'successful': row[1],
                        'avg_response_time': round(row[2] or 0, 2),
                        'avg_confidence': round(row[3] or 0, 2)
                    }
            
            # 活跃用户排行
            async with db.execute("""
                SELECT 
                    u.username,
                    u.first_name,
                    COUNT(ua.id) as activity_count
                FROM users u
                LEFT JOIN user_actions ua ON u.id = ua.user_id 
                    AND ua.timestamp >= ?
                WHERE u.is_banned = 0
                GROUP BY u.id
                ORDER BY activity_count DESC
                LIMIT 10
            """, (since_date,)) as cursor:
                top_users = []
                async for row in cursor:
                    top_users.append({
                        'username': row[0] or row[1] or 'Unknown',
                        'activity_count': row[2]
                    })
                stats['top_users'] = top_users
        
        return stats
    
    # ===== 系统配置方法 =====
    
    async def set_system_config(self, key: str, value: str, updated_by: str = "") -> None:
        """设置系统配置"""
        updated_at = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO system_config (key, value, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
            """, (key, value, updated_at, updated_by))
            await db.commit()
    
    async def get_system_config(self, key: str, default_value: str = "") -> str:
        """获取系统配置"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM system_config WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default_value
    
    # ===== 数据维护方法 =====
    
    async def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """清理旧数据"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        cleanup_stats = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            # 清理旧的检查历史
            cursor = await db.execute(
                "DELETE FROM check_history WHERE check_time < ?", 
                (cutoff_date,)
            )
            cleanup_stats['check_history'] = cursor.rowcount
            
            # 清理旧的用户行为日志
            cursor = await db.execute(
                "DELETE FROM user_actions WHERE timestamp < ?", 
                (cutoff_date,)
            )
            cleanup_stats['user_actions'] = cursor.rowcount
            
            # 清理旧的通知历史
            cursor = await db.execute(
                "DELETE FROM notification_history WHERE sent_at < ?", 
                (cutoff_date,)
            )
            cleanup_stats['notification_history'] = cursor.rowcount
            
            await db.commit()
        
        self.logger.info(f"数据清理完成: {cleanup_stats}")
        return cleanup_stats
    
    async def clear_user_monitors(self, user_id: str, admin_user_id: str = "") -> int:
        """清空用户所有监控项（管理员功能）"""
        async with aiosqlite.connect(self.db_path) as db:
            # 获取要删除的监控项
            monitor_ids = []
            async with db.execute(
                "SELECT id FROM monitor_items WHERE user_id = ?", 
                (user_id,)
            ) as cursor:
                async for row in cursor:
                    monitor_ids.append(row[0])
            
            if monitor_ids:
                # 删除相关记录
                for monitor_id in monitor_ids:
                    await db.execute("DELETE FROM check_history WHERE monitor_id = ?", (monitor_id,))
                    await db.execute("DELETE FROM notification_history WHERE monitor_id = ?", (monitor_id,))
                
                # 删除监控项
                await db.execute("DELETE FROM monitor_items WHERE user_id = ?", (user_id,))
                
                # 重置用户监控计数
                await db.execute("UPDATE users SET total_monitors = 0 WHERE id = ?", (user_id,))
                
                await db.commit()
            
            await self._log_user_action(admin_user_id, "admin_clear_user_monitors", 
                                      f"清空用户 {user_id} 的所有监控项")
            
            return len(monitor_ids)


# 使用示例
async def example_usage():
    """多用户版本使用示例"""
    db_manager = DatabaseManager("vps_monitor.db")
    
    # 初始化数据库
    await db_manager.initialize()
    
    # 添加用户
    user = await db_manager.add_or_update_user(
        user_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User"
    )
    print(f"用户: {user.username}")
    
    # 添加监控项
    item_id, success = await db_manager.add_monitor_item(
        user_id="123456789",
        name="测试VPS",
        url="https://example.com/vps",
        config="2GB RAM, 20GB SSD",
        tags=["vps", "test"]
    )
    
    if success:
        print(f"监控项添加成功: {item_id}")
    
    # 获取用户统计
    stats = await db_manager.get_user_statistics("123456789")
    print(f"用户统计: {stats}")


if __name__ == "__main__":
    asyncio.run(example_usage())
