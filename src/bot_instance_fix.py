#!/usr/bin/env python3
"""
Bot实例冲突修复补丁
解决多个Bot实例同时运行的问题
"""

import os
import sys
import signal
import psutil
import fcntl
import atexit
import logging
from pathlib import Path
from typing import Optional


class SingletonBot:
    """确保只有一个Bot实例运行的管理器"""
    
    def __init__(self, lock_file: str = "/tmp/vps_monitor_bot.lock"):
        self.lock_file = lock_file
        self.lock_fd = None
        self.logger = logging.getLogger(__name__)
    
    def acquire_lock(self) -> bool:
        """获取进程锁"""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            atexit.register(self.release_lock)
            return True
        except IOError:
            if self.lock_fd:
                self.lock_fd.close()
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
    
    def kill_existing_bot(self) -> bool:
        """终止现有的Bot进程"""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # 检查进程是否存在
                try:
                    old_process = psutil.Process(old_pid)
                    # 检查是否是Python进程
                    if 'python' in old_process.name().lower():
                        self.logger.info(f"发现旧的Bot进程 PID: {old_pid}，正在终止...")
                        old_process.terminate()
                        old_process.wait(timeout=5)
                        return True
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    pass
        except Exception as e:
            self.logger.error(f"终止旧进程失败: {e}")
        
        return False
    
    def check_and_fix_conflicts(self) -> bool:
        """检查并修复冲突"""
        # 尝试获取锁
        if self.acquire_lock():
            self.logger.info("成功获取进程锁，没有其他实例在运行")
            return True
        
        # 如果获取锁失败，尝试终止旧进程
        self.logger.warning("检测到另一个Bot实例正在运行")
        
        if self.kill_existing_bot():
            # 等待一下让旧进程完全退出
            import time
            time.sleep(2)
            
            # 再次尝试获取锁
            if self.acquire_lock():
                self.logger.info("成功终止旧进程并获取锁")
                return True
        
        return False


def setup_signal_handlers():
    """设置信号处理器"""
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在优雅关闭...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def patch_telegram_bot(bot_instance):
    """修补Telegram Bot实例"""
    original_stop = bot_instance.stop
    
    async def safe_stop():
        """安全停止Bot"""
        try:
            # 先停止接收更新
            if hasattr(bot_instance, 'updater') and bot_instance.updater:
                await bot_instance.updater.stop()
            
            # 关闭应用
            if hasattr(bot_instance, 'app') and bot_instance.app:
                await bot_instance.app.stop()
                await bot_instance.app.shutdown()
            
            # 调用原始stop方法
            await original_stop()
        except Exception as e:
            logging.error(f"停止Bot时出错: {e}")
    
    bot_instance.stop = safe_stop


# 修改后的main_monitor.py启动代码
async def safe_start_monitor():
    """安全启动监控器"""
    from main_monitor import VPSMonitor
    
    # 创建单例管理器
    singleton = SingletonBot()
    
    # 检查并修复冲突
    if not singleton.check_and_fix_conflicts():
        print("❌ 无法启动：另一个Bot实例正在运行且无法终止")
        print("请手动终止旧进程后重试")
        print("可以使用以下命令查找进程：")
        print("  ps aux | grep 'python.*monitor'")
        sys.exit(1)
    
    # 设置信号处理器
    setup_signal_handlers()
    
    # 创建并启动监控器
    monitor = VPSMonitor()
    
    # 修补telegram_bot以确保优雅关闭
    if hasattr(monitor, 'telegram_bot'):
        patch_telegram_bot(monitor.telegram_bot)
    
    try:
        await monitor.start()
    except Exception as e:
        print(f"❌ 监控器运行失败: {e}")
        raise
    finally:
        # 确保释放锁
        singleton.release_lock()


# 添加到main.py的修改
def patch_main_py():
    """修补main.py文件"""
    main_py_content = '''#!/usr/bin/env python3
"""
VPS监控系统 v3.1 - 多用户智能监控版
作者: kure29
网站: https://kure29.com
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加源码目录到Python路径
src_path = Path(__file__).parent / 'src'
if src_path.exists():
    sys.path.insert(0, str(src_path))

from utils import setup_project_paths
from bot_instance_fix import safe_start_monitor, SingletonBot

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vps_monitor.log'),
        logging.StreamHandler()
    ]
)

async def main():
    """主函数"""
    try:
        # 设置项目路径
        setup_project_paths()
        
        # 使用安全启动
        await safe_start_monitor()
        
    except KeyboardInterrupt:
        print("\\n程序被用户中断")
    except Exception as e:
        print(f"程序运行失败: {e}")
        logging.error(f"程序运行失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    return main_py_content


# 快速修复脚本
if __name__ == "__main__":
    print("🔧 VPS监控Bot实例冲突修复工具")
    print("-" * 40)
    
    # 检查是否有其他Python进程在运行监控程序
    current_pid = os.getpid()
    monitor_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] != current_pid and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info.get('cmdline', []))
                if any(keyword in cmdline for keyword in ['monitor', 'VPSMonitor', 'telegram_bot']):
                    monitor_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if monitor_processes:
        print(f"⚠️  发现 {len(monitor_processes)} 个可能的监控进程：")
        for proc in monitor_processes:
            print(f"   PID: {proc.pid} - {' '.join(proc.cmdline()[:3])}")
        
        answer = input("\n是否终止这些进程？(y/n): ")
        if answer.lower() == 'y':
            for proc in monitor_processes:
                try:
                    print(f"终止进程 {proc.pid}...")
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception as e:
                    print(f"终止进程 {proc.pid} 失败: {e}")
            print("✅ 清理完成")
        else:
            print("❌ 取消操作")
    else:
        print("✅ 没有发现其他监控进程")
    
    print("\n💡 修复建议：")
    print("1. 将此文件保存到 src/bot_instance_fix.py")
    print("2. 修改 main.py 使用安全启动方法")
    print("3. 确保只有一个Bot实例在运行")
    print("\n使用方法：")
    print("python main.py")
