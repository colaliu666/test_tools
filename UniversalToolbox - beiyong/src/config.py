import pathlib
import sys
import importlib
import inspect
import os

# --- 核心配置 ---

# 应用程序的根目录，通常是 main_app.py 所在的目录
APP_DIR = pathlib.Path(__file__).parent
PLUGINS_DIR = APP_DIR / "plugins"

# --- 日志和安全调用 ---

def log(*args):
    """
    默认日志函数。在 ToolboxApp 启动后，它会被重定向到 GUI 的 Log Console。
    启动前，它直接打印到标准输出。
    """
    print(f"[LOG] {' '.join(str(a) for a in args)}")


def safe_call(func, *args, **kwargs):
    """
    安全地执行一个函数，捕获并记录所有异常，防止插件错误导致主程序崩溃。
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        import traceback
        log(f"[ERROR] Safe call failed on {func.__name__}: {e}")
        log(traceback.format_exc())
        return None

# --- 插件发现逻辑 ---

def discover_plugins():
    """
    发现并尝试重载 'plugins' 目录下的所有 Python 模块。
    返回 [(name, module, meta), ...] 列表。
    """
    plugins = []
    
    if not PLUGINS_DIR.is_dir():
        log(f"[WARNING] 插件目录不存在: {PLUGINS_DIR}")
        return plugins
        
    # 确保插件目录在 sys.path 中，以便 import_module 能够找到它
    if str(PLUGINS_DIR) not in sys.path:
        sys.path.insert(0, str(PLUGINS_DIR))

    for item in PLUGINS_DIR.iterdir():
        # 仅处理有效的 Python 模块 (.py 文件)，忽略私有文件
        if item.suffix == ".py" and not item.name.startswith('_'):
            module_name = item.stem
            
            try:
                # 关键：使用 importlib.reload 实现动态重载
                if module_name in sys.modules:
                    # 尝试重载已导入的模块
                    module = importlib.reload(sys.modules[module_name])
                    log(f"Reloaded module: {module_name}")
                else:
                    # 首次导入模块
                    module = importlib.import_module(module_name)
                    
                # 检查模块是否包含注册函数
                if hasattr(module, 'register'):
                    # 提取插件元数据
                    meta = getattr(module, 'PLUGIN_META', {'name': module_name, 'version': '1.0'})
                    plugins.append((module_name, module, meta))
                
            except Exception as e:
                # 记录加载失败的插件
                import traceback
                log(f"[ERROR] 无法加载插件 {module_name}: {e}")
                log(traceback.format_exc())
                
    # 清理 sys.path，避免污染
    if str(PLUGINS_DIR) in sys.path:
        sys.path.remove(str(PLUGINS_DIR))

    return plugins