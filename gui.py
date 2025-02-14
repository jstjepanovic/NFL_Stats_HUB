import dearpygui.dearpygui as dpg
import asyncio
from scoreboard import update_standings, sort_teams
from stats_leaders import fetch_stats_leaders


dpg.create_context()
dpg.create_viewport(title='NFL Stats HUB')

def show_team_details(sender, app_data, user_data):
    """Show team details in a new modal window"""
    team = user_data
    
    # Create unique window tag
    window_tag = f"window_{team['name'].replace(' ', '_')}"
    
    # Check if window already exists
    if not dpg.does_item_exist(window_tag):
        with dpg.window(label=f"{team['name']} Details", 
                       tag=window_tag,
                       width=400, 
                       height=300,
                       pos=[300, 200],
                       modal=True,
                       no_resize=True):
            
            # Add close button
            dpg.add_button(label="Close", callback=lambda: dpg.delete_item(window_tag), pos=[320, 250])
            
            # Team info
            dpg.add_text(f"Team: {team['name']}")
            dpg.add_text(f"Division: {team['division']}")
            dpg.add_text(f"Record: {team['wins']}-{team['losses']}-{team['ties']}")
            dpg.add_text(f"Win Percentage: {team['winPercent']:.3f}")

def create_standings_tables(divisions):
    with dpg.group(horizontal=True):
        # AFC Conference (Left side)
        with dpg.child_window(width=400, height=600):
            dpg.add_text("American Football Conference", color=(204, 16, 16))
            afc_divisions = {k: v for k, v in divisions.items() if k.startswith('AFC')}
            for div_name, teams in sorted(afc_divisions.items()):
                with dpg.collapsing_header(label=div_name, default_open=True):
                    with dpg.table(tag=f"table_{div_name}",
                                 header_row=True, 
                                 borders_innerH=True, 
                                 borders_outerH=True, 
                                 borders_innerV=True, 
                                 borders_outerV=True,
                                 policy=dpg.mvTable_SizingFixedFit):
                        
                        dpg.add_table_column(label="Team", width=200)
                        dpg.add_table_column(label="W", width=40)
                        dpg.add_table_column(label="L", width=40)
                        dpg.add_table_column(label="T", width=40)
                        dpg.add_table_column(label="Win%", width=60)
                        
                        sorted_teams = sort_teams(teams)
                        for idx, team in enumerate(sorted_teams):
                            with dpg.table_row():
                                dpg.add_selectable(label=team['name'], 
                                                callback=show_team_details,
                                                user_data=team,
                                                span_columns=True,
                                                tag=f"{div_name}_pos{idx}_name",
                                                indent=5)
                                dpg.add_text(f"{team['wins']}", tag=f"{div_name}_pos{idx}_wins", indent=15)
                                dpg.add_text(f"{team['losses']}", tag=f"{div_name}_pos{idx}_losses", indent=15)
                                dpg.add_text(f"{team['ties']}", tag=f"{div_name}_pos{idx}_ties", indent=15)
                                dpg.add_text(f"{team['winPercent']:.3f}", tag=f"{div_name}_pos{idx}_winpct", indent=10)

                            
                            
        # NFC Conference (Right side)
        with dpg.child_window(width=400, height=600):
            dpg.add_text("National Football Conference", color=(44, 117, 219))
            nfc_divisions = {k: v for k, v in divisions.items() if k.startswith('NFC')}
            for div_name, teams in sorted(nfc_divisions.items()):
                with dpg.collapsing_header(label=div_name, default_open=True):
                    with dpg.table(tag=f"table_{div_name}",
                                    header_row=True, 
                                    borders_innerH=True, 
                                    borders_outerH=True, 
                                    borders_innerV=True, 
                                    borders_outerV=True,
                                    policy=dpg.mvTable_SizingFixedFit):
                        
                        dpg.add_table_column(label="Team", width=200)
                        dpg.add_table_column(label="W", width=40)
                        dpg.add_table_column(label="L", width=40)
                        dpg.add_table_column(label="T", width=40)
                        dpg.add_table_column(label="Win%", width=60)
                        
                        sorted_teams = sort_teams(teams)
                        for idx, team in enumerate(sorted_teams):
                            with dpg.table_row():
                                dpg.add_selectable(label=team['name'], 
                                                callback=show_team_details,
                                                user_data=team,
                                                span_columns=True,
                                                tag=f"{div_name}_pos{idx}_name",
                                                indent=5)
                                dpg.add_text(f"{team['wins']}", tag=f"{div_name}_pos{idx}_wins", indent=15)
                                dpg.add_text(f"{team['losses']}", tag=f"{div_name}_pos{idx}_losses", indent=15)
                                dpg.add_text(f"{team['ties']}", tag=f"{div_name}_pos{idx}_ties", indent=15)
                                dpg.add_text(f"{team['winPercent']:.3f}", tag=f"{div_name}_pos{idx}_winpct", indent=10)

def update_standings_data(divisions):
    """Update text values in tables by position"""
    for div_name, teams in divisions.items():
        sorted_teams = sort_teams(teams)
        for idx, team in enumerate(sorted_teams):
            try:
                dpg.configure_item(f"{div_name}_pos{idx}_name", 
                                 label=team['name'],
                                 user_data=team)
                dpg.set_value(f"{div_name}_pos{idx}_wins", str(team['wins']))
                dpg.set_value(f"{div_name}_pos{idx}_losses", str(team['losses']))
                dpg.set_value(f"{div_name}_pos{idx}_ties", str(team['ties']))
                dpg.set_value(f"{div_name}_pos{idx}_winpct", f"{team['winPercent']:.3f}")
            except Exception as e:
                print(f"Error updating position {idx} in {div_name}: {e}")
                dpg.delete_item("Primary Window", children_only=True)
                create_standings_tables(divisions)
                break

def create_leaderboard(leaders_data):
    """Create leaderboard tables for stats leaders"""
    with dpg.child_window(width=300, height=600):
        dpg.add_text("League Leaders", color=(255, 215, 0))
        for category, leaders in leaders_data.items():
            with dpg.collapsing_header(label=category, default_open=False):
                with dpg.table(header_row=True,
                             borders_innerH=True, borders_outerH=True,
                             borders_innerV=True, borders_outerV=True,
                             policy=dpg.mvTable_SizingFixedFit):
                    dpg.add_table_column(label="Rank", width=40)
                    dpg.add_table_column(label="Player", width=150)
                    dpg.add_table_column(label="Value", width=70)
                    
                    for player in leaders:
                        with dpg.table_row():
                            dpg.add_text(f"#{player['rank']}", tag=f"{category}_rank{player['rank']}")
                            dpg.add_text(f"{player['name']}", tag=f"{category}_name{player['rank']}")
                            dpg.add_text(f"{player['value']}", tag=f"{category}_value{player['rank']}")

def update_leaderboard(leaders):
    """Update text values in leaderboard tables"""
    for category, players in leaders.items():
        for player in players:
            try:
                dpg.set_value(f"{category}_name{player['rank']}", player['name'])
                dpg.set_value(f"{category}_value{player['rank']}", player['value'])
            except Exception as e:
                print(f"Error updating {category} leaderboard: {e}")
                dpg.delete_item("Primary Window", children_only=True)
                create_leaderboard(leaders)
                break

async def handle_year_change(year):
    try:
        divisions = await update_standings(year)
        leaders = await fetch_stats_leaders(year)
        update_standings_data(divisions)
        update_leaderboard(leaders)

    except Exception as e:
        print(f"Error updating data: {e}")

def year_callback(sender, app_data):
    """Handle year selection changes"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(handle_year_change(app_data))
        
        loop.close()
    except Exception as e:
        print(f"Error in year callback: {e}")

async def init_gui():
    with dpg.window(tag="Primary Window", label="NFL Standings"):
        # Year selector dropdown
        dpg.add_combo(
            items=[str(year) for year in range(2004, 2025)],
            default_value="2024",
            callback=year_callback,
            width=200
        )
        
        with dpg.group(horizontal=True):
            divisions = await update_standings("2024")
            create_standings_tables(divisions)
            leaders = await fetch_stats_leaders("2024")
            create_leaderboard(leaders)
            


dpg.setup_dearpygui()
dpg.show_viewport()
asyncio.run(init_gui())
dpg.set_primary_window("Primary Window", True)
dpg.maximize_viewport()
dpg.start_dearpygui()
dpg.destroy_context()