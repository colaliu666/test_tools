# src/plugins/uds_viewer.py

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from ttkbootstrap.constants import *
from datetime import datetime

# 导入 config 中的工具函数
try:
    from config import run_background, safe_call, log
except ImportError:
    def log(*args): print(f"[PLUGIN] {' '.join(str(a) for a in args)}")
    def run_background(func, on_done=None, *args, **kwargs):
        # 简化版 run_background，用于独立测试
        try: result = func(*args, **kwargs)
        except Exception as e: result, e = None, e
        if on_done: on_done(result, e)
    def safe_call(func, *args, **kwargs): return func(*args, **kwargs)

name = "UDS_Viewer"

def register(app, parent_frame):
    """插件的注册函数：将 UI 放置在 parent_frame 中"""

    # 清空 parent_frame 里的默认内容
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # --- 状态管理 ---
    # 使用 App 实例来保存输出文本框的引用
    app.uds_output_ref = scrolledtext.ScrolledText(parent_frame, height=15)

    # --- UI 布局 ---
    title = "ISO 14229 (Diagnostic) Viewer"
    ttk.Label(parent_frame, text=title, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=8, pady=6)
    
    ctrl_frame = ttk.Frame(parent_frame)
    ctrl_frame.pack(fill="x", padx=8, pady=6)
    
    ttk.Label(ctrl_frame, text="Service (HEX):").pack(side="left", padx=(0,4))
    service_var = tk.StringVar(value="22") 
    service_entry = ttk.Entry(ctrl_frame, textvariable=service_var, width=5)
    service_entry.pack(side="left", padx=(0,12))

    ttk.Label(ctrl_frame, text="Payload (HEX):").pack(side="left", padx=(0,4))
    payload_var = tk.StringVar(value="F190") 
    payload_entry = ttk.Entry(ctrl_frame, textvariable=payload_var, width=15)
    payload_entry.pack(side="left", padx=(0,12))
    
    # 绑定发送请求按钮
    ttk.Button(ctrl_frame, text="Send Request (Mock)", 
               command=lambda: safe_call(_send_uds_mock, app, service_var.get(), payload_var.get())
               ).pack(side="left", padx=(0,6))
    
    ttk.Separator(parent_frame, orient="horizontal").pack(fill="x", padx=8, pady=4)

    ttk.Label(parent_frame, text="UDS Log / Response Decode:").pack(anchor="w", padx=8)
    app.uds_output_ref.pack(fill="both", expand=True, padx=8, pady=6)
    app.uds_output_ref.insert("end", "ISO 14229 诊断工具已加载。使用 config.run_background 进行异步通信模拟。\n")
    
    log(f"插件 {name} 已加载。")

# ----------------------------
# UDS 逻辑函数
# ----------------------------

def _send_uds_mock(app, service, payload):
    """模拟 UDS 请求和解码响应 (在后台线程运行)"""
    
    uds_output = app.uds_output_ref
    service = service.upper().strip()
    payload = payload.upper().strip().replace(" ", "")
    request_msg = f"{service}{payload}"
    
    # Log request immediately (in main thread via safe_call)
    uds_output.insert("end", f"\n[{datetime.now().strftime('%H:%M:%S')}] --- REQUEST ---\n")
    uds_output.insert("end", f"Tx: {request_msg}\n")
    uds_output.see("end")
    app.update_status("Sending UDS Request...")
    
    # --- 后台任务：模拟发送和接收 ---
    def mock_send():
        import time; time.sleep(0.3)
        # --- UDS 响应模拟 ---
        if service == "22": 
            if payload == "F190": return "62F1904142434445313233343536373839" 
            elif payload == "1122": return "621122DEADC0DE" 
            else: return f"7F2231" 
        elif service == "10": return "500300320014"
        elif service == "3E": return "7E00" 
        else: return f"7F{service}11" 
        
    def on_done(response_hex, exc):
        if exc:
            app.update_status("UDS Simulation Failed.")
            uds_output.insert("end", f"--- ERROR ---\n{exc}\n")
            return
            
        _decode_uds_response(app, response_hex)
        
    run_background(mock_send, on_done=on_done)

def _decode_uds_response(app, response_hex):
    """解码 UDS 响应并在 UI 中显示 (在主线程中调用)"""
    
    uds_output = app.uds_output_ref
    app.update_status("Decoding UDS Response...")
    
    uds_output.insert("end", f"Rx: {response_hex}\n")
    uds_output.insert("end", f"--- DECODE ---\n")
    
    response_bytes = [response_hex[i:i+2].upper() for i in range(0, len(response_hex), 2)]
    
    did_map = {"F190": "VIN", "F191": "ECU SN"}
    
    if response_bytes[0] == "7F":
        # Negative Response
        nrc = response_bytes[2]
        service_id = response_bytes[1]
        nrc_map = {"11": "Service Not Supported", "31": "Request Out Of Range", "33": "Security Access Denied"}
        
        decode_txt = f"[Negative Response]\n"
        decode_txt += f" - Original SID: 0x{service_id}\n"
        decode_txt += f" - NRC Code: 0x{nrc} ({nrc_map.get(nrc, 'Unknown NRC')})\n"
        
    else:
        # Positive Response
        try:
            original_sid_dec = int(response_bytes[0], 16) - 0x40
            service_id = hex(original_sid_dec)[2:].zfill(2).upper()
        except ValueError:
            service_id = "Unknown"
            
        decode_txt = f"[Positive Response]\n"
        decode_txt += f" - Service ID: 0x{service_id}\n"
        
        # Specific service decoding examples
        if service_id == "22" and len(response_bytes) >= 3:
            did_hex = "".join(response_bytes[1:3])
            data = "".join(response_bytes[3:])
            did_name = did_map.get(did_hex, "Unknown DID")
            
            try:
                data_ascii = bytes.fromhex(data).decode('ascii', errors='replace').strip()
            except ValueError:
                data_ascii = "N/A"
                
            decode_txt += f" - DID: 0x{did_hex} ({did_name})\n"
            decode_txt += f" - Data (HEX): {data}\n"
            decode_txt += f" - Data (ASCII): {data_ascii}\n"
        # Add more decoding logic here

    uds_output.insert("end", decode_txt + "\n")
    uds_output.see("end")
    app.update_status("UDS Simulation Complete.")