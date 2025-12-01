import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from ttkbootstrap.constants import *
import re

# 必须导入 config，因为它包含 run_background 和 safe_call
try:
    from config import safe_call, log
except ImportError:
    # 插件在外部运行时的回退机制
    def log(*args): print(f"[PLUGIN] {' '.join(str(a) for a in args)}")
    def safe_call(func, *args, **kwargs): return func(*args, **kwargs)

# 插件元数据（可选）
name = "HEX_Converter"

# --- 辅助函数 ---

def _remove_spaces(text):
    """Removes all whitespace characters."""
    return text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")

def _add_spaces_by_bytes(hex_string, byte_interval=4):
    """Adds spaces to a clean HEX string based on byte intervals (1 byte = 2 HEX chars)."""
    hex_string = _remove_spaces(hex_string)
    if not hex_string or len(hex_string) % 2 != 0:
        return hex_string
    
    char_interval = byte_interval * 2
    
    # Split the string every char_interval characters and join with a space
    return " ".join(hex_string[i:i + char_interval] for i in range(0, len(hex_string), char_interval))

def _hex_to_ascii(hex_string):
    """Converts a clean HEX string to an ASCII string."""
    try:
        bytes_object = bytes.fromhex(hex_string)
        # Attempt decode using utf-8 first, then fall back to latin-1 (common for raw data)
        try:
            return bytes_object.decode('utf-8')
        except UnicodeDecodeError:
            return bytes_object.decode('latin-1')
    except ValueError as e:
        return f"[ERROR] Invalid HEX string for ASCII conversion: {e}"

def _ascii_to_hex(ascii_string):
    """Converts an ASCII string to a HEX string (UTF-8 encoding)."""
    return ascii_string.encode('utf-8').hex().upper()

# --- 插件主逻辑 ---

def register(app, parent_frame):
    """插件的注册函数：将 UI 放置在 parent_frame 中"""
    
    # 清空 parent_frame 里的默认内容
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # --- 1. 状态变量 ---
    mode = tk.StringVar(value="auto")
    space_mode = tk.StringVar(value="remove")
    byte_interval = tk.StringVar(value="4")
    
    # --- 2. UI 布局：创建所有控件 ---
    
    title = "HEX Converter & Utility - 进制转换与工具"
    ttk.Label(parent_frame, text=title, font=("Segoe UI", 20, "bold"), bootstyle="primary").pack(anchor="w", padx=20, pady=(20, 10))
    
    # 输入和控制区容器
    input_control_container = ttk.Frame(parent_frame, padding=15, relief="groove", borderwidth=1, bootstyle="secondary")
    input_control_container.pack(fill="x", padx=15, pady=5)

    # 转换模式和间隔设置 (Grid Layout)
    control_frame = ttk.Frame(input_control_container)
    control_frame.pack(fill="x", pady=(0, 10))
    
    # 2.1. 转换模式 Combobox
    ttk.Label(control_frame, text="Conversion Mode:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    conversion_modes = [
        "auto", 
        "hex->bin", "bin->hex", 
        "dec->hex", "hex->dec",
        "hex->ascii", "ascii->hex"
    ]
    mode_box = ttk.Combobox(control_frame, values=conversion_modes, textvariable=mode, width=15, state="readonly")
    mode_box.grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")
    mode_box.current(0)

    # 2.2. 空格处理模式 Combobox
    ttk.Label(control_frame, text="Spacing Policy:", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, padx=(20, 5), pady=5, sticky="w")
    
    space_mode_box = ttk.Combobox(control_frame, 
                                  values=["remove", "add"], 
                                  textvariable=space_mode, 
                                  width=10, 
                                  state="readonly")
    space_mode_box.grid(row=0, column=3, padx=(0, 5), pady=5, sticky="w")
    space_mode_box.current(0)
    
    # 2.3. 间隔 (字节) Combobox
    ttk.Label(control_frame, text="Byte Interval:", font=("Segoe UI", 10, "bold")).grid(row=0, column=4, padx=5, pady=5, sticky="w")
    
    byte_interval_box = ttk.Combobox(control_frame, 
                                     values=["1", "2", "4", "8", "16"], 
                                     textvariable=byte_interval, 
                                     width=5, 
                                     state="disabled") 
    byte_interval_box.grid(row=0, column=5, padx=5, pady=5, sticky="w")
    byte_interval_box.current(2) 

    # 分隔线
    ttk.Separator(input_control_container, orient=HORIZONTAL).pack(fill="x", pady=10)

    # Input Frame & Entry
    input_frame = ttk.Frame(input_control_container)
    input_frame.pack(fill="x")
    
    ttk.Label(input_frame, text="Input Data:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
    inp = ttk.Entry(input_frame, width=70, bootstyle="info")
    inp.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    # Output Box
    ttk.Label(parent_frame, text="Output Results:", font=("Segoe UI", 12, "bold"), bootstyle="info").pack(anchor="w", padx=15, pady=(10, 0))
    # Removed bootstyle from scrolledtext.ScrolledText to fix the TclError
    out_box = scrolledtext.ScrolledText(parent_frame, height=12, font=('Consolas', 10))
    out_box.pack(fill="both", expand=True, padx=15, pady=(5, 15))

    # --- 3. 定义逻辑函数 (所有控件已存在) ---

    def update_space_interval_state(*args): # Accepts event argument if called from bind
        """Controls the enabled state of the byte interval input."""
        if space_mode.get() == "add":
            byte_interval_box.config(state="readonly")
        else:
            byte_interval_box.config(state="disabled")

    def do_convert():
        data = inp.get().strip()
        out_box.delete("1.0", "end")
        
        if not data:
            messagebox.showwarning("Warning", "Please enter data to convert.")
            return

        current_mode = mode.get()
        # When space_mode is 'remove', use _remove_spaces. Otherwise, pass data directly.
        space_handler = _remove_spaces if space_mode.get() == "remove" else lambda x: x
        
        # 0. 预处理输入 (针对所有数值转换，去除空格/换行)
        clean_input = space_handler(data)
        
        result_text = f"--- CONVERSION RESULT ---\n"
        num = None # Numeric value after conversion

        try:
            if current_mode == "auto":
                # 1. Try to treat input as HEX number
                try:
                    num = int(clean_input, 16)
                    result_text += f"Mode: Auto-detected as HEX (Numeric)\n"
                except ValueError:
                    # 2. If not a HEX number, try to treat input as DEC number
                    try:
                        # Try DEC (decimal) without removing spaces for clarity
                        num = int(data) 
                        result_text += f"Mode: Auto-detected as DEC (Decimal)\n"
                        # Use clean decimal string for output, although num is used for calculation
                        clean_input = str(num) 
                    except ValueError:
                        # 3. If not a number, treat input as ASCII text
                        result_text += f"Mode: Auto-detected as ASCII (Text)\n"
                        
                        # --- Run ASCII -> HEX conversion ---
                        hex_result = _ascii_to_hex(data)
                        result_text += f"ASCII: {data}\n"
                        result_text += f"HEX: {hex_result}\n"
                        
                        # Stop numerical conversion flow here
                        out_box.insert("end", result_text)
                        return

            elif current_mode == "hex->bin" or current_mode == "hex->dec":
                num = int(clean_input, 16)
                
            elif current_mode == "bin->hex":
                # Ensure binary string contains only 0/1
                if not re.fullmatch(r"[01]+", clean_input):
                    raise ValueError("Binary input must only contain 0 and 1.")
                num = int(clean_input, 2)
                
            elif current_mode == "dec->hex":
                num = int(data) # Decimal input allows for spaces and should handle negative numbers if needed
            
            elif current_mode == "hex->ascii":
                ascii_result = _hex_to_ascii(clean_input)
                result_text += f"HEX: {clean_input}\n"
                result_text += f"ASCII: {ascii_result}\n"
                # Stop further numerical conversion
                out_box.insert("end", result_text)
                return

            elif current_mode == "ascii->hex":
                hex_result = _ascii_to_hex(data)
                result_text += f"ASCII: {data}\n"
                result_text += f"HEX: {hex_result}\n"
                # Stop further numerical conversion
                out_box.insert("end", result_text)
                return

            # --- 数值转换结果输出 ---
            if num is not None:
                # 1. 应用空格处理到最终 HEX 结果
                hex_val = hex(num).lstrip('0x').upper()
                
                # Check if we need to add spaces
                final_hex_output = hex_val
                if space_mode.get() == "add":
                    try:
                        interval = int(byte_interval.get())
                        # Re-run _add_spaces_by_bytes with the clean hex value
                        final_hex_output = _add_spaces_by_bytes(hex_val, interval)
                    except ValueError:
                        result_text += "[ERROR] Invalid byte interval for spacing.\n"
                        
                # 2. 输出所有进制
                result_text += f"DEC (Decimal): {num}\n"
                result_text += f"HEX (Hexadecimal): 0x{hex_val} ({final_hex_output})\n"
                result_text += f"BIN (Binary): {bin(num)}\n"
                
                # 3. 尝试进行 HEX->ASCII 转换 (仅当输入可被视为HEX时)
                if current_mode not in ("dec->hex", "bin->hex") and clean_input:
                    ascii_check = _hex_to_ascii(hex_val)
                    if not ascii_check.startswith("[ERROR]"):
                         result_text += f"ASCII (Text): {ascii_check}\n"

        except ValueError as e:
            result_text += f"Conversion Failed (Input Error or Base Mismatch): {e}\n"
        except Exception as e:
            result_text += f"Unknown Error Occurred: {e}\n"

        out_box.insert("end", result_text)


    # --- 4. 应用绑定和回调 ---
    
    # 绑定 Enter 键到转换函数
    inp.bind("<Return>", lambda event: safe_call(do_convert)) 

    # 转换按钮
    ttk.Button(input_frame, text="Convert", command=lambda: safe_call(do_convert), bootstyle="success").pack(side="left")
    
    # 绑定空格模式下拉框的回调
    space_mode_box.bind('<<ComboboxSelected>>', update_space_interval_state)

    # 确保初始化时更新间隔状态
    update_space_interval_state()
    log(f"插件 {name} 已加载。")