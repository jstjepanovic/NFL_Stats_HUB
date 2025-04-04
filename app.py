import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import asyncio
import threading
from datetime import datetime
import csv
from abc import ABC, abstractmethod
from functools import wraps
from typing import Dict, List, Any
from PIL import Image, ImageTk
from io import BytesIO

from standings import update_standings
from stats_leaders import fetch_stats_leaders, STAT_CATEGORIES

class CSVHandler(ABC):
    @abstractmethod
    async def save_to_csv(self, data, filename) -> bool:
        pass

class NFLDataCSVHandler(CSVHandler):
    async def save_to_csv(self, data, filename):
        try:
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                if data and len(data) > 0:
                    writer.writerow(data[0].keys())
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
        self.root.bind('<Escape>', lambda _: self.root.attributes('-fullscreen', False))
        
        self.current_standings = {}
        
        self.setup_ui()
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_background_loop, daemon=True)
        self.thread.start()
        
        self.root.after(100, self.initial_data_fetch)
        
        self.root.after(600000, self.schedule_refresh)
    
        self.stats_loaded = False

    def setup_ui(self):
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create year selection frame first
        self.year_frame = ttk.Frame(self.main_frame)
        self.year_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add year selection label
        year_label = ttk.Label(self.year_frame, text="Select Year:")
        year_label.pack(side=tk.LEFT, padx=5)
        
        # Add year selection dropdown
        style = ttk.Style()
        style.map('Custom.TCombobox',
            fieldbackground=[('readonly', 'white')],
            selectbackground=[('readonly', 'white')],
            selectforeground=[('readonly', 'black')])
    
        current_year = datetime.now().year
        years = [str(year) for year in range(2004, current_year)]
        self.year_var = tk.StringVar()
        self.year_dropdown = ttk.Combobox(self.year_frame, textvariable=self.year_var, 
                                    values=years, style='Custom.TCombobox', state='readonly')
        self.year_dropdown.set(str(current_year - 1))
        self.year_dropdown.pack(side=tk.LEFT, padx=5)

        # Create tabs
        self.tab_control = ttk.Notebook(self.main_frame)
        
        # Standings tab
        self.standings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.standings_tab, text="Standings")
        
        # Player stats tab
        self.player_stats_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.player_stats_tab, text="Player Stats")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)

        # Bind events after creating components
        self.tab_control.bind('<<NotebookTabChanged>>', self.on_tab_change)
        self.year_dropdown.bind("<<ComboboxSelected>>", self.on_year_change)
        
        # Setup each tab
        self.setup_standings_tab()
        self.setup_player_stats_tab()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_year_change(self, event):
        selected_year = self.year_var.get()
        
        current_tab = self.tab_control.index(self.tab_control.select())
        if current_tab == 0:
            self.refresh_standings(selected_year)
        elif current_tab == 1:
            selected_category_tab = self.stats_notebook.index(self.stats_notebook.select())
            categories = list(STAT_CATEGORIES.keys())
            if selected_category_tab < len(categories):
                self.refresh_player_stats(categories[selected_category_tab], selected_year)

        self._last_selected_year = selected_year

    def on_tab_change(self, event):
        current_tab = self.tab_control.index(self.tab_control.select())
        selected_year = self.year_var.get()
    
        if current_tab == 0:
            self.refresh_standings(selected_year)
        elif current_tab == 1:
            selected_category_tab = self.stats_notebook.index(self.stats_notebook.select())
            categories = list(STAT_CATEGORIES.keys())
            
            if selected_category_tab < len(categories):
                category = categories[selected_category_tab]
                self.refresh_player_stats(category, selected_year)

    def on_stats_tab_change(self, event):
        selected_category_tab = self.stats_notebook.index(self.stats_notebook.select())
        categories = list(STAT_CATEGORIES.keys())
        selected_year = self.year_var.get()

        if selected_category_tab < len(categories):
            category = categories[selected_category_tab]
            self.refresh_player_stats(category, selected_year)

    
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
    # Create a notebook for different stat categories
        self.stats_notebook = ttk.Notebook(self.player_stats_tab)
        self.stats_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create frames for each stat category
        self.stat_frames = {}
        self.stat_trees = {}
        
        # Define stat categories to display
        categories = [
            'passingYards', 'rushingYards', 'receivingYards', 
            'sacks', 'interceptions', 'passingTouchdowns', 'receptions'
        ]
        
        # Create a tab and treeview for each category
        for category in categories:
            # Create frame
            frame = ttk.Frame(self.stats_notebook)
            self.stat_frames[category] = frame
            
            # Add to notebook with display name
            display_name = STAT_CATEGORIES[category]
            self.stats_notebook.add(frame, text=display_name)
            
            # Create treeview for this category
            columns = ("Rank", "Player", "Position", "Team", "Value")
            tree = ttk.Treeview(frame, columns=columns, show="headings")
            
            # Configure columns
            tree.heading("Rank", text="Rank")
            tree.heading("Player", text="Player")
            tree.heading("Position", text="Pos")
            tree.heading("Team", text="Team")
            tree.heading("Value", text=display_name)
            
            tree.column("Rank", width=50, anchor=tk.CENTER)
            tree.column("Player", width=150, anchor=tk.W)
            tree.column("Position", width=50, anchor=tk.CENTER)
            tree.column("Team", width=100, anchor=tk.CENTER)
            tree.column("Value", width=100, anchor=tk.CENTER)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            # Pack widgets
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Store reference to tree
            self.stat_trees[category] = tree
            
            # Add player click event
            tree.bind("<Double-1>", lambda e, cat=category: self.on_player_click(e, cat))
        
        # Control frame
        control_frame = ttk.Frame(self.player_stats_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Refresh button
        selected_category_tab = self.stats_notebook.index(self.stats_notebook.select())
        categories = list(STAT_CATEGORIES.keys())
        selected_year = self.year_var.get()
        refresh_btn = ttk.Button(control_frame, text="Refresh Stats", command=lambda: self.refresh_player_stats(selected_year, categories[selected_category_tab]))
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Export button
        export_btn = ttk.Button(control_frame, text="Export to CSV",
                            command=lambda: asyncio.run_coroutine_threadsafe(self.export_player_stats_to_csv(), self.loop))
        export_btn.pack(side=tk.LEFT, padx=5)
        
        self.stats_notebook.bind("<<NotebookTabChanged>>", self.on_stats_tab_change)

        # Last updated label
        self.player_stats_updated_var = tk.StringVar()
        self.player_stats_updated_var.set("Last updated: Never")
        updated_label = ttk.Label(control_frame, textvariable=self.player_stats_updated_var)
        updated_label.pack(side=tk.RIGHT, padx=5)

    
    def start_background_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def initial_data_fetch(self):
        self.status_var.set("Fetching initial data...")
        # Fetch standings
        asyncio.run_coroutine_threadsafe(self.fetch_and_display_standings(), self.loop)

    
    def schedule_refresh(self):
        self.root.after(300000, self.schedule_refresh)
        current_tab = self.tab_control.index(self.tab_control.select())
        if current_tab == 0:
            self.refresh_standings()
        elif current_tab == 1:
            selected_category_tab = self.stats_notebook.index(self.stats_notebook.select())
            categories = list(STAT_CATEGORIES.keys())
            selected_year = self.year_var.get()

            if selected_category_tab < len(categories):
                self.refresh_player_stats(selected_year, categories[selected_category_tab])
    
    def refresh_standings(self, year: str | None = None):
        self.status_var.set("Refreshing standings...")
        asyncio.run_coroutine_threadsafe(self.fetch_and_display_standings(year), self.loop)
    
    @log_operation
    async def fetch_and_display_standings(self, year: str | None = None):
        try:
            standings_data = await update_standings(year)
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
        
        CONFERENCE_ORDER = ['AFC', 'NFC']
        DIVISION_ORDER = ['North', 'South', 'East', 'West']
        
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
        
        # Insert conference headers, then divisions, then teams in fixed order
        for conference_name in CONFERENCE_ORDER:
            if conference_name not in conferences:
                continue
            
            # Add conference header
            conference_id = self.standings_tree.insert("", "end", text=conference_name, 
                                                    values=("", "", "", "", "", "", ""))
            
            # Add divisions under conference in fixed order
            for division_suffix in DIVISION_ORDER:
                division_name = f"{conference_name} {division_suffix}"
                if division_name not in conferences[conference_name]:
                    continue
                
                # Add division header
                division_id = self.standings_tree.insert(conference_id, "end", text=division_name, 
                                                        values=("", "", "", "", "", "", ""))
                
                # Sort teams by wins and win percentage
                teams = conferences[conference_name][division_name]
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

        # Expand all items
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
        details_window.geometry("500x350")
        
        # Create a frame for the logo and info
        top_frame = ttk.Frame(details_window)
        top_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Create a clickable placeholder for the logo
        logo_frame = ttk.Frame(top_frame, width=100, height=100, relief=tk.GROOVE, borderwidth=2)
        logo_frame.pack(side=tk.LEFT, padx=10)
        logo_frame.pack_propagate(False)  # Prevent frame from shrinking
        
        # Add a label with instructions
        logo_label = ttk.Label(logo_frame, text="Click to\nload logo", cursor="hand2")
        logo_label.pack(expand=True, fill=tk.BOTH)
        
        # Bind click event to load the logo
        # logo_url = f"https://a.espncdn.com/i/teamlogos/nfl/500/{team_data['abbreviation'].lower()}.png"
        # logo_label.bind("<Button-1>", lambda e: self.load_team_logo(logo_frame, logo_url))
        
        # Create info frame
        info_frame = ttk.Frame(top_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # Add team info
        ttk.Label(info_frame, text=f"{team_data['name']} ({team_data['abbreviation']})",
                font=("Arial", 16, "bold")).pack(anchor="w")
        ttk.Label(info_frame, text=f"Conference: {team_data['conference']}").pack(anchor="w")
        ttk.Label(info_frame, text=f"Division: {team_data['division']}").pack(anchor="w")
        ttk.Label(info_frame, text=f"Record: {team_data['wins']}-{team_data['losses']}-{team_data['ties']} ({team_data['winPercent']:.3f})").pack(anchor="w")
        
        # Add a button to close the window
        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=20)


    def refresh_player_stats(self, category: str, year: str | None = None):
        self.status_var.set(f"Loading {STAT_CATEGORIES[category]} data...")
        asyncio.run_coroutine_threadsafe(self.fetch_and_display_player_stats(year, category), self.loop)

    @log_operation
    async def fetch_and_display_player_stats(self, year: str | None, category: str):
        try:
            # Fetch player stats for just this category
            stats_data = await fetch_stats_leaders(year, category)
            
            # Store in the current player stats dictionary
            if not hasattr(self, 'current_player_stats'):
                self.current_player_stats = {}
            
            # Update only the requested category
            if category in stats_data:
                self.current_player_stats[category] = stats_data[category]
            
            # Update UI for just this category
            self.root.after(0, lambda: self.update_player_stats_category_ui(category, stats_data.get(category, [])))
            
            # Update status
            self.root.after(0, lambda: self.status_var.set(f"{STAT_CATEGORIES[category]} data updated successfully"))
            
            # Update last updated time
            now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            self.root.after(0, lambda: self.player_stats_updated_var.set(f"Last updated: {now}"))
            
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Error updating {STAT_CATEGORIES[category]} data: {str(e)}"))

    def update_player_stats_category_ui(self, category, players):
        if category not in self.stat_trees:
            return
            
        tree = self.stat_trees[category]
        
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)
        
        # Insert player data
        for player in players:
            tree.insert(
                "", 
                "end", 
                values=(
                    player['rank'],
                    player['name'],
                    player['position'],
                    player['team_abbr'],
                    player['value']
                ),
                tags=(str(player['athlete_id']),)
            )

    def on_player_click(self, event, category):
        # Get selected item
        tree = self.stat_trees[category]
        item_id = tree.identify('item', event.x, event.y)
        if not item_id:
            return
        
        # Get athlete ID from tags
        athlete_id = tree.item(item_id, "tags")[0]
        
        # Find player data
        player_data = None
        for player in self.current_player_stats.get(category, []):
            if str(player['athlete_id']) == athlete_id:
                player_data = player
                break
        
        if player_data:
            self.show_player_details(player_data)

    def show_player_details(self, player_data):
        # Create a new window for player details
        details_window = tk.Toplevel(self.root)
        details_window.title(f"{player_data['name']} Details")
        details_window.geometry("600x400")
        
        # Add player info
        ttk.Label(details_window, text=f"{player_data['name']}", 
                font=("Arial", 16, "bold")).pack(pady=10)
        
        ttk.Label(details_window, text=f"Position: {player_data['position']}").pack(anchor="w", padx=20)
        ttk.Label(details_window, text=f"Team: {player_data['team']}").pack(anchor="w", padx=20)
        
        # Add stat value
        ttk.Label(details_window, text=f"Value: {player_data['value']}").pack(anchor="w", padx=20)
        
        # Add a button to close the window
        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=20)

    @validate_data
    async def export_player_stats_to_csv(self):
        if not hasattr(self, 'current_player_stats') or not self.current_player_stats:
            self.root.after(0, lambda: messagebox.showinfo("Export", "No player stats data to export"))
            return
        
        # Get current tab/category
        current_tab = self.stats_notebook.index(self.stats_notebook.select())
        categories = list(STAT_CATEGORIES.keys())
        if current_tab >= len(categories):
            self.root.after(0, lambda: messagebox.showinfo("Export", "Please select a stat category"))
            return
        
        current_category = categories[current_tab]
        players = self.current_player_stats.get(current_category, [])
        
        if not players:
            self.root.after(0, lambda: messagebox.showinfo("Export", "No data to export for this category"))
            return
        
        # Ask for save location - must be done in the main thread
        filename_future = asyncio.Future()
        self.root.after(0, lambda: self._get_save_filename(filename_future, f"NFL_{STAT_CATEGORIES[current_category]}_Leaders"))
        
        # Wait for the filename
        filename = await filename_future
        
        if not filename:
            return
        
        # Create CSV handler and save
        csv_handler = NFLDataCSVHandler()
        success = await csv_handler.save_to_csv(players, filename)
        
        # Show result message in the main thread
        if success:
            self.root.after(0, lambda: messagebox.showinfo("Export", "Data exported successfully"))
        else:
            self.root.after(0, lambda: messagebox.showerror("Export Error", "Failed to export data"))

    
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

    def _get_save_filename(self, future, default_name="NFL_Stats"):
        """Helper method to get filename from dialog and set the future result"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Standings Data",
            initialfile=default_name
        )
        future.set_result(filename)


def run_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    root = tk.Tk()

    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    threading_loop = threading.Thread(target=run_asyncio_loop, args=(loop,),
                                      daemon=True)
    threading_loop.start()
    
    app = NFLStatsApp(root)
    root.mainloop()
    
    loop.call_soon_threadsafe(loop.stop)
    threading_loop.join()
    loop.close()
