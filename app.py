import asyncio
import logging
import os
import types
from datetime import datetime
from functools import wraps
from io import BytesIO
from typing import (
    Any, Dict, List, Callable, Awaitable, Optional
)
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk

from standings import update_standings
from stats_leaders import fetch_stats_leaders, STAT_CATEGORIES
from image import fetch_image
from exporters import (
    CSVDataExporter, JSONDataExporter, ExcelDataExporter
)

# POSTAVKE LOGGING LIBRARY
def setup_logging() -> None:
    now = datetime.now()
    log_dir = os.path.join("logs", now.strftime("%Y-%m-%d"))
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(
        log_dir,
        now.strftime("run_%Y-%m-%d_%H-%M-%S.log")
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_filename, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

# LOGOVI
def log_operation(func: Callable[..., Awaitable[Any]]
                  ) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        logging.info(f"Executing {func.__name__}")
        result = await func(*args, **kwargs)
        logging.info(f"Finished {func.__name__}")
        return result
    return wrapper

# VALIDACIJA PODATAKA PRIJE EXPORTA
def validate_data(func: Callable[..., Awaitable[Any]]
                  ) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        logging.info(f"Validating data before {func.__name__}")
        self = args[0] if args else None
        if self is None:
            logging.error(
                "validate_data: No self instance found for validation."
            )
            return
        
        if func.__name__ == 'export_player_stats_to_csv':
            if (not hasattr(self, 'current_player_stats') or
                not self.current_player_stats):
                logging.error(
                    "No player stats data to export (validation failed)."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Export Error",
                        "No player stats data to export (validation failed)."
                    )
                )
                return
            
            if not hasattr(self, 'stats_notebook'):
                logging.error(
                    "No stats_notebook attribute found (validation failed)."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Export Error",
                        "Internal error: stats_notebook missing "
                        "(validation failed)."
                    )
                )
                return
            
            current_tab = self.stats_notebook.index(
                self.stats_notebook.select()
            )
            categories = list(STAT_CATEGORIES.keys())

            if current_tab >= len(categories):
                logging.error(
                    "No stat category selected for export "
                    "(validation failed)."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Export Error",
                        "Please select a stat category (validation failed)."
                    )
                )
                return
            
            current_category = categories[current_tab]
            players = self.current_player_stats.get(current_category, [])
            
            if not players:
                logging.error(
                    f"No data to export for category: {current_category} "
                    "(validation failed)."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Export Error",
                        "No data to export for this category "
                        "(validation failed)."
                    )
                )
                return
            required_fields = [
                "name", "position", "team", "team_abbr", "value", "rank"
            ]
            
            for player in players:
                for field in required_fields:
                    if field not in player or player[field] in (None, ""):
                        logging.error(
                            f"Player data missing required field '{field}': "
                            f"{player}"
                        )
                        self.root.after(
                            0,
                            lambda: messagebox.showerror(
                                "Export Error",
                                f"Player data missing required field "
                                f"'{field}'.",
                            )
                        )
                        return
        
        if func.__name__ == 'export_standings_to_csv':
            if (not hasattr(self, 'current_standings') or
                not self.current_standings):
                logging.error(
                    "No standings data to export (validation failed)."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Export Error",
                        "No standings data to export (validation failed)."
                    )
                )
                return
            
            flat_data = []
            for division, teams in self.current_standings.items():
                for team in teams:
                    team_copy = team.copy()
                    team_copy['division'] = division
                    flat_data.append(team_copy)
            if not flat_data:
                logging.error(
                    "No flattened standings data to export "
                    "(validation failed)."
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Export Error",
                        "No standings data to export (validation failed)."
                    )
                )
                return
            
            required_fields = [
                "conference", "division", "name", "abbreviation", "wins",
                "losses", "ties", "winPercent"
            ]
            for team in flat_data:
                for field in required_fields:
                    if field not in team or team[field] in (None, ""):
                        logging.error(
                            f"Team data missing required field '{field}': "
                            f"{team}"
                        )
                        self.root.after(
                            0,
                            lambda: messagebox.showerror(
                                "Export Error",
                                f"Team data missing required field '{field}'.",
                            )
                        )
                        return
            
            result = await func(*args, **kwargs)
            return result
        return await func(*args, **kwargs)
    return wrapper


def create_filter(filter_criteria: Callable[[Any], bool]
                  ) -> Callable[[List[Any]], List[Any]]:
    def filter_data(data: List[Any]) -> List[Any]:
        return [item for item in data if filter_criteria(item)]
    return filter_data

class NFLStatsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("NFL STATS HUB")
        self.root.geometry("1200x800")
        self.root.bind(
            '<Escape>',
            lambda _: self.root.attributes('-fullscreen', False)
        )
        
        self.current_standings: Dict[str, List[Dict[str, Any]]] = {}
        
        self.setup_ui()
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.start_background_loop,
                                       daemon=True)
        self.thread.start()
        
        self.root.after(100, self.initial_data_fetch)
        
        self.root.after(600000, self.schedule_refresh)
    
        self.stats_loaded: bool = False

    def setup_ui(self) -> None:
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.year_frame = ttk.Frame(self.main_frame)
        self.year_frame.pack(fill=tk.X, padx=10, pady=5)

        # Odabir godine        
        year_label = ttk.Label(self.year_frame, text="Select Year:")
        year_label.pack(side=tk.LEFT, padx=5)
        
        current_year = datetime.now().year
        years = [str(year) for year in range(2004, current_year)]
        self.year_var = tk.StringVar()
        self.year_dropdown = ttk.Combobox(
            self.year_frame,
            textvariable=self.year_var,
            values=years,
            state='readonly'
        )
        self.year_dropdown.set(str(current_year - 1))
        self.year_dropdown.pack(side=tk.LEFT, padx=5)

        self.tab_control = ttk.Notebook(self.main_frame)
        
        self.standings_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.standings_tab, text="Standings")
        
        self.player_stats_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.player_stats_tab, text="Player Stats")
        
        self.tab_control.pack(fill=tk.BOTH, expand=True)

        self.tab_control.bind('<<NotebookTabChanged>>', self.on_tab_change)
        self.year_dropdown.bind("<<ComboboxSelected>>", self.on_year_change)
        
        self.setup_standings_tab()
        self.setup_player_stats_tab()

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_year_change(self, event: Any) -> None:
        selected_year = self.year_var.get()
        
        current_tab = self.tab_control.index(self.tab_control.select())
        if current_tab == 0:
            self.refresh_standings(selected_year)
        elif current_tab == 1:
            selected_category_tab = self.stats_notebook.index(
                self.stats_notebook.select()
            )
            categories = list(STAT_CATEGORIES.keys())
            if selected_category_tab < len(categories):
                self.refresh_player_stats(
                    categories[selected_category_tab], selected_year
                )

        self._last_selected_year = selected_year

    def on_tab_change(self, event: Any) -> None:
        current_tab = self.tab_control.index(self.tab_control.select())
        selected_year = self.year_var.get()
    
        if current_tab == 0:
            self.refresh_standings(selected_year)
        elif current_tab == 1:
            selected_category_tab = self.stats_notebook.index(
                self.stats_notebook.select()
            )
            categories = list(STAT_CATEGORIES.keys())
            
            if selected_category_tab < len(categories):
                category = categories[selected_category_tab]
                self.refresh_player_stats(category, selected_year)

    def on_stats_tab_change(self, event: Any) -> None:
        selected_category_tab = self.stats_notebook.index(
            self.stats_notebook.select()
        )
        categories = list(STAT_CATEGORIES.keys())
        selected_year = self.year_var.get()

        if selected_category_tab < len(categories):
            category = categories[selected_category_tab]
            self.refresh_player_stats(category, selected_year)
  
    def setup_standings_tab(self) -> None:
        self.standings_frame = ttk.Frame(self.standings_tab)
        self.standings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("Rank", "Abbreviation", "Team", "W", "L", "T", "Win%")
        self.standings_tree = ttk.Treeview(
            self.standings_frame, columns=columns, show="tree headings"
        )
        
        for col in columns:
            self.standings_tree.heading(col, text=col)
            width = 50 if col != "Team" else 150
            self.standings_tree.column(col, width=width, anchor=tk.CENTER)
        
        self.standings_tree.column("#0", width=120, stretch=tk.NO)
        self.standings_tree.heading("#0", text="Conference/Division")
        
        scrollbar = ttk.Scrollbar(
            self.standings_frame, orient=tk.VERTICAL,
            command=self.standings_tree.yview
        )
        self.standings_tree.configure(yscrollcommand=scrollbar.set)
        
        self.standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.standings_tree.bind("<Double-1>", self.on_team_click)
        
        control_frame = ttk.Frame(self.standings_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        refresh_btn = ttk.Button(
            control_frame, text="Refresh Data", command=self.refresh_standings
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        export_btn_csv = ttk.Button(
            control_frame,
            text="Export CSV",
            command=lambda: self.export_standings_to_file_sync('csv')
        )
        export_btn_csv.pack(side=tk.LEFT, padx=2)
        
        export_btn_json = ttk.Button(
            control_frame,
            text="Export JSON",
            command=lambda: self.export_standings_to_file_sync('json')
        )
        export_btn_json.pack(side=tk.LEFT, padx=2)
        
        export_btn_xlsx = ttk.Button(
            control_frame,
            text="Export Excel",
            command=lambda: self.export_standings_to_file_sync('xlsx')
        )
        export_btn_xlsx.pack(side=tk.LEFT, padx=2)

        self.division_filter_var = tk.StringVar()
        self.min_wins_var = tk.StringVar(value="0")

        ttk.Label(control_frame, text="Division:").pack(side=tk.LEFT, padx=2)

        division_entry = ttk.Entry(
            control_frame,
            textvariable=self.division_filter_var,
            width=12
        )
        division_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(control_frame, text="Min Wins:").pack(side=tk.LEFT, padx=2)

        min_wins_entry = ttk.Entry(
            control_frame,
            textvariable=self.min_wins_var,
            width=4
        )
        min_wins_entry.pack(side=tk.LEFT, padx=2)

        apply_div_filter_btn = ttk.Button(
            control_frame,
            text="Apply Filter",
            command=self.apply_division_filter
        )
        apply_div_filter_btn.pack(side=tk.LEFT, padx=2)

        clear_div_filter_btn = ttk.Button(
            control_frame,
            text="Clear Filter",
            command=self.clear_division_filter
        )
        clear_div_filter_btn.pack(side=tk.LEFT, padx=2)

        self.standings_updated_var = tk.StringVar()
        self.standings_updated_var.set("Last updated: Never")
        
        updated_label = ttk.Label(
            control_frame,
            textvariable=self.standings_updated_var
        )
        updated_label.pack(side=tk.RIGHT, padx=5)

    def apply_division_filter(self) -> None:
        division_name = self.division_filter_var.get().strip()
        
        try:
            min_wins = int(self.min_wins_var.get())
        except ValueError:
            messagebox.showinfo("Filter", "Minimum wins must be an integer.")
            return
        filtered = {}
        
        if not division_name:
            for div, teams in self.current_standings.items():
                filtered_teams = self.filter_teams_by_division(div, min_wins)
                if filtered_teams:
                    filtered[div] = filtered_teams
            if not filtered:
                messagebox.showinfo(
                    "Filter", f"No teams found with min {min_wins} wins."
                )
                return
            self.filtered_standings = filtered
            self.update_standings_ui(filtered)
            self.status_var.set(f"Filtered standings: min {min_wins} wins")
            return
        
        for div, teams in self.current_standings.items():
            if division_name.lower() in div.lower():
                filtered_teams = self.filter_teams_by_division(div, min_wins)
                if filtered_teams:
                    filtered[div] = filtered_teams
        if not filtered:
            messagebox.showinfo(
                "Filter",
                f"No divisions or teams found for '{division_name}' with"
                f"min {min_wins} wins."
            )
            return
        
        self.filtered_standings = filtered
        self.update_standings_ui(filtered)
        self.status_var.set(
            f"Filtered standings: {division_name} with min {min_wins} wins"
        )

    def clear_division_filter(self) -> None:
        self.filtered_standings = None
        self.update_standings_ui(self.current_standings)
        self.status_var.set("Cleared division filter")

    def setup_player_stats_tab(self) -> None:
        self.stats_notebook = ttk.Notebook(self.player_stats_tab)
        self.stats_notebook.pack(
            fill=tk.BOTH,
            expand=True,
            padx=10,
            pady=10
        )
        
        self.stat_frames = {}
        self.stat_trees = {}
        
        
        for category, display_name in STAT_CATEGORIES.items():
            frame = ttk.Frame(self.stats_notebook)
            self.stat_frames[category] = frame
            
            self.stats_notebook.add(frame, text=display_name)
            
            columns = ("Rank", "Player", "Position", "Team", "Value")
            tree = ttk.Treeview(
                frame,
                columns=columns,
                show="headings"
            )
            
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
            
            scrollbar = ttk.Scrollbar(
                frame,
                orient=tk.VERTICAL,
                command=tree.yview
            )
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.stat_trees[category] = tree
            
            tree.bind(
                "<Double-1>", lambda e,
                cat=category: self.on_player_click(e, cat)
            )
        
        control_frame = ttk.Frame(self.player_stats_tab)
        control_frame.pack(
            fill=tk.X,
            padx=10,
            pady=5
        )
        
        selected_category_tab = self.stats_notebook.index(
            self.stats_notebook.select()
        )
        categories = list(STAT_CATEGORIES.keys())
        selected_year = self.year_var.get()
        
        refresh_btn = ttk.Button(
            control_frame,
            text="Refresh Stats",
            command=lambda: self.refresh_player_stats(
                selected_year,
                categories[selected_category_tab]
            )
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
    
        export_btn_csv = ttk.Button(
            control_frame,
            text="Export CSV",
            command=lambda: self.export_player_stats_to_file_sync('csv')
        )
        
        export_btn_csv.pack(side=tk.LEFT, padx=2)
        export_btn_json = ttk.Button(
            control_frame,
            text="Export JSON",
            command=lambda: self.export_player_stats_to_file_sync('json')
        )
        
        export_btn_json.pack(side=tk.LEFT, padx=2)
        export_btn_xlsx = ttk.Button(
            control_frame,
            text="Export Excel",
            command=lambda: self.export_player_stats_to_file_sync('xlsx')
        )
        export_btn_xlsx.pack(side=tk.LEFT, padx=2)

        self.team_filter_var = tk.StringVar()
        ttk.Label(control_frame, text="Team Abbr:").pack(side=tk.LEFT, padx=2)
        team_entry = ttk.Entry(
            control_frame,
            textvariable=self.team_filter_var,
            width=6
        )
        team_entry.pack(side=tk.LEFT, padx=2)
        apply_team_filter_btn = ttk.Button(
            control_frame,
            text="Apply Team Filter",
            command=self.apply_team_filter
        )
        apply_team_filter_btn.pack(side=tk.LEFT, padx=2)
        clear_team_filter_btn = ttk.Button(
            control_frame,
            text="Clear Filter",
            command=self.clear_team_filter
        )
        clear_team_filter_btn.pack(side=tk.LEFT, padx=2)

        self.stats_notebook.bind(
            "<<NotebookTabChanged>>", self.on_stats_tab_change
        )

        self.player_stats_updated_var = tk.StringVar()
        self.player_stats_updated_var.set("Last updated: Never")
        updated_label = ttk.Label(
            control_frame,
            textvariable=self.player_stats_updated_var
        )
        updated_label.pack(side=tk.RIGHT, padx=5)

    def apply_team_filter(self) -> None:
        selected_category_tab = self.stats_notebook.index(
            self.stats_notebook.select()
        )
        categories = list(STAT_CATEGORIES.keys())
        if selected_category_tab >= len(categories):
            return
        category = categories[selected_category_tab]
        
        team_abbr = self.team_filter_var.get().strip().upper()
        if not team_abbr:
            messagebox.showinfo("Filter", "Please enter a team abbreviation.")
            return
        
        filtered_players = self.filter_players_by_team(category, team_abbr)
        self.update_player_stats_category_ui(category, filtered_players)
        self.status_var.set(
            f"Filtered {STAT_CATEGORIES[category]} by team: {team_abbr}"
        )

    def clear_team_filter(self) -> None:
        selected_category_tab = self.stats_notebook.index(
            self.stats_notebook.select()
        )
        categories = list(STAT_CATEGORIES.keys())
        
        if selected_category_tab >= len(categories):
            return
        category = categories[selected_category_tab]
        
        players = self.current_player_stats.get(category, [])
        self.update_player_stats_category_ui(category, players)
        self.status_var.set(
            f"Cleared team filter for {STAT_CATEGORIES[category]}"
        )

    def start_background_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def initial_data_fetch(self) -> None:
        self.status_var.set("Fetching initial data...")
        coroutine = self.fetch_and_display_standings()
        
        if not isinstance(coroutine, types.CoroutineType):
            raise RuntimeError(
                """fetch_and_display_standings 
                did not return a coroutine object!"""
            )
        asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def schedule_refresh(self) -> None:
        self.root.after(300000, self.schedule_refresh)
        current_tab = self.tab_control.index(self.tab_control.select())
        
        if current_tab == 0:
            self.refresh_standings()
        elif current_tab == 1:
            selected_category_tab = self.stats_notebook.index(
                self.stats_notebook.select()
            )
            categories = list(STAT_CATEGORIES.keys())
            selected_year = self.year_var.get()

            if selected_category_tab < len(categories):
                self.refresh_player_stats(
                    selected_year, categories[selected_category_tab]
                )
    
    def refresh_standings(self, year: Optional[str] = None) -> None:
        self.status_var.set("Refreshing standings...")
        coroutine = self.fetch_and_display_standings(year)
        
        if not isinstance(coroutine, types.CoroutineType):
            raise RuntimeError(
                """fetch_and_display_standings 
                did not return a coroutine object!"""
            )
        asyncio.run_coroutine_threadsafe(coroutine, self.loop)
    
    @log_operation
    async def fetch_and_display_standings(self, year: Optional[str] = None
                                          ) -> None:
        try:
            standings_data = await update_standings(year)
            self.current_standings = standings_data
            
            self.root.after(
                0, lambda: self.update_standings_ui(standings_data)
            )
            
            self.root.after(
                0,
                lambda: self.status_var.set("Standings updated successfully")
            )
            
            now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            self.root.after(
                0,
                lambda: self.standings_updated_var.set(f"Last updated: {now}")
            )
            
        except Exception as e:
            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"Error updating standings: {str(e)}"
                )
            )
        
    def update_standings_ui(self,
                            standings_data: Dict[str, List[Dict[str, Any]]]
                            ) -> None:
        for item in self.standings_tree.get_children():
            self.standings_tree.delete(item)
        
        CONFERENCE_ORDER = ['AFC', 'NFC']
        DIVISION_ORDER = ['North', 'South', 'East', 'West']
        
        conferences = {}
        for division_name, teams in standings_data.items():
            for team in teams:
                conference = team['conference']
                if conference not in conferences:
                    conferences[conference] = {}
                
                if division_name not in conferences[conference]:
                    conferences[conference][division_name] = []
                
                conferences[conference][division_name].append(team)
        
        for conference_name in CONFERENCE_ORDER:
            if conference_name not in conferences:
                continue
            
            conference_id = self.standings_tree.insert(
                "", "end", text=conference_name, 
                values=("", "", "", "", "", "", "")
            )
            
            for division_suffix in DIVISION_ORDER:
                division_name = f"{conference_name} {division_suffix}"
                if division_name not in conferences[conference_name]:
                    continue
                
                division_id = self.standings_tree.insert(
                    conference_id, "end", text=division_name, 
                    values=("", "", "", "", "", "", "")
                )
                
                teams = conferences[conference_name][division_name]
                sorted_teams = sorted(
                    teams, key=lambda x: (-x['wins'], -x['winPercent'])
                )
                
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
                    
                    self.standings_tree.item(
                        team_id, tags=(team['abbreviation'],)
                    )

        for conference_id in self.standings_tree.get_children():
            self.standings_tree.item(conference_id, open=True)
            for division_id in self.standings_tree.get_children(conference_id):
                self.standings_tree.item(division_id, open=True)

    def on_team_click(self, event: Any) -> None:
        item_id = self.standings_tree.identify('item', event.x, event.y)
        if not item_id:
            return
        
        parent_id = self.standings_tree.parent(item_id)
        if not parent_id:
            return
        
        team_abbr = self.standings_tree.item(item_id, "tags")[0]
        
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
    
    def show_team_details(self, team_data: Dict[str, Any]) -> None:
        details_window = tk.Toplevel(self.root)
        details_window.title(f"{team_data['name']} Details")
        details_window.geometry("500x350")
        
        top_frame = ttk.Frame(details_window)
        top_frame.pack(fill=tk.X, padx=20, pady=10)
        
        logo_frame = ttk.Frame(
            top_frame, width=100, height=100, relief=tk.GROOVE, borderwidth=2
        )
        logo_frame.pack(side=tk.LEFT, padx=10)
        logo_frame.pack_propagate(False)
        
        logo_label = ttk.Label(
            logo_frame, text="Click to\nload logo", cursor="hand2"
        )
        logo_label.pack(expand=True, fill=tk.BOTH)
        
        logo_label.bind(
            "<Button-1>",
            lambda _: self.load_photo(logo_frame, team_data['logo'])
        )
        
        info_frame = ttk.Frame(top_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        ttk.Label(
            info_frame,
            text=f"{team_data['name']} ({team_data['abbreviation']})",
            font=("Arial", 16, "bold")
        ).pack(anchor="w")
        ttk.Label(
            info_frame, text=f"Conference: {team_data['conference']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Division: {team_data['division']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=(
                f"Record: {team_data['wins']}-"
                f"{team_data['losses']}-"
                f"{team_data['ties']} "
                f"({team_data['winPercent']:.3f})"
            )
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Points For: {team_data['pointsFor']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Points Against: {team_data['pointsAgainst']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Point Differential: {team_data['pointDifferential']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Home Record: {team_data['homeRecord']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Away Record: {team_data['awayRecord']}"
        ).pack(anchor="w")
        ttk.Label(
            info_frame,
            text=f"Venue: {team_data['venue']}"
        ).pack(anchor="w")

        address = team_data['address']
        ttk.Label(
            info_frame,
            text=f"Location: {address['city']}, {address['state']}"
        ).pack(anchor="w")

        ttk.Button(
            details_window, text="Close",
            command=details_window.destroy
        ).pack(pady=20)

    def refresh_player_stats(self, category: str, year: Optional[str] = None
                             ) -> None:
        self.status_var.set(f"Loading {STAT_CATEGORIES[category]} data...")
        coroutine = self.fetch_and_display_player_stats(year, category)

        if not isinstance(coroutine, types.CoroutineType):
            raise RuntimeError(
                """fetch_and_display_standings 
                did not return a coroutine object!"""
            )
        asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    @log_operation
    async def fetch_and_display_player_stats(self, year: Optional[str],
                                             category: str) -> None:
        try:
            stats_data = await fetch_stats_leaders(year, category)
            
            if not hasattr(self, 'current_player_stats'):
                self.current_player_stats = {}
            
            if category in stats_data:
                self.current_player_stats[category] = stats_data[category]
            
            self.root.after(
                0,
                lambda: self.update_player_stats_category_ui(
                    category, stats_data.get(category, [])
                )
            )
            
            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"{STAT_CATEGORIES[category]} data updated successfully"
                )
            )
            
            now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            self.root.after(
                0,
                lambda: self.player_stats_updated_var.set(
                    f"Last updated: {now}"
                )
            )
            
        except Exception as e:
            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"Error updating {STAT_CATEGORIES[category]} "
                    f"data: {str(e)}"
                )
            )

    def update_player_stats_category_ui(self, category: str,
                                        players: List[Dict[str, Any]]) -> None:
        if category not in self.stat_trees:
            return
            
        tree = self.stat_trees[category]
        
        for item in tree.get_children():
            tree.delete(item)
        
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

    def on_player_click(self, event: Any, category: str) -> None:
        tree = self.stat_trees[category]
        item_id = tree.identify('item', event.x, event.y)
        if not item_id:
            return
        
        athlete_id = tree.item(item_id, "tags")[0]
        
        player_data = None
        for player in self.current_player_stats.get(category, []):
            if str(player['athlete_id']) == athlete_id:
                player_data = player
                break
        
        if player_data:
            self.show_player_details(player_data)

    def show_player_details(self, player_data: Dict[str, Any]) -> None:
        details_window = tk.Toplevel(self.root)
        details_window.title(f"{player_data['name']} Details")
        details_window.geometry("600x400")
        
        top_frame = ttk.Frame(details_window)
        top_frame.pack(fill=tk.X, padx=20, pady=10)
        
        headshot__frame = ttk.Frame(
            top_frame, width=100, height=100, relief=tk.GROOVE, borderwidth=2
        )
        headshot__frame.pack(side=tk.LEFT, padx=10)
        headshot__frame.pack_propagate(False)
        
        headshot_label = ttk.Label(
            headshot__frame,
            text="Click to\nload headshot",
            cursor="hand2"
        )
        headshot_label.pack(expand=True, fill=tk.BOTH)
        
        headshot_label.bind(
            "<Button-1>",
            lambda e: self.load_photo(headshot__frame, player_data['headshot'])
        )

        player_info_frame = ttk.Frame(top_frame)
        player_info_frame.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10
        )

        ttk.Label(player_info_frame, text=f"{player_data['name']}", 
                font=("Arial", 16, "bold")).pack(pady=10)
        
        ttk.Label(
            player_info_frame,
            text=f"Position: {player_data['position']}"
        ).pack(anchor="w", padx=20)
        ttk.Label(
            player_info_frame,
            text=f"Team: {player_data['team']}"
        ).pack(anchor="w", padx=20)
        ttk.Label(
            player_info_frame,
            text=f"DoB: {player_data['date_of_birth']}"
        ).pack(anchor="w", padx=20)
        ttk.Label(
            player_info_frame,
            text=f"College: {player_data['college']}"
        ).pack(anchor="w", padx=20)
        ttk.Label(
            player_info_frame,
            text=f"Draft {player_data['draft']}"
        ).pack(anchor="w", padx=20)
        ttk.Label(
            player_info_frame,
            text=f"Debut Year: {player_data['debut_year']}"
        ).pack(anchor="w", padx=20)
        
        ttk.Button(
            details_window, text="Close", command=details_window.destroy
        ).pack(pady=20)

    def load_photo(self, parent_widget: tk.Widget, url: str) -> None:
        for widget in parent_widget.winfo_children():
            widget.destroy()

        loading_label = ttk.Label(parent_widget, text="Loading...")
        loading_label.pack(expand=True, fill=tk.BOTH)

        coroutine = self.fetch_and_display_logo(parent_widget, url)

        if not isinstance(coroutine, types.CoroutineType):
            raise RuntimeError(
                """fetch_and_display_standings 
                did not return a coroutine object!"""
            )
        asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    async def fetch_and_display_logo(self, parent_widget: tk.Widget, url: str
                                     ) -> None:
        try:
            image = await fetch_image(url)
            if image:
                self.root.after(
                    0,
                    lambda: self.update_logo_widget(parent_widget, image)
                )
        except Exception as e:
            self.root.after(
                0,
                lambda: self.update_logo_widget(
                    parent_widget, None, f"Error: {str(e)}"
                )
            )

    def update_logo_widget(self, parent_widget: tk.Widget, image_data: Any,
                           error_text: Optional[str] = None) -> None:
        for widget in parent_widget.winfo_children():
            widget.destroy()

        if error_text:
            logging.error(f"Logo/Image error: {error_text}")
            error_label = ttk.Label(
                parent_widget, text=error_text, wraplength=90
            )
            error_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        
        if not image_data:
            logging.error("Logo/Image not available for widget.")
            na_label = ttk.Label(parent_widget, text="Logo not\navailable")
            na_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        
        try:
            img = Image.open(BytesIO(image_data))
            img = img.resize((100, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
        
            if not hasattr(parent_widget, '_image_references'):
                setattr(parent_widget, '_image_references', [])
            getattr(parent_widget, '_image_references').append(photo)
            logo_label = ttk.Label(parent_widget, image=photo)
            logo_label.place(relx=0.5, rely=0.5, anchor="center")
        except Exception as e:
            logging.error(f"Exception in update_logo_widget: {str(e)}")
            error_label = ttk.Label(
                parent_widget, text=f"Error: {str(e)}", wraplength=90
            )
            error_label.place(relx=0.5, rely=0.5, anchor="center")

    @validate_data
    async def export_player_stats_to_csv(self) -> None:
        if not hasattr(self, 'current_player_stats'):
            return
        if not self.current_player_stats:
            logging.error("No player stats data to export.")
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export", "No player stats data to export"
                )
            )
            return
        
        current_tab = self.stats_notebook.index(self.stats_notebook.select())
        categories = list(STAT_CATEGORIES.keys())
        if current_tab >= len(categories):
            logging.error("No stat category selected for export.")
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export", "Please select a stat category"
                )
            )
            return
        
        current_category = categories[current_tab]
        players = self.current_player_stats.get(current_category, [])
        
        if not players:
            logging.error(
                f"No data to export for category: {current_category}"
            )
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export", "No data to export for this category"
                )
            )
            return
        
        required_fields = [
            "name", "position", "team", "team_abbr", "value", "rank"
        ]
        
        for player in players:
            for field in required_fields:
                if field not in player or player[field] in (None, ""):
                    logging.error(
                        f"Player data missing required" 
                        f"field '{field}': {player}"
                    )
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Export Error",
                            f"Player data missing required field '{field}'."
                        )
                    )
                    return
        
        filename_future = asyncio.Future()
        self.root.after(
            0,
            lambda: self._get_save_filename(
                filename_future,
                f"NFL_{STAT_CATEGORIES[current_category]}_Leaders"
            )
        )
        
        filename = await filename_future
        
        if not filename:
            logging.error("No filename provided for player stats export.")
            return
        
        csv_handler = CSVDataExporter()
        success = await csv_handler.save(players, filename)
        
        if success:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export", "Data exported successfully"
                )
            )
        else:
            logging.error("Failed to export player stats data to CSV.")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error", "Failed to export data"
                )
            )

    
    @validate_data
    async def export_standings_to_csv(self) -> None:
        standings_to_export = getattr(
            self,
            'filtered_standings', None
        ) or self.current_standings
        
        if not standings_to_export:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    "No standings data to export"
                )
            )
            return
        
        flat_data = []
        for division, teams in standings_to_export.items():
            for team in teams:
                team_copy = team.copy()
                team_copy['division'] = division
                flat_data.append(team_copy)
        
        filename_future = asyncio.Future()
        self.root.after(0, lambda: self._get_save_filename(filename_future))
        
        filename = await filename_future
        print(f"Selected filename: {filename}")
        
        if not filename:
            return
        
        csv_handler = CSVDataExporter()
        success = await csv_handler.save(flat_data, filename)
        
        if success:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    "Data exported successfully"
                )
            )
        else:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    "Failed to export data"
                )
            )

    def _get_save_filename(self, future: asyncio.Future,
                           default_name: str = "NFL_Stats") -> None:
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Standings Data",
            initialfile=default_name
        )
        future.set_result(filename)

    async def export_player_stats_to_file(self, filetype: str = 'csv') -> None:
        if not hasattr(
            self, 'current_player_stats'
        ) or not self.current_player_stats:
            logging.error("No player stats data to export.")
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    "No player stats data to export"
                )
            )
            return
        
        current_tab = self.stats_notebook.index(self.stats_notebook.select())
        categories = list(STAT_CATEGORIES.keys())
        if current_tab >= len(categories):
            logging.error("No stat category selected for export.")
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    "Please select a stat category"
                )
            )
            return
        
        current_category = categories[current_tab]
        players = self.current_player_stats.get(current_category, [])
        if not players:
            logging.error(
                f"No data to export for category: {current_category}"
            )
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    "No data to export for this category"
                )
            )
            return
        
        required_fields = [
            "name", "position", "team", "team_abbr", "value", "rank"
        ]
        
        for player in players:
            for field in required_fields:
                if field not in player or player[field] in (None, ""):
                    logging.error(
                        f"Player data missing required "
                        f"field '{field}': {player}")
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Export Error",
                            f"Player data missing required field '{field}'."
                        )
                    )
                    return
        
        filename_future = asyncio.Future()
        default_name = f"NFL_{STAT_CATEGORIES[current_category]}_Leaders"
        self.root.after(
            0,
            lambda: self.get_save_filename_ext(
                filename_future, default_name,
                filetype
            )
        )
        
        filename = await filename_future
        if not filename:
            logging.error("No filename provided for player stats export.")
            return
        
        if filetype == 'csv':
            exporter = CSVDataExporter()
        elif filetype == 'json':
            exporter = JSONDataExporter()
        elif filetype == 'xlsx':
            exporter = ExcelDataExporter()
        else:
            logging.error(f"Unsupported export filetype: {filetype}")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Unsupported filetype: {filetype}"
                )
            )
            return
        
        success = await exporter.save(players, filename)
        if success:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    f"Data exported successfully as {filetype.upper()}"
                )
            )
        else:
            logging.error(
                f"Failed to export player stats data to {filetype.upper()}."
            )
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Failed to export data as {filetype.upper()}"
                )
            )

    async def export_standings_to_file(self, filetype: str = 'csv') -> None:
        standings_to_export = getattr(
            self,
            'filtered_standings',
            None
        ) or self.current_standings
        
        if not standings_to_export:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    "No standings data to export"
                )
            )
            return
        
        flat_data = []
        for division, teams in standings_to_export.items():
            for team in teams:
                team_copy = team.copy()
                team_copy['division'] = division
                flat_data.append(team_copy)
        
        filename_future = asyncio.Future()
        self.root.after(
            0,
            lambda: self.get_save_filename_ext(
                filename_future,
                "NFL_Standings",
                filetype
            )
        )
        
        filename = await filename_future
        if not filename:
            return
        
        if filetype == 'csv':
            exporter = CSVDataExporter()
        elif filetype == 'json':
            exporter = JSONDataExporter()
        elif filetype == 'xlsx':
            exporter = ExcelDataExporter()
        else:
            logging.error(f"Unsupported export filetype: {filetype}")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Unsupported filetype: {filetype}"
                )
            )
            return
        
        success = await exporter.save(flat_data, filename)
        if success:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    f"Data exported successfully as {filetype.upper()}"
                )
            )
        else:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Failed to export data as {filetype.upper()}"
                )
            )

    def get_save_filename_ext(self, future: asyncio.Future, default_name: str,
                              filetype: str) -> None:
        if filetype == 'csv':
            ext = '.csv'
            filetypes = [("CSV files", "*.csv"), ("All files", "*")]
        elif filetype == 'json':
            ext = '.json'
            filetypes = [("JSON files", "*.json"), ("All files", "*")]
        elif filetype == 'xlsx':
            ext = '.xlsx'
            filetypes = [("Excel files", "*.xlsx"), ("All files", "*")]
        else:
            ext = ''
            filetypes = [("All files", "*")]
        
        filename = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=filetypes,
            title="Save Data",
            initialfile=default_name
        )
        future.set_result(filename)

    def filter_players_by_team(self, category: str, team_abbr: str
                               ) -> List[Dict[str, Any]]:
        if not hasattr(self, 'current_player_stats'):
            return []
        players = self.current_player_stats.get(category, [])
        team_abbr_lower = team_abbr.lower()
        team_filter = create_filter(
            lambda p: team_abbr_lower in p['team_abbr'].lower()
        )
        return team_filter(players)

    def filter_teams_by_division(self, division_name: str, min_wins: int = 0
                                 ) -> List[Dict[str, Any]]:
        if not hasattr(self, 'current_standings'):
            return []
        division_teams = self.current_standings.get(division_name, [])
        win_filter = create_filter(lambda t: t['wins'] >= min_wins)
        return win_filter(division_teams)
    
    def export_player_stats_to_file_sync(self, filetype: str = 'csv') -> None:
        if not hasattr(self, 'current_player_stats'):
            return
        if not self.current_player_stats:
            logging.error("No player stats data to export.")
            messagebox.showinfo("Export", "No player stats data to export")
            return
        
        current_tab = self.stats_notebook.index(self.stats_notebook.select())
        categories = list(STAT_CATEGORIES.keys())
        if current_tab >= len(categories):
            logging.error("No stat category selected for export.")
            messagebox.showinfo("Export", "Please select a stat category")
            return
        
        current_category = categories[current_tab]
        players = self.current_player_stats.get(current_category, [])
        if not players:
            logging.error(
                f"No data to export for category: {current_category}"
            )
            messagebox.showinfo(
                "Export",
                "No data to export for this category"
            )
            return
        
        required_fields = [
            "name", "position", "team", "team_abbr", "value", "rank"
        ]
        for player in players:
            for field in required_fields:
                if field not in player or player[field] in (None, ""):
                    logging.error(
                        f"Player data missing required "
                        f"field '{field}': {player}"
                    )
                    messagebox.showerror(
                        "Export Error",
                        f"Player data missing required field '{field}'."
                    )
                    return
        
        default_name = f"NFL_{STAT_CATEGORIES[current_category]}_Leaders"
        
        if filetype == 'csv':
            ext = '.csv'
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
            exporter = CSVDataExporter()
        elif filetype == 'json':
            ext = '.json'
            filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
            exporter = JSONDataExporter()
        elif filetype == 'xlsx':
            ext = '.xlsx'
            filetypes = [("Excel files", "*.xlsx"), ("All files", "*.*")]
            exporter = ExcelDataExporter()
        else:
            logging.error(f"Unsupported export filetype: {filetype}")
            messagebox.showerror(
                "Export Error",
                f"Unsupported filetype: {filetype}"
            )
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=filetypes,
            title="Save Data",
            initialfile=default_name
        )
        if not filename:
            logging.info("Export cancelled by user.")
            return
        self.run_export_in_thread(exporter, players, filename, filetype)

    def run_export_in_thread(self, exporter: Any,
                             players: List[Dict[str, Any]], filename: str,
                             filetype: str) -> None:
        threading.Thread(
            target=self.do_export_player_stats,
            args=(exporter, players, filename, filetype),
            daemon=True
        ).start()

    def do_export_player_stats(self, exporter: Any,
                               players: List[Dict[str, Any]], filename: str,
                               filetype: str) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            success = loop.run_until_complete(
                exporter.save(players, filename)
            )
        except Exception as e:
            logging.error(f"Exception during export: {e}")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Failed to export data: {e}"
                )
            )
            loop.close()
            return
        
        loop.close()
        if success:
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    f"Data exported successfully as {filetype.upper()}"
                )
            )
        else:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Failed to export data as {filetype.upper()}"
                )
            )

    def export_standings_to_file_sync(self, filetype: str = 'csv') -> None:
        standings_to_export = getattr(
            self,
            'filtered_standings',
            None
        ) or self.current_standings
        
        if not standings_to_export:
            logging.error("No standings data to export.")
            messagebox.showinfo("Export", "No standings data to export")
            return
        
        flat_data = []
        for division, teams in standings_to_export.items():
            for team in teams:
                team_copy = team.copy()
                team_copy['division'] = division
                flat_data.append(team_copy)
        
        if filetype == 'csv':
            ext = '.csv'
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
            exporter = CSVDataExporter()
        elif filetype == 'json':
            ext = '.json'
            filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
            exporter = JSONDataExporter()
        elif filetype == 'xlsx':
            ext = '.xlsx'
            filetypes = [("Excel files", "*.xlsx"), ("All files", "*.*")]
            exporter = ExcelDataExporter()
        else:
            logging.error(f"Unsupported export filetype: {filetype}")
            messagebox.showerror(
                "Export Error",
                f"Unsupported filetype: {filetype}"
            )
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=filetypes,
            title="Save Data",
            initialfile="NFL_Standings"
        )
        if not filename:
            logging.info("Export cancelled by user.")
            return
        self.run_export_standings_in_thread(
            exporter, flat_data, filename, filetype
        )

    def run_export_standings_in_thread(self, exporter: Any,
                                       flat_data: List[Dict[str, Any]],
                                       filename: str, filetype: str) -> None:
        threading.Thread(
            target=self.do_export_standings,
            args=(exporter, flat_data, filename, filetype),
            daemon=True
        ).start()

    def do_export_standings(self, exporter: Any,
                            flat_data: List[Dict[str, Any]],
                            filename: str, filetype: str) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            logging.info(
                f"Exporting standings to {filename} as {filetype.upper()}..."
            )
            success = loop.run_until_complete(exporter.save(flat_data, filename))
        except Exception as e:
            logging.error(f"Exception during export: {e}")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Failed to export data: {e}"
                )
            )
            loop.close()
            return
        
        loop.close()
        
        if success:
            logging.info(
                f"Standings exported successfully "
                f"to {filename} as {filetype.upper()}."
            )
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Export",
                    f"Data exported successfully as {filetype.upper()}"
                )
            )
        else:
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Export Error",
                    f"Failed to export data as {filetype.upper()}"
                )
            )

def run_asyncio_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == "__main__":
    setup_logging()
    root = tk.Tk()
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "light")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    threading_loop = threading.Thread(
        target=run_asyncio_loop,
        args=(loop,),
        daemon=True
    )
    threading_loop.start()
    
    app = NFLStatsApp(root)
    root.mainloop()
    
    loop.call_soon_threadsafe(loop.stop)
    threading_loop.join()
    loop.close()
