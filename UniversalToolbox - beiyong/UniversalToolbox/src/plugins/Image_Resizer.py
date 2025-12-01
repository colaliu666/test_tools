import tkinter as tk
from tkinter import ttk, messagebox
# 导入 ttkbootstrap 的常量和样式
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
# 导入所需的库，例如 Pillow (PIL)
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 插件名称 (主程序会用这个名字来显示和查找)
name = "Image_Resizer"
PLUGIN_NAME = name

# --- 插件主 UI/逻辑类 ---
class ImageResizerUI:
    """图片尺寸调整插件的 UI 和逻辑类"""
    def __init__(self, app, parent_frame):
        self.app = app
        self.parent = parent_frame
        
        # 假设所有依赖都已满足
        self._create_ui()

    def _create_ui(self):
        # 清空父容器，确保干净加载
        for widget in self.parent.winfo_children():
            widget.destroy()
            
        ttk.Label(self.parent, text="图片尺寸调整工具", 
                  font=("Segoe UI", 24, "bold"), 
                  bootstyle="primary").pack(anchor="w", padx=15, pady=15)
        
        # 您的插件 UI 元素将在这里
        # ...
        
        ttk.Label(self.parent, text="TODO: 实现选择文件和调整逻辑").pack(padx=15, pady=10)

        # 如果依赖缺失，可以禁用按钮或显示警告
        if not HAS_PIL:
            ttk.Label(self.parent, 
                      text="🔴 依赖缺失: 请运行 pip install Pillow 安装依赖以启用此插件", 
                      bootstyle="danger").pack(padx=15, pady=10)
        else:
            ttk.Label(self.parent, 
                      text="✅ 依赖已安装: Pillow 库已找到，可以开始构建功能。", 
                      bootstyle="success").pack(padx=15, pady=10)
            

# --- 插件入口点 (必需) ---
def register(app, parent_frame):
    """
    主程序加载插件时调用的函数。
    app: 主应用程序实例 (ToolboxApp)
    parent_frame: 插件内容应该放置在其内部的容器 (ttk.Frame)
    """
    # 清空容器 frame，确保插件干净加载
    for widget in parent_frame.winfo_children():
        widget.destroy()
        
    # 创建插件 UI 实例
    ImageResizerUI(app, parent_frame)

    # 记录插件加载状态，使用 app.update_status
    status_message = f"插件 {name} 注册完成。"
    if not HAS_PIL:
        status_message += "警告: Pillow 依赖缺失。"
    
    app.update_status(status_message)