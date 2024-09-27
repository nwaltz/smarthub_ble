from tkinter import *
from tkinter import ttk
from retrieve_data import *
import multiprocessing as mp
import sys
import os
import glob
# import cred
import asyncio

from view_data_tab import ViewData
from record_data_tab import RecordData
from calibrate_tab import Calibrate

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

if getattr(sys, 'frozen', False):
    # Running in a bundle
    base_path = sys._MEIPASS
    theme_file_path = os.path.join(base_path, 'data', 'forest-dark.tcl')
else:
    # Running as a script
    base_path = os.path.dirname(os.path.abspath(__file__))
    theme_file_path = os.path.join(base_path, 'forest-dark.tcl')

def end_fullscreen(root=None):
        root.attributes("-fullscreen", False)

def connect_to_db_password(username, password):
    
    uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(uri, server_api=ServerApi('1'))
    smarthub_db = client.Smarthub
    return smarthub_db

def connect_to_db_certificate(path_to_cert):
    # uri = "mongodb+srv://<username>:<password>@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
    uri = "mongodb+srv://smarthub.gbdlpxs.mongodb.net?authSource=$external&authMechanism=MONGODB-X509"
    client = MongoClient(uri, tls=True, tlsCertificateKeyFile=path_to_cert)
    smarthub_db = client.Smarthub
    return smarthub_db

def initalize_gui(db):
    root = Tk()
    style = ttk.Style(root)

    root.attributes("-fullscreen", True)

    root.bind("<Escape>", lambda event: end_fullscreen(root))
    root.bind("<Control-Key-q>", lambda event: root.destroy())

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

    # db = connect_to_db()

    ViewData(view_data_tab, database=db)
    RecordData(record_data_tab, database=db)
    Calibrate(calibrate_tab, database=db)

    root.mainloop()

def login(root, username, password, login_button):
    try:
        db = connect_to_db_password(username, password)
        collections = db.list_collection_names()
        root.destroy()
        initalize_gui(db)
    except Exception as e:
        print("Failed to connect to MongoDB:", e)
        ttk.Label(root, text="Invalid username or password").grid(row=3, column=1)
    # root.destroy()

def authenticate():
    root = Tk()
    root.title('Authentication')
    root.geometry('300x200')
    root.resizable(False, False)
    style = ttk.Style(root)
    root.tk.call('source', theme_file_path)
    style.theme_use('forest-dark')

    ttk.Label(root, text="Username:").grid(row=0, column=0)
    username_entry = ttk.Entry(root)
    username_entry.grid(row=0, column=1)
    ttk.Label(root, text="Password:").grid(row=1, column=0)
    password_entry = ttk.Entry(root, show="*")
    password_entry.grid(row=1, column=1)

    login_button = ttk.Button(root, text="Login", command=lambda: login(root, username_entry.get(), password_entry.get(), login_button))
    login_button.grid(row=2, column=1)
    root.bind("<Return>", lambda event: login(root, username_entry.get(), password_entry.get(), login_button))


    root.mainloop()





if __name__ == '__main__':

    pem_files = glob.glob('*.pem')
    if pem_files:
        valid_file = False
        for file in pem_files:
            try:
                # print(file)
                db = connect_to_db_certificate(file)
                collections = db.list_collection_names()
                valid_file = True
                initalize_gui(db)
                break
            except Exception as e:
                print(e)
                pass

    if not valid_file:
        authenticate()



    # initalize_gui()

