from __future__ import annotations

import threading
import queue
import time
from pathlib import Path
from typing import Dict

import customtkinter as ctk
from tkinter import messagebox

from core.scanner import scan_directories, DirectoryStat
from core.rules import RuleOptions, CleanPriority
from core.cleaner import delete_directory, DeleteOptions
from core.ai_analyzer import AiAnalyzer, AiAnalysisOptions
from core.smart_rules import PathCategory, get_quick_clean_targets, get_system_clean_guide, is_critical_system_path
from core.scan_cache import save_scan_cache, load_scan_cache, verify_cached_directory, get_cached_paths_set
from core.logger import (
    logger, log_startup, log_shutdown, log_scan_start, log_scan_complete,
    log_scan_cancelled, log_rule_evaluation, log_ai_analysis_start,
    log_ai_analysis_complete, log_ai_error, log_ai_service_start,
    log_ai_service_status, log_ai_config_save, log_delete_operation,
    log_delete_success, log_delete_error, log_settings_change,
    log_user_action, log_error
)


class DiskCleanerApp:
    def __init__(self, root: ctk.CTk) -> None:
        log_startup()
        self.root = root
        self.root.title("💎 DiskCleaner Pro - C盘智能清理工具")
        self.root.geometry("1100x700")
        
        # 设置现代化主题
        ctk.set_appearance_mode("dark")  # 深色模式
        ctk.set_default_color_theme("blue")  # 蓝色主题
        
        # 窗口关闭时记录日志
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 扫描配置
        self.scan_root = Path("C:/")
        self.excluded_roots = {
            Path("C:/Windows"),
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path("C:/ProgramData"),
        }
        # 默认推荐规则参数
        self.rule_options = RuleOptions(
            high_priority_size_bytes=1 * 1024 * 1024 * 1024,  # 1GB
            high_priority_days=180,
            normal_priority_size_bytes=500 * 1024 * 1024,      # 500MB
            normal_priority_days=90,
        )

        # AI 配置
        self.ai_analyzer = AiAnalyzer()
        self.ai_options = AiAnalysisOptions(
            enable_ai=False,
            api_base_url=None,
            api_key=None,
        )
        
        # 自动启动 AI 服务（如果已配置）
        self._auto_start_ai_service()

        # 扫描状态
        self.scan_thread: threading.Thread | None = None
        self.scan_queue: "queue.Queue[DirectoryStat]" = queue.Queue()
        self.scanned_count = 0
        self.scanning = False

        # UI 元素
        self._build_widgets()

        # Treeview 中 item id -> DirectoryStat
        self.item_stats: Dict[str, DirectoryStat] = {}
        
        # AI 分析结果缓存 {path: {category, summary, confidence}}
        self.ai_results: Dict[str, Dict] = {}

        # 定时从队列取数据更新 UI
        self.root.after(100, self._poll_queue)
    
    def _on_closing(self):
        """窗口关闭时的处理"""
        log_shutdown()
        self.root.destroy()
    
    def _auto_start_ai_service(self):
        """自动启动 AI 服务（如果配置文件存在且已配置）"""
        import json
        import subprocess
        import sys
        from pathlib import Path
        
        config_file = Path("ai_config.json")
        if not config_file.exists():
            return
        
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            api_key = config.get("api_key", "")
            if not api_key:
                return
            
            # 检查服务是否已经运行
            try:
                import requests
                response = requests.get("http://localhost:10089/health", timeout=1)
                if response.status_code == 200:
                    logger.info("AI 服务已经运行")
                    return
            except:
                pass
            
            # 启动 AI 服务
            logger.info("正在后台启动 AI 服务...")
            
            # 获取 ai_proxy.py 的路径（支持打包后的场景）
            if getattr(sys, 'frozen', False):
                # 打包后的 exe
                base_path = Path(sys._MEIPASS)
            else:
                # 未打包的源码
                base_path = Path(__file__).parent
            
            ai_proxy_path = base_path / "ai_proxy.py"
            
            # 后台启动
            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, str(ai_proxy_path)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(ai_proxy_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            logger.info("AI 服务已后台启动")
            
        except Exception as e:
            logger.error(f"自动启动 AI 服务失败: {e}")
    
    def _show_context_menu(self, event):
        """显示右键菜单"""
        # 获取点击的项
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        # 选中该项
        self.tree.selection_set(item_id)
        
        # 创建菜单
        import tkinter as tk
        menu = tk.Menu(self.root, tearoff=0, bg="#2c3e50", fg="white", 
                      activebackground="#3498db", activeforeground="white",
                      font=("Arial", 10))
        
        menu.add_command(
            label="📂 在资源管理器中打开",
            command=lambda: self._open_in_explorer(item_id)
        )
        
        # 显示菜单
        menu.post(event.x_root, event.y_root)
    
    def _open_in_explorer(self, item_id):
        """在资源管理器中打开指定目录"""
        stat = self.item_stats.get(item_id)
        if not stat:
            return
        
        import os
        import subprocess
        
        path = stat.path
        
        # 检查目录是否存在
        if not path.exists():
            messagebox.showerror("目录不存在", f"目录已被删除或不存在：\n{path}")
            return
        
        try:
            # Windows 资源管理器打开并选中该目录
            subprocess.run(["explorer", "/select,", str(path)], check=False)
            log_user_action("资源管理器打开", str(path))
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开目录：{e}")

    def _build_widgets(self) -> None:
        # 顶部标题栏
        header_frame = ctk.CTkFrame(self.root, fg_color=("#1e3a5f", "#0d1b2a"), corner_radius=0)
        header_frame.pack(fill=ctk.X, padx=0, pady=0)
        
        title_label = ctk.CTkLabel(
            header_frame, 
            text="💎 DiskCleaner Pro",
            font=("Arial", 24, "bold"),
            text_color=("#ffffff", "#00d4ff")
        )
        title_label.pack(side=ctk.LEFT, padx=20, pady=15)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="C盘智能清理 · AI驱动 · 安全可靠",
            font=("Arial", 12),
            text_color=("#b0c4de", "#6495ed")
        )
        subtitle_label.pack(side=ctk.LEFT, padx=(0, 20), pady=15)
        
        # 设置按钮（右上角）
        settings_btn = ctk.CTkButton(
            header_frame,
            text="⚙️ 设置",
            command=self.open_settings,
            width=100,
            fg_color=("#4a90e2", "#2c5f8d"),
            hover_color=("#357abd", "#1a4d7a")
        )
        settings_btn.pack(side=ctk.RIGHT, padx=10, pady=15)
        
        ai_settings_btn = ctk.CTkButton(
            header_frame,
            text="🤖 AI配置",
            command=self.open_ai_settings,
            width=100,
            fg_color=("#9b59b6", "#6c3483"),
            hover_color=("#8e44ad", "#5b2c6f")
        )
        ai_settings_btn.pack(side=ctk.RIGHT, padx=5, pady=15)

        # 主内容区
        main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        main_container.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)
        
        # 控制面板
        control_panel = ctk.CTkFrame(main_container, fg_color=("#2c3e50", "#1a252f"), corner_radius=10)
        control_panel.pack(fill=ctk.X, pady=(0, 15))
        
        # 按钮区
        button_row = ctk.CTkFrame(control_panel, fg_color="transparent")
        button_row.pack(fill=ctk.X, padx=20, pady=15)

        self.start_button = ctk.CTkButton(
            button_row,
            text="🚀 开始扫描",
            command=self.start_scan,
            width=140,
            height=40,
            font=("Arial", 14, "bold"),
            fg_color=("#27ae60", "#1e8449"),
            hover_color=("#229954", "#196f3d")
        )
        self.start_button.pack(side=ctk.LEFT, padx=5)

        self.stop_button = ctk.CTkButton(
            button_row,
            text="⏹ 停止扫描",
            command=self.stop_scan,
            state="disabled",
            width=140,
            height=40,
            font=("Arial", 14, "bold"),
            fg_color=("#e74c3c", "#c0392b"),
            hover_color=("#d62c1a", "#a93226")
        )
        self.stop_button.pack(side=ctk.LEFT, padx=5)
        
        # 清除缓存按钮
        clear_cache_btn = ctk.CTkButton(
            button_row,
            text="🗑️ 清除缓存",
            command=self.clear_cache,
            width=120,
            height=40,
            font=("Arial", 13),
            fg_color=("#95a5a6", "#7f8c8d"),
            hover_color=("#7f8c8d", "#626567")
        )
        clear_cache_btn.pack(side=ctk.LEFT, padx=5)

        self.status_var = ctk.StringVar(value="✨ 就绪 - 点击开始扫描按钮开始分析您的C盘")
        status_label = ctk.CTkLabel(
            button_row,
            textvariable=self.status_var,
            font=("Arial", 13),
            text_color=("#ecf0f1", "#95a5a6")
        )
        status_label.pack(side=ctk.LEFT, padx=(30, 0))

        # 进度条和扫描路径显示
        progress_container = ctk.CTkFrame(control_panel, fg_color="transparent")
        progress_container.pack(fill=ctk.X, padx=20, pady=(0, 15))

        self.progress = ctk.CTkProgressBar(
            progress_container,
            mode="indeterminate",
            height=8,
            progress_color=("#3498db", "#2980b9")
        )
        self.progress.pack(fill=ctk.X)
        self.progress.set(0)
        
        # 当前扫描路径显示（滚动文本）
        self.current_path_var = ctk.StringVar(value="")
        self.current_path_label = ctk.CTkLabel(
            progress_container,
            textvariable=self.current_path_var,
            font=("Arial", 10),
            text_color=("#7f8c8d", "#95a5a6"),
            anchor="w"
        )
        self.current_path_label.pack(fill=ctk.X, pady=(5, 0))

        # 结果列表容器
        table_frame = ctk.CTkFrame(main_container, fg_color=("#34495e", "#1c2833"), corner_radius=10)
        table_frame.pack(fill=ctk.BOTH, expand=True, pady=(0, 15))
        
        table_header = ctk.CTkLabel(
            table_frame,
            text="📊 扫描结果",
            font=("Arial", 16, "bold"),
            text_color=("#ecf0f1", "#3498db")
        )
        table_header.pack(anchor=ctk.W, padx=20, pady=(15, 10))
        
        # 使用tkinter原生Treeview（CustomTkinter暂不支持表格）
        import tkinter as tk
        from tkinter import ttk
        
        # 创建样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Custom.Treeview",
            background="#2c3e50",
            foreground="#ecf0f1",
            fieldbackground="#2c3e50",
            borderwidth=0,
            font=("Arial", 10)
        )
        style.configure(
            "Custom.Treeview.Heading",
            background="#1a252f",
            foreground="#3498db",
            borderwidth=0,
            font=("Arial", 11, "bold")
        )
        style.map("Custom.Treeview", background=[("selected", "#3498db")])
        
        tree_container = tk.Frame(table_frame, bg="#34495e")
        tree_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        columns = ("path", "size_gb", "priority", "category", "ai_category")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", style="Custom.Treeview")
        self.tree.heading("path", text="📁 目录路径")
        self.tree.heading("size_gb", text="💾 大小 (GB)")
        self.tree.heading("priority", text="⚡ 优先级")
        self.tree.heading("category", text="🏷️ 类型")
        self.tree.heading("ai_category", text="🤖 AI 分析")

        self.tree.column("path", width=400, anchor=tk.W)
        self.tree.column("size_gb", width=100, anchor=tk.E)
        self.tree.column("priority", width=80, anchor=tk.CENTER)
        self.tree.column("category", width=140, anchor=tk.W)
        self.tree.column("ai_category", width=180, anchor=tk.W)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 绑定右键菜单
        self.tree.bind("<Button-3>", self._show_context_menu)  # Windows 右键

        # 底部操作区
        action_panel = ctk.CTkFrame(main_container, fg_color=("#2c3e50", "#1a252f"), corner_radius=10)
        action_panel.pack(fill=ctk.X)
        
        action_row = ctk.CTkFrame(action_panel, fg_color="transparent")
        action_row.pack(fill=ctk.X, padx=20, pady=15)

        self.delete_button = ctk.CTkButton(
            action_row,
            text="🗑️ 删除选中",
            command=self.delete_selected,
            width=130,
            height=38,
            font=("Arial", 13, "bold"),
            fg_color=("#e74c3c", "#c0392b"),
            hover_color=("#d62c1a", "#a93226")
        )
        self.delete_button.pack(side=ctk.LEFT, padx=5)

        self.ai_analyze_button = ctk.CTkButton(
            action_row,
            text="🤖 AI 分析",
            command=self.ai_analyze_selected,
            width=130,
            height=38,
            font=("Arial", 13, "bold"),
            fg_color=("#9b59b6", "#6c3483"),
            hover_color=("#8e44ad", "#5b2c6f")
        )
        self.ai_analyze_button.pack(side=ctk.LEFT, padx=5)
        
        self.quick_clean_button = ctk.CTkButton(
            action_row,
            text="⚡ 快速清理",
            command=self.quick_clean,
            width=130,
            height=38,
            font=("Arial", 13, "bold"),
            fg_color=("#f39c12", "#d68910"),
            hover_color=("#e67e22", "#ca6f1e")
        )
        self.quick_clean_button.pack(side=ctk.LEFT, padx=5)
        
        self.system_guide_button = ctk.CTkButton(
            action_row,
            text="📖 清理指南",
            command=self.show_system_guide,
            width=130,
            height=38,
            font=("Arial", 13, "bold"),
            fg_color=("#16a085", "#117a65"),
            hover_color=("#138d75", "#0e6655")
        )
        self.system_guide_button.pack(side=ctk.LEFT, padx=5)

        tip_label = ctk.CTkLabel(
            action_row,
            text="💡 提示: 默认移入回收站，安全可恢复",
            font=("Arial", 11),
            text_color=("#95a5a6", "#7f8c8d")
        )
        tip_label.pack(side=ctk.LEFT, padx=(30, 0))

    # ----------------- 扫描逻辑 -----------------
    def start_scan(self) -> None:
        if self.scanning:
            return

        log_user_action("开始扫描", f"root={self.scan_root}")
        log_scan_start(str(self.scan_root))
        self.scan_start_time = time.time()
        
        # 清空旧数据
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.item_stats.clear()
        self.scanned_count = 0
        self.current_path_var.set("🚀 正在启动扫描...")  # 初始化路径显示

        self.scanning = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("🔍 正在扫描 C:/ ...")
        self.progress.start()

        self.scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self.scan_thread.start()

    def stop_scan(self) -> None:
        if not self.scanning:
            return
        log_user_action("停止扫描")
        log_scan_cancelled()
        self.scanning = False
        self.status_var.set("停止扫描中... 可能需几秒结束当前目录")
    
    def clear_cache(self) -> None:
        """清除扫描缓存"""
        from pathlib import Path
        
        cache_file = Path("scan_cache.json")
        if not cache_file.exists():
            messagebox.showinfo("缓存为空", "当前没有扫描缓存。")
            return
        
        result = messagebox.askyesno(
            "清除缓存",
            "确认清除扫描缓存？\n\n清除后，下次扫描将从头开始全盘扫描。"
        )
        
        if result:
            try:
                cache_file.unlink()
                messagebox.showinfo("清除成功", "扫描缓存已清除！")
                log_user_action("清除扫描缓存")
                logger.info("扫描缓存已清除")
            except Exception as e:
                messagebox.showerror("清除失败", f"无法清除缓存: {e}")
    
    def _open_ai_log(self) -> None:
        """打开 AI 服务日志"""
        from pathlib import Path
        import os
        
        log_file = Path("ai_service.log")
        
        if not log_file.exists():
            messagebox.showinfo(
                "日志不存在",
                "AI 服务日志文件不存在。\n\n可能原因：\n- 服务还未启动过\n- 服务启动失败"
            )
            return
        
        try:
            # 使用系统默认编辑器打开
            os.startfile(str(log_file))
            log_user_action("查看 AI 服务日志")
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开日志文件: {e}")

    def _scan_worker(self) -> None:
        try:
            # ========== 阶段1：快速检查缓存 ==========
            cached_items = load_scan_cache()
            if cached_items:
                self.status_var.set(f"⚡ 正在快速检查缓存的 {len(cached_items)} 个目录...")
                
                for idx, cached in enumerate(cached_items, 1):
                    if not self.scanning:
                        break
                    
                    # 更新进度
                    self.current_path_var.set(f"🔎 检查缓存 ({idx}/{len(cached_items)}): {cached['path']}")
                    
                    # 验证目录是否仍需清理
                    stat = verify_cached_directory(cached)
                    if stat:
                        self.scan_queue.put(stat)
            
            # ========== 阶段2：全盘扫描（排除已检查的） ==========
            if self.scanning:
                self.status_var.set("🔍 开始全盘扫描...")
                cached_paths = get_cached_paths_set()
                
                for stat in scan_directories(self.scan_root, self.excluded_roots):
                    if not self.scanning:
                        break
                    
                    # 跳过已经检查过的目录
                    if stat.path in cached_paths:
                        continue
                    
                    self.scan_queue.put(stat)
        finally:
            self.scan_queue.put(None)  # 结束标记

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self.scan_queue.get_nowait()
                if item is None:
                    # 扫描结束
                    self.scanning = False
                    self.progress.stop()
                    self.progress.set(0)
                    self.start_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    
                    duration = time.time() - self.scan_start_time
                    log_scan_complete(self.scanned_count, duration)
                    
                    # 统计优先级分布
                    high_count = sum(1 for item_id in self.item_stats if 
                                    self.tree.item(item_id, "values")[2] == "HIGH")
                    normal_count = sum(1 for item_id in self.item_stats if 
                                      self.tree.item(item_id, "values")[2] == "NORMAL")
                    log_rule_evaluation(high_count, normal_count, self.scanned_count - high_count - normal_count)
                    
                    # 保存扫描结果到缓存（包含 AI 分析结果）
                    all_stats = list(self.item_stats.values())
                    if all_stats:
                        save_scan_cache(all_stats, self.ai_results)
                        logger.info(f"已保存 {len(all_stats)} 个目录到扫描缓存，AI 结果: {len(self.ai_results)} 个")
                    
                    self.status_var.set(f"✅ 扫描完成！已分析 {self.scanned_count} 个目录")
                    self.current_path_var.set("")  # 清空路径显示
                    break

                self._handle_stat(item)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_queue)

    def _handle_stat(self, stat: DirectoryStat) -> None:
        self.scanned_count += 1
        
        # 更新状态和当前路径
        self.status_var.set(f"🔍 扫描中... 已分析 {self.scanned_count} 个目录")
        
        # 显示当前扫描路径（截断过长路径）
        path_str = str(stat.path)
        if len(path_str) > 80:
            # 只显示前30和后45字符，中间用...连接
            display_path = path_str[:30] + "..." + path_str[-45:]
        else:
            display_path = path_str
        
        self.current_path_var.set(f"📂 {display_path}")

        # 按规则计算优先级
        priority = self._evaluate_priority(stat)
        if priority == CleanPriority.IGNORE:
            return

        size_gb = stat.size_bytes / (1024 ** 3)
        
        # 智能识别路径类型
        category_info = PathCategory.categorize_path(stat.path)
        if category_info:
            category_name = category_info["name"]
            # 如果是关键系统路径，标记为不建议删除
            if is_critical_system_path(stat.path):
                category_name = f"⚠️ {category_name} (系统关键)"
        else:
            category_name = "普通目录"
            if is_critical_system_path(stat.path):
                category_name = "⚠️ 系统关键"
        
        # AI 分析列初始为空，等待用户手动触发
        item_id = self.tree.insert("", "end", values=(str(stat.path), f"{size_gb:.2f}", priority.name, category_name, ""))
        self.item_stats[item_id] = stat

    def _evaluate_priority(self, stat: DirectoryStat) -> CleanPriority:
        # 这里直接复制 rules.evaluate_candidates 的逻辑
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if stat.latest_atime <= 0 and stat.latest_mtime <= 0:
            return CleanPriority.IGNORE

        latest_ts = max(stat.latest_atime, stat.latest_mtime)
        last_dt = datetime.fromtimestamp(latest_ts, tz=timezone.utc)
        delta = now - last_dt

        if stat.size_bytes >= self.rule_options.high_priority_size_bytes and delta.days >= self.rule_options.high_priority_days:
            return CleanPriority.HIGH
        if stat.size_bytes >= self.rule_options.normal_priority_size_bytes and delta.days >= self.rule_options.normal_priority_days:
            return CleanPriority.NORMAL
        return CleanPriority.IGNORE

    # ----------------- 删除逻辑 -----------------
    def delete_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先在列表中选择要删除的目录。")
            return
        
        # 检查是否包含社交软件或系统关键路径
        social_paths = []
        critical_paths = []
        
        for item_id in selected:
            stat = self.item_stats.get(item_id)
            if not stat:
                continue
            
            category_info = PathCategory.categorize_path(stat.path)
            if category_info and category_info["category"] == "社交软件":
                social_paths.append((stat.path, category_info))
            
            if is_critical_system_path(stat.path):
                critical_paths.append(stat.path)
        
        # 如果有社交软件路径，显示清理指引
        if social_paths:
            guides = "\n\n".join([f"⚠️ {info['name']}: {info['guide']}" for _, info in social_paths[:3]])
            result = messagebox.askyesnocancel(
                "检测到社交软件路径",
                f"选中的目录包含社交软件数据，建议使用官方清理功能：\n\n{guides}\n\n是: 仍然继续删除\n否: 取消操作\n取消: 仅删除其他选中目录"
            )
            if result is None:  # 取消 - 移除社交软件路径
                selected = [item_id for item_id in selected 
                           if item_id not in [self.tree.selection()[i] for i, (p, _) in enumerate(social_paths)]]
                if not selected:
                    return
            elif result is False:  # 否 - 取消整个操作
                return
        
        # 如果有系统关键路径，警告
        if critical_paths:
            critical_preview = "\n".join([str(p) for p in critical_paths[:5]])
            if len(critical_paths) > 5:
                critical_preview += f"\n... 共 {len(critical_paths)} 个关键路径"
            
            messagebox.showwarning(
                "⚠️ 系统关键路径警告",
                f"选中的目录包含系统关键路径，强烈不建议删除！\n\n{critical_preview}\n\n删除这些文件可能导致系统或软件无法运行。"
            )
            return

        # 先确认是否直接删除
        direct = messagebox.askyesno("删除方式", "是否直接删除选中目录？\n是: 直接删除(不可恢复)\n否: 移入回收站")
        options = DeleteOptions(use_trash=not direct)
        
        log_user_action("删除选中", f"count={len(selected)}, use_trash={options.use_trash}")

        # 再次确认
        paths = [str(self.item_stats[i].path) for i in selected]
        log_delete_operation(paths, options.use_trash, len(paths))
        preview = "\n".join(paths[:10])
        if len(paths) > 10:
            preview += "\n... (仅显示前10项)"

        ok = messagebox.askyesno(
            "确认删除",
            f"即将删除 {len(paths)} 个目录:\n{preview}\n\n确认执行吗？",
        )
        if not ok:
            return

        failed = []
        for item_id in selected:
            stat = self.item_stats.get(item_id)
            if not stat:
                continue
            try:
                delete_directory(stat.path, options)
                log_delete_success(str(stat.path), options.use_trash)
                self.tree.delete(item_id)
                del self.item_stats[item_id]
            except Exception as exc:  # pragma: no cover
                log_delete_error(str(stat.path), exc)
                failed.append((stat.path, exc))

        if failed:
            msg = "\n".join(f"{p}: {e}" for p, e in failed[:5])
            if len(failed) > 5:
                msg += "\n... (仅显示前5条)"
            messagebox.showwarning("部分删除失败", msg)
        else:
            if options.use_trash:
                messagebox.showinfo("完成", "已将选中目录移入回收站。")
            else:
                messagebox.showinfo("完成", "已直接删除选中目录。请谨慎核对。")

    # ----------------- 设置对话框 -----------------
    def open_settings(self) -> None:
        log_user_action("打开规则设置")
        
        # 创建 CustomTkinter 对话框
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("⚙️ 调整规则阈值")
        dialog.geometry("600x750")  # 增加高度适配预设方案
        dialog.resizable(False, False)
        
        # 设置为模态对话框
        dialog.transient(self.root)
        dialog.grab_set()

        # 当前值
        high_size_mb = self.rule_options.high_priority_size_bytes // (1024 * 1024)
        high_days = self.rule_options.high_priority_days
        normal_size_mb = self.rule_options.normal_priority_size_bytes // (1024 * 1024)
        normal_days = self.rule_options.normal_priority_days
        
        # 主容器
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        
        # ========== 预设方案选择 ==========
        preset_frame = ctk.CTkFrame(main_frame, fg_color=("#2c3e50", "#1a252f"), corner_radius=10)
        preset_frame.pack(fill=ctk.X, pady=(0, 20))
        
        ctk.CTkLabel(
            preset_frame,
            text="🎯 快速选择预设方案",
            font=("Arial", 14, "bold"),
            text_color=("#3498db", "#5dade2")
        ).pack(pady=(15, 10))
        
        preset_btn_frame = ctk.CTkFrame(preset_frame, fg_color="transparent")
        preset_btn_frame.pack(pady=(0, 15))
        
        def apply_conservative():
            """保守方案：只清理确定无用的大文件"""
            high_size_var.set(2048)  # 2GB
            high_days_var.set(365)   # 1年
            normal_size_var.set(1024) # 1GB
            normal_days_var.set(180)  # 6个月
            messagebox.showinfo(
                "预设方案",
                "已应用《保守方案》\n\n• 高优先级: 2048 MB + 365 天\n• 普通优先级: 1024 MB + 180 天\n\n适合：第一次使用，不确定哪些可以删",
                parent=dialog
            )
        
        def apply_normal():
            """普通方案：平衡安全与清理效果"""
            high_size_var.set(1024)  # 1GB
            high_days_var.set(180)   # 6个月
            normal_size_var.set(500)  # 500MB
            normal_days_var.set(90)   # 3个月
            messagebox.showinfo(
                "预设方案",
                "已应用《普通方案》（推荐）\n\n• 高优先级: 1024 MB + 180 天\n• 普通优先级: 500 MB + 90 天\n\n适合：大多数用户，安全且有效",
                parent=dialog
            )
        
        def apply_aggressive():
            """激进方案：最大化清理空间"""
            high_size_var.set(500)   # 500MB
            high_days_var.set(90)    # 3个月
            normal_size_var.set(200)  # 200MB
            normal_days_var.set(30)   # 1个月
            messagebox.showinfo(
                "预设方案",
                "已应用《激进方案》\n\n• 高优先级: 500 MB + 90 天\n• 普通优先级: 200 MB + 30 天\n\n适合：C盘极度紧张，熟悉系统的用户",
                parent=dialog
            )
        
        ctk.CTkButton(
            preset_btn_frame,
            text="🐢 保守方案",
            command=apply_conservative,
            width=150,
            height=45,
            font=("Arial", 13, "bold"),
            fg_color=("#16a085", "#138d75"),
            hover_color=("#1abc9c", "#17a589")
        ).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(
            preset_btn_frame,
            text="⚖️ 普通方案",
            command=apply_normal,
            width=150,
            height=45,
            font=("Arial", 13, "bold"),
            fg_color=("#3498db", "#2980b9"),
            hover_color=("#5dade2", "#3498db")
        ).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(
            preset_btn_frame,
            text="🚀 激进方案",
            command=apply_aggressive,
            width=150,
            height=45,
            font=("Arial", 13, "bold"),
            fg_color=("#e74c3c", "#c0392b"),
            hover_color=("#ec7063", "#e74c3c")
        ).pack(side=ctk.LEFT, padx=5)
        
        # 方案说明
        info_frame = ctk.CTkFrame(preset_frame, fg_color=("#34495e", "#1c2833"), corner_radius=5)
        info_frame.pack(fill=ctk.X, padx=15, pady=(10, 15))
        
        ctk.CTkLabel(
            info_frame,
            text="💡 选择后会自动填充下方参数，您也可以手动微调",
            font=("Arial", 10),
            text_color=("#95a5a6", "#7f8c8d")
        ).pack(pady=8)

        # 高优先级设置
        ctk.CTkLabel(
            main_frame,
            text="🔥 高优先级规则",
            font=("Arial", 14, "bold"),
            text_color=("#e74c3c", "#c0392b")
        ).pack(anchor=ctk.W, pady=(0, 10))
        
        ctk.CTkLabel(
            main_frame,
            text="建议: 1024 MB + 180 天（用于标记长期未使用的大文件）",
            font=("Arial", 10),
            text_color=("#95a5a6", "#7f8c8d")
        ).pack(anchor=ctk.W, pady=(0, 10))

        high_size_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        high_size_frame.pack(fill=ctk.X, pady=5)
        ctk.CTkLabel(high_size_frame, text="目录大小阈值 (MB):", width=150).pack(side=ctk.LEFT)
        high_size_var = ctk.IntVar(value=high_size_mb)
        high_size_entry = ctk.CTkEntry(high_size_frame, textvariable=high_size_var, width=120)
        high_size_entry.pack(side=ctk.LEFT, padx=(10, 0))

        high_days_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        high_days_frame.pack(fill=ctk.X, pady=5)
        ctk.CTkLabel(high_days_frame, text="未访问天数阈值 (天):", width=150).pack(side=ctk.LEFT)
        high_days_var = ctk.IntVar(value=high_days)
        high_days_entry = ctk.CTkEntry(high_days_frame, textvariable=high_days_var, width=120)
        high_days_entry.pack(side=ctk.LEFT, padx=(10, 0))

        # 普通优先级设置
        ctk.CTkLabel(
            main_frame,
            text="⚡ 普通优先级规则",
            font=("Arial", 14, "bold"),
            text_color=("#f39c12", "#d68910")
        ).pack(anchor=ctk.W, pady=(20, 10))
        
        ctk.CTkLabel(
            main_frame,
            text="建议: 500 MB + 90 天（用于标记中等大小的临时文件）",
            font=("Arial", 10),
            text_color=("#95a5a6", "#7f8c8d")
        ).pack(anchor=ctk.W, pady=(0, 10))

        normal_size_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        normal_size_frame.pack(fill=ctk.X, pady=5)
        ctk.CTkLabel(normal_size_frame, text="目录大小阈值 (MB):", width=150).pack(side=ctk.LEFT)
        normal_size_var = ctk.IntVar(value=normal_size_mb)
        normal_size_entry = ctk.CTkEntry(normal_size_frame, textvariable=normal_size_var, width=120)
        normal_size_entry.pack(side=ctk.LEFT, padx=(10, 0))

        normal_days_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        normal_days_frame.pack(fill=ctk.X, pady=5)
        ctk.CTkLabel(normal_days_frame, text="未访问天数阈值 (天):", width=150).pack(side=ctk.LEFT)
        normal_days_var = ctk.IntVar(value=normal_days)
        normal_days_entry = ctk.CTkEntry(normal_days_frame, textvariable=normal_days_var, width=120)
        normal_days_entry.pack(side=ctk.LEFT, padx=(10, 0))

        # 底部按钮
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill=ctk.X, pady=(30, 0))

        def save_settings() -> None:
            try:
                new_high_size = high_size_var.get() * 1024 * 1024
                new_high_days = high_days_var.get()
                new_normal_size = normal_size_var.get() * 1024 * 1024
                new_normal_days = normal_days_var.get()

                if new_high_size <= 0 or new_high_days <= 0 or new_normal_size <= 0 or new_normal_days <= 0:
                    messagebox.showerror("输入错误", "所有阈值必须大于 0", parent=dialog)
                    return

                log_settings_change(
                    "rule_options",
                    f"high={self.rule_options.high_priority_size_bytes//1024//1024}MB/{self.rule_options.high_priority_days}d",
                    f"high={new_high_size//1024//1024}MB/{new_high_days}d"
                )
                
                self.rule_options = RuleOptions(
                    high_priority_size_bytes=new_high_size,
                    high_priority_days=new_high_days,
                    normal_priority_size_bytes=new_normal_size,
                    normal_priority_days=new_normal_days,
                )
                messagebox.showinfo("保存成功", "规则阈值已更新，将在下次扫描时生效。", parent=dialog)
                dialog.destroy()
            except Exception:
                messagebox.showerror("输入错误", "请输入有效的数字", parent=dialog)

        def reset_defaults() -> None:
            high_size_var.set(1024)
            high_days_var.set(180)
            normal_size_var.set(500)
            normal_days_var.set(90)

        ctk.CTkButton(
            button_frame,
            text="✅ 保存",
            command=save_settings,
            width=120,
            fg_color=("#27ae60", "#1e8449"),
            hover_color=("#229954", "#196f3d")
        ).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="🔄 恢复默认",
            command=reset_defaults,
            width=120,
            fg_color=("#f39c12", "#d68910"),
            hover_color=("#e67e22", "#ca6f1e")
        ).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="❌ 取消",
            command=dialog.destroy,
            width=120,
            fg_color=("#95a5a6", "#7f8c8d"),
            hover_color=("#7f8c8d", "#626567")
        ).pack(side=ctk.LEFT, padx=5)

    # ----------------- AI 配置对话框 -----------------
    def open_ai_settings(self) -> None:
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("🤖 AI 服务配置")
        dialog.geometry("600x500")
        dialog.resizable(False, False)
        
        # 设置为模态对话框
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 主容器
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=25, pady=25)
        
        # 标题
        ctk.CTkLabel(
            main_frame,
            text="🤖 AI 分析服务",
            font=("Arial", 18, "bold"),
            text_color=("#3498db", "#2980b9")
        ).pack(pady=(0, 20))
        
        # 自动检测服务状态
        import json
        from pathlib import Path
        
        service_running = False
        current_provider = None
        config_exists = False
        
        # 检查服务状态
        try:
            import requests
            response = requests.get("http://localhost:10089/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                current_provider = data.get("provider", "unknown")
                service_running = True
        except Exception:
            pass
        
        # 检查配置文件
        config_file = Path("ai_config.json")
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if config.get("api_key"):
                        config_exists = True
            except Exception:
                pass
        
        # ========== 场景1：服务已运行 ==========
        if service_running:
            # 状态显示
            status_frame = ctk.CTkFrame(main_frame, fg_color=("#27ae60", "#1e8449"), corner_radius=10)
            status_frame.pack(fill=ctk.X, pady=(0, 20))
            
            ctk.CTkLabel(
                status_frame,
                text=f"✅ 服务已运行",
                font=("Arial", 16, "bold"),
                text_color="white"
            ).pack(pady=15)
            
            ctk.CTkLabel(
                status_frame,
                text=f"当前模型: {current_provider}",
                font=("Arial", 12),
                text_color="white"
            ).pack(pady=(0, 15))
            
            # 启用开关
            enable_frame = ctk.CTkFrame(main_frame, fg_color=("#34495e", "#1c2833"), corner_radius=10)
            enable_frame.pack(fill=ctk.X, pady=(0, 20))
            
            enable_var = ctk.BooleanVar(value=self.ai_options.enable_ai)
            
            def toggle_ai():
                self.ai_options = AiAnalysisOptions(
                    enable_ai=enable_var.get(),
                    api_base_url="http://localhost:10089",
                    api_key=None,
                )
                status_text = "已启用" if enable_var.get() else "已禁用"
                messagebox.showinfo(
                    "AI 分析",
                    f"AI 分析功能{status_text}！",
                    parent=dialog
                )
                dialog.destroy()
            
            ctk.CTkSwitch(
                enable_frame,
                text="启用 AI 分析功能",
                variable=enable_var,
                font=("Arial", 14),
                command=toggle_ai,
                switch_width=50,
                switch_height=25
            ).pack(pady=20)
            
            # 重新配置按钮
            def reconfigure():
                dialog.destroy()
                # 重新打开对话框，但强制显示配置界面
                self._open_ai_config_form()
            
            ctk.CTkButton(
                main_frame,
                text="🔧 重新配置",
                command=reconfigure,
                fg_color=("#95a5a6", "#7f8c8d"),
                hover_color=("#7f8c8d", "#626567"),
                height=35
            ).pack(fill=ctk.X, pady=(0, 10))
            
            # 测试 AI 分析按钮
            def test_ai_analysis():
                """测试 AI 分析接口"""
                try:
                    import requests
                    from pathlib import Path
                    
                    # 测试请求
                    test_path = Path("C:/Windows/Temp")
                    payload = {
                        "path": str(test_path),
                        "size_bytes": 1024 * 1024 * 100,  # 100MB
                        "file_count": 50,
                        "dir_count": 10
                    }
                    
                    response = requests.post(
                        "http://localhost:10089/analyze-path",
                        json=payload,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        messagebox.showinfo(
                            "测试成功",
                            f"✅ AI 分析接口正常！\n\n测试结果：\n分类: {data.get('category', 'N/A')}\n总结: {data.get('summary', 'N/A')[:50]}...\n置信度: {data.get('confidence', 0):.0%}",
                            parent=dialog
                        )
                    else:
                        messagebox.showerror(
                            "测试失败",
                            f"❌ HTTP {response.status_code}\n\n{response.text[:200]}",
                            parent=dialog
                        )
                except requests.exceptions.ConnectionError:
                    messagebox.showerror(
                        "测试失败",
                        "❌ 无法连接 AI 服务\n\n请确认：\n- 服务已启动 (http://localhost:10089)\n- 端口 10089 未被占用",
                        parent=dialog
                    )
                except Exception as e:
                    messagebox.showerror(
                        "测试错误",
                        f"❌ {str(e)[:200]}",
                        parent=dialog
                    )
            
            ctk.CTkButton(
                main_frame,
                text="🧪 测试 AI 分析",
                command=test_ai_analysis,
                fg_color=("#9b59b6", "#8e44ad"),
                hover_color=("#8e44ad", "#7d3c98"),
                height=35,
                font=("Arial", 12)
            ).pack(fill=ctk.X, pady=(0, 10))
            
            ctk.CTkButton(
                main_frame,
                text="✔️ 关闭",
                command=dialog.destroy,
                fg_color=("#3498db", "#2980b9"),
                hover_color=("#2980b9", "#21618c"),
                height=35
            ).pack(fill=ctk.X)
        
        # ========== 场景2：服务未运行 ==========
        else:
            # 状态显示
            status_frame = ctk.CTkFrame(main_frame, fg_color=("#e74c3c", "#c0392b"), corner_radius=10)
            status_frame.pack(fill=ctk.X, pady=(0, 20))
            
            ctk.CTkLabel(
                status_frame,
                text="❌ 服务未运行",
                font=("Arial", 16, "bold"),
                text_color="white"
            ).pack(pady=15)
            
            if config_exists:
                ctk.CTkLabel(
                    status_frame,
                    text="检测到已有配置，点击下方按钮启动服务",
                    font=("Arial", 11),
                    text_color="white"
                ).pack(pady=(0, 15))
                
                # 快速启动按钮
                def quick_start():
                    import subprocess
                    import time
                    
                    try:
                        subprocess.Popen(
                            ["cmd", "/c", "start", "/B", "python", "ai_proxy.py"],
                            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        
                        # 显示启动中
                        progress = ctk.CTkProgressBar(main_frame, mode="indeterminate")
                        progress.pack(fill=ctk.X, pady=10)
                        progress.start()
                        
                        def check_and_close():
                            time.sleep(3)
                            try:
                                import requests
                                response = requests.get("http://localhost:10089/health", timeout=2)
                                if response.status_code == 200:
                                    self.ai_options = AiAnalysisOptions(
                                        enable_ai=True,
                                        api_base_url="http://localhost:10089",
                                        api_key=None,
                                    )
                                    messagebox.showinfo(
                                        "启动成功",
                                        "AI 服务已启动！\n\nAI 分析功能已自动启用。",
                                        parent=dialog
                                    )
                                    dialog.destroy()
                                else:
                                    raise Exception("服务响应异常")
                            except Exception:
                                progress.stop()
                                progress.destroy()
                                messagebox.showerror(
                                    "启动失败",
                                    "服务启动失败，可能原因：\n- API Key 配置错误\n- 网络连接问题\n- 端口 10089 被占用\n\n点击 '📝 查看服务日志' 按钮获取详细错误。",
                                    parent=dialog
                                )
                        
                        threading.Thread(target=check_and_close, daemon=True).start()
                    except Exception as e:
                        messagebox.showerror("启动失败", f"无法启动服务: {e}", parent=dialog)
                
                ctk.CTkButton(
                    main_frame,
                    text="🚀 快速启动服务",
                    command=quick_start,
                    fg_color=("#27ae60", "#1e8449"),
                    hover_color=("#229954", "#196f3d"),
                    height=40,
                    font=("Arial", 14, "bold")
                ).pack(fill=ctk.X, pady=(0, 10))
            else:
                ctk.CTkLabel(
                    status_frame,
                    text="需要配置 AI 模型",
                    font=("Arial", 11),
                    text_color="white"
                ).pack(pady=(0, 15))
            
            # 配置按钮
            ctk.CTkButton(
                main_frame,
                text="⚙️ 配置 AI 模型",
                command=lambda: (dialog.destroy(), self._open_ai_config_form()),
                fg_color=("#3498db", "#2980b9"),
                hover_color=("#2980b9", "#21618c"),
                height=40,
                font=("Arial", 14, "bold")
            ).pack(fill=ctk.X, pady=(0, 10))
            
            # 查看日志按钮
            ctk.CTkButton(
                main_frame,
                text="📝 查看服务日志",
                command=self._open_ai_log,
                fg_color=("#7f8c8d", "#626567"),
                hover_color=("#95a5a6", "#7f8c8d"),
                height=35,
                font=("Arial", 12)
            ).pack(fill=ctk.X, pady=(0, 10))
            
            ctk.CTkButton(
                main_frame,
                text="❌ 取消",
                command=dialog.destroy,
                fg_color=("#95a5a6", "#7f8c8d"),
                hover_color=("#7f8c8d", "#626567"),
                height=35
            ).pack(fill=ctk.X)
    
    def _open_ai_config_form(self) -> None:
        """打开 AI 配置表单（完整版）"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("⚙️ 配置 AI 模型")
        dialog.geometry("600x750")  # 增加高度适配测试按钮
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=25, pady=25)
        
        ctk.CTkLabel(
            main_frame,
            text="🤖 AI 模型配置",
            font=("Arial", 18, "bold"),
            text_color=("#3498db", "#2980b9")
        ).pack(pady=(0, 20))
        
        # 模型提供商
        provider_frame = ctk.CTkFrame(main_frame, fg_color=("#34495e", "#1c2833"), corner_radius=10)
        provider_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(provider_frame, text="模型提供商", font=("Arial", 12, "bold")).pack(anchor=ctk.W, padx=15, pady=(15, 5))
        
        provider_var = ctk.StringVar(value="deepseek")
        provider_options = ["deepseek", "gemini", "doubao", "openai"]
        
        ctk.CTkOptionMenu(
            provider_frame,
            variable=provider_var,
            values=provider_options,
            width=200
        ).pack(padx=15, pady=(0, 15))
        
        # API Key
        key_frame = ctk.CTkFrame(main_frame, fg_color=("#34495e", "#1c2833"), corner_radius=10)
        key_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(key_frame, text="API Key", font=("Arial", 12, "bold")).pack(anchor=ctk.W, padx=15, pady=(15, 5))
        
        key_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            key_frame,
            textvariable=key_var,
            width=450,
            height=35,
            show="*",
            placeholder_text="请输入您的 API Key"
        ).pack(padx=15, pady=(0, 15))
        
        # 模型名称
        model_frame = ctk.CTkFrame(main_frame, fg_color=("#34495e", "#1c2833"), corner_radius=10)
        model_frame.pack(fill=ctk.X, pady=(0, 15))
        
        ctk.CTkLabel(model_frame, text="模型名称（可选）", font=("Arial", 12, "bold")).pack(anchor=ctk.W, padx=15, pady=(15, 5))
        
        model_name_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            model_frame,
            textvariable=model_name_var,
            width=450,
            height=35,
            placeholder_text="留空使用默认（豆包必填接入点ID）"
        ).pack(padx=15, pady=(0, 10))
        
        ctk.CTkLabel(
            model_frame,
            text="提示：大多数情况下无需填写，系统会使用推荐模型",
            font=("Arial", 9),
            text_color=("#95a5a6", "#7f8c8d")
        ).pack(anchor=ctk.W, padx=15, pady=(0, 15))
        
        # 测试连接按钮
        def test_connection():
            """测试 API Key 是否有效"""
            import json
            from pathlib import Path
            
            provider = provider_var.get()
            api_key = key_var.get().strip()
            model_name = model_name_var.get().strip()
            
            if not api_key:
                messagebox.showwarning("输入不完整", "请先填写 API Key", parent=dialog)
                return
            
            # 保存临时配置
            test_config = Path("ai_config.json")
            config_data = {
                "provider": provider,
                "api_key": api_key,
                "model_name": model_name,
                "comment": "测试配置"
            }
            
            try:
                with open(test_config, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                
                # 显示测试中
                test_label = ctk.CTkLabel(
                    main_frame,
                    text="🔍 正在测试 API Key...",
                    font=("Arial", 11),
                    text_color=("#f39c12", "#e67e22")
                )
                test_label.pack(pady=5)
                dialog.update()
                
                # 执行测试
                def run_test():
                    try:
                        # 动态导入模块测试
                        if provider == "deepseek":
                            from openai import OpenAI
                            client = OpenAI(
                                api_key=api_key,
                                base_url="https://api.deepseek.com/v1"
                            )
                            response = client.chat.completions.create(
                                model=model_name or "deepseek-chat",
                                messages=[{"role": "user", "content": "test"}],
                                max_tokens=5
                            )
                            return True, "✅ DeepSeek API Key 有效！"
                        elif provider == "openai":
                            from openai import OpenAI
                            client = OpenAI(api_key=api_key)
                            response = client.chat.completions.create(
                                model=model_name or "gpt-4o-mini",
                                messages=[{"role": "user", "content": "test"}],
                                max_tokens=5
                            )
                            return True, "✅ OpenAI API Key 有效！"
                        elif provider == "gemini":
                            import google.generativeai as genai
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel(model_name or "gemini-pro")
                            response = model.generate_content("test")
                            return True, "✅ Gemini API Key 有效！"
                        elif provider == "doubao":
                            if not model_name:
                                return False, "⚠️ 豆包必须填写接入点 ID"
                            from openai import OpenAI
                            client = OpenAI(
                                api_key=api_key,
                                base_url="https://ark.cn-beijing.volces.com/api/v3"
                            )
                            response = client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "user", "content": "test"}],
                                max_tokens=5
                            )
                            return True, "✅ 豆包 API Key 有效！"
                        else:
                            return False, f"⚠️ 不支持的提供商: {provider}"
                    except Exception as e:
                        error_msg = str(e)
                        if "401" in error_msg or "Unauthorized" in error_msg:
                            return False, "❌ API Key 无效或已过期"
                        elif "429" in error_msg or "rate" in error_msg.lower():
                            return False, "⚠️ 请求过于频繁，请稍后再试"
                        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                            return False, "❌ 网络连接失败，请检查网络"
                        else:
                            return False, f"❌ 测试失败: {error_msg[:100]}"
                
                import threading
                result_success = False
                result_msg = ""
                
                def test_thread():
                    nonlocal result_success, result_msg
                    result_success, result_msg = run_test()
                    test_label.destroy()
                    if result_success:
                        messagebox.showinfo("测试成功", result_msg, parent=dialog)
                    else:
                        messagebox.showerror("测试失败", result_msg, parent=dialog)
                
                threading.Thread(target=test_thread, daemon=True).start()
                
            except Exception as e:
                messagebox.showerror("测试错误", f"无法执行测试: {e}", parent=dialog)
        
        ctk.CTkButton(
            main_frame,
            text="🧪 测试 API Key",
            command=test_connection,
            fg_color=("#9b59b6", "#8e44ad"),
            hover_color=("#8e44ad", "#7d3c98"),
            height=40,
            font=("Arial", 13, "bold")
        ).pack(fill=ctk.X, pady=(0, 10))
        
        # 保存并启动
        def save_and_start():
            import json
            from pathlib import Path
            import subprocess
            
            provider = provider_var.get()
            api_key = key_var.get().strip()
            model_name = model_name_var.get().strip()
            
            if not api_key:
                messagebox.showwarning("配置不完整", "请填写 API Key", parent=dialog)
                return
            
            config_file = Path("ai_config.json")
            config_data = {
                "provider": provider,
                "api_key": api_key,
                "model_name": model_name,
                "comment": "此文件由 DiskCleaner 自动生成"
            }
            
            try:
                with open(config_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
                
                # 启动服务
                subprocess.Popen(
                    ["cmd", "/c", "start", "/B", "python", "ai_proxy.py"],
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                
                # 等待检测
                progress = ctk.CTkProgressBar(main_frame, mode="indeterminate")
                progress.pack(fill=ctk.X, pady=10)
                progress.start()
                
                def check_and_close():
                    import time
                    time.sleep(3)
                    try:
                        import requests
                        response = requests.get("http://localhost:10089/health", timeout=2)
                        if response.status_code == 200:
                            self.ai_options = AiAnalysisOptions(
                                enable_ai=True,
                                api_base_url="http://localhost:10089",
                                api_key=None,
                            )
                            messagebox.showinfo(
                                "配置完成",
                                "AI 配置已保存，服务已启动！\n\nAI 分析功能已自动启用。",
                                parent=dialog
                            )
                            dialog.destroy()
                        else:
                            raise Exception("服务响应异常")
                    except Exception:
                        progress.stop()
                        progress.destroy()
                        
                        # 读取日志文件获取错误信息
                        error_detail = "未知错误"
                        try:
                            from pathlib import Path
                            log_file = Path("ai_service.log")
                            if log_file.exists():
                                with open(log_file, "r", encoding="utf-8") as f:
                                    lines = f.readlines()
                                    # 读取最后10行
                                    last_lines = lines[-10:] if len(lines) > 10 else lines
                                    error_detail = "".join(last_lines)
                        except Exception:
                            pass
                        
                        messagebox.showerror(
                            "启动失败",
                            f"配置已保存，但服务启动失败。\n\n请检查：\n- API Key 是否正确\n- 网络连接是否正常\n- 端口 10089 是否被占用\n\n点击 '📝 查看服务日志' 按钮获取详细错误信息。",
                            parent=dialog
                        )
                
                threading.Thread(target=check_and_close, daemon=True).start()
                
            except Exception as e:
                messagebox.showerror("保存失败", f"配置保存失败: {e}", parent=dialog)
        
        ctk.CTkButton(
            main_frame,
            text="✅ 保存并启动服务",
            command=save_and_start,
            fg_color=("#27ae60", "#1e8449"),
            hover_color=("#229954", "#196f3d"),
            height=40,
            font=("Arial", 14, "bold")
        ).pack(fill=ctk.X, pady=(0, 10))
        
        ctk.CTkButton(
            main_frame,
            text="❌ 取消",
            command=dialog.destroy,
            fg_color=("#95a5a6", "#7f8c8d"),
            hover_color=("#7f8c8d", "#626567"),
            height=35
        ).pack(fill=ctk.X)

    # ----------------- AI 分析功能 -----------------
    def ai_analyze_selected(self) -> None:
        if not self.ai_options.enable_ai:
            messagebox.showinfo("未启用 AI", "请先在'设置 > 配置 AI 服务'中启用并配置 AI。")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先在列表中选择要分析的目录。")
            return

        log_user_action("AI分析选中", f"count={len(selected)}")
        
        # 检查 AI 服务是否可用
        try:
            import requests
            response = requests.get("http://localhost:10089/health", timeout=2)
            if response.status_code != 200:
                raise Exception("服务响应异常")
            log_ai_service_status(True, response.json().get("provider", "unknown"))
        except Exception as e:
            log_ai_service_status(False)
            result = messagebox.askyesno(
                "AI 服务未启动",
                "检测到 AI 代理服务未运行。\n\n是否现在启动服务？\n\n提示: 也可以双击 start_ai_service.bat 手动启动。"
            )
            if result:
                self._start_ai_service_background()
            return

        log_ai_analysis_start(len(selected))
        self.status_var.set(f"🤖 正在调用 AI 分析 {len(selected)} 个目录...")
        self.ai_analyze_button.configure(state="disabled")

        def analyze_worker() -> None:
            error_count = 0
            first_error = None
            error_details = []  # 收集错误详情
            
            for item_id in selected:
                stat = self.item_stats.get(item_id)
                if not stat:
                    continue

                result = self.ai_analyzer.analyze_path(stat, self.ai_options)
                
                # 保存 AI 分析结果到缓存（包括错误时的本地结果）
                path_str = str(stat.path)
                self.ai_results[path_str] = {
                    "category": result.category,
                    "summary": result.summary,
                    "confidence": result.confidence,
                }
                
                # 记录错误
                if result.error:
                    error_count += 1
                    if not first_error:
                        first_error = result.error
                    # 收集详细错误信息
                    error_details.append(f"{stat.path.name}: {result.error}")
                    log_ai_error(str(stat.path), result.error)
                    logger.error(f"AI 分析失败 - {stat.path}: {result.error}")
                
                # 更新表格中的 AI 分析列
                values = list(self.tree.item(item_id, "values"))
                if result.error:
                    values[4] = f"{result.category} [本地] ({result.confidence:.0%})"
                else:
                    values[4] = f"{result.category} ({result.confidence:.0%})"
                self.tree.item(item_id, values=values)

            # 分析完成后提示
            log_ai_analysis_complete(len(selected) - error_count, error_count)
            if error_count > 0:
                self.status_var.set(f"⚠️ AI 分析完成 ({error_count}/{len(selected)} 项使用本地规则)")
                
                # 显示详细错误信息
                error_summary = "\n".join(error_details[:5])  # 最多显示5条
                if len(error_details) > 5:
                    error_summary += f"\n... 还有 {len(error_details) - 5} 个错误"
                
                messagebox.showwarning(
                    "部分 AI 调用失败",
                    f"有 {error_count} 项使用了本地启发式规则\n\n错误详情：\n{error_summary}\n\n建议检查：\n- AI 代理服务是否正常运行\n- API Key 是否正确\n- 网络连接是否正常\n\n点击 '📝 查看服务日志' 按钮查看详细错误。"
                )
            else:
                self.status_var.set(f"✅ AI 分析完成！成功分析 {len(selected)} 个目录")
            
            self.ai_analyze_button.configure(state="normal")

        threading.Thread(target=analyze_worker, daemon=True).start()

    def _start_ai_service_background(self) -> None:
        """在后台启动 AI 代理服务"""
        import subprocess
        from pathlib import Path
        
        log_ai_service_start()
        
        script_path = Path("start_ai_service.bat")
        if not script_path.exists():
            messagebox.showerror("文件缺失", "未找到 start_ai_service.bat 文件")
            return
        
        try:
            # 后台启动，不显示窗口
            subprocess.Popen(
                ["cmd", "/c", "start", "/B", "python", "ai_proxy.py"],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            messagebox.showinfo("服务启动中", "AI 代理服务正在后台启动，请稍等 3 秒后重试分析。")
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动 AI 服务: {e}")
    
    # ----------------- 一键快速清理 -----------------
    def quick_clean(self) -> None:
        """一键快速清理：自动清理临时文件、缓存等安全目录"""
        log_user_action("一键快速清理")
        
        targets = get_quick_clean_targets()
        if not targets:
            messagebox.showinfo("无需清理", "未检测到可快速清理的目录。")
            return
        
        # 展示清理列表
        preview = "\n".join([f"{item['name']}: {item['path']}\n  ({item['reason']})" for item in targets])
        
        result = messagebox.askyesno(
            "一键快速清理",
            f"检测到 {len(targets)} 个可安全清理的目录：\n\n{preview}\n\n确认清理？\n\n注意：将移入回收站，删不掉的文件自动跳过。",
        )
        
        if not result:
            return
        
        # 执行清理
        options = DeleteOptions(use_trash=True)
        success_count = 0
        failed_items = []
        
        for item in targets:
            path = item["path"]
            try:
                # 删除目录下的所有内容
                import shutil
                from send2trash import send2trash
                
                # 遍历目录内容，逐个删除
                if path.exists() and path.is_dir():
                    for entry in path.iterdir():
                        try:
                            if entry.is_file():
                                send2trash(str(entry))
                            elif entry.is_dir():
                                send2trash(str(entry))
                        except Exception:
                            # 跳过被占用的文件
                            continue
                    success_count += 1
                    log_delete_success(str(path), True)
            except Exception as e:
                failed_items.append((item["name"], e))
                log_delete_error(str(path), e)
        
        # 显示结果
        if success_count == len(targets):
            messagebox.showinfo(
                "清理完成",
                f"已成功清理 {success_count} 个目录！\n\n文件已移入回收站，如需恢复请从回收站还原。"
            )
        elif success_count > 0:
            failed_preview = "\n".join([f"{name}: {e}" for name, e in failed_items[:3]])
            messagebox.showwarning(
                "部分成功",
                f"成功清理 {success_count}/{len(targets)} 个目录\n\n失败项：\n{failed_preview}"
            )
        else:
            messagebox.showerror("清理失败", "无法清理任何目录，请检查权限。")
    
    def show_system_guide(self) -> None:
        """显示 Windows 系统磁盘清理工具使用指引"""
        log_user_action("查看系统清理指引")
        guide = get_system_clean_guide()
        messagebox.showinfo("系统磁盘清理指引", guide)


def main() -> None:
    # 检查 customtkinter 依赖
    try:
        import customtkinter
    except ImportError:
        import subprocess
        import sys
        print("正在安装 customtkinter...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
        print("安装完成！")
    
    root = ctk.CTk()
    app = DiskCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
