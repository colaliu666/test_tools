import tkinter as tk
from tkinter import ttk, messagebox
# 导入 ttkbootstrap 的常量和样式
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import re

# ------------------------------------------------
# 0. Plugin Metadata (插件元数据)
# ------------------------------------------------
name = "HEX Toolkit: Space & Math" 
PLUGIN_NAME = name
__version__ = "1.0.0"

# -------------------- 独立工具函数 --------------------
# 这些函数不直接操作 UI，可以放在 register 外部以保持代码整洁

def _remove_spaces(text):
    """去除所有空格和换行符"""
    return text.replace(" ", "").replace("\n", "").replace("\r", "")

def _add_spaces(text, interval):
    """按指定间隔添加空格"""
    clean = _remove_spaces(text)
    try:
        interval = int(interval)
    except ValueError:
        return clean
    if interval <= 0:
        return clean
        
    # 按间隔切片并用空格连接
    return " ".join(clean[i:i+interval] for i in range(0, len(clean), interval))

# ------------------------------------------------
# 1. Plugin Entry Point (插件入口函数)
# ------------------------------------------------
def register(app, parent_frame):
    """
    将脚本注册为 Universal Toolbox 的插件。
    app: 主应用实例，用于访问日志、状态栏等。
    parent_frame: 插件UI的容器 frame。
    """
    # 清空容器 frame，确保插件干净加载
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # --- 状态变量定义 (Local Scoped Variables) ---
    mode = tk.StringVar(value="remove")
    space_interval = tk.StringVar(value="4")

    # --- 核心 UI 交互函数定义 ---
    # 定义在内部以访问局部变量 (e.g., input_text, space_interval_box)

    def convert_spaces():
        """执行空格的添加或移除操作"""
        text = input_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("警告", "请输入数据")
            return
            
        if mode.get() == "remove":
            result = _remove_spaces(text)
        else:
            try:
                interval = int(space_interval.get())
            except ValueError:
                messagebox.showerror("错误", "无效的间隔值")
                return
            result = _add_spaces(text, interval)
            
        output_text.delete("1.0", tk.END)
            # 确保只插入非空结果，防止输出框中出现意外的空行
        if result:
            output_text.insert(tk.END, result)
        app.update_status(f"Space conversion completed. Mode: {mode.get()}")


    def mode_changed():
        """根据模式切换间隔输入框的状态"""
        # 必须使用 config(state=...)，因为 ttkbootstrap 的 Combobox 继承自 ttk.Entry
        space_interval_box.config(state="readonly" if mode.get() == "add" else "disabled")


    def calculate_groups():
        """批量计算 4 字节 HEX 值并换算为角度"""
        raw = group_input.get("1.0", tk.END).strip()
        clean = _remove_spaces(raw).upper()
        
        if not clean:
            messagebox.showwarning("提示", "请输入 HEX 数据")
            return
        # 检查是否为 8 的倍数（4字节 = 8位HEX字符）
        if len(clean) % 8 != 0:
            messagebox.showerror("错误", f"HEX 长度必须是 8 的倍数（每 4 字节一组），当前长度：{len(clean)}")
            return
        if not re.fullmatch(r"[0-9A-F]*", clean):
            messagebox.showerror("错误", "输入包含非法 HEX 字符 (A-F, 0-9)")
            return

        # 清空表格
        for row in result_table.get_children():
            result_table.delete(row)
        
        # 批量处理
        error_flag = False
        for i in range(0, len(clean), 8):
            block = clean[i:i+8]
            try:
                # 假设这是大端序或根据需要处理字节序
                dec_value = int(block, 16)
                # 应用公式：(value - 20000) / 1000
                calc_value = (dec_value - 20000) / 1000
                result_table.insert("", "end", values=(i//8 + 1, block, dec_value, f"{calc_value:.6f}"))
            except ValueError:
                messagebox.showerror("错误", f"HEX 块 '{block}' 无法转换为整数")
                error_flag = True
                break
        
        if not error_flag:
            app.update_status(f"Calculated {len(clean)//8} 4-byte groups successfully.")
            
    # -------------------- UI 布局开始 --------------------

    # 顶级容器替换为 parent_frame
    ttk.Label(parent_frame, text="HEX 工具套装：专业版", 
              font=("Segoe UI", 24, "bold"), 
              bootstyle="primary").pack(pady=10)

    # 主分栏窗口
    main_pane = ttk.Panedwindow(parent_frame, orient=tk.VERTICAL) 
    main_pane.pack(fill="both", expand=True, padx=10, pady=5)

    # ---------- 1. 空格处理 ----------
    # 已修正: 使用 Labelframe (小写 f)
    frame_space = ttk.Labelframe(main_pane, text="1. 空格处理工具", padding=15, bootstyle="secondary")
    main_pane.add(frame_space, weight=1)

    # 模式选择
    frame_mode = ttk.Frame(frame_space)
    frame_mode.pack(pady=5)
    ttk.Radiobutton(frame_mode, text="去除空格 (Remove)", variable=mode, value="remove", command=mode_changed, bootstyle="info").grid(row=0, column=0, padx=20)
    ttk.Radiobutton(frame_mode, text="按位添加空格 (Add)", variable=mode, value="add", command=mode_changed, bootstyle="info").grid(row=0, column=1, padx=20)

    # 间隔设置
    frame_bit = ttk.Frame(frame_space)
    frame_bit.pack(pady=10)
    ttk.Label(frame_bit, text="每 N 位添加空格:").grid(row=0, column=0, padx=5)
    
    # 必须在此处定义 space_interval_box
    space_interval_box = ttk.Combobox(frame_bit, values=["2","3","4","5","6","8"], width=5, textvariable=space_interval, state="disabled", bootstyle="info")
    space_interval_box.grid(row=0, column=1, padx=5)

    ttk.Label(frame_space, text="输入数据:").pack(padx=10, anchor='w')
    input_text = tk.Text(frame_space, height=5, font=('Consolas', 11))
    input_text.pack(fill="x", padx=10, pady=5)

    ttk.Button(frame_space, text="执行转换 (Convert)", command=convert_spaces, bootstyle="success").pack(pady=10)

    ttk.Label(frame_space, text="转换结果:").pack(padx=10, anchor='w')
    output_text = tk.Text(frame_space, height=5, font=('Consolas', 11))
    output_text.pack(fill="x", padx=10, pady=5)
    
    # 初始化状态
    mode_changed()

    # ---------- 2. 四字节批量计算 ----------
    # 已修正: 使用 Labelframe (小写 f)
    frame_group = ttk.Labelframe(main_pane, text="2. 4 字节批量换算 (camera 角度: (value-20000)/1000)", padding=15, bootstyle="primary")
    main_pane.add(frame_group, weight=2)

    ttk.Label(frame_group, text="输入 HEX 数据（每 4 字节一组，即 8 位字符）:").pack(padx=10, anchor='w')
    group_input = tk.Text(frame_group, height=6, font=('Consolas', 11))
    group_input.pack(fill="x", padx=10, pady=5)

    ttk.Button(frame_group, text="开始批量计算 (Calculate)", command=calculate_groups, bootstyle="warning").pack(pady=10)

    # 表格
    columns = ("序号", "HEX (4 Byte)", "十进制", "换算结果")
    result_table = ttk.Treeview(frame_group, columns=columns, show="headings", height=10, bootstyle="info")
    
    # 配置列
    column_widths = {"序号": 50, "HEX (4 Byte)": 100, "十进制": 120, "换算结果": 150}
    for col, width in column_widths.items():
        result_table.heading(col, text=col)
        result_table.column(col, anchor="center", width=width, stretch=False)
        
    result_table.pack(fill="both", expand=True, padx=10, pady=10)

    app.update_status(f"HEX Toolkit Plugin loaded successfully.")