# from tkinter import *
import tkinter as tk
from tkinter import font
from tkinter import ttk
from retrieve_data import *
import multiprocessing as mp
import sys
import time
import os

def draw_grid_lines(tab):
    rows, cols = tab.grid_size()
    for i in range(rows):
        ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    for i in range(cols):
        ttk.Separator(tab, orient='vertical').grid(row=0, column=i, rowspan=rows, sticky='nse')

class ViewData:

    def __init__(self, tab):
        self.tab = tab

        self.initialize_tab()

    def find_test_runs(self, user_id):

        username = cred.username
        password = cred.password

        uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
        client = MongoClient(uri, server_api=ServerApi('1'))
        smarthub_db = client.Smarthub
        self.test_collection = smarthub_db.test_collection

        self.all_ids = self.test_collection.find({'user_id': user_id}, {'_id': 1, 'test_name': 1})
        self.valid_ids = []

        self.new_valid_ids = []
        for id in self.all_ids:
            id_val = id['_id']
            if 'test_name' in id:
                self.new_valid_ids.append(id['test_name'])
            else:
                self.new_valid_ids.append(id_val)
            self.valid_ids.append(id_val)

        print(self.valid_ids)

        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=20)

        self.select_test_run = ttk.Combobox(self.tab, values=self.new_valid_ids, width=15, font=font.Font(size=14))
        self.select_test_run.grid(row=2, column=0, pady=10, columnspan=2, sticky='nsew')
        # self.select_test_run.set(self.new_valid_ids[0])
        self.select_test_run.bind("<<ComboboxSelected>>", self.show_data)

    def zoom(self, direction):
        if direction == '+':
            if self.dpi < 150: 
                self.dpi += 10
                self.show_data(None, dpi=self.dpi)
        else:
            if self.dpi > 50:
                self.dpi -= 10
                self.show_data(None, dpi=self.dpi)


        
    
    def show_data(self, event, dpi=100):
        self.dpi = dpi
        test_name = self.valid_ids[self.new_valid_ids.index(self.select_test_run.get())]

        data = self.test_collection.find({'_id': test_name})[0]

        screen_width = self.tab.winfo_screenwidth()
        screen_height = self.tab.winfo_screenheight()

        fig = Figure(figsize=((screen_width-400)/dpi, (screen_height-200)/dpi), dpi=dpi)
        fig.set_facecolor(str(ttk.Style().lookup('TFrame', 'background')))
        axs=[]
        axs.append(fig.add_subplot(221))
        axs.append(fig.add_subplot(222))
        axs.append(fig.add_subplot(223))
        axs.append(fig.add_subplot(224))
        for ax in axs:
            ax.tick_params(colors='white')
            # ax.set_facecolor(str(ttk.Style().lookup('TFrame', 'foreground')))
            ax.set_facecolor('lightgray')
            

        # fig.subplots_adjust(left=, right=0.6, bottom=0.4, top=0.6, wspace=0.2, hspace=0.2)
        border = dpi/400
        print(border)
        # fig.subplots_adjust(left=0.05, right=1-border, bottom=0.05, top=1-border)

        fig.subplots_adjust(left=0.05, right=0.95, bottom=0.075, top=0.95, wspace=border, hspace=border)

        canvas = FigureCanvasTkAgg(fig, master=self.tab)

        # fig.tight_layout()

        self.tab.columnconfigure(2, minsize=150)
        # draw_grid_lines(self.tab)

        canvas.get_tk_widget().grid(row=1, column=3, columnspan=100, rowspan=100, padx=0, pady=0, sticky='nsew')

        operator_id_label = Label(self.tab, text=f'Operator ID: {data["user_id"]}', font=font.Font(size=18))
        operator_id_label.grid(row=0, column=3, columnspan=100, sticky='sew')

        if event:
            self.zoom_in_button = ttk.Button(self.tab, text='+', command=lambda: self.zoom('+'))
            self.zoom_in_button.grid(row=0, column=95, pady=10, columnspan=3, sticky='nsew')
            self.zoom_out_button = ttk.Button(self.tab, text='-', command=lambda: self.zoom('-'))
            self.zoom_out_button.grid(row=0, column=92, pady=10, columnspan=3, sticky='nsew')
        else:
            self.zoom_in_button.lift()
            self.zoom_out_button.lift()

        # draw_grid_lines(self.tab)


        # Set overall title of figure:
        # fig.suptitle(f'Operator ID: {data["user_id"]}', fontsize=20)

        data['heading_deg'] = get_heading_deg(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])
        data['velocity'] = get_velocity_m_s(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])

        axs[0].set_xlabel('Time (sec)').set_color('white')
        axs[0].set_ylabel('Displacement (m)').set_color('white')
        axs[0].set_title('Displacement vs Time').set_color('white')
        axs[0].plot(data['elapsed_time_s'], data['distance_m'])

        axs[1].set_xlabel('X Trajectory (m)').set_color('white')
        axs[1].set_ylabel('Y Trajectory (m)').set_color('white')
        axs[1].set_title('Trajectory').set_color('white')
        axs[1].plot(data['traj_x'], data['traj_y'])

        axs[2].set_xlabel('Time (sec)').set_color('white')
        axs[2].set_ylabel('Heading (deg)').set_color('white')
        axs[2].set_title('Heading vs Time').set_color('white')
        axs[2].plot(data['elapsed_time_s'], data['heading_deg'])

        axs[3].set_xlabel('Time (sec)').set_color('white')
        axs[3].set_ylabel('Velocity (m/s)').set_color('white')
        axs[3].set_title('Velocity vs Time').set_color('white')
        axs[3].plot(data['elapsed_time_s'], data['velocity'])

        # draw_grid_lines(self.tab)


    def initialize_tab(self):

        ttk.Label(self.tab, text="Select User ID: ", justify='center', font=font.Font(size=14))\
            .grid(row=0, column=0, pady=10, columnspan=2)

        select_user_id = ttk.Entry(self.tab, width=10, font=font.Font(size=12))
        select_user_id.grid(row=1, column=0, pady=10, sticky='nsew')

        ttk.Button(self.tab, text='Enter', command=lambda: self.find_test_runs(select_user_id.get())).grid(row=1, column=1, pady=10, sticky='nsew')

        select_user_id.bind('<Return>', lambda event: self.find_test_runs(select_user_id.get()))
                            