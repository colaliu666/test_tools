import sys
import os
import pathlib
import tkinter as tk
import ttkbootstrap as tb

# 1. 将项目根目录添加到 sys.path
# 确保可以进行绝对导入： import src.config, import src.main_app
PROJECT_ROOT = pathlib.Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
print(f"Project Root Added to Path: {PROJECT_ROOT}")

try:
    # 2. 尝试导入主应用
    import src.main_app as main_app
except ImportError as e:
    print("--- FATAL ERROR ---")
    print("Failed to import src.main_app. Make sure src/ is in the correct location.")
    print(f"Details: {e}")
    # 尝试打印 sys.path 帮助调试
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


def main():
    """初始化并运行主应用程序。"""
    
    # 使用 ttkbootstrap 的父类 tk.Tk 创建根窗口
    root = tb.Window(themename="superhero") 
    root.title("Universal Toolbox")
    
    try:
        app = main_app.ToolboxApp(root)
        
        # 3. 启动 Tkinter 主循环
        # 在主循环启动前强制处理一下日志（防止启动信息丢失）
        app.redirect_log() 
        print("Starting main loop...")
        
        root.mainloop()

    except Exception as e:
        print(f"An unexpected error occurred during application startup: {e}")
        # 如果应用崩溃，确保控制台信息能够显示
        if sys.stdout != sys.__stdout__ and hasattr(sys.__stdout__, 'write'):
            sys.__stdout__.write(f"\nFATAL ERROR: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()