import sys
import subprocess
import sqlite3
from datetime import datetime
import threading
import time
import tkinter as tk
from tkinter import ttk

# Install packages if they are missing
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Ensure necessary packages are installed
try:
    import speedtest
except ImportError:
    install('speedtest-cli')
    import speedtest

# Database file
DB_FILE = 'speedtest_results.db'

# Ensure the 'results' table is created if it doesn't exist
def initialize_database():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                download REAL,
                upload REAL,
                ping REAL,
                server_name TEXT,
                server_location TEXT
            )
        ''')
        conn.commit()

# Perform the speed test and update the SQLite database
def run_speedtest():
    try:
        # Speedtest object
        st = speedtest.Speedtest()
        server = st.get_best_server()
        server_name = server['sponsor']
        server_location = f"{server['name']}, {server['country']}"

        # Perform the speed test
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        ping = st.results.ping

        # Get the current time for the record
        timestamp = datetime.now()

        # Insert results into the SQLite database
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results (timestamp, download, upload, ping, server_name, server_location)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, download_speed, upload_speed, ping, server_name, server_location))
            conn.commit()

        return {
            "timestamp": timestamp,
            "download": download_speed,
            "upload": upload_speed,
            "ping": ping,
            "server_name": server_name,
            "server_location": server_location
        }
    except Exception as e:
        # Log the exception for debugging
        print(f"Error running speed test: {e}")
        return {"error": str(e)}

# Fetch records from the database (based on limit)
def fetch_records(limit=5):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, download, upload, ping, server_name, server_location
            FROM results
            ORDER BY id DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
    return rows

# Background speed test service (runs every 60 seconds)
def background_speedtest_service(app):
    while True:
        time.sleep(60)  # Adjust the sleep to run every 60 seconds
        run_speedtest()
        app.refresh_data()

# GUI Application Class
class SpeedTestApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Speed Test App")
        self.geometry("600x400")

        # Initialize the database (ensure table exists)
        initialize_database()

        # Number of records to display
        self.records_to_display = tk.IntVar(value=5)

        # Create UI elements
        self.create_widgets()

        # Start background thread for periodic speed tests (initially paused)
        self.is_testing = False
        self.bg_thread = threading.Thread(target=background_speedtest_service, args=(self,), daemon=True)
        self.bg_thread.start()

    def create_widgets(self):
        # Label for status updates
        self.status_label = tk.Label(self, text="Press 'Run Test' to start a speed test", font=("Arial", 12))
        self.status_label.pack(pady=10)

        # Button to run a new speed test manually
        self.test_button = tk.Button(self, text="Run Test", command=self.run_speedtest_thread, font=("Arial", 12))
        self.test_button.pack(pady=10)

        # Dropdown to filter number of records displayed
        filter_label = tk.Label(self, text="Records to Display:", font=("Arial", 10))
        filter_label.pack(pady=5)

        filter_dropdown = ttk.Combobox(self, textvariable=self.records_to_display, values=[5, 10, 20])
        filter_dropdown.pack(pady=5)
        filter_dropdown.bind("<<ComboboxSelected>>", lambda event: self.refresh_data())

        # Table to display results
        self.tree = ttk.Treeview(self, columns=('Timestamp', 'Download', 'Upload', 'Ping', 'Server', 'Location'), show='headings')
        self.tree.heading('Timestamp', text='Timestamp')
        self.tree.heading('Download', text='Download (Mbps)')
        self.tree.heading('Upload', text='Upload (Mbps)')
        self.tree.heading('Ping', text='Ping (ms)')
        self.tree.heading('Server', text='Server')
        self.tree.heading('Location', text='Location')
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Initially load data
        self.refresh_data()

    def run_speedtest_thread(self):
        # Prevent multiple tests from running simultaneously
        if not self.is_testing:
            self.is_testing = True
            self.status_label.config(text="Running speed test...")
            threading.Thread(target=self.run_speedtest, daemon=True).start()

    def run_speedtest(self):
        result = run_speedtest()
        if "error" in result:
            self.status_label.config(text=f"Error: {result['error']}")
        else:
            self.status_label.config(text="Speed test completed!")
            self.refresh_data()

        # Allow tests again
        self.is_testing = False

    def refresh_data(self):
        # Clear the current data
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Fetch new records based on the selected filter
        records = fetch_records(self.records_to_display.get())
        for record in records:
            self.tree.insert('', 'end', values=record)

# Start the Tkinter app
if __name__ == "__main__":
    app = SpeedTestApp()
    app.mainloop()
