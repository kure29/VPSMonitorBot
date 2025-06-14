#!/usr/bin/env python3
"""
VPS监控系统 v3.1 - 多用户智能监控版（改进版）
作者: kure29
网站: https://kure29.com
"""

import asyncio
import logging
import sys
import os
import signal
import fcntl
import atexit
from pathlib import Path
from datetime import datetime

# 添加源码目录到Python路径
src_path = Path(__file__).parent / 'src'
if src_path.exists():
    sys.path.insert(0, str(src_path))

from utils import setup_project_paths
from main_monitor import VPSMonitor


class BotInstanceManager:
    """Bot实例管理器，确保只有一个实例运行"""
    
    def __init__(self):
        self.lock_file = "/tmp/vps_monitor_bot.lock"
        self.lock_fd = None
        self.monitor = None
        self.logger = logging.getLogger(__name__)
    
    def acquire_lock(self) -> bool:
        """获取进程锁"""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(f"{os.getpid()}\n{datetime.now().isoformat()}")
            self.lock_fd.flush()
            return True
        except IOError:
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            return False
    
    def release_lock(self):
        """释放进程锁"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                self.lock_fd.close()
                os.remove(self.lock_file)
            except:
                pass
            finally:
                self.lock_fd = None
    
    def check_existing_instance(self) -> tuple[bool, str]:
        """检查是否有其他实例在运行"""
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, 'r') as f:
                    content = f.read().strip().split('\n')
                    pid = int(content[0]) if content else 0
                    start_time = content[1] if len(content) > 1 else "未知"
                
                # 检查进程是否真的存在
                try:
                    os.kill(pid, 0)  # 发送空信号测试进程是否存在
                    return True, f"PID: {pid}, 启动时间: {start_time}"
                except OSError:
                    # 进程不存在，清理锁文件
                    os.remove(self.lock_file)
                    return False, ""
            except:
                return False, ""
        return False, ""
    
    async def start_monitor(self):
        """启动监控器"""
        self.monitor = VPSMonitor()
        
        # 注册清理函数
        atexit.register(self.cleanup)
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            await self.monitor.start()
        except Exception as e:
            self.logger.error(f"监控器运行失败: {e}")
            raise
        finally:
            await self.cleanup_async()
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        print(f"\n收到信号 {signum}，正在优雅关闭...")
        asyncio.create_task(self.cleanup_async())
        sys.exit(0)
    
    async def cleanup_async(self):
        """异步清理资源"""
        try:
            if self.monitor:
                print("正在停止监控器...")
                await self.monitor.stop()
                self.monitor = None
        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")
        finally:
            self.release_lock()
    
    def cleanup(self):
        """同步清理资源（用于atexit）"""
        self.release_lock()


async def main():
    """主函数"""
    manager = BotInstanceManager()
    
    try:
        # 设置项目路径
        setup_project_paths()
        
        print("=" * 60)
        print("🚀 VPS监控系统 v3.1 - 多用户智能监控版")
        print("=" * 60)
        
        # 检查是否有其他实例在运行
        has_instance, info = manager.check_existing_instance()
        if has_instance:
            print(f"❌ 检测到另一个监控实例正在运行")
            print(f"   {info}")
            print("\n解决方案：")
            print("1. 等待当前实例完成")
            print("2. 运行 'python quick_fix.py' 强制清理")
            print("3. 手动终止进程: kill <PID>")
            return
        
        # 尝试获取锁
        if not manager.acquire_lock():
            print("❌ 无法获取进程锁，可能有另一个实例正在启动")
            return
        
        print("✅ 进程锁获取成功")
        print(f"📝 PID: {os.getpid()}")
        print(f"🕐 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)
        
        # 启动监控
        await manager.start_monitor()
        
    except KeyboardInterrupt:
        print("\n⚠️  收到中断信号，正在优雅关闭...")
    except Exception as e:
        print(f"\n❌ 程序运行失败: {e}")
        logging.error(f"程序运行失败: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # 确保清理资源
        manager.cleanup()
        print("\n👋 程序已退出")


if __name__ == "__main__":
    # 设置日志
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 创建logs目录
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(logs_dir / f'vps_monitor_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )
    
    # 运行主程序
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
