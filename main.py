from tkinter import *
import tkinter as tk
from tkinter import ttk
import json
import sys
import os
import glob
import platform
from gui.view_data_tab import ViewData
from gui.record_data_tab import RecordData
from gui.calibrate_tab import Calibrate
from gui.new_calibrate_tab import NewCalibrate

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

class SmarthubApp:

    def __init__(self):

        if getattr(sys, 'frozen', False):
            # Running in a bundle
            self.base_path = sys._MEIPASS
            self.data_path = os.path.join(self.base_path, 'data')
            self.file_path = os.path.dirname(sys.executable)
            self.theme_file_path = os.path.join(self.base_path, 'data', 'forest-dark.tcl')
        else:
            # Running as a script
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            self.file_path = self.base_path 
            self.data_path = self.file_path
            self.theme_file_path = os.path.join(self.base_path, 'gui/theme/forest-dark.tcl')

        self.get_config()

    def end_fullscreen(self):
        self.root.attributes("-fullscreen", False)

    def connect_to_db_password(self, username, password):
        
        uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
        self.client = MongoClient(uri, server_api=ServerApi('1'))
        smarthub_db = self.client
        return smarthub_db

    def connect_to_db_certificate(self, path_to_cert):
        uri = "mongodb+srv://smarthub.gbdlpxs.mongodb.net/?authSource=$external&authMechanism=MONGODB-X509"
        self.client = MongoClient(uri, tls=True, tlsCertificateKeyFile=path_to_cert)
        return self.client

    def initalize_gui(self, db):
        self.root = Tk()
        style = ttk.Style(self.root)

        self.root.attributes("-fullscreen", True)

        self.root.bind("<Escape>", lambda event: self.end_fullscreen(self.root))
        self.root.bind("<Control-Key-q>", lambda event: self.on_exit())
        self.root.bind("<Command-q>", lambda event: self.on_exit())
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        if platform.system() == 'MacOS':
            self.setup_macos_menu()


        self.root.tk.call('source', self.theme_file_path)
        style.theme_use('forest-dark')
        self.root.title('SmartHub Data Visualization')

        # find dimensions of screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        self.root.geometry(f"{screen_width-5}x{screen_height}")

        self.root.geometry(f"+0+0")

        notebook = ttk.Notebook(self.root)
        notebook.grid(sticky='NESW')

        record_data_tab = ttk.Frame(notebook)
        view_data_tab =   ttk.Frame(notebook)
        calibrate_tab =   ttk.Frame(notebook)
        new_calibrate_tab = ttk.Frame(notebook)

        notebook.add(view_data_tab, text="View Data")
        notebook.add(record_data_tab, text="Record Data")
        notebook.add(calibrate_tab, text="Calibrate")
        notebook.add(new_calibrate_tab, text="New Calibrate")

        # db = connect_to_db()

        self.record_data_class = RecordData(record_data_tab, 
                                            database=db, 
                                            filepath=self.data_path, 
                                            screen_size=(screen_width, screen_height),
                                            config=self.config)
        
        self.view_data_class = ViewData(view_data_tab, 
                                        self.record_data_class, 
                                        database=db, 
                                        filepath=self.data_path, 
                                        screen_size=(screen_width, screen_height),
                                        config=self.config)
        
        self.calibrate_data_class = Calibrate(calibrate_tab, 
                                              database=db, 
                                              filepath=self.data_path, 
                                              screen_size=(screen_width, screen_height),
                                              config=self.config)
        
        self.new_calibrate_data_class = NewCalibrate(new_calibrate_tab,
                                                    database=db,
                                                    filepath=self.data_path,
                                                    screen_size=(screen_width, screen_height),
                                                    config=self.config)

        self.root.mainloop()

    def get_config(self):
        """
        :param: None
        :returns: None

        used to get config information from config.json
        """

        if not os.path.exists('config.json'):
            self.config = {}
            with open('config.json', 'w') as config_file:
                json.dump(self.config, config_file)
        else:
            with open('config.json', 'r') as config_file:
                self.config = json.load(config_file)

    def update_config(self, key, value=None):
        """
        :param key: variable name to save
        :param value: if None, removes key from config
                        else inputs value to config

        used to create persistent user config information between sessions
        not currently used, but if user settings can be applied this should be included
        
        """

        # most recent config info is retrieved from file and stored in self.config. no need to manually set self.config
        # if value is none, key is removed from config
        with open('config.json', 'r') as config_file:
            self.config = json.load(config_file)
            if value == None:
                self.config.pop(key)
            else:
                self.config[key] = value

        with open('config.json', 'w') as config_file:
            json.dump(self.config, config_file)

    def on_exit(self):
        """
        :param: None
        :returns None

        used to save user settings on exit
        """
        if hasattr(self.view_data_class, 'trajectory_gridlines_check'):
            self.update_config('gridlines', self.view_data_class.trajectory_gridlines_check.get())
        self.client.close()
        self.root.destroy()
        # sys.exit()

    def login(self, username, password, login_button):
        try:
            db = self.connect_to_db_password(username, password)
            collections = db.list_collection_names()
            self.root.destroy()
            self.initalize_gui(db)
        except Exception as e:
            print("Failed to connect to MongoDB:", e)
            ttk.Label(self.root, text="Invalid username or password").grid(row=3, column=1)
        # self.root.destroy()

    def authenticate(self):
        self.root = Tk()
        self.root.title('Authentication')
        self.root.geometry('300x200')
        self.root.resizable(False, False)

        style = ttk.Style(self.root)
        self.root.tk.call('source', self.theme_file_path)
        style.theme_use('forest-dark')

        ttk.Label(self.root, text="Username:").grid(row=0, column=0)
        username_entry = ttk.Entry(self.root)
        username_entry.grid(row=0, column=1)
        ttk.Label(self.root, text="Password:").grid(row=1, column=0)
        password_entry = ttk.Entry(self.root, show="*")
        password_entry.grid(row=1, column=1)

        login_button = ttk.Button(self.root, text="Login", command=lambda: self.login(self.root, username_entry.get(), password_entry.get(), login_button))
        login_button.grid(row=2, column=1)
        self.root.bind("<Return>", lambda event: self.login(self.root, username_entry.get(), password_entry.get(), login_button))


        self.root.mainloop()


if __name__ == '__main__':

    app = SmarthubApp()

    print('Base path:', app.base_path)

    pem_files = glob.glob(app.file_path + '/*.pem')
    valid_file = False
    if pem_files:
        for file in pem_files:
            try:
                print('Authenticating with', file)
                db = app.connect_to_db_certificate(file)
                collections = db.Smarthub.list_collection_names()
                print(collections)
                valid_file = True
                app.initalize_gui(db)
                break
            except Exception as e:
                print(e)
                pass

    if not valid_file:
        app.authenticate()



    # initalize_gui()

