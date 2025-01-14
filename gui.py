import dearpygui.dearpygui as dpg
import asyncio
from scoreboard import update_standings, sort_teams

dpg.create_context()
dpg.create_viewport(title='NFL Stats HUB')

def create_standings_tables(divisions):
    with dpg.group(horizontal=True):
        # AFC Conference (Left side)
        with dpg.child_window(width=400, height=600):
            dpg.add_text("American Football Conference", color=(255, 0, 0))
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
                        
                        dpg.add_table_column(label="Team", width=150)
                        dpg.add_table_column(label="W", width=40)
                        dpg.add_table_column(label="L", width=40)
                        dpg.add_table_column(label="T", width=40)
                        dpg.add_table_column(label="Win%", width=70)
                        
                        sorted_teams = sort_teams(teams)
                        for idx, team in enumerate(sorted_teams):
                            with dpg.table_row():
                                dpg.add_text(team['name'], tag=f"{div_name}_pos{idx}_name")
                                dpg.add_text(f"{team['wins']}", tag=f"{div_name}_pos{idx}_wins", indent=15)
                                dpg.add_text(f"{team['losses']}", tag=f"{div_name}_pos{idx}_losses", indent=15)
                                dpg.add_text(f"{team['ties']}", tag=f"{div_name}_pos{idx}_ties", indent=15)
                                dpg.add_text(f"{team['winPercent']:.3f}", tag=f"{div_name}_pos{idx}_winpct", indent=10)
        
        # NFC Conference (Right side)
        with dpg.child_window(width=400, height=600):
            dpg.add_text("National Football Conference", color=(0, 0, 255))
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
                        
                        dpg.add_table_column(label="Team", width=150)
                        dpg.add_table_column(label="W", width=40)
                        dpg.add_table_column(label="L", width=40)
                        dpg.add_table_column(label="T", width=40)
                        dpg.add_table_column(label="Win%", width=70)
                        
                        sorted_teams = sort_teams(teams)
                        for idx, team in enumerate(sorted_teams):
                            with dpg.table_row():
                                dpg.add_text(team['name'], tag=f"{div_name}_pos{idx}_name")
                                dpg.add_text(f"{team['wins']}", tag=f"{div_name}_pos{idx}_wins", indent=15)
                                dpg.add_text(f"{team['losses']}", tag=f"{div_name}_pos{idx}_losses", indent=15)
                                dpg.add_text(f"{team['ties']}", tag=f"{div_name}_pos{idx}_ties", indent=15)
                                dpg.add_text(f"{team['winPercent']:.3f}", tag=f"{div_name}_pos{idx}_winpct", indent=10)

async def update_standings_data(divisions):
    """Update text values in tables by position"""
    for div_name, teams in divisions.items():
        sorted_teams = sort_teams(teams)
        for idx, team in enumerate(sorted_teams):
            try:
                dpg.set_value(f"{div_name}_pos{idx}_name", team['name'])
                dpg.set_value(f"{div_name}_pos{idx}_wins", str(team['wins']))
                dpg.set_value(f"{div_name}_pos{idx}_losses", str(team['losses']))
                dpg.set_value(f"{div_name}_pos{idx}_ties", str(team['ties']))
                dpg.set_value(f"{div_name}_pos{idx}_winpct", f"{team['winPercent']:.3f}")
            except Exception as e:
                print(f"Error updating position {idx} in {div_name}: {e}")
                dpg.delete_item("Primary Window", children_only=True)
                create_standings_tables(divisions)
                break

async def handle_year_change(year):
    try:
        divisions = await update_standings(year)
        await update_standings_data(divisions)
    except Exception as e:
        print(f"Error updating standings: {e}")

def year_callback(sender, app_data):
    """Handle year selection changes"""
    try:
        # Create and set new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async operation
        loop.run_until_complete(handle_year_change(app_data))
        
        # Clean up
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
        
        # Initial data load
        divisions = await update_standings("2024")
        create_standings_tables(divisions)


dpg.setup_dearpygui()
dpg.show_viewport()
asyncio.run(init_gui())
dpg.set_primary_window("Primary Window", True)
dpg.maximize_viewport()
dpg.start_dearpygui()
dpg.destroy_context()