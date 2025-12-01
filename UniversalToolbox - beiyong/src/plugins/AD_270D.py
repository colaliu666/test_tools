import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as ttkb
import sys
import os

# 尝试导入核心库
try:
    from .. import config
    run_background = config.run_background
    safe_call = config.safe_call
    log = config.log
except ImportError:
    # 依赖降级方案
    def log(*args, level="INFO"): print(f"[{level}][PLUGIN] {' '.join(str(a) for a in args)}")
    def safe_call(func, *args, **kwargs):
        try: return func(*args, **kwargs)
        except Exception as e: log(f"Safe call failed: {e}", level="ERROR"); return None
    # 假设在插件中，不需要后台运行，直接执行
    def run_background(func, on_done=None, *args, **kwargs):
        log("警告: config 模块未完全加载，任务在主线程执行。", level="WARNING")
        try: result = func(*args, **kwargs)
        except Exception as e: result, e = None, e
        if on_done: on_done(result, e)


# 插件名称
name = "AD_270D"

# ---------------- 故障数据定义 ----------------
# 这是您的内嵌 JSON 数据
fault_data = {
    "fault_info": [
        {"fault_id": 0, "fault_name": "Fault_0", "dtc_id": 0x01, "description": "描述0"},
        {"fault_id": 1, "fault_name": "Fault_1", "dtc_id": 0x02, "description": "描述1"},
        {"fault_id": 2, "fault_name": "Fault_2", "dtc_id": 0x03, "description": "描述2"},
        {"fault_id": 100, "fault_name": "Fault_100", "dtc_id": 0x64, "description": "示例故障: 位于 Byte 12, Bit 4"},
        {"fault_id": 101, "fault_name": "Fault_101", "dtc_id": 0x65, "description": "另一示例故障"},
        {"fault_id": 511, "fault_name": "Fault_511", "dtc_id": 0x1FF, "description": "最后一个可能的故障"},
        # 实际应用中，您可以在此继续添加所有 4096 个故障定义
    ]
}

# 预处理数据以快速查找 (Fault ID -> Fault Dictionary)
fault_dict = {f["fault_id"]: f for f in fault_data["fault_info"]}

# ---------------- 插件 UI/逻辑类 ----------------
class FaultParserUI:
    def __init__(self, app, parent_frame):
        self.app = app
        self.root = parent_frame # 使用传入的父框架作为根
        
        # UI 构建
        self._create_ui()
        log(f"插件 {name} UI 初始化完成。")

    def _create_ui(self):
        # 标题
        ttkb.Label(self.root, text="512 Bytes 故障码解析器", font=("Segoe UI", 12, "bold")).pack(padx=10, pady=(10, 5), anchor="w")
        
        # 输入区
        ttkb.Label(self.root, text="请输入 512 Bytes HEX 字符串（支持连续 HEX 或空格分隔）:").pack(padx=10, pady=5, anchor="w")
        self.text_input = tk.Text(self.root, height=8)
        self.text_input.pack(fill="x", padx=10, pady=5)

        # 示例输入（方便测试）
        example_hex = "00000000000000000000000010000000" + ("00" * 496)
        ttkb.Button(self.root, text="插入示例 HEX (Fault 100)", command=lambda: self.text_input.insert(tk.END, example_hex), bootstyle="secondary-outline").pack(padx=10, anchor="w")
        
        # 解析按钮
        self.parse_btn = ttkb.Button(self.root, text="解析 512 Bytes", 
                                     command=lambda: safe_call(self.parse_hex),
                                     bootstyle="primary")
        self.parse_btn.pack(padx=10, pady=10)

        # 输出区
        ttkb.Label(self.root, text="解析结果 (检测到的激活故障):").pack(padx=10, pady=5, anchor="w")
        self.text_output = tk.Text(self.root, height=20)
        self.text_output.pack(fill="both", padx=10, pady=5, expand=True)
        
        self.app.update_status("Fault Parser 插件已加载。")

    def parse_hex(self):
        """解析输入，查找激活的故障 ID，并显示信息。"""
        self.text_output.delete("1.0", tk.END)
        raw_input = self.text_input.get("1.0", tk.END).strip()

        # 清理输入：移除所有非十六进制字符 (空格, 换行等)
        hex_clean = ''.join(filter(str.isalnum, raw_input)).upper()

        if len(hex_clean) != 512 * 2:
            messagebox.showerror("错误", f"输入长度错误: 当前 {len(hex_clean)//2} 字节，需要 512 字节")
            return

        # 将连续 HEX 字符串切分为字节列表
        hex_list = [hex_clean[i:i+2] for i in range(0, len(hex_clean), 2)]

        try:
            # 将 HEX 字节转换为十进制整数列表
            byte_values = [int(i, 16) for i in hex_list]
        except ValueError:
            messagebox.showerror("错误", "HEX 字符串格式错误，包含非十六进制字符")
            return

        result_lines = []

        # 遍历 512 个字节
        for index, byte_value in enumerate(byte_values):
            # 如果字节值不为 0，则其中必有置位
            if byte_value != 0:
                # 遍历字节中的 8 个位 (i=0是最低位/最右位)
                # format(byte_value, '08b') 确保是 8 位二进制字符串
                # [::-1] 反转字符串，使 i=0 对应 Bit 0, i=7 对应 Bit 7
                for bit_position, bit_value in enumerate(format(byte_value, '08b')[::-1]):
                    if bit_value == '1':
                        # 计算总的 Fault ID: (Byte Index * 8) + Bit Position
                        fault_id = bit_position + index * 8 
                        
                        f = fault_dict.get(fault_id)
                        
                        if f:
                            line = (f"✅ [ID: {fault_id:04d}] (Byte {index}, Bit {bit_position}) "
                                    f"| Name: {f['fault_name']} | DTC: 0x{f['dtc_id']:X} | Desc: {f['description']}")
                            result_lines.append(line)
                        else:
                            # 故障 ID 激活，但在 fault_dict 中未找到
                            line = (f"⚠️ [ID: {fault_id:04d}] (Byte {index}, Bit {bit_position}) "
                                    f"| Name: [未找到] | DTC: 0x{fault_id:X} | Desc: 故障ID已置位，但定义缺失。")
                            result_lines.append(line)

        if result_lines:
            self.text_output.insert(tk.END, "\n".join(result_lines))
        else:
            self.text_output.insert(tk.END, "🎉 512 Bytes 中未发现任何激活的故障位。")
        self.text_output.insert(tk.END, "\n\n--- 解析完成 ---")
        
        self.app.update_status(f"解析完成，发现 {len(result_lines)} 个激活故障。")


# ---------------- 插件入口点 (必需) ----------------
def register(app, parent_frame):
    """
    主程序加载插件时调用的函数。
    app: 主应用程序实例 (ToolboxApp)
    parent_frame: 插件内容应该放置在其内部的容器 (ttk.Frame)
    """
    # 创建插件 UI 实例
    FaultParserUI(app, parent_frame)

    log(f"插件 {name} 注册完成。")