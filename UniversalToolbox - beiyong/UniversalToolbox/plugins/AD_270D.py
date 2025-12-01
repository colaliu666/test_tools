import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttkb

# ------------------------------------------------
# 0. Plugin Metadata (插件元数据)
# ------------------------------------------------
PLUGIN_NAME = "512 Bytes Fault Parser" 
__version__ = "1.0.0" 
PLUGIN_META = {
    'name': PLUGIN_NAME,
    'version': __version__,
    'description': '解析 512 字节的 HEX 字符串，根据内置的故障字典识别并列出所有置位的故障 ID。',
    'author': 'AI Assistant'
}

# ---------------- 内嵌 fault_info 数据 ----------------
fault_data = {
    "fault_info": [
        {"fault_id": 0, "fault_name": "Fault_0", "dtc_id": 0x01, "description": "描述0"},
        {"fault_id": 1, "fault_name": "Fault_1", "dtc_id": 0x02, "description": "描述1"},
        {"fault_id": 2, "fault_name": "Fault_2", "dtc_id": 0x03, "description": "描述2"},
        {"fault_id": 100, "fault_name": "Fault_100", "dtc_id": 0x64, "description": "示例故障"},
        # ⚠️ 注意：您可以在这里继续添加您的 JSON 故障内容
    ]
}

fault_dict = {f["fault_id"]: f for f in fault_data["fault_info"]}

# ---------------- 核心应用逻辑 (重构为插件模式) ----------------
class FaultParserApp:
    def __init__(self, parent_frame, app_instance):
        """
        初始化故障解析器 UI。
        parent_frame: 插件UI的容器 frame。
        app_instance: 主应用实例，用于日志和状态更新。
        """
        self.parent_frame = parent_frame
        self.app = app_instance
        
        # 确保容器 frame 填充空间
        self.main_container = ttkb.Frame(parent_frame, padding=15)
        self.main_container.pack(fill="both", expand=True)

        # 标题
        ttkb.Label(self.main_container, text=PLUGIN_NAME, 
                  font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(padx=10, pady=(0, 10), anchor="w")

        # 输入区域
        ttkb.Label(self.main_container, text="请输入 512 Bytes HEX 字符串（支持连续 HEX 或空格分隔）:", 
                   bootstyle="info").pack(padx=10, pady=(5, 0), anchor="w")
        
        self.text_input = tk.Text(self.main_container, height=8, font=('Consolas', 10))
        self.text_input.pack(fill="x", padx=10, pady=5)

        # 解析按钮
        self.parse_btn = ttkb.Button(self.main_container, text="🚀 开始解析故障", 
                                     command=self.parse_hex, bootstyle="success")
        self.parse_btn.pack(padx=10, pady=10, anchor="w")

        # 输出区域
        ttkb.Label(self.main_container, text="解析结果: (总共 4096 个可能的故障位)", 
                   bootstyle="secondary").pack(padx=10, pady=(5, 0), anchor="w")
        
        self.text_output = tk.Text(self.main_container, height=20, font=('Consolas', 10))
        self.text_output.pack(fill="both", padx=10, pady=5, expand=True)
        
        self.app.update_status(f"{PLUGIN_NAME} UI loaded.")

    def parse_hex(self):
        """核心解析逻辑：从 HEX 字符串提取故障 ID 并查找描述。"""
        self.text_output.delete("1.0", tk.END)
        raw_input = self.text_input.get("1.0", tk.END).strip()
        
        # 清理输入，只保留字母数字字符，并转大写
        hex_clean = ''.join(filter(str.isalnum, raw_input)).upper()

        if len(hex_clean) != 512 * 2:
            messagebox.showerror("错误", self.parent_frame, 
                                 f"输入长度错误: 当前 {len(hex_clean)//2} 字节，不是 512 字节 (预期长度: 1024 个 HEX 字符)")
            self.app.update_status("Error: Incorrect HEX length.")
            return

        # 将长 HEX 字符串分割成字节列表
        hex_list = [hex_clean[i:i+2] for i in range(0, len(hex_clean), 2)]

        try:
            # 将 HEX 字节转换为整数列表
            my_list = [int(i, 16) for i in hex_list]
        except ValueError:
            messagebox.showerror("错误", "HEX 字符串格式错误：包含非法的 HEX 字符 (0-9, A-F)。", parent=self.parent_frame)
            self.app.update_status("Error: Invalid HEX format.")
            return

        result_lines = []
        
        # 遍历 512 个字节
        for index, num in enumerate(my_list):
            if num != 0:
                # 检查每个字节的 8 个位
                # format(num, '08b') 将整数转为 8 位二进制字符串
                # [::-1] 反转字符串，使位 0 对应最低位
                for i, bit in enumerate(format(num, '08b')[::-1]):
                    if bit == '1':
                        # 计算全局故障 ID (0 到 4095)
                        fault_id = i + index * 8 
                        f = fault_dict.get(fault_id)
                        
                        if f:
                            # 格式化输出
                            line = (f"ID: {fault_id} (0x{fault_id:04X}) | "
                                    f"Name: {f['fault_name']} | "
                                    f"DTC: 0x{f['dtc_id']:X} | "
                                    f"Description: {f['description']}")
                            result_lines.append(line)
                        else:
                            # 如果 ID 存在但字典中没有定义
                            result_lines.append(f"ID: {fault_id} (0x{fault_id:04X}) | --- 未找到对应故障信息 ---")

        if result_lines:
            self.text_output.insert(tk.END, f"--- 成功解析 {len(result_lines)} 个故障 ---\n")
            self.text_output.insert(tk.END, "\n".join(result_lines))
        else:
            self.text_output.insert(tk.END, "未发现故障 (所有位均为 0)")
            
        self.text_output.insert(tk.END, "\n\n--- 解析结束 ---")
        self.app.update_status(f"Parse complete. Found {len(result_lines)} active faults.")


# ------------------------------------------------
# 1. Plugin Entry Point (插件注册入口)
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

    # 初始化应用逻辑和 UI
    # ttkbootstrap 的主题由主应用控制
    FaultParserApp(parent_frame, app)
    
# --- [ End of Plugin Entry Point ] ---

# --- [ Universal Toolbox Plugin Entry Point - 插件注册入口 ] ---
# 请将您脚本的核心 UI/逻辑代码移至此函数内。
# 'parent_frame' 是插件界面的容器。
import tkinter as tk
from tkinter import ttk

def register(app, parent_frame):
    """
    将脚本注册为 Universal Toolbox 的插件。
    app: 主应用实例，用于访问日志、状态栏等。
    parent_frame: 插件UI的容器 frame。
    """
    # 清空容器 frame，确保插件干净加载
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # ------------------------------------------------
    # ⬇️ 请将您的脚本核心逻辑从这里开始粘贴 ⬇️
    # ------------------------------------------------
    
    ttk.Label(parent_frame, text="✅ 插件已加载。请手动将您的脚本逻辑粘贴到此处。", 
              font=('Segoe UI', 12, 'italic')).pack(padx=20, pady=20)

    # ------------------------------------------------
    # ⬆️ 请将您的脚本核心逻辑粘贴到这里 ⬆️
    # ------------------------------------------------
    
    # 提示: 如果原脚本使用 'root' 作为主窗口，请替换为 'parent_frame'
    app.update_status(f"Plugin loaded via register function.")

# --- [ End of Plugin Entry Point ] ---
