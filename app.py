import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import asyncio
import threading
from datetime import datetime
import csv
from abc import ABC, abstractmethod
from functools import wraps
from typing import Dict, List, Any

from standings import update_standings

class CSVHandler(ABC):
    @abstractmethod
    async def save_to_csv(self, data, filename) -> bool:
        pass

class NFLDataCSVHandler(CSVHandler):
    async def save_to_csv(self, data, filename):
        try:
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                # Write header
                if data and len(data) > 0:
                    writer.writerow(data[0].keys())
                    # Write data rows
                    for row in data:
                        writer.writerow(row.values())
            return True
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return False

# Decorator for logging
def log_operation(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        print(f"[{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}] Executing {func.__name__}")
        result = await func(*args, **kwargs)
        print(f"[{datetime.now().strftime("%d-%m-%Y %H:%M:%S")}] Completed {func.__name__}")
        return result
    return wrapper

# Decorator for data validation
def validate_data(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        print(f"Validating data before {func.__name__}")
        # Add validation logic here
        result = await func(*args, **kwargs)
        return result
    return wrapper

# Closure for filtering data
def create_filter(filter_criteria):
    def filter_data(data):
        return [item for item in data if filter_criteria(item)]
    return filter_data

class NFLStatsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NFL STATS HUB")
        self.root.geometry("1200x800")
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda _: self.root.attributes('-fullscreen', False))
        
        # Store current data
        self.current_standings = {}
        
        # Set up UI
        self.setup_ui()
        
        # Initialize asyncio loop in a separate thread
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_background_loop, daemon=True)
        self.thread.start()
        
        # Schedule initial data fetch
        self.root.after(100, self.initial_data_fetch)
        
        # Set up periodic refresh (every 5 minutes)
        self.root.after(600000, self.schedule_refresh)
    
    def setup_ui(self):
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.tab_control = ttk.Notebook(self.main_frame)
        
        # Standings tab
        self.standings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.standings_tab, text="Standings")
        
        # Player stats tab
        self.player_stats_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.player_stats_tab, text="Player Stats")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)
        
        # Setup each tab
        self.setup_standings_tab()
        self.setup_player_stats_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def setup_standings_tab(self):
        # Frame for standings
        self.standings_frame = ttk.Frame(self.standings_tab)
        self.standings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create Treeview widget with show="tree headings" to display the hierarchy
        columns = ("Rank", "Abbreviation", "Team", "W", "L", "T", "Win%")
        self.standings_tree = ttk.Treeview(self.standings_frame, columns=columns, show="tree headings")
        
        # Define headings
        for col in columns:
            self.standings_tree.heading(col, text=col)
            width = 50 if col != "Team" else 150
            self.standings_tree.column(col, width=width, anchor=tk.CENTER)
        
        # Configure the tree column (hierarchy column)
        self.standings_tree.column("#0", width=120, stretch=tk.NO)
        self.standings_tree.heading("#0", text="Conference/Division")
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.standings_frame, orient=tk.VERTICAL, command=self.standings_tree.yview)
        self.standings_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        self.standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add team click event
        self.standings_tree.bind("<Double-1>", self.on_team_click)
        
        # Control frame
        control_frame = ttk.Frame(self.standings_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Refresh button
        refresh_btn = ttk.Button(control_frame, text="Refresh Data", command=self.refresh_standings)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Export button
        export_btn = ttk.Button(control_frame, text="Export to CSV", 
                                command=lambda: asyncio.run_coroutine_threadsafe(self.export_standings_to_csv(), self.loop))
        export_btn.pack(side=tk.LEFT, padx=5)

        
        # Last updated label
        self.standings_updated_var = tk.StringVar()
        self.standings_updated_var.set("Last updated: Never")
        updated_label = ttk.Label(control_frame, textvariable=self.standings_updated_var)
        updated_label.pack(side=tk.RIGHT, padx=5)

    
    def setup_player_stats_tab(self):
        # Placeholder for player stats tab
        # This will be implemented later
        label = ttk.Label(self.player_stats_tab, text="Player stats will be displayed here")
        label.pack(pady=20)
    
    def start_background_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def initial_data_fetch(self):
        self.status_var.set("Fetching initial data...")
        # Fetch standings
        asyncio.run_coroutine_threadsafe(self.fetch_and_display_standings(), self.loop)
    
    def schedule_refresh(self):
        # Schedule next refresh
        self.root.after(300000, self.schedule_refresh)
        # Refresh data based on active tab
        current_tab = self.tab_control.index(self.tab_control.select())
        if current_tab == 0:  # Standings tab
            self.refresh_standings()
    
    def refresh_standings(self):
        self.status_var.set("Refreshing standings...")
        asyncio.run_coroutine_threadsafe(self.fetch_and_display_standings(), self.loop)
    
    @log_operation
    async def fetch_and_display_standings(self):
        try:
            standings_data = await update_standings()
            self.current_standings = standings_data
            
            self.root.after(0, lambda: self.update_standings_ui(standings_data))
            
            self.root.after(0, lambda: self.status_var.set("Standings updated successfully"))
            
            now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            self.root.after(0, lambda: self.standings_updated_var.set(f"Last updated: {now}"))
            
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Error updating standings: {str(e)}"))
    
    
    def update_standings_ui(self, standings_data: Dict[str, List[Dict[str, Any]]]):
    # Clear existing data
        for item in self.standings_tree.get_children():
            self.standings_tree.delete(item)
        
        # Group teams by conference and division
        conferences = {}
        for division_name, teams in standings_data.items():
            for team in teams:
                conference = team['conference']
                if conference not in conferences:
                    conferences[conference] = {}
                
                if division_name not in conferences[conference]:
                    conferences[conference][division_name] = []
                
                conferences[conference][division_name].append(team)
        
        # Insert conference headers, then divisions, then teams
        for conference_name, divisions in conferences.items():
            # Add conference header
            conference_id = self.standings_tree.insert("", "end", text=conference_name, 
                                                    values=("", "", "", "", "", "", ""))
            
            # Add divisions under conference
            for division_name, teams in divisions.items():
                # Add division header
                division_id = self.standings_tree.insert(conference_id, "end", text=division_name, 
                                                        values=("", "", "", "", "", "", ""))
                
                # Sort teams by wins and win percentage
                sorted_teams = sorted(teams, key=lambda x: (-x['wins'], -x['winPercent']))
                
                # Add teams under division
                for i, team in enumerate(sorted_teams, 1):
                    team_id = self.standings_tree.insert(
                        division_id, 
                        "end", 
                        values=(
                            i,
                            team['abbreviation'],
                            team['name'], 
                            team['wins'], 
                            team['losses'], 
                            team['ties'], 
                            f"{team['winPercent']:.3f}"
                        ),
                        tags=(team['abbreviation'],)
                    )
                    
                    # Store team data in the tree item
                    self.standings_tree.item(team_id, tags=(team['abbreviation'],))

        for conference_id in self.standings_tree.get_children():
            self.standings_tree.item(conference_id, open=True)
            for division_id in self.standings_tree.get_children(conference_id):
                self.standings_tree.item(division_id, open=True)

    
    def on_team_click(self, event):
        # Get selected item
        item_id = self.standings_tree.identify('item', event.x, event.y)
        if not item_id:
            return
        
        # Get parent (division) if this is a team
        parent_id = self.standings_tree.parent(item_id)
        if not parent_id:
            # This is a division header, not a team
            return
        
        # Get team abbreviation from tags
        team_abbr = self.standings_tree.item(item_id, "tags")[0]
        
        # Find team data
        team_data = None
        for division in self.current_standings.values():
            for team in division:
                if team['abbreviation'] == team_abbr:
                    team_data = team
                    break
            if team_data:
                break
        
        if team_data:
            self.show_team_details(team_data)
    
    def show_team_details(self, team_data):
        # Create a new window for team details
        details_window = tk.Toplevel(self.root)
        details_window.title(f"{team_data['name']} Details")
        details_window.geometry("400x300")
        
        # Add team info
        ttk.Label(details_window, text=f"{team_data['name']} ({team_data['abbreviation']})", 
                 font=("Arial", 16, "bold")).pack(pady=10)
        
        ttk.Label(details_window, text=f"Conference: {team_data['conference']}").pack(anchor="w", padx=20)
        ttk.Label(details_window, text=f"Division: {team_data['division']}").pack(anchor="w", padx=20)
        ttk.Label(details_window, text=f"Record: {team_data['wins']}-{team_data['losses']}-{team_data['ties']} ({team_data['winPercent']:.3f})").pack(anchor="w", padx=20)
        
        # Add a button to close the window
        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=20)
    
    @validate_data
    async def export_standings_to_csv(self):
        if not self.current_standings:
            # Use after to schedule UI updates from the main thread
            self.root.after(0, lambda: messagebox.showinfo("Export", "No standings data to export"))
            return
        
        # Flatten the data for CSV export
        flat_data = []
        for division, teams in self.current_standings.items():
            for team in teams:
                team_copy = team.copy()
                team_copy['division'] = division
                flat_data.append(team_copy)
        
        # Ask for save location - must be done in the main thread
        filename_future = asyncio.Future()
        self.root.after(0, lambda: self._get_save_filename(filename_future))
        
        # Wait for the filename
        filename = await filename_future
        print(f"Selected filename: {filename}")
        
        if not filename:
            return
        
        # Create CSV handler and save
        csv_handler = NFLDataCSVHandler()
        success = await csv_handler.save_to_csv(flat_data, filename)
        
        # Show result message in the main thread
        if success:
            self.root.after(0, lambda: messagebox.showinfo("Export", "Data exported successfully"))
        else:
            self.root.after(0, lambda: messagebox.showerror("Export Error", "Failed to export data"))

    def _get_save_filename(self, future):
        """Helper method to get filename from dialog and set the future result"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Standings Data"
        )
        future.set_result(filename)


# Run the application
if __name__ == "__main__":
    root = tk.Tk()

    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    threading_loop = threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True)
    threading_loop.start()
    
    app = NFLStatsApp(root)
    root.mainloop()
    
    # Clean up asyncio loop
    loop.call_soon_threadsafe(loop.stop)
    threading_loop.join()
    loop.close()
