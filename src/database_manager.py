"""
数据库版本的数据管理器
支持SQLite和可选的PostgreSQL/MySQL
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
class MonitorItem:
    """监控项数据类"""
    id: str
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


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "vps_monitor.db"):
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> None:
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            await self._create_tables(db)
            await self._create_indexes(db)
            await db.commit()
        
        self.logger.info("数据库初始化完成")
    
    async def _create_tables(self, db: aiosqlite.Connection) -> None:
        """创建数据表"""
        
        # 监控项表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitor_items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                config TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                last_checked TEXT DEFAULT '',
                status INTEGER DEFAULT NULL,
                notification_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                enabled INTEGER DEFAULT 1
            )
        """)
        
        # 检查历史表
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
                FOREIGN KEY (monitor_id) REFERENCES monitor_items (id)
            )
        """)
        
        # 配置表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 统计表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS statistics (
                date TEXT PRIMARY KEY,
                total_checks INTEGER DEFAULT 0,
                successful_checks INTEGER DEFAULT 0,
                failed_checks INTEGER DEFAULT 0,
                notifications_sent INTEGER DEFAULT 0,
                unique_items_checked INTEGER DEFAULT 0
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection) -> None:
        """创建索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_monitor_items_url ON monitor_items(url)",
            "CREATE INDEX IF NOT EXISTS idx_monitor_items_enabled ON monitor_items(enabled)",
            "CREATE INDEX IF NOT EXISTS idx_check_history_monitor_id ON check_history(monitor_id)",
            "CREATE INDEX IF NOT EXISTS idx_check_history_check_time ON check_history(check_time)",
            "CREATE INDEX IF NOT EXISTS idx_statistics_date ON statistics(date)"
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
    
    async def add_monitor_item(self, name: str, url: str, config: str = "", tags: List[str] = None) -> str:
        """添加监控项"""
        item_id = str(int(datetime.now().timestamp() * 1000))
        created_at = datetime.now().isoformat()
        tags_json = json.dumps(tags or [])
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO monitor_items 
                (id, name, url, config, created_at, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item_id, name, url, config, created_at, tags_json))
            await db.commit()
        
        self.logger.info(f"添加监控项: {name} - {url}")
        return item_id
    
    async def get_monitor_items(self, enabled_only: bool = True) -> Dict[str, MonitorItem]:
        """获取所有监控项"""
        items = {}
        
        sql = "SELECT * FROM monitor_items"
        if enabled_only:
            sql += " WHERE enabled = 1"
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql) as cursor:
                async for row in cursor:
                    item = MonitorItem(
                        id=row[0],
                        name=row[1],
                        url=row[2],
                        config=row[3],
                        created_at=row[4],
                        last_checked=row[5],
                        status=None if row[6] is None else bool(row[6]),
                        notification_count=row[7],
                        success_count=row[8],
                        failure_count=row[9],
                        last_error=row[10],
                        tags=row[11],
                        enabled=bool(row[12])
                    )
                    items[item.id] = item
        
        return items
    
    async def get_monitor_item_by_url(self, url: str) -> Optional[MonitorItem]:
        """根据URL获取监控项"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM monitor_items WHERE url = ?", (url,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return MonitorItem(
                        id=row[0],
                        name=row[1],
                        url=row[2],
                        config=row[3],
                        created_at=row[4],
                        last_checked=row[5],
                        status=None if row[6] is None else bool(row[6]),
                        notification_count=row[7],
                        success_count=row[8],
                        failure_count=row[9],
                        last_error=row[10],
                        tags=row[11],
                        enabled=bool(row[12])
                    )
        return None
    
    async def update_monitor_item_status(self, item_id: str, status: bool, 
                                       notification_count: int = None,
                                       error_message: str = "") -> None:
        """更新监控项状态"""
        last_checked = datetime.now().isoformat()
        
        sql = """
            UPDATE monitor_items 
            SET status = ?, last_checked = ?, last_error = ?
        """
        params = [status, last_checked, error_message]
        
        if notification_count is not None:
            sql += ", notification_count = ?"
            params.append(notification_count)
        
        # 更新成功/失败计数
        if status:
            sql += ", success_count = success_count + 1"
        else:
            sql += ", failure_count = failure_count + 1"
        
        sql += " WHERE id = ?"
        params.append(item_id)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, params)
            await db.commit()
    
    async def remove_monitor_item(self, url: str) -> bool:
        """删除监控项"""
        async with aiosqlite.connect(self.db_path) as db:
            # 首先获取item_id
            async with db.execute("SELECT id FROM monitor_items WHERE url = ?", (url,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return False
                
                item_id = row[0]
            
            # 删除相关的历史记录
            await db.execute("DELETE FROM check_history WHERE monitor_id = ?", (item_id,))
            
            # 删除监控项
            await db.execute("DELETE FROM monitor_items WHERE id = ?", (item_id,))
            await db.commit()
            
            self.logger.info(f"删除监控项: {url}")
            return True
    
    async def add_check_history(self, monitor_id: str, status: Optional[bool],
                              response_time: float, error_message: str = "",
                              http_status: int = 0, content_length: int = 0) -> None:
        """添加检查历史记录"""
        check_time = datetime.now().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO check_history 
                (monitor_id, check_time, status, response_time, error_message, http_status, content_length)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (monitor_id, check_time, status, response_time, error_message, http_status, content_length))
            await db.commit()
    
    async def get_check_history(self, monitor_id: str = None, 
                              days: int = 7, limit: int = 100) -> List[CheckHistory]:
        """获取检查历史记录"""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        sql = """
            SELECT * FROM check_history 
            WHERE check_time >= ?
        """
        params = [since_date]
        
        if monitor_id:
            sql += " AND monitor_id = ?"
            params.append(monitor_id)
        
        sql += " ORDER BY check_time DESC LIMIT ?"
        params.append(limit)
        
        history = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, params) as cursor:
                async for row in cursor:
                    history.append(CheckHistory(
                        id=row[0],
                        monitor_id=row[1],
                        check_time=row[2],
                        status=None if row[3] is None else bool(row[3]),
                        response_time=row[4],
                        error_message=row[5],
                        http_status=row[6],
                        content_length=row[7]
                    ))
        
        return history
    
    async def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """获取统计信息"""
        since_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            # 总体统计
            stats = {}
            
            # 检查次数统计
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_checks,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as successful_checks,
                    COUNT(CASE WHEN status = 0 THEN 1 END) as failed_checks,
                    AVG(response_time) as avg_response_time
                FROM check_history 
                WHERE check_time >= ?
            """, (since_date,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats.update({
                        'total_checks': row[0],
                        'successful_checks': row[1],
                        'failed_checks': row[2],
                        'avg_response_time': round(row[3] or 0, 2)
                    })
            
            # 监控项统计
            async with db.execute("""
                SELECT 
                    COUNT(*) as total_items,
                    COUNT(CASE WHEN enabled = 1 THEN 1 END) as enabled_items,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as items_in_stock,
                    COUNT(CASE WHEN status = 0 THEN 1 END) as items_out_of_stock
                FROM monitor_items
            """) as cursor:
                row = await cursor.fetchone()
                if row:
                    stats.update({
                        'total_items': row[0],
                        'enabled_items': row[1],
                        'items_in_stock': row[2],
                        'items_out_of_stock': row[3]
                    })
            
            # 每日统计趋势
            daily_stats = []
            async with db.execute("""
                SELECT 
                    DATE(check_time) as date,
                    COUNT(*) as checks,
                    COUNT(CASE WHEN status = 1 THEN 1 END) as successful,
                    COUNT(DISTINCT monitor_id) as unique_items
                FROM check_history 
                WHERE check_time >= ?
                GROUP BY DATE(check_time)
                ORDER BY date DESC
                LIMIT 30
            """, (since_date,)) as cursor:
                async for row in cursor:
                    daily_stats.append({
                        'date': row[0],
                        'checks': row[1],
                        'successful': row[2],
                        'unique_items': row[3]
                    })
            
            stats['daily_trends'] = daily_stats
            
            return stats
    
    async def cleanup_old_history(self, days: int = 90) -> int:
        """清理旧的历史记录"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM check_history WHERE check_time < ?", 
                (cutoff_date,)
            )
            deleted_count = cursor.rowcount
            await db.commit()
        
        self.logger.info(f"清理了 {deleted_count} 条历史记录")
        return deleted_count
    
    async def backup_database(self, backup_path: str) -> bool:
        """备份数据库"""
        try:
            async with aiosqlite.connect(self.db_path) as source:
                async with aiosqlite.connect(backup_path) as backup:
                    await source.backup(backup)
            
            self.logger.info(f"数据库备份完成: {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"数据库备份失败: {e}")
            return False
    
    async def export_to_json(self, file_path: str) -> bool:
        """导出数据到JSON格式"""
        try:
            data = {
                'monitor_items': [],
                'exported_at': datetime.now().isoformat()
            }
            
            items = await self.get_monitor_items(enabled_only=False)
            for item in items.values():
                item_data = asdict(item)
                # 获取最近的历史记录
                history = await self.get_check_history(item.id, days=30, limit=50)
                item_data['recent_history'] = [asdict(h) for h in history]
                data['monitor_items'].append(item_data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"数据导出完成: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"数据导出失败: {e}")
            return False
    
    async def import_from_json(self, file_path: str) -> bool:
        """从JSON文件导入数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item_data in data.get('monitor_items', []):
                # 检查是否已存在
                existing = await self.get_monitor_item_by_url(item_data['url'])
                if existing:
                    self.logger.warning(f"跳过已存在的URL: {item_data['url']}")
                    continue
                
                # 添加监控项
                await self.add_monitor_item(
                    name=item_data['name'],
                    url=item_data['url'],
                    config=item_data.get('config', ''),
                    tags=json.loads(item_data.get('tags', '[]'))
                )
            
            self.logger.info(f"数据导入完成: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"数据导入失败: {e}")
            return False


# 使用示例
async def example_usage():
    """使用示例"""
    db_manager = DatabaseManager("vps_monitor.db")
    
    # 初始化数据库
    await db_manager.initialize()
    
    # 添加监控项
    item_id = await db_manager.add_monitor_item(
        name="Racknerd 2G VPS",
        url="https://example.com/vps",
        config="2GB RAM, 20GB SSD",
        tags=["vps", "racknerd", "budget"]
    )
    
    # 获取所有监控项
    items = await db_manager.get_monitor_items()
    print(f"监控项数量: {len(items)}")
    
    # 更新状态
    await db_manager.update_monitor_item_status(item_id, True, 1)
    
    # 添加检查历史
    await db_manager.add_check_history(
        monitor_id=item_id,
        status=True,
        response_time=1.5,
        http_status=200,
        content_length=5000
    )
    
    # 获取统计信息
    stats = await db_manager.get_statistics(days=7)
    print(f"统计信息: {stats}")
    
    # 清理旧数据
    await db_manager.cleanup_old_history(days=30)
    
    # 备份数据库
    await db_manager.backup_database("backup.db")


if __name__ == "__main__":
    asyncio.run(example_usage())
