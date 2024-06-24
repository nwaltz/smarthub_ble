from tkinter import *
from tkinter import ttk
from retrieve_data import *
import multiprocessing as mp
import sys
import os

from view_data_tab import ViewData

if getattr(sys, 'frozen', False):
    # Running in a bundle
    base_path = sys._MEIPASS
    theme_file_path = os.path.join(base_path, 'data', 'forest-dark.tcl')
else:
    # Running as a script
    base_path = os.path.dirname(os.path.abspath(__file__))
    theme_file_path = os.path.join(base_path, 'forest-dark.tcl')

def initalize_gui():
    root = Tk()
    style = ttk.Style(root)
    root.tk.call('source', theme_file_path)
    style.theme_use('forest-dark')
    root.title('SmartHub Data Visualization')

    # find dimensions of screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    root.geometry(f"{screen_width-5}x{screen_height}")
    # root.geometry(f"500x500")
    # set screen to be at the top left corner
    root.geometry(f"+0+0")

    notebook = ttk.Notebook(root)
    notebook.grid(sticky='NESW')

    # record_data_tab = ttk.Frame(notebook, width=screen_width-50, height=screen_height-150)
    # view_data_tab =   ttk.Frame(notebook, width=screen_width-50, height=screen_height-150)
    # calibrate_tab =   ttk.Frame(notebook, width=screen_width-50, height=screen_height-150)
    record_data_tab = ttk.Frame(notebook)
    view_data_tab =   ttk.Frame(notebook)
    calibrate_tab =   ttk.Frame(notebook)

    notebook.add(view_data_tab, text="View Data")
    notebook.add(record_data_tab, text="Record Data")
    notebook.add(calibrate_tab, text="Calibrate")

    ViewData(view_data_tab)


    root.mainloop()

if __name__ == '__main__':
    initalize_gui()