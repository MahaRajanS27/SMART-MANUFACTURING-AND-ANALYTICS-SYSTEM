import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime, timedelta
import random
import mysql.connector  # Import the MySQL connector

# --- Configuration Constants ---
REFRESH_INTERVAL_MS = 2000  # Refresh live sensor data every 2 seconds
MAX_LIVE_DATA_POINTS = 100  # Max data points to display on live plots
APP_TITLE = "Smart Manufacturing & Analytics System"

# --- Database Configuration ---
# !!! IMPORTANT: UPDATE THESE DETAILS WITH YOUR MYSQL CREDENTIALS !!!
DB_CONFIG = {
    'host': 'localhost',         # SHOULD BE 'localhost' or '127.0.0.1'
    'user': 'root',   # REPLACE with your MySQL username (e.g., 'root')
    'password': 'R12345678', # REPLACE with your MySQL password
    'database': 'manufacturing'  # Updated to match your actual DB name!
}
# Default MySQL port is 3306. You typically don't need to specify it
# unless it's non-standard, or if the host isn't 'localhost'.
# For example, if you explicitly needed to specify it:
# 'port': 3306,

# --- Custom Styling Configuration ---
# Color Palette (Dark Theme for industrial feel)
COLOR_BACKGROUND_DARK = "#2E2E2E"
COLOR_BACKGROUND_LIGHT = "#3C3C3C"
COLOR_FOREGROUND_LIGHT = "#F0F0F0"
COLOR_ACCENT = "#007ACC"  # Blue for highlights
COLOR_ERROR = "#DC3545"  # Red for potential issues
COLOR_SUCCESS = "#28A745"  # Green for good status

# Fonts
FONT_TITLE = ("Arial", 16, "bold")
FONT_HEADING = ("Arial", 12, "bold")
FONT_NORMAL = ("Arial", 10)
FONT_MONO = ("Consolas", 10)


# --- Database Manager Class ---
class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.connection = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                print("Database connection successful.")
            return self.connection
        except mysql.connector.Error as err:
            messagebox.showerror("Database Error", f"Error connecting to MySQL: {err}")
            print(f"Error connecting to MySQL: {err}")
            self.connection = None
            return None

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Database connection closed.")

    def fetch_data(self, query, params=None):
        if not self.connection or not self.connection.is_connected():
            self.connect()  # Attempt to reconnect if disconnected

        if self.connection:
            try:
                cursor = self.connection.cursor(dictionary=True)  # Fetch rows as dictionaries
                cursor.execute(query, params)
                result = cursor.fetchall()
                cursor.close()
                return result
            except mysql.connector.Error as err:
                # Catch specific error for table not found, etc., if needed
                messagebox.showerror("Database Query Error", f"Error fetching data: {err}\nQuery: {query}")
                print(f"Error fetching data: {err}\nQuery: {query}")
                return None
        return None

    def execute_query(self, query, params=None):
        if not self.connection or not self.connection.is_connected():
            self.connect()

        if self.connection:
            try:
                cursor = self.connection.cursor()
                cursor.execute(query, params)
                self.connection.commit()
                cursor.close()
                return True
            except mysql.connector.Error as err:
                messagebox.showerror("Database Execute Error", f"Error executing query: {err}\nQuery: {query}")
                print(f"Error executing query: {err}\nQuery: {query}")
                self.connection.rollback()
                return False
        return False


class SmartManufacturingApp:
    def __init__(self, master):
        self.master = master
        self.master.title(APP_TITLE)
        self.master.geometry("1400x900")  # Increased size for more content
        self.master.configure(bg=COLOR_BACKGROUND_DARK)

        self.db_manager = DatabaseManager(DB_CONFIG)
        self.db_manager.connect()  # Connect to DB on startup

        self.running_simulation = False
        self.live_data_df = self._initialize_live_data()  # For simulated sensor data

        self._setup_styles()
        self._create_widgets()
        self._setup_matplotlib_plots()

        # Load initial database data
        self.load_all_db_data()

        # Start simulation automatically
        self.start_live_simulation()

        # Ensure database connection is closed on app exit
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.stop_live_simulation()
        self.db_manager.disconnect()
        self.master.destroy()

    def _initialize_live_data(self):
        """Initializes an empty Pandas DataFrame for live simulated manufacturing data."""
        return pd.DataFrame(columns=[
            'timestamp', 'temperature', 'pressure', 'vibration',
            'defects', 'production_rate'
        ])

    def _setup_styles(self):
        """Applies custom styling to Tkinter widgets using ttk.Style."""
        style = ttk.Style(self.master)
        style.theme_use('clam')

        # Overall application background
        style.configure('.', background=COLOR_BACKGROUND_DARK, foreground=COLOR_FOREGROUND_LIGHT, font=FONT_NORMAL)

        # Frames
        style.configure('TFrame', background=COLOR_BACKGROUND_DARK)
        style.configure('Light.TFrame', background=COLOR_BACKGROUND_LIGHT)

        # Labels
        style.configure('TLabel', background=COLOR_BACKGROUND_DARK, foreground=COLOR_FOREGROUND_LIGHT)
        style.configure('Heading.TLabel', font=FONT_HEADING, foreground=COLOR_ACCENT)
        style.configure('Title.TLabel', font=FONT_TITLE, foreground=COLOR_FOREGROUND_LIGHT, background=COLOR_ACCENT)
        style.configure('Data.TLabel', font=FONT_MONO, foreground=COLOR_FOREGROUND_LIGHT)

        # Buttons
        style.configure('TButton',
                        background=COLOR_ACCENT,
                        foreground=COLOR_FOREGROUND_LIGHT,
                        font=FONT_NORMAL,
                        relief="flat",
                        padding=5)
        style.map('TButton',
                  background=[('active', COLOR_ACCENT)])

        style.configure('Stop.TButton', background=COLOR_ERROR)
        style.map('Stop.TButton', background=[('active', COLOR_ERROR)])

        # Notebook (Tabs)
        style.configure('TNotebook', background=COLOR_BACKGROUND_DARK, foreground=COLOR_FOREGROUND_LIGHT, borderwidth=0)
        style.configure('TNotebook.Tab', background=COLOR_BACKGROUND_LIGHT, foreground=COLOR_FOREGROUND_LIGHT,
                        padding=[10, 5])
        style.map('TNotebook.Tab',
                  background=[('selected', COLOR_ACCENT), ('active', COLOR_BACKGROUND_LIGHT)],
                  foreground=[('selected', COLOR_FOREGROUND_LIGHT), ('active', COLOR_FOREGROUND_LIGHT)])

        # Treeview (for tabular data from DB)
        style.configure("Treeview",
                        background=COLOR_BACKGROUND_DARK,
                        foreground=COLOR_FOREGROUND_LIGHT,
                        fieldbackground=COLOR_BACKGROUND_DARK,
                        rowheight=25,
                        borderwidth=0)
        style.map('Treeview',
                  background=[('selected', COLOR_ACCENT)])  # Selected row background
        style.configure("Treeview.Heading",
                        font=FONT_HEADING,
                        background=COLOR_ACCENT,
                        foreground=COLOR_FOREGROUND_LIGHT,
                        relief="flat")
        style.map("Treeview.Heading",
                  background=[('active', COLOR_ACCENT)])

    def _create_widgets(self):
        """Creates and places all GUI widgets, now using Notebook for tabs."""
        # --- Main Layout Frames ---
        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)

        # Header Frame
        header_frame = ttk.Frame(self.master, style='Light.TFrame')
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header_frame.grid_columnconfigure(0, weight=1)
        ttk.Label(header_frame, text=APP_TITLE, style='Title.TLabel', anchor='center', background=COLOR_ACCENT).grid(
            row=0, column=0, sticky="ew", pady=5)

        # --- Notebook (Tabbed Interface) ---
        self.notebook = ttk.Notebook(self.master, style='TNotebook')
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # --- Existing Tabs ---
        self.historical_production_tab = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.historical_production_tab, text=' Historical Production ')
        self._create_historical_production_tab(self.historical_production_tab)

        self.manufacturing_assets_tab = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.manufacturing_assets_tab, text=' Manufacturing & Assets ')
        self._create_manufacturing_assets_tab(self.manufacturing_assets_tab)

        self.financial_orders_tab = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.financial_orders_tab, text=' Financial & Orders ')
        self._create_financial_orders_tab(self.financial_orders_tab)

        self.orders_tab = self.financial_orders_tab  # Financial & Orders tab contains orders

        # --- New Tabs for Live Data ---
        self.live_sensor_readings_tab = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.live_sensor_readings_tab, text=' Live Sensor Readings ')
        self._create_live_sensor_readings_tab(self.live_sensor_readings_tab)

        self.live_production_metrics_tab = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.live_production_metrics_tab, text=' Live Production Metrics ')
        self._create_live_production_metrics_tab(self.live_production_metrics_tab)

        # --- Control Buttons (at the bottom, apply to overall app or selected tab) ---
        control_frame = ttk.Frame(self.master, style='Light.TFrame')
        control_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        control_frame.grid_columnconfigure(2, weight=1)

        ttk.Button(control_frame, text="Start Live Simulation", command=self.start_live_simulation).grid(row=0,
                                                                                                         column=0,
                                                                                                         padx=5, pady=5,
                                                                                                         sticky="ew")
        ttk.Button(control_frame, text="Stop Live Simulation", style='Stop.TButton',
                   command=self.stop_live_simulation).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(control_frame, text="Refresh DB Data", command=self.load_all_db_data).grid(row=0, column=2, padx=5,
                                                                                              pady=5, sticky="ew")

    def _create_live_sensor_readings_tab(self, parent_frame):
        """Widgets for the Live Sensor Readings tab (formerly part of Live Monitoring)."""
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)

        # Current Status Panel
        status_panel = ttk.Frame(parent_frame, style='Light.TFrame', padding="10 10 10 10")
        status_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        status_panel.grid_columnconfigure(1, weight=1)

        ttk.Label(status_panel, text="Current Machine Status", style='Heading.TLabel').grid(row=0, column=0,
                                                                                            columnspan=2, sticky="w",
                                                                                            pady=5)

        self.labels = {}
        row_idx = 1
        for key, text in [
            ("timestamp", "Last Update:"),
            ("temperature", "Temperature (C):"),
            ("pressure", "Pressure (kPa):"),
            ("vibration", "Vibration (mm/s):"),
            ("defects", "Defects (count):"),
            ("production_rate", "Prod. Rate (units/hr):")
        ]:
            ttk.Label(status_panel, text=text, style='TLabel').grid(row=row_idx, column=0, sticky="w", pady=2)
            self.labels[key] = ttk.Label(status_panel, text="N/A", style='Data.TLabel')
            self.labels[key].grid(row=row_idx, column=1, sticky="e", pady=2)
            row_idx += 1

        # Plot Frame for Live Sensor Readings
        self.live_plot_frame_sensors = ttk.Frame(parent_frame, style='Light.TFrame', padding="5")
        self.live_plot_frame_sensors.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.live_plot_frame_sensors.grid_columnconfigure(0, weight=1)
        self.live_plot_frame_sensors.grid_rowconfigure(0, weight=1)  # For canvas
        self.live_plot_frame_sensors.grid_rowconfigure(1, weight=0)  # For toolbar (fixed height)

    def _create_live_production_metrics_tab(self, parent_frame):
        """Widgets for the Live Production Metrics tab (formerly part of Live Monitoring)."""
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)

        # Plot Frame for Live Production Metrics
        self.live_plot_frame_production = ttk.Frame(parent_frame, style='Light.TFrame', padding="5")
        self.live_plot_frame_production.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.live_plot_frame_production.grid_columnconfigure(0, weight=1)
        self.live_plot_frame_production.grid_rowconfigure(0, weight=1)  # For canvas
        self.live_plot_frame_production.grid_rowconfigure(1, weight=0)  # For toolbar (fixed height)

    def _create_historical_production_tab(self, parent_frame):
        """Widgets for the Historical Production tab."""
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)  # Plots
        parent_frame.grid_rowconfigure(1, weight=1)  # Treeview

        # Plots for Historical Production
        plot_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        plot_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        plot_frame.grid_columnconfigure(0, weight=1)
        plot_frame.grid_columnconfigure(1, weight=1)
        plot_frame.grid_rowconfigure(0, weight=1)  # Each plot will take half width

        self.hist_prod_plot_frame = ttk.Frame(plot_frame, style='Light.TFrame')
        self.hist_prod_plot_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.hist_prod_plot_frame.grid_columnconfigure(0, weight=1)
        self.hist_prod_plot_frame.grid_rowconfigure(0, weight=1)  # For canvas
        self.hist_prod_plot_frame.grid_rowconfigure(1, weight=0)  # For toolbar

        self.hist_defects_plot_frame = ttk.Frame(plot_frame, style='Light.TFrame')
        self.hist_defects_plot_frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        self.hist_defects_plot_frame.grid_columnconfigure(0, weight=1)
        self.hist_defects_plot_frame.grid_rowconfigure(0, weight=1)  # For canvas
        self.hist_defects_plot_frame.grid_rowconfigure(1, weight=0)  # For toolbar

        # Treeview for Historical Production Data
        table_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        ttk.Label(table_frame, text="Recent Production & Quality Records", style='Heading.TLabel').pack(pady=5,
                                                                                                        anchor='w')
        # Use the updated _create_treeview
        self.production_tree, production_tree_wrapper = self._create_treeview(table_frame,
                                                                              ('prod_id', 'product', 'machine',
                                                                               'worker', 'date', 'qty', 'hours',
                                                                               'defective', 'passed', 'inspector'))
        production_tree_wrapper.pack(fill='both', expand=True)  # Pack the wrapper frame into table_frame

        self.production_tree.heading('prod_id', text='Prod ID', anchor='center')
        self.production_tree.heading('product', text='Product Name', anchor='w')
        self.production_tree.heading('machine', text='Machine', anchor='w')
        self.production_tree.heading('worker', text='Worker', anchor='w')
        self.production_tree.heading('date', text='Date', anchor='center')
        self.production_tree.heading('qty', text='Qty Prod.', anchor='e')
        self.production_tree.heading('hours', text='Hours', anchor='e')
        self.production_tree.heading('defective', text='Defective', anchor='e')
        self.production_tree.heading('passed', text='Passed', anchor='e')
        self.production_tree.heading('inspector', text='Inspector', anchor='w')

        # Set column widths
        self.production_tree.column('prod_id', width=60, anchor='center')
        self.production_tree.column('product', width=150)
        self.production_tree.column('machine', width=120)
        self.production_tree.column('worker', width=120)
        self.production_tree.column('date', width=100, anchor='center')
        self.production_tree.column('qty', width=80, anchor='e')
        self.production_tree.column('hours', width=70, anchor='e')
        self.production_tree.column('defective', width=80, anchor='e')
        self.production_tree.column('passed', width=80, anchor='e')
        self.production_tree.column('inspector', width=120)

    def _create_manufacturing_assets_tab(self, parent_frame):
        """Widgets for the Manufacturing Assets tab."""
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(1, weight=1)
        parent_frame.grid_rowconfigure(2, weight=1)

        # Products Table
        prod_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        prod_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        prod_frame.grid_columnconfigure(0, weight=1)
        prod_frame.grid_rowconfigure(0, weight=1)
        ttk.Label(prod_frame, text="Products Catalog", style='Heading.TLabel').pack(pady=5, anchor='w')
        self.products_tree, products_tree_wrapper = self._create_treeview(prod_frame,
                                                                          ('id', 'name', 'category', 'cost'))
        products_tree_wrapper.pack(fill='both', expand=True)
        self.products_tree.heading('id', text='ID');
        self.products_tree.heading('name', text='Name');
        self.products_tree.heading('category', text='Category');
        self.products_tree.heading('cost', text='Std Cost')
        self.products_tree.column('id', width=50, anchor='center');
        self.products_tree.column('cost', width=100, anchor='e')

        # Machines Table
        machine_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        machine_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        machine_frame.grid_columnconfigure(0, weight=1)
        machine_frame.grid_rowconfigure(0, weight=1)
        ttk.Label(machine_frame, text="Machines Overview", style='Heading.TLabel').pack(pady=5, anchor='w')
        self.machines_tree, machines_tree_wrapper = self._create_treeview(machine_frame,
                                                                          ('id', 'name', 'date', 'status', 'location'))
        machines_tree_wrapper.pack(fill='both', expand=True)
        self.machines_tree.heading('id', text='ID');
        self.machines_tree.heading('name', text='Name');
        self.machines_tree.heading('date', text='Installation Date');
        self.machines_tree.heading('status', text='Status');
        self.machines_tree.heading('location', text='Location')
        self.machines_tree.column('id', width=50, anchor='center');
        self.machines_tree.column('date', width=120, anchor='center');
        self.machines_tree.column('status', width=100, anchor='center')

        # Workers Table
        worker_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        worker_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        worker_frame.grid_columnconfigure(0, weight=1)
        worker_frame.grid_rowconfigure(0, weight=1)
        ttk.Label(worker_frame, text="Workers Directory", style='Heading.TLabel').pack(pady=5, anchor='w')
        self.workers_tree, workers_tree_wrapper = self._create_treeview(worker_frame,
                                                                        ('id', 'name', 'department', 'shift',
                                                                         'hire_date', 'phone'))
        workers_tree_wrapper.pack(fill='both', expand=True)
        self.workers_tree.heading('id', text='ID');
        self.workers_tree.heading('name', text='Name');
        self.workers_tree.heading('department', text='Department');
        self.workers_tree.heading('shift', text='Shift');
        self.workers_tree.heading('hire_date', text='Hire Date');
        self.workers_tree.column('phone', width=120, anchor='center')
        self.workers_tree.column('id', width=50, anchor='center');
        self.workers_tree.column('hire_date', width=100, anchor='center');
        self.workers_tree.column('shift', width=80, anchor='center');
        self.workers_tree.column('phone', width=120, anchor='center')

    def _create_financial_orders_tab(self, parent_frame):
        """Widgets for the Financial & Orders tab."""
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_rowconfigure(0, weight=1)  # Profit plot
        parent_frame.grid_rowconfigure(1, weight=1)  # Orders table

        # Profit Plot
        profit_plot_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        profit_plot_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        profit_plot_frame.grid_columnconfigure(0, weight=1)
        profit_plot_frame.grid_rowconfigure(0, weight=1)  # For canvas
        profit_plot_frame.grid_rowconfigure(1, weight=0)  # For toolbar
        self.profit_plot_frame = profit_plot_frame  # Store for later Matplotlib embedding

        # Orders Table
        orders_table_frame = ttk.Frame(parent_frame, style='Light.TFrame', padding=5)
        orders_table_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        orders_table_frame.grid_columnconfigure(0, weight=1)
        orders_table_frame.grid_rowconfigure(0, weight=1)

        ttk.Label(orders_table_frame, text="Outstanding Orders", style='Heading.TLabel').pack(pady=5, anchor='w')
        self.orders_tree, orders_tree_wrapper = self._create_treeview(orders_table_frame,
                                                                      ('order_id', 'product_name', 'total', 'remaining',
                                                                       'delivery_date'))
        orders_tree_wrapper.pack(fill='both', expand=True)
        self.orders_tree.heading('order_id', text='Order ID');
        self.orders_tree.heading('product_name', text='Product Name');
        self.orders_tree.heading('total', text='Total Orders');
        self.orders_tree.heading('remaining', text='Remaining');
        self.orders_tree.heading('delivery_date', text='Delivery Date')
        self.orders_tree.column('order_id', width=80, anchor='center');
        self.orders_tree.column('product_name', width=150);
        self.orders_tree.column('total', width=100, anchor='e');
        self.orders_tree.column('remaining', width=100, anchor='e');
        self.orders_tree.column('delivery_date', width=120, anchor='center')

    def _create_treeview(self, parent_frame, columns):
        """Helper to create a Treeview widget with scrollbar,
           returning the Treeview instance and its wrapper frame."""
        tree_wrapper_frame = ttk.Frame(parent_frame, style='TFrame')

        tree = ttk.Treeview(tree_wrapper_frame, columns=columns, show='headings', style="Treeview")
        tree_scrollbar_y = ttk.Scrollbar(tree_wrapper_frame, orient="vertical", command=tree.yview)
        tree_scrollbar_x = ttk.Scrollbar(tree_wrapper_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=tree_scrollbar_y.set, xscrollcommand=tree_scrollbar_x.set)

        tree.grid(row=0, column=0, sticky='nsew')
        tree_scrollbar_y.grid(row=0, column=1, sticky='ns')
        tree_scrollbar_x.grid(row=1, column=0, sticky='ew')

        tree_wrapper_frame.grid_rowconfigure(0, weight=1)
        tree_wrapper_frame.grid_columnconfigure(0, weight=1)

        return tree, tree_wrapper_frame  # Return both the tree for populating and its wrapper frame for placement by caller

    def _setup_matplotlib_plots(self):
        """Initializes Matplotlib figures and embeds them into Tkinter frames."""
        # --- Live Monitoring Plots ---
        self.fig_live_sensors, self.ax_live_sensors = plt.subplots(figsize=(8, 4), dpi=100)
        self.canvas_live_sensors = FigureCanvasTkAgg(self.fig_live_sensors, master=self.live_plot_frame_sensors)
        self.canvas_live_sensors_widget = self.canvas_live_sensors.get_tk_widget()
        self.canvas_live_sensors_widget.grid(row=0, column=0, sticky="nsew")

        # Live Sensors Toolbar: Create a dedicated frame for it
        self.live_toolbar_frame_sensors = ttk.Frame(self.live_plot_frame_sensors, style='Light.TFrame')
        self.live_toolbar_frame_sensors.grid(row=1, column=0, sticky="ew")
        self.toolbar_live_sensors = NavigationToolbar2Tk(self.canvas_live_sensors, self.live_toolbar_frame_sensors)
        self.toolbar_live_sensors.update()  # This will pack the toolbar into live_toolbar_frame_sensors

        self.fig_live_production, self.ax_live_production = plt.subplots(figsize=(10, 3), dpi=100)
        self.canvas_live_production = FigureCanvasTkAgg(self.fig_live_production,
                                                        master=self.live_plot_frame_production)
        self.canvas_live_production_widget = self.canvas_live_production.get_tk_widget()
        self.canvas_live_production_widget.grid(row=0, column=0, sticky="nsew")

        # Live Production Toolbar: Create a dedicated frame for it
        self.live_toolbar_frame_production = ttk.Frame(self.live_plot_frame_production, style='Light.TFrame')
        self.live_toolbar_frame_production.grid(row=1, column=0, sticky="ew")
        self.toolbar_live_production = NavigationToolbar2Tk(self.canvas_live_production,
                                                            self.live_toolbar_frame_production)
        self.toolbar_live_production.update()

        # --- Historical Production Plots ---
        self.fig_hist_prod, self.ax_hist_prod = plt.subplots(figsize=(6, 3), dpi=100)
        self.canvas_hist_prod = FigureCanvasTkAgg(self.fig_hist_prod, master=self.hist_prod_plot_frame)
        self.canvas_hist_prod_widget = self.canvas_hist_prod.get_tk_widget()
        self.canvas_hist_prod_widget.grid(row=0, column=0, sticky="nsew")

        # Historical Production Toolbar: Create a dedicated frame for it
        self.hist_toolbar_frame_prod = ttk.Frame(self.hist_prod_plot_frame, style='Light.TFrame')
        self.hist_toolbar_frame_prod.grid(row=1, column=0, sticky="ew")
        self.toolbar_hist_prod = NavigationToolbar2Tk(self.canvas_hist_prod, self.hist_toolbar_frame_prod)
        self.toolbar_hist_prod.update()

        self.fig_hist_defects, self.ax_hist_defects = plt.subplots(figsize=(6, 3), dpi=100)
        self.canvas_hist_defects = FigureCanvasTkAgg(self.fig_hist_defects, master=self.hist_defects_plot_frame)
        self.canvas_hist_defects_widget = self.canvas_hist_defects.get_tk_widget()
        self.canvas_hist_defects_widget.grid(row=0, column=0, sticky="nsew")

        # Historical Defects Toolbar: Create a dedicated frame for it
        self.hist_toolbar_frame_defects = ttk.Frame(self.hist_defects_plot_frame, style='Light.TFrame')
        self.hist_toolbar_frame_defects.grid(row=1, column=0, sticky="ew")
        self.toolbar_hist_defects = NavigationToolbar2Tk(self.canvas_hist_defects, self.hist_toolbar_frame_defects)
        self.toolbar_hist_defects.update()

        # --- Financial Plot ---
        self.fig_profit, self.ax_profit = plt.subplots(figsize=(10, 4), dpi=100)
        self.canvas_profit = FigureCanvasTkAgg(self.fig_profit, master=self.profit_plot_frame)
        self.canvas_profit_widget = self.canvas_profit.get_tk_widget()
        self.canvas_profit_widget.grid(row=0, column=0, sticky="nsew")

        # Profit Toolbar: Create a dedicated frame for it
        self.profit_toolbar_frame = ttk.Frame(self.profit_plot_frame, style='Light.TFrame')
        self.profit_toolbar_frame.grid(row=1, column=0, sticky="ew")
        self.toolbar_profit = NavigationToolbar2Tk(self.canvas_profit, self.profit_toolbar_frame)
        self.toolbar_profit.update()

        # Call configure_plot_style after all toolbars are setup.
        self._configure_plot_style(self.fig_live_sensors, self.ax_live_sensors, "Live Sensor Readings")
        self._configure_plot_style(self.fig_live_production, self.ax_live_production, "Live Production Metrics")
        self._configure_plot_style(self.fig_hist_prod, self.ax_hist_prod, "Historical Quantity Produced")
        self._configure_plot_style(self.fig_hist_defects, self.ax_hist_defects, "Historical Defective Units")
        self._configure_plot_style(self.fig_profit, self.ax_profit, "Monthly Net Profit Trend")

    def _configure_plot_style(self, fig, ax, title):
        """Applies consistent styling to Matplotlib plots."""
        fig.patch.set_facecolor(COLOR_BACKGROUND_LIGHT)
        ax.set_facecolor(COLOR_BACKGROUND_DARK)
        ax.tick_params(axis='x', colors=COLOR_FOREGROUND_LIGHT)
        ax.tick_params(axis='y', colors=COLOR_FOREGROUND_LIGHT)
        ax.xaxis.label.set_color(COLOR_FOREGROUND_LIGHT)
        ax.yaxis.label.set_color(COLOR_FOREGROUND_LIGHT)
        ax.title.set_color(COLOR_FOREGROUND_LIGHT)
        ax.set_title(title, fontdict={'fontsize': 12, 'fontweight': 'bold'})
        ax.grid(True, linestyle='--', alpha=0.6, color=COLOR_FOREGROUND_LIGHT)
        ax.spines['bottom'].set_color(COLOR_FOREGROUND_LIGHT)
        ax.spines['top'].set_color(COLOR_FOREGROUND_LIGHT)
        ax.spines['left'].set_color(COLOR_FOREGROUND_LIGHT)
        ax.spines['right'].set_color(COLOR_FOREGROUND_LIGHT)
        plt.tight_layout()  # Adjust layout to prevent labels overlapping

    def _generate_new_data_point(self):
        """Generates a single new row of synthetic manufacturing data."""
        timestamp = datetime.now()
        # Sensor data (with some random fluctuations)
        temperature = np.random.normal(loc=70, scale=3)
        pressure = np.random.normal(loc=150, scale=10)
        vibration = np.random.normal(loc=5, scale=1.5)

        # Production data
        defects = random.randint(0, 3) if random.random() < 0.2 else 0  # 20% chance of defects
        production_rate = np.random.uniform(90, 110)  # units per hour

        return {
            'timestamp': timestamp,
            'temperature': max(0, round(temperature, 2)),
            'pressure': max(0, round(pressure, 2)),
            'vibration': max(0, round(vibration, 2)),
            'defects': defects,
            'production_rate': round(production_rate, 2)
        }

    def _update_live_data_and_gui(self):
        """
        Generates new live data, appends to DataFrame, updates GUI labels and plots.
        Scheduled to run periodically for the Live Monitoring tab.
        """
        if self.running_simulation:
            new_data = self._generate_new_data_point()
            self.live_data_df = pd.concat([self.live_data_df, pd.DataFrame([new_data])], ignore_index=True)

            # Keep only the latest MAX_LIVE_DATA_POINTS
            if len(self.live_data_df) > MAX_LIVE_DATA_POINTS:
                self.live_data_df = self.live_data_df.iloc[-MAX_LIVE_DATA_POINTS:].reset_index(drop=True)

            self._update_current_status_labels(new_data)
            self._update_live_sensor_plot()
            self._update_live_production_plot()

        self.master.after(REFRESH_INTERVAL_MS, self._update_live_data_and_gui)

    def _update_current_status_labels(self, latest_data):
        """Updates the current status labels in the GUI."""
        self.labels["timestamp"].config(text=latest_data['timestamp'].strftime("%Y-%m-%d %H:%M:%S"))
        self.labels["temperature"].config(text=f"{latest_data['temperature']} °C")
        self.labels["pressure"].config(text=f"{latest_data['pressure']} kPa")
        self.labels["vibration"].config(text=f"{latest_data['vibration']} mm/s")
        self.labels["defects"].config(text=f"{latest_data['defects']}")
        self.labels["production_rate"].config(text=f"{latest_data['production_rate']} units/hr")

        # Optional: Add color coding for alerts
        temp_color = COLOR_SUCCESS if latest_data['temperature'] < 75 else COLOR_ERROR
        pressure_color = COLOR_SUCCESS if latest_data['pressure'] < 170 else COLOR_ERROR
        vibration_color = COLOR_SUCCESS if latest_data['vibration'] < 7 else COLOR_ERROR
        defects_color = COLOR_SUCCESS if latest_data['defects'] == 0 else COLOR_ERROR

        self.labels["temperature"].config(foreground=temp_color)
        self.labels["pressure"].config(foreground=pressure_color)
        self.labels["vibration"].config(foreground=vibration_color)
        self.labels["defects"].config(foreground=defects_color)
        self.labels["production_rate"].config(foreground=COLOR_FOREGROUND_LIGHT)  # No special color for rate

    def _update_live_sensor_plot(self):
        """Updates the live sensor data plot."""
        self.ax_live_sensors.cla()  # Clear current axes
        self._configure_plot_style(self.fig_live_sensors, self.ax_live_sensors, "Live Sensor Readings")

        if not self.live_data_df.empty:
            timestamps = self.live_data_df['timestamp'].apply(lambda x: x.strftime('%H:%M:%S'))
            x_indices = np.arange(len(timestamps))  # Numeric indices for plotting

            self.ax_live_sensors.plot(x_indices, self.live_data_df['temperature'], label='Temperature (°C)',
                                      color='red')
            self.ax_live_sensors.plot(x_indices, self.live_data_df['pressure'], label='Pressure (kPa)', color='blue')
            self.ax_live_sensors.plot(x_indices, self.live_data_df['vibration'], label='Vibration (mm/s)',
                                      color='green')

            self.ax_live_sensors.set_xlabel("Time")
            self.ax_live_sensors.set_ylabel("Value")
            self.ax_live_sensors.legend(loc='upper left', frameon=False, labelcolor=COLOR_FOREGROUND_LIGHT)
            num_ticks = min(5, len(x_indices))  # Show up to 5 ticks
            if num_ticks > 0:
                self.ax_live_sensors.set_xticks(x_indices[::len(x_indices) // num_ticks + 1])
                self.ax_live_sensors.set_xticklabels(timestamps[::len(timestamps) // num_ticks + 1], rotation=45,
                                                     ha='right')
            else:
                self.ax_live_sensors.set_xticks([])

        self.canvas_live_sensors.draw_idle()

    def _update_live_production_plot(self):
        """Updates the live production data plot."""
        self.ax_live_production.cla()  # Clear current axes
        self._configure_plot_style(self.fig_live_production, self.ax_live_production, "Live Production Metrics")

        if not self.live_data_df.empty:
            timestamps = self.live_data_df['timestamp'].apply(lambda x: x.strftime('%H:%M:%S'))
            x_indices = np.arange(len(timestamps))

            # Production Rate (Line Plot)
            self.ax_live_production.plot(x_indices, self.live_data_df['production_rate'], label='Prod. Rate (units/hr)',
                                         color='cyan', linestyle='-')
            self.ax_live_production.set_ylabel("Prod. Rate", color='cyan')
            self.ax_live_production.tick_params(axis='y', labelcolor='cyan')

            # Defects (Bar Plot on a secondary Y-axis)
            ax2 = self.ax_live_production.twinx()
            ax2.bar(x_indices, self.live_data_df['defects'], label='Defects', color='orange', alpha=0.6, width=0.8)
            ax2.set_ylabel("Defects", color='orange')
            ax2.tick_params(axis='y', labelcolor='orange')
            ax2.tick_params(axis='x', colors=COLOR_FOREGROUND_LIGHT)  # Keep x-axis labels foreground color
            ax2.spines['right'].set_color('orange')  # Color for secondary y-axis spine
            ax2.spines['left'].set_color('cyan')  # Color for primary y-axis spine

            # Set X-axis labels for both plots
            self.ax_live_production.set_xlabel("Time")
            num_ticks = min(5, len(x_indices))
            if num_ticks > 0:
                self.ax_live_production.set_xticks(x_indices[::len(x_indices) // num_ticks + 1])
                self.ax_live_production.set_xticklabels(timestamps[::len(timestamps) // num_ticks + 1], rotation=45,
                                                        ha='right')
            else:
                self.ax_live_production.set_xticks([])

            # Combined legend
            lines, labels = self.ax_live_production.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.ax_live_production.legend(lines + lines2, labels + labels2, loc='upper left', frameon=False,
                                           labelcolor=COLOR_FOREGROUND_LIGHT)

        self.canvas_live_production.draw_idle()

    def start_live_simulation(self):
        """Starts the data generation and GUI update loop for live data."""
        if not self.running_simulation:
            self.running_simulation = True
            print("Live Simulation Started.")
            # Immediately run once, then schedule
            self._update_live_data_and_gui()

    def stop_live_simulation(self):
        """Stops the data generation and GUI update loop for live data."""
        self.running_simulation = False
        print("Live Simulation Stopped.")

    def clear_live_data(self):
        """Clears all accumulated live data and resets the GUI."""
        self.stop_live_simulation()
        self.live_data_df = self._initialize_live_data()
        print("Live Data Cleared.")
        # Reset labels
        for key in self.labels:
            self.labels[key].config(text="N/A", foreground=COLOR_FOREGROUND_LIGHT)
        # Clear plots
        self.ax_live_sensors.cla()
        self._configure_plot_style(self.fig_live_sensors, self.ax_live_sensors, "Live Sensor Readings")
        self.canvas_live_sensors.draw_idle()

        self.ax_live_production.cla()
        self._configure_plot_style(self.fig_live_production, self.ax_live_production, "Live Production Metrics")
        self.canvas_live_production.draw_idle()

    # --- Database Loading Functions ---
    def load_all_db_data(self):
        print("Refreshing all database data...")
        self._load_products_data()
        self._load_machines_data()
        self._load_workers_data()
        self._load_production_quality_data()
        self._load_profit_data()
        self._load_orders_data()
        print("Database data refresh complete.")

    def _clear_treeview(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _load_products_data(self):
        self._clear_treeview(self.products_tree)
        query = "SELECT product_id, product_name, category, standard_cost FROM products ORDER BY product_id ASC"
        products = self.db_manager.fetch_data(query)
        if products:
            for p in products:
                self.products_tree.insert('', tk.END, values=(p['product_id'], p['product_name'], p['category'],
                                                              f"{p['standard_cost']:.2f}"))

    def _load_machines_data(self):
        self._clear_treeview(self.machines_tree)
        query = "SELECT machine_id, machine_name, installation_date, status, location FROM machines ORDER BY machine_id ASC"
        machines = self.db_manager.fetch_data(query)
        if machines:
            for m in machines:
                # Example of conditional styling based on status
                tags = ()
                if m['status'] == 'Active':
                    tags = ('active_machine',)
                elif m['status'] == 'Maintenance':
                    tags = ('maintenance_machine',)
                elif m['status'] == 'Inactive':
                    tags = ('inactive_machine',)

                self.machines_tree.insert('', tk.END,
                                          values=(m['machine_id'], m['machine_name'], m['installation_date'],
                                                  m['status'], m['location']), tags=tags)

            # Configure tags globally (only needs to be done once, but safe here)
            self.machines_tree.tag_configure('active_machine', foreground=COLOR_SUCCESS)
            self.machines_tree.tag_configure('maintenance_machine', foreground=COLOR_ERROR)
            self.machines_tree.tag_configure('inactive_machine', foreground='gray')  # Example of custom tag styling

    def _load_workers_data(self):
        self._clear_treeview(self.workers_tree)
        query = "SELECT worker_id, worker_name, department, shift, hire_date, phone_number FROM workers ORDER BY worker_id ASC"
        workers = self.db_manager.fetch_data(query)
        if workers:
            for w in workers:
                self.workers_tree.insert('', tk.END,
                                         values=(w['worker_id'], w['worker_name'], w['department'], w['shift'],
                                                 w['hire_date'], w['phone_number']))

    def _load_production_quality_data(self):
        self._clear_treeview(self.production_tree)
        query = """
        SELECT
            p.production_id, pr.product_name, m.machine_name, w.worker_name,
            p.production_date, p.quantity_produced, p.production_hours,
            qc.defective_units, qc.passed_units, qc.inspector_name
        FROM production p
        JOIN products pr ON p.product_id = pr.product_id
        JOIN machines m ON p.machine_id = m.machine_id
        JOIN workers w ON p.worker_id = w.worker_id
        LEFT JOIN quality_check qc ON p.production_id = qc.production_id
        ORDER BY p.production_date DESC, p.production_id DESC
        LIMIT 50; -- Limit to recent records
        """
        data = self.db_manager.fetch_data(query)
        if data:
            df = pd.DataFrame(data)
            # Fill None values for LEFT JOIN
            df[['defective_units', 'passed_units']] = df[['defective_units', 'passed_units']].fillna(0)
            df['inspector_name'] = df['inspector_name'].fillna('N/A')

            for _, row in df.iterrows():
                self.production_tree.insert('', tk.END, values=(
                    row['production_id'], row['product_name'], row['machine_name'], row['worker_name'],
                    row['production_date'], row['quantity_produced'], row['production_hours'],
                    int(row['defective_units']), int(row['passed_units']), row['inspector_name']
                ))

            self._update_historical_production_plots(df)
        else:
            self._update_historical_production_plots(pd.DataFrame())  # Clear plots

    def _update_historical_production_plots(self, df):
        """Updates plots for historical quantity produced and defective units."""
        # Plot 1: Historical Quantity Produced
        self.ax_hist_prod.cla()
        self._configure_plot_style(self.fig_hist_prod, self.ax_hist_prod, "Historical Quantity Produced")
        if not df.empty:
            df_sorted = df.sort_values(by='production_date')
            daily_production = df_sorted.groupby('production_date')['quantity_produced'].sum().reset_index()

            # Ensure dates are in a plottable format
            dates = pd.to_datetime(daily_production['production_date'])

            self.ax_hist_prod.plot(dates, daily_production['quantity_produced'], marker='o', linestyle='-',
                                   color='purple')
            self.ax_hist_prod.set_xlabel("Date")
            self.ax_hist_prod.set_ylabel("Total Quantity")

            # Format x-axis dates more cleanly
            self.fig_hist_prod.autofmt_xdate(rotation=45, ha='right')
        self.canvas_hist_prod.draw_idle()

        # Plot 2: Historical Defective Units
        self.ax_hist_defects.cla()
        self._configure_plot_style(self.fig_hist_defects, self.ax_hist_defects, "Historical Defective Units")
        if not df.empty:
            df_sorted = df.sort_values(by='production_date')
            daily_defects = df_sorted.groupby('production_date')['defective_units'].sum().reset_index()

            # Ensure dates are in a plottable format
            dates = pd.to_datetime(daily_defects['production_date'])

            self.ax_hist_defects.bar(dates, daily_defects['defective_units'], color='red', alpha=0.7)
            self.ax_hist_defects.set_xlabel("Date")
            self.ax_hist_defects.set_ylabel("Defective Units")
            self.fig_hist_defects.autofmt_xdate(rotation=45, ha='right')
        self.canvas_hist_defects.draw_idle()

    def _load_profit_data(self):
        query = "SELECT month_name, year, total_revenue, total_cost, net_profit FROM profit ORDER BY year ASC, FIELD(month_name, 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')"
        profits = self.db_manager.fetch_data(query)
        if profits:
            df = pd.DataFrame(profits)
            # Create a combined date string for chronological sorting
            # Convert month name to numerical month for proper date handling
            month_to_num = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
            }
            df['month_num'] = df['month_name'].map(month_to_num)
            df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month_num'].astype(str) + '-01')
            df_sorted = df.sort_values(by='date')

            # Update profit plot
            self.ax_profit.cla()
            self._configure_plot_style(self.fig_profit, self.ax_profit, "Monthly Net Profit Trend")
            self.ax_profit.plot(df_sorted['date'], df_sorted['net_profit'], marker='o', linestyle='-',
                                color=COLOR_SUCCESS)
            self.ax_profit.set_xlabel("Date")
            self.ax_profit.set_ylabel("Net Profit")

            # Format x-axis dates more cleanly (e.g., "Jan 2024")
            self.fig_profit.autofmt_xdate(rotation=45, ha='right')

            # Format y-axis as currency
            self.ax_profit.ticklabel_format(style='plain', axis='y')  # Prevent scientific notation
            # Optional: custom formatter for $K, but often better to let matplotlib handle it for exact values
            # self.ax_profit.set_yticklabels([f"${int(y/1000)}k" for y in self.ax_profit.get_yticks()])
        else:
            self.ax_profit.cla()
            self._configure_plot_style(self.fig_profit, self.ax_profit,
                                       "Monthly Net Profit Trend")  # Clear plot if no data

        self.canvas_profit.draw_idle()

    def _load_orders_data(self):
        self._clear_treeview(self.orders_tree)
        # Note: product_id in orders table seems to start from 1001, but products table starts from 1.
        # This query will fetch product_name if product_id in orders refers to products.product_id
        # If order.product_id are different IDs (e.g., internal SKUs), adjust query.
        query = """
        SELECT
            o.order_id,
            p.product_name, -- Fetch product name from products table
            o.total_orders,
            o.remaining_orders,
            o.delivery_date
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.product_id -- Assuming a join, adjust if IDs differ
        ORDER BY o.delivery_date ASC
        """
        orders = self.db_manager.fetch_data(query)
        if orders:
            for o in orders:
                # Handle cases where product_name might be None if no join match
                product_display_name = o['product_name'] if o['product_name'] else f"Product ID {o['product_id']}"

                tags = ()
                if o['remaining_orders'] > 0:
                    tags += ('outstanding_order',)
                    self.orders_tree.tag_configure('outstanding_order', background=COLOR_BACKGROUND_DARK,
                                                   foreground='yellow')

                # Check for urgency based on delivery date AND remaining orders
                if o['delivery_date'] and o['remaining_orders'] > 0:
                    time_to_delivery = (o['delivery_date'] - datetime.now().date()).days
                    if time_to_delivery <= 7:  # Within 7 days
                        tags += ('urgent_order',)
                        self.orders_tree.tag_configure('urgent_order', background=COLOR_ERROR,
                                                       foreground=COLOR_FOREGROUND_LIGHT)  # Red for urgent
                    elif time_to_delivery <= 14:  # Within 14 days
                        tags += ('near_due_order',)
                        self.orders_tree.tag_configure('near_due_order', background='#FFA500',
                                                       foreground=COLOR_FOREGROUND_LIGHT)  # Orange for near due

                self.orders_tree.insert('', tk.END, values=(o['order_id'], product_display_name, o['total_orders'],
                                                            o['remaining_orders'], o['delivery_date']), tags=tags)


# --- Main Application Entry Point ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SmartManufacturingApp(root)
    root.mainloop()
