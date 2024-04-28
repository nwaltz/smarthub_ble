from tkinter import *
from tkinter import ttk
from gui_functions_filtered import *
from get_recorded_data import *
import multiprocessing as mp
import sys
import os

if getattr(sys, 'frozen', False):
    # Running in a bundle
    base_path = sys._MEIPASS
    theme_file_path = os.path.join(base_path, 'data', 'forest-dark.tcl')
else:
    # Running as a script
    base_path = os.path.dirname(os.path.abspath(__file__))
    theme_file_path = os.path.join(base_path, 'forest-dark.tcl')

# theme_file_path = os.path.join(base_path, 'data', 'forest-dark.tcl')
# theme_file_path = os.path.join(base_path, 'forest-dark.tcl')



def remove_all_widgets(root):
    for widget in root.winfo_children():
        widget.destroy()

def start_screen(root):

    from gui_functions_filtered import grab_raw_data, record_data

    from get_recorded_data import view_data

    # root = Tk()
    root.title('SmartHub Data Visualization')
    frm = ttk.Frame(root, padding=10)
    # frm.grid()

    net_screen_size = [1100,750]


    frame_select_text = ttk.Frame(root)
    # frame_select_text.pack()
    frame_select_text.place(x=380,y=120)
    user_select_text = ttk.Label(frame_select_text, text="SMARTHUB MAIN MENU", font=("Verdana", 25))
    user_select_text.pack()

    frame_select_text = ttk.Frame(root)
    # frame_select_text.pack()
    frame_select_text.place(x=450,y=240)
    user_select_text = ttk.Label(frame_select_text, text="I am looking to ...", font=("Verdana", 20))
    user_select_text.pack()

    button_frame_left = ttk.Frame(root)
    button_frame_left.pack()
    button_frame_left.place(x=300,y=300)
    button_user_menu_left = ttk.Button(button_frame_left, text="view data", style="user_select.TButton", command=lambda: view_data(root))
    button_user_menu_left.pack()
    
    q_send = mp.Queue()
    q_recieve = mp.Queue()

    ## put logic here that makes the process only run once

    process = mp.Process(target=grab_raw_data, args=(q_send, q_recieve))
    process.start()
    # mp.Process(target=record_data, args=(root, button_user_menu_right, button_user_menu_left, user_select_text, q_send, q_recieve)).start()

    button_frame_right = ttk.Frame(root)
    button_frame_right.pack()
    button_frame_right.place(x=600,y=300)
    button_user_menu_right = ttk.Button(button_frame_right, text="record data", style="user_select.TButton", command=lambda: record_data(root, button_user_menu_right, button_user_menu_left, user_select_text, q_send, q_recieve))
    button_user_menu_right.pack()
    
    # root.mainloop()



if __name__ == '__main__':
    mp.freeze_support()
    root = Tk()

    net_screen_size = [1100,750]

    style = ttk.Style(root)
    root.tk.call('source', theme_file_path)
    style.theme_use('forest-dark')
    root.geometry(f"{net_screen_size[0]}x{net_screen_size[1]}")

    style.configure("user_select.TButton", padding=(20,10), font=("Verdana", 20))
    start_screen(root)
    root.mainloop()