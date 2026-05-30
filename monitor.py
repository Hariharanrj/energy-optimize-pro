import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import cv2
import pygame
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import queue
import json
from collections import deque
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------
# CONFIGURATION — set these as environment variables or edit here
# EMAIL_SENDER : your Gmail address
# EMAIL_PASSWORD: your Gmail App Password (not your login password)
#   Generate at: https://myaccount.google.com/apppasswords
# ---------------------------------------------------------------
EMAIL_SENDER   = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")


class EnergyOptimizationSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Energy Optimization Pro: AI Smart Grid Management")

        # Make window fullscreen by default
        self.root.state('zoomed')  # Windows
        self.root.update_idletasks()
        screen_width  = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")

        self.root.configure(bg='#f0f0f0')

        self.setup_styles()
        self.create_scrollable_frame()

        # Variables
        self.serial_port    = None
        self.is_reading     = False
        self.alert_playing  = False
        self.last_email_time = 0
        self.email_cooldown  = 60  # seconds between emails

        # Email credentials (loaded from env / config)
        self.email_sender   = EMAIL_SENDER
        self.email_password = EMAIL_PASSWORD

        # Configuration file
        self.config_file = "energy_optimizer_config.json"
        self.load_config()

        # Data storage
        self.max_data_points  = 100
        self.time_data        = deque(maxlen=self.max_data_points)
        self.temperature_data = deque(maxlen=self.max_data_points)
        self.humidity_data    = deque(maxlen=self.max_data_points)
        self.pulse_data       = deque(maxlen=self.max_data_points)
        self.spo2_data        = deque(maxlen=self.max_data_points)

        # Scaled data for energy grid visualisation
        self.energy_data      = deque(maxlen=self.max_data_points)
        self.efficiency_data  = deque(maxlen=self.max_data_points)
        self.peak_load_data   = deque(maxlen=self.max_data_points)
        self.renewable_data   = deque(maxlen=self.max_data_points)

        self.data_queue = queue.Queue()
        self.start_time = time.time()

        # Initialize pygame for audio
        pygame.mixer.init()

        # Create alerts directory
        os.makedirs("alerts", exist_ok=True)

        self.setup_gui()
        self.update_display()
        self.refresh_ports()
        self.root.bind('<Configure>', self.on_window_resize)

    # ------------------------------------------------------------------
    # Window / scroll helpers
    # ------------------------------------------------------------------

    def on_window_resize(self, event):
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox('all'))

    def setup_styles(self):
        style = ttk.Style()

        self.colors = {
            'primary':   '#2c3e50',
            'secondary': '#3498db',
            'success':   '#27ae60',
            'warning':   '#f39c12',
            'danger':    '#e74c3c',
            'info':      '#1abc9c',
            'light':     '#ecf0f1',
            'dark':      '#34495e',
        }

        style.configure('Title.TLabel',    font=('Arial', 20, 'bold'),  foreground=self.colors['primary'])
        style.configure('Subtitle.TLabel', font=('Arial', 11),          foreground=self.colors['dark'])
        style.configure('Heading.TLabel',  font=('Arial', 12, 'bold'),  foreground=self.colors['primary'])
        style.configure('Value.TLabel',    font=('Arial', 20, 'bold'),  foreground=self.colors['dark'])
        style.configure('Status.TLabel',   font=('Arial', 10, 'bold'))
        style.configure('Start.TButton',   font=('Arial', 11, 'bold'))
        style.configure('Stop.TButton',    font=('Arial', 11, 'bold'))
        style.configure('Action.TButton',  font=('Arial', 10))
        style.configure('Card.TLabelframe',        background='white', relief='solid', borderwidth=1)
        style.configure('Card.TLabelframe.Label',  font=('Arial', 11, 'bold'), foreground=self.colors['primary'])

    def create_scrollable_frame(self):
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self.main_canvas = tk.Canvas(self.main_container, bg='#f0f0f0', highlightthickness=0)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.main_container, orient=tk.VERTICAL, command=self.main_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.main_canvas.configure(yscrollcommand=scrollbar.set)

        self.scrollable_frame = ttk.Frame(self.main_canvas)
        self.canvas_window    = self.main_canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor='nw',
            width=self.main_canvas.winfo_width()
        )

        def configure_scroll_region(event):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox('all'))
            self.main_canvas.itemconfig(self.canvas_window, width=self.main_canvas.winfo_width())

        self.scrollable_frame.bind('<Configure>', configure_scroll_region)

        def _on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        self.main_canvas.bind_all('<MouseWheel>', _on_mousewheel)

        def configure_canvas(event):
            self.main_canvas.itemconfig(self.canvas_window, width=event.width)

        self.main_canvas.bind('<Configure>', configure_canvas)

    # ------------------------------------------------------------------
    # Config load / save
    # ------------------------------------------------------------------

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                self.saved_threshold = config.get('threshold', '37.5')
                self.saved_email     = config.get('receiver_email', '')
            else:
                self.saved_threshold = '37.5'
                self.saved_email     = ''
        except Exception as e:
            print(f"Error loading config: {e}")
            self.saved_threshold = '37.5'
            self.saved_email     = ''

    def save_config(self):
        try:
            config = {
                'threshold':      self.threshold_var.get(),
                'receiver_email': self.email_var.get(),
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f)

            self.saved_threshold = config['threshold']
            self.saved_email     = config['receiver_email']

            self.saved_threshold_label.config(text=f"{self.saved_threshold} °C")
            self.saved_email_label.config(
                text=self.saved_email if self.saved_email else "Not set"
            )

            if hasattr(self, 'ax1') and len(self.ax1.lines) > 1:
                data = [float(self.saved_threshold)] * max(2, len(self.time_data))
                self.ax1.lines[1].set_ydata(data)
                self.canvas.draw_idle()

            messagebox.showinfo("Success", "Configuration saved successfully!", parent=self.root)
            self.log(f"Configuration saved — Threshold: {self.saved_threshold}°C, Email: {self.saved_email}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}", parent=self.root)

    # ------------------------------------------------------------------
    # GUI setup
    # ------------------------------------------------------------------

    def setup_gui(self):
        main_frame = ttk.Frame(self.scrollable_frame, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(1, weight=1)

        # Header
        header_frame = tk.Frame(main_frame, bg='#2c3e50', height=90)
        header_frame.grid(row=0, column=0, columnspan=3, pady=(0, 15), sticky=(tk.W, tk.E))
        header_frame.grid_propagate(False)
        tk.Label(header_frame,
                 text="ENERGY OPTIMIZATION PRO: AI SMART GRID MANAGEMENT",
                 font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white').pack(pady=15)
        tk.Label(header_frame,
                 text="Intelligent Energy Monitoring & Optimisation System | Real-time Grid Analytics",
                 font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack()

        # Left panel — Controls
        left_frame = ttk.LabelFrame(main_frame, text="CONTROLS & SETTINGS",
                                    padding="15", style='Card.TLabelframe')
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        port_frame = ttk.Frame(left_frame)
        port_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(port_frame, text="Serial Port:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        self.port_var   = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, width=15, state='readonly')
        self.port_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(port_frame, text="Refresh", command=self.refresh_ports, width=10).pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=15)
        self.start_button = tk.Button(button_frame, text="START MONITORING",
                                      command=self.toggle_monitoring,
                                      font=('Arial', 11, 'bold'),
                                      bg='#27ae60', fg='white',
                                      padx=20, pady=8, relief='flat', cursor='hand2')
        self.start_button.pack()

        ttk.Separator(left_frame, orient='horizontal').grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(left_frame, text="ALERT SETTINGS",
                  font=('Arial', 11, 'bold'), foreground='#e74c3c').grid(
            row=3, column=0, columnspan=3, pady=5)

        threshold_frame = ttk.Frame(left_frame)
        threshold_frame.grid(row=4, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        ttk.Label(threshold_frame, text="Temperature Threshold:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.threshold_var = tk.StringVar(value=self.saved_threshold)
        ttk.Spinbox(threshold_frame, from_=35.0, to=42.0,
                    textvariable=self.threshold_var, width=8, increment=0.1).pack(side=tk.LEFT, padx=5)
        ttk.Label(threshold_frame, text="°C").pack(side=tk.LEFT)

        email_frame = ttk.Frame(left_frame)
        email_frame.grid(row=5, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        ttk.Label(email_frame, text="Alert Email:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        self.email_var = tk.StringVar(value=self.saved_email)
        ttk.Entry(email_frame, textvariable=self.email_var, width=22).pack(side=tk.LEFT, padx=5)

        tk.Button(left_frame, text="SAVE CONFIGURATION", command=self.save_config,
                  font=('Arial', 10, 'bold'), bg='#3498db', fg='white',
                  padx=15, pady=5, relief='flat', cursor='hand2').grid(
            row=6, column=0, columnspan=3, pady=10)

        test_frame = ttk.Frame(left_frame)
        test_frame.grid(row=7, column=0, columnspan=3, pady=5)
        for (label, cmd, color) in [
            ("Test Email",  self.test_email,  '#f39c12'),
            ("Test Camera", self.test_camera, '#1abc9c'),
        ]:
            tk.Button(test_frame, text=label, command=cmd,
                      font=('Arial', 9), bg=color, fg='white',
                      padx=10, pady=3, relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)

        ttk.Separator(left_frame, orient='horizontal').grid(
            row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(left_frame, text="CURRENT READINGS",
                  font=('Arial', 11, 'bold'), foreground='#3498db').grid(
            row=9, column=0, columnspan=3, pady=5)

        readings_frame = tk.Frame(left_frame, bg='white', relief='solid', bd=1)
        readings_frame.grid(row=10, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))

        def _reading_row(parent, label_text, attr):
            row = tk.Frame(parent, bg='white')
            row.pack(fill=tk.X, padx=10, pady=5)
            tk.Label(row, text=label_text, font=('Arial', 10), bg='white').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="--", font=('Arial', 20, 'bold'), bg='white', fg='#2c3e50')
            lbl.pack(side=tk.RIGHT)
            return lbl

        self.temp_label     = _reading_row(readings_frame, "Temperature:", "temp")
        self.humidity_label = _reading_row(readings_frame, "Humidity:", "hum")
        self.pulse_label    = _reading_row(readings_frame, "Heart Rate:", "pulse")
        self.spo2_label     = _reading_row(readings_frame, "Oxygen Level:", "spo2")

        tk.Frame(readings_frame, height=1, bg='#bdc3c7').pack(fill=tk.X, padx=10, pady=5)

        status_row = tk.Frame(readings_frame, bg='white')
        status_row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(status_row, text="Grid Status:", font=('Arial', 10, 'bold'), bg='white').pack(side=tk.LEFT)
        self.grid_status_label = tk.Label(status_row, text="STANDBY",
                                          font=('Arial', 16, 'bold'), bg='white', fg='#7f8c8d')
        self.grid_status_label.pack(side=tk.RIGHT)

        ttk.Separator(left_frame, orient='horizontal').grid(
            row=11, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(left_frame, text="SAVED CONFIGURATION",
                  font=('Arial', 11, 'bold'), foreground='#27ae60').grid(
            row=12, column=0, columnspan=3, pady=5)

        saved_frame = tk.Frame(left_frame, bg='white', relief='solid', bd=1)
        saved_frame.grid(row=13, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))

        thresh_row = tk.Frame(saved_frame, bg='white')
        thresh_row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(thresh_row, text="Threshold:", font=('Arial', 10), bg='white').pack(side=tk.LEFT)
        self.saved_threshold_label = tk.Label(thresh_row,
                                              text=f"{self.saved_threshold} °C",
                                              font=('Arial', 10, 'bold'), bg='white', fg='#27ae60')
        self.saved_threshold_label.pack(side=tk.RIGHT)

        email_row = tk.Frame(saved_frame, bg='white')
        email_row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(email_row, text="Alert Email:", font=('Arial', 10), bg='white').pack(side=tk.LEFT)
        self.saved_email_label = tk.Label(email_row,
                                          text=self.saved_email if self.saved_email else "Not set",
                                          font=('Arial', 10, 'bold'), bg='white', fg='#3498db',
                                          wraplength=150)
        self.saved_email_label.pack(side=tk.RIGHT)

        status_indicator = tk.Frame(left_frame, bg='white', relief='solid', bd=1)
        status_indicator.grid(row=14, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        self.status_label = tk.Label(status_indicator, text="● Disconnected",
                                     font=('Arial', 11, 'bold'), bg='white', fg='#e74c3c')
        self.status_label.pack(pady=5)

        tk.Frame(left_frame, height=20).grid(row=15, column=0, columnspan=3)

        # Middle panel — Graphs
        middle_frame = ttk.LabelFrame(main_frame, text="LIVE ENERGY ANALYTICS",
                                      padding="10", style='Card.TLabelframe')
        middle_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        self.fig = Figure(figsize=(9, 8), dpi=100, facecolor='white')
        self.fig.subplots_adjust(hspace=0.4)

        self.ax1 = self.fig.add_subplot(311)
        self.ax1.set_title('Energy Consumption (kW)', fontsize=11, fontweight='bold', color='#2c3e50')
        self.ax1.set_ylim(0, 120); self.ax1.set_xlim(0, 60)
        self.ax1.grid(True, alpha=0.3, linestyle='--', color='#95a5a6')
        self.ax1.set_facecolor('#f8f9f9')
        self.ax1.set_ylabel('Power (kW)', fontsize=9, color='#2c3e50')
        self.ax1.tick_params(colors='#2c3e50')
        self.temp_line, = self.ax1.plot([], [], 'r-', linewidth=2, label='Consumption')
        self.threshold_line = self.ax1.axhline(
            y=float(self.saved_threshold), color='#f39c12',
            linestyle='--', linewidth=2, label='Threshold', alpha=0.7)
        self.ax1.legend(loc='upper right', fontsize=8, frameon=True, facecolor='white')

        self.ax2 = self.fig.add_subplot(312)
        self.ax2.set_title('Grid Efficiency (%)', fontsize=11, fontweight='bold', color='#2c3e50')
        self.ax2.set_ylim(0, 100); self.ax2.set_xlim(0, 60)
        self.ax2.grid(True, alpha=0.3, linestyle='--', color='#95a5a6')
        self.ax2.set_facecolor('#f8f9f9')
        self.ax2.set_ylabel('Efficiency %', fontsize=9, color='#2c3e50')
        self.ax2.tick_params(colors='#2c3e50')
        self.humidity_line, = self.ax2.plot([], [], 'b-', linewidth=2, label='Efficiency')
        self.ax2.legend(loc='upper right', fontsize=8, frameon=True, facecolor='white')

        self.ax3 = self.fig.add_subplot(313)
        self.ax3.set_title('Load Distribution', fontsize=11, fontweight='bold', color='#2c3e50')
        self.ax3.set_ylim(0, 100); self.ax3.set_xlim(0, 60)
        self.ax3.grid(True, alpha=0.3, linestyle='--', color='#95a5a6')
        self.ax3.set_facecolor('#f8f9f9')
        self.ax3.set_ylabel('Load %', fontsize=9, color='#2c3e50')
        self.ax3.set_xlabel('Time (seconds)', fontsize=9, color='#2c3e50')
        self.ax3.tick_params(colors='#2c3e50')
        self.pulse_line, = self.ax3.plot([], [], 'g-', linewidth=2, label='Peak Load')

        self.ax3_spo2 = self.ax3.twinx()
        self.ax3_spo2.set_ylim(0, 100)
        self.spo2_line, = self.ax3_spo2.plot([], [], 'm-', linewidth=2, label='Renewable %', alpha=0.7)
        self.ax3_spo2.set_ylabel('Renewable %', color='#8e44ad', fontsize=9)
        self.ax3_spo2.tick_params(axis='y', labelcolor='#8e44ad')

        lines  = [self.pulse_line, self.spo2_line]
        labels = [l.get_label() for l in lines]
        self.ax3.legend(lines, labels, loc='upper right', fontsize=8, frameon=True, facecolor='white')

        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=middle_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # Right panel — Log
        right_frame = ttk.LabelFrame(main_frame, text="SYSTEM EVENTS & ALERTS",
                                     padding="10", style='Card.TLabelframe')
        right_frame.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        log_frame = ttk.Frame(right_frame)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_area = scrolledtext.ScrolledText(
            log_frame, width=40, height=35, font=('Consolas', 9),
            bg='#1e1e1e', fg='#00ff00', insertbackground='white', wrap=tk.WORD)
        self.log_area.pack(fill=tk.BOTH, expand=True)

        log_control_frame = ttk.Frame(right_frame)
        log_control_frame.pack(fill=tk.X, pady=5)
        for (label, cmd, color) in [
            ("Clear Log",  self.clear_log,  '#e74c3c'),
            ("Export Log", self.export_log, '#3498db'),
        ]:
            tk.Button(log_control_frame, text=label, command=cmd,
                      font=('Arial', 9), bg=color, fg='white',
                      padx=10, pady=3, relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)

        # Footer
        footer_frame = tk.Frame(main_frame, bg='#2c3e50', height=30)
        footer_frame.grid(row=2, column=0, columnspan=3, pady=(15, 0), sticky=(tk.W, tk.E))
        footer_frame.grid_propagate(False)
        tk.Label(footer_frame,
                 text="Energy Optimization Pro v2.0 | AI-Powered Smart Grid Management | © 2024",
                 font=('Arial', 9), bg='#2c3e50', fg='#ecf0f1').pack(pady=5)

        tk.Frame(main_frame, height=20).grid(row=3, column=0, columnspan=3)

    # ------------------------------------------------------------------
    # Monitoring control
    # ------------------------------------------------------------------

    def export_log(self):
        try:
            filename = f"grid_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                f.write(self.log_area.get(1.0, tk.END))
            messagebox.showinfo("Success", f"Log exported to {filename}", parent=self.root)
            self.log(f"Log exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export log: {str(e)}", parent=self.root)

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
        self.log(f"Found {len(ports)} serial port(s): {', '.join(ports) if ports else 'none'}")

    def toggle_monitoring(self):
        if not self.is_reading:
            self.start_monitoring()
        else:
            self.stop_monitoring()

    def start_monitoring(self):
        try:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Please select a serial port", parent=self.root)
                return

            self.serial_port = serial.Serial(port, 9600, timeout=1)
            time.sleep(2)
            self.is_reading = True

            self.start_button.config(text="STOP MONITORING", bg='#e74c3c')
            self.status_label.config(text="● Connected — Optimising Grid", fg='#27ae60')
            self.grid_status_label.config(text="OPTIMISING", fg='#f39c12')

            for buf in (self.time_data, self.temperature_data, self.humidity_data,
                        self.pulse_data, self.spo2_data, self.energy_data,
                        self.efficiency_data, self.peak_load_data, self.renewable_data):
                buf.clear()

            self.start_time = time.time()
            self.reset_graphs()

            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()

            self.log("=" * 70)
            self.log("ENERGY OPTIMISATION SYSTEM ACTIVATED")
            self.log("=" * 70)
            self.log(f"Port: {port}")
            self.log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.log(f"Optimisation Threshold: {self.saved_threshold} kW")
            self.log(f"Alert Email: {self.saved_email or 'Not configured'}")
            self.log("=" * 70)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open port: {str(e)}", parent=self.root)
            self.status_label.config(text="● Connection Failed", fg="#e74c3c")

    def stop_monitoring(self):
        self.is_reading = False
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.start_button.config(text="START MONITORING", bg='#27ae60')
        self.status_label.config(text="● Disconnected", fg="#e74c3c")
        self.grid_status_label.config(text="STANDBY", fg="#7f8c8d")
        self.log("ENERGY OPTIMISATION SYSTEM DEACTIVATED")
        self.log("=" * 70)

    def reset_graphs(self):
        for line in (self.temp_line, self.humidity_line, self.pulse_line, self.spo2_line):
            line.set_data([], [])
        self.canvas.draw_idle()

    def read_serial_data(self):
        while self.is_reading and self.serial_port and self.serial_port.is_open:
            try:
                line = self.serial_port.readline().decode('utf-8').strip()
                if line:
                    self.data_queue.put(line)
            except Exception as e:
                self.log(f"Serial read error: {str(e)}")
            time.sleep(0.01)

    def update_display(self):
        while not self.data_queue.empty():
            self.process_data(self.data_queue.get())
        if len(self.time_data) > 1:
            self.update_graphs()
        self.root.after(100, self.update_display)

    # ------------------------------------------------------------------
    # Data processing
    # ------------------------------------------------------------------

    def process_data(self, data):
        self.log(data)
        try:
            if 'TEMP:' not in data or 'PULSE:' not in data:
                return

            temperature = humidity = pulse = spo2 = None
            for part in data.split(','):
                if 'TEMP:'  in part: temperature = float(part.replace('TEMP:', '').strip())
                elif 'HUM:' in part: humidity    = float(part.replace('HUM:', '').strip())
                elif 'PULSE:' in part: pulse     = int(part.replace('PULSE:', '').strip())
                elif 'SPO2:' in part: spo2       = int(part.replace('SPO2:', '').strip())

            if None in (temperature, humidity, pulse, spo2):
                return

            energy_consumption    = temperature * 2.4
            grid_efficiency       = humidity
            peak_load             = pulse / 2
            renewable_contribution = spo2
            current_time          = time.time() - self.start_time

            self.time_data.append(current_time)
            self.temperature_data.append(temperature)
            self.humidity_data.append(humidity)
            self.pulse_data.append(pulse)
            self.spo2_data.append(spo2)
            self.energy_data.append(energy_consumption)
            self.efficiency_data.append(grid_efficiency)
            self.peak_load_data.append(peak_load)
            self.renewable_data.append(renewable_contribution)

            self.temp_label.config(text=f"{temperature:.1f} °C")
            self.humidity_label.config(text=f"{humidity:.1f} %")
            self.pulse_label.config(text=f"{pulse} BPM")
            self.spo2_label.config(text=f"{spo2} %")

            if temperature > float(self.saved_threshold):
                self.grid_status_label.config(text="OVERLOAD",     fg="#e74c3c")
            elif renewable_contribution > 70:
                self.grid_status_label.config(text="GREEN ENERGY", fg="#27ae60")
            else:
                self.grid_status_label.config(text="OPTIMISING",   fg="#f39c12")

            self.update_label_colors(temperature, pulse, spo2)

            if temperature > float(self.saved_threshold):
                self.trigger_alert(temperature)

        except Exception as e:
            self.log(f"Parse error: {str(e)} — Data: {data}")

    def update_label_colors(self, temperature, pulse, spo2):
        if   temperature > float(self.saved_threshold): self.temp_label.config(fg="#e74c3c")
        elif temperature < 36:                          self.temp_label.config(fg="#3498db")
        else:                                           self.temp_label.config(fg="#27ae60")

        if pulse > 100 or pulse < 60: self.pulse_label.config(fg="#e74c3c")
        else:                          self.pulse_label.config(fg="#27ae60")

        if spo2 < 95: self.spo2_label.config(fg="#e74c3c")
        else:          self.spo2_label.config(fg="#27ae60")

    def update_graphs(self):
        try:
            t  = list(self.time_data)
            e  = list(self.energy_data)
            ef = list(self.efficiency_data)
            pl = list(self.peak_load_data)
            re = list(self.renewable_data)
            n  = min(len(t), len(e), len(ef), len(pl), len(re))
            if n < 2:
                return
            t, e, ef, pl, re = t[-n:], e[-n:], ef[-n:], pl[-n:], re[-n:]

            self.temp_line.set_data(t, e)
            self.humidity_line.set_data(t, ef)
            self.pulse_line.set_data(t, pl)
            self.spo2_line.set_data(t, re)

            if hasattr(self, 'threshold_line'):
                self.threshold_line.set_ydata([float(self.saved_threshold)] * len(t))

            for ax, data, color in [
                (self.ax1, e,  '#e74c3c'),
                (self.ax2, ef, '#3498db'),
            ]:
                for coll in ax.collections:
                    coll.remove()
                ax.fill_between(t, 0, data, alpha=0.2, color=color)

            x_min = max(0, t[0])
            x_max = t[-1] + 5
            for ax in (self.ax1, self.ax2, self.ax3):
                ax.set_xlim(x_min, x_max)

            self.canvas.draw_idle()

        except Exception as e:
            self.log(f"Graph update error: {str(e)}")

    # ------------------------------------------------------------------
    # Alert system
    # ------------------------------------------------------------------

    def trigger_alert(self, temperature):
        if time.time() - self.last_email_time < self.email_cooldown:
            return
        if not self.saved_email:
            self.log("WARNING: No alert email configured.")
            return
        if not self.alert_playing:
            self.alert_playing      = True
            self.last_email_time    = time.time()
            self.log("!" * 70)
            self.log("GRID ALERT: ENERGY CONSUMPTION EXCEEDED THRESHOLD!")
            self.log(f"Temperature: {temperature:.1f}°C  Threshold: {self.saved_threshold}°C")
            self.log(f"Energy: {temperature * 2.4:.1f} kW  →  Alerting: {self.saved_email}")
            self.log("!" * 70)
            threading.Thread(target=self.play_alarm, daemon=True).start()
            threading.Thread(target=self.capture_and_send_alert, args=(temperature,), daemon=True).start()

    def play_alarm(self):
        try:
            if os.path.exists("alarm.mp3"):
                pygame.mixer.music.load("alarm.mp3")
                pygame.mixer.music.play()
                time.sleep(5)
                pygame.mixer.music.stop()
            else:
                for _ in range(5):
                    print("\a", end='', flush=True)
                    time.sleep(0.5)
                try:
                    import winsound
                    winsound.Beep(1000, 500)
                except Exception:
                    pass
        except Exception as e:
            self.log(f"Alarm error: {str(e)}")
        finally:
            self.alert_playing = False

    def capture_and_send_alert(self, temperature):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename  = f"alerts/grid_alert_{timestamp}.avi"
            if self.capture_video(filename, 5, temperature) and self.saved_email:
                self.send_email(temperature, filename)
        except Exception as e:
            self.log(f"Alert handling error: {str(e)}")

    def capture_video(self, filename, duration, temperature):
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.log("Could not open camera.")
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)

            fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))  or 640
            fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

            out = cv2.VideoWriter(filename, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (fw, fh))
            self.log(f"Recording grid status for {duration}s…")

            start, frames = time.time(), 0
            while time.time() - start < duration:
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                    frames += 1
                    cv2.putText(frame, "GRID ALERT - OVERLOAD DETECTED",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    cv2.putText(frame, f"Temp: {temperature:.1f}C | Thresh: {self.saved_threshold}C",
                                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.putText(frame, f"Energy: {temperature * 2.4:.1f} kW | {datetime.now().strftime('%H:%M:%S')}",
                                (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    cv2.imshow('Grid Alert Recording — Q to stop', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                else:
                    break

            cap.release(); out.release(); cv2.destroyAllWindows()

            if frames > 0:
                self.log(f"Video saved: {filename} ({frames} frames)")
                return True
            self.log("No frames captured")
            return False

        except Exception as e:
            self.log(f"Video capture error: {str(e)}")
            return False

    def send_email(self, temperature, video_file):
        try:
            if not self.email_sender or not self.email_password:
                self.log("Email credentials not configured. Set EMAIL_SENDER and EMAIL_PASSWORD env vars.")
                return

            self.log("Sending alert email…")
            msg = MIMEMultipart()
            msg['From']    = self.email_sender
            msg['To']      = self.saved_email
            msg['Subject'] = f"ENERGY GRID ALERT — OVERLOAD at {datetime.now().strftime('%H:%M:%S')}"

            body = f"""
ENERGY OPTIMIZATION PRO: AI SMART GRID MANAGEMENT
====================================================

GRID ALERT: ENERGY CONSUMPTION THRESHOLD EXCEEDED!

Temperature      : {temperature:.1f}°C
Energy Consumption: {temperature * 2.4:.1f} kW
Threshold Setting : {self.saved_threshold} kW
Time of Alert    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Grid Efficiency         : {self.humidity_label.cget('text')}
Peak Load               : {self.pulse_label.cget('text')}
Renewable Contribution  : {self.spo2_label.cget('text')}

Immediate Actions Required:
1. Check for overload conditions
2. Initiate load-balancing protocols
3. Monitor grid stability
4. Consider activating backup systems

A video recording is attached.
====================================================
Energy Optimization Pro — Making grids smarter, one watt at a time.
"""
            msg.attach(MIMEText(body, 'plain'))

            if os.path.exists(video_file):
                with open(video_file, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition',
                                f'attachment; filename={os.path.basename(video_file)}')
                msg.attach(part)

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)

            self.log(f"Alert email sent to {self.saved_email}")
            try:
                if os.path.exists(video_file):
                    os.remove(video_file)
            except Exception:
                pass

        except Exception as e:
            self.log(f"Email error: {str(e)}")
            try:
                if os.path.exists(video_file):
                    os.rename(video_file, video_file.replace('.avi', '_failed.avi'))
            except Exception:
                pass

    def test_email(self):
        if not self.saved_email:
            messagebox.showerror("Error", "Please save an email first.", parent=self.root)
            return
        if not self.email_sender or not self.email_password:
            messagebox.showerror("Error",
                                 "Set EMAIL_SENDER and EMAIL_PASSWORD environment variables first.",
                                 parent=self.root)
            return
        try:
            self.log("Sending test email…")
            msg = MIMEMultipart()
            msg['From']    = self.email_sender
            msg['To']      = self.saved_email
            msg['Subject'] = "Test Email — Energy Optimization Pro"
            msg.attach(MIMEText(
                f"Test successful!\nTime: {datetime.now()}\nThreshold: {self.saved_threshold} kW",
                'plain'
            ))
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            messagebox.showinfo("Success", "Test email sent!", parent=self.root)
            self.log(f"Test email sent to {self.saved_email}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {str(e)}", parent=self.root)
            self.log(str(e))

    def test_camera(self):
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                messagebox.showerror("Error", "Could not open camera", parent=self.root)
                return
            self.log("Testing camera — press Q to close")
            while True:
                ret, frame = cap.read()
                if ret:
                    cv2.putText(frame, "Energy Optimization Pro — Camera Test",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.imshow('Camera Test', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                else:
                    break
            cap.release(); cv2.destroyAllWindows()
            self.log("Camera test completed")
        except Exception as e:
            messagebox.showerror("Error", f"Camera test failed: {str(e)}", parent=self.root)

    def clear_log(self):
        self.log_area.delete(1.0, tk.END)

    def log(self, message):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_area.insert(tk.END, f"[{ts}] {message}\n")
        self.log_area.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app  = EnergyOptimizationSystem(root)
    root.mainloop()
