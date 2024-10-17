import tkinter as tk
from tkinter import font, ttk, Label
import cred
import sys
import time
import os
import csv
import json
import bisect
import pandas as pd
import math
from tk_slider_widget import Slider

import multiprocessing as mp

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from base_ble.calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)
from base_ble.data_analyze import export_metrics, calculate_bout, Metrics

def draw_grid_lines(tab):
    rows, cols = tab.grid_size()
    # for i in range(rows):
    #     ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    
    # for i in range(rows):
    #     ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    for i in range(10):
        ttk.Separator(tab, orient='vertical').grid(row=0, column=i, rowspan=rows, sticky='nse')

class ViewData:

    def __init__(self, tab, record_data_tab, database):
        self.tab = tab
        self.record_data_tab = record_data_tab
        self.test_collection = database.test_collection

        self.last_scale_update = time.time()
        self.overlay = tk.BooleanVar(value=False)

        self.prev_data = []

        # self.initialize_tab(auto=True)
        self.initialize_tab(auto=False)
        
        if not os.path.exists('config.json'):
            self.config = {}
        else:
            with open('config.json', 'r') as config_file:
                self.config = json.load(config_file)


    def update_config(self, key, value=None):
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
        self.update_config('gridlines', self.trajectory_gridlines_check.get())
        self.client.close()
        sys.exit()


    def find_test_runs(self, user_id, auto=False):


        # username = cred.username
        # password = cred.password

        # uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
        # client = MongoClient(uri, server_api=ServerApi('1'))
        # smarthub_db = client.Smarthub
        # self.test_collection = smarthub_db.test_collection

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

        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=20)

        self.select_test_run = ttk.Combobox(self.tab, values=self.new_valid_ids, width=15, font=font.Font(size=14))
        self.select_test_run.grid(row=2, column=0, pady=10, columnspan=2, sticky='nsew')
        # self.select_test_run.set(self.new_valid_ids[0])
        self.select_test_run.bind("<<ComboboxSelected>>", self.show_data)

        self.tab.columnconfigure(2, minsize=150)

        self.overlay_check = tk.Checkbutton(self.tab, text='Overlay', variable=self.overlay, selectcolor='black')
        self.overlay_check.grid(row=2, column=2, pady=10, columnspan=2, sticky='nsew')

        if auto:
            self.select_test_run.set(self.new_valid_ids[-1])
            self.show_data(auto)

    def zoom(self, direction):
        if direction == '+':
            if self.dpi < 150: 
                self.dpi += 10
                self.show_data(None, dpi=self.dpi)
        else:
            if self.dpi > 50:
                self.dpi -= 10
                self.show_data(None, dpi=self.dpi)

    def download_metrics(self, data):
        metrics = calculate_bout(time=data['elapsed_time_s'],
                                distance=data['distance_m'],
                                velocity=data['velocity'])
        
        output_data = export_metrics(time_from_start=data['elapsed_time_s'],
                                    distance=data['distance_m'],
                                    velocity=data['velocity'],
                                    heading=data['heading_deg'],
                                    trajectory_x=data['traj_x'],
                                    trajectory_y=data['traj_y'],
                                    metrics=metrics)

        filename = tk.filedialog.asksaveasfilename(title='Save Metrics', filetypes=[('CSV files', '*.csv')])
        if filename == '':
            return
        
        if '.csv' not in filename:
            filename += '.csv'

        output_data.to_csv(filename, index=False)

    def download_raw_data(self, data):
        filename = tk.filedialog.asksaveasfilename(title='Save Metrics', filetypes=[('CSV files', '*.csv')])
        if filename == '':
            return
        
        if '.csv' not in filename:
            filename += '.csv'

        # data['heading_deg'] = get_heading_deg(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])
        # data['velocity'] = get_velocity_m_s(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])

        # data['distance_m'] = get_distance_m(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])

        # data['traj_x'], data['traj_y'] = get_top_traj(data['distance_m'], data['velocity'], data['heading_deg'], data['elapsed_time_s'])

        max_length = len(data['elapsed_time_s'])

        # Pad shorter lists with None
        listed_data = {key: [value] if type(value) != list else value for key, value in data.items()}
        output_data = {key: (value + [None] * (max_length - len(value))) for key, value in listed_data.items()}

        with open(filename, 'w', newline='') as csvfile:
            fieldnames = output_data.keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for i in range(max_length):
                row = {key: output_data[key][i] for key in fieldnames}
                writer.writerow(row)

        # df = pd.DataFrame(output_data)
        # print(filename)
        # df.to_csv(filename, index=False)

    def delete_test(self, data):
        self.test_collection.delete_one({'_id': data['_id']})
        # delete all widgets in notebook
        for widget in self.tab.winfo_children():
            widget.destroy()
        self.initialize_tab(auto=False)

    # make available to other classes that want to use the subplot labels
    @staticmethod
    def set_subplot_labels(axs):

        axs[0].set_xlabel('Time (sec)').set_color('white')
        axs[0].set_ylabel('Displacement (m)').set_color('white')
        axs[0].set_title('Displacement vs Time').set_color('white')

        axs[1].set_xlabel('X Trajectory (m)').set_color('white')
        axs[1].set_ylabel('Y Trajectory (m)').set_color('white')
        axs[1].set_title('Trajectory').set_color('white')
        axs[1].set_aspect('equal', adjustable='datalim')

        axs[2].set_xlabel('Time (sec)').set_color('white')
        axs[2].set_ylabel('Heading (deg)').set_color('white')
        axs[2].set_title('Heading vs Time').set_color('white')

        axs[3].set_xlabel('Time (sec)').set_color('white')
        axs[3].set_ylabel('Velocity (m/s)').set_color('white')
        axs[3].set_title('Velocity vs Time').set_color('white')

    def populate_metadata(self, data):

        def on_entry_change(var, key):
            # self.data[key] = var.get()
            # print(f"{key} changed to {var.get()}")  # Replace with desired action
            save_metadata_button.config(text='Save Metadata', state='enabled')
            # pass

        ttk.Separator(self.tab, orient='horizontal').grid(row=10, column=0, columnspan=3, sticky='new')

        test_name_var = tk.StringVar()
        Label(self.tab, text=f'Test Name: ', font=font.Font(size=14)).grid(row=14, column=0, sticky='nsw')
        test_name_entry = ttk.Entry(self.tab, textvariable=test_name_var, width=15, font=font.Font(size=12))
        if 'test_name' in data:
            test_name_var.set(data['test_name'])
            # test_name_var.set(data['_id'])
            # test_name_entry.insert(0, data['_id'])
        elif '_id' in data:
            test_name_var.set(data['_id'])
            # test_name_entry.insert(0, data['test_name'])
        else:
            test_name_var.set('')
        test_name_entry.grid(row=14, column=1, columnspan=2, sticky='nsew')
        test_name_var.trace_add('write', lambda name, index, mode, var=test_name_var: on_entry_change(var, 'test_name'))

        clinician_id_var = tk.StringVar()
        Label(self.tab, text=f'Clinician ID: ', font=font.Font(size=14)).grid(row=18, column=0, sticky='nsw')
        clinician_id_entry = ttk.Entry(self.tab, textvariable=clinician_id_var, width=15, font=font.Font(size=12))
        if 'clinician_id' in data:
            # clinician_id_entry.insert(0, data['clinician_id'])
            clinician_id_var.set(data['clinician_id'])
        clinician_id_entry.grid(row=18, column=1, columnspan=2, sticky='nsew')
        clinician_id_var.trace_add('write', lambda name, index, mode, var=clinician_id_var: on_entry_change(var, 'clinician_id'))

        location_id_var = tk.StringVar()
        Label(self.tab, text=f'Location ID: ', font=font.Font(size=14)).grid(row=22, column=0, sticky='nsw')
        location_id_entry = ttk.Entry(self.tab, textvariable=location_id_var, width=15, font=font.Font(size=12))
        if 'location_id' in data:
            location_id_var.set(data['location_id'])
            # location_id_entry.insert(0, data['location_id'])
        location_id_entry.grid(row=22, column=1, columnspan=2, sticky='nsew')
        location_id_var.trace_add('write', lambda name, index, mode, var=location_id_var: on_entry_change(var, 'location_id'))

        ttk.Separator(self.tab, orient='horizontal').grid(row=26, column=0, columnspan=3, sticky='new')

        Label(self.tab, text=f'Additional Information: ', font=font.Font(size=14)).grid(row=30, column=0, columnspan=3, sticky='nsew')
        additional_notes_entry = tk.Text(self.tab, width=30, height=10, font=font.Font(size=12), bg='whitesmoke', fg='black', insertbackground='black')
        if 'additional_notes' in data:
            additional_notes_entry.insert(1.0, data['additional_notes'])
        additional_notes_entry.grid(row=34, column=0, columnspan=3, rowspan=30, sticky='nsew')
        additional_notes_entry.bind('<KeyRelease>', lambda event: on_entry_change(additional_notes_entry, 'additional_notes'))


        ttk.Separator(self.tab, orient='horizontal').grid(row=68, column=0, columnspan=3, sticky='new')

        def save_metadata():
            data['test_name'] = test_name_entry.get()
            data['clinician_id'] = clinician_id_entry.get()
            data['location_id'] = location_id_entry.get()
            data['additional_notes'] = additional_notes_entry.get(1.0, 'end')

            self.test_collection.update_one({'_id': data['_id']}, {'$set': data})

            save_metadata_button.config(text='Saved Metadata', state='disabled')

        style = ttk.Style()
        style.configure('TButton', foreground='whitesmoke')
        style.map('TButton', foreground=[('disabled', 'whitesmoke')])

        save_metadata_button = ttk.Button(self.tab, text='Save Metadata', command=save_metadata)
        save_metadata_button.grid(row=72, column=0, columnspan=3, sticky='nsew')

        test_name_entry.bind('<Return>', lambda event: save_metadata())
        clinician_id_entry.bind('<Return>', lambda event: save_metadata())
        location_id_entry.bind('<Return>', lambda event: save_metadata())
        additional_notes_entry.bind('<Return>', lambda event: save_metadata())

        # draw_grid_lines(self.tab)

        download_metrics_button = ttk.Button(self.tab, text='Download Metrics', command=lambda: self.download_metrics(data))
        download_metrics_button.grid(row=76, column=0, columnspan=3, sticky='nsew')

        download_raw_data_button = ttk.Button(self.tab, text='Download Raw Data', command=lambda: self.download_raw_data(data))
        download_raw_data_button.grid(row=80, column=0, columnspan=3, sticky='nsew')

        ttk.Separator(self.tab, orient='horizontal').grid(row=84, column=0, columnspan=3, sticky='new')

        set_record_background_button = ttk.Button(self.tab, text='Set Record Background', command=lambda: self.set_record_background(data))
        set_record_background_button.grid(row=88, column=0, columnspan=3, sticky='nsew')

        ttk.Separator(self.tab, orient='horizontal').grid(row=92, column=0, columnspan=3, sticky='new')


        delete_test_button = ttk.Button(self.tab, text='Delete Test Run (Ctrl + Click)')
        delete_test_button.grid(row=96, column=0, columnspan=3, sticky='nsew')

        delete_test_button.bind("<Control-Button-1>", lambda event: self.delete_test(data))


    def set_record_background(self, data):
        self.record_data_tab.set_background(data)
        
    
    def show_data(self, event, dpi=100, gridlines=False, data=None):
        # if hasattr(self, 'canvas_widgets'):
        #     for i, widget in enumerate(self.canvas_widgets):
        #         print(widget)
        #         widget.grid_forget()
        #         widget.destroy()
        #         self.canvas_widgets.pop(i)
        # time.sleep(0.5)
        self.dpi = dpi

        if data is None:
            test_name = self.valid_ids[self.new_valid_ids.index(self.select_test_run.get())]
            data = self.test_collection.find({'_id': test_name})[0]

            min_len = len(data['traj_x'])

            for key, value in data.items():
                if len(value) > min_len:
                    data[key] = value[:min_len]
                


        if not hasattr(self, 'fig'):
            screen_width = self.tab.winfo_screenwidth()
            screen_height = self.tab.winfo_screenheight()

            self.fig = Figure(figsize=((screen_width-400)/dpi, (screen_height-200)/dpi), dpi=dpi)
            self.fig.set_facecolor(str(ttk.Style().lookup('TFrame', 'background')))
            self.axs=[]
            self.axs.append(self.fig.add_subplot(221))
            self.axs.append(self.fig.add_subplot(222))
            self.axs.append(self.fig.add_subplot(223))
            self.axs.append(self.fig.add_subplot(224))
            for ax in self.axs:
                ax.tick_params(colors='white')
                # ax.set_facecolor(str(ttk.Style().lookup('TFrame', 'foreground')))
                ax.set_facecolor('whitesmoke')

            self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab)

        border = dpi/400
        self.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.075, top=0.95, wspace=border, hspace=border)
        
        self.canvas_widgets = []

        self.tab.columnconfigure(2, minsize=150)
        # draw_grid_lines(self.tab)

        operator_id_label = Label(self.tab, text=f'Operator ID: {data["user_id"]}', font=font.Font(size=18))
        operator_id_label.grid(row=0, column=3, columnspan=100, sticky='sew')
        self.canvas_widgets.append(operator_id_label)

        if type(event) != type(True):
            self.zoom_in_button = ttk.Button(self.tab, text='+', command=lambda: self.zoom('+'))
            self.zoom_in_button.grid(row=0, column=95, pady=10, columnspan=3, sticky='nsew')
            self.zoom_out_button = ttk.Button(self.tab, text='-', command=lambda: self.zoom('-'))
            self.zoom_out_button.grid(row=0, column=92, pady=10, columnspan=3, sticky='nsew')
        elif type(event) == type(True) and event == True:
            self.zoom_in_button = ttk.Button(self.tab, text='+', command=lambda: self.zoom('+'))
            self.zoom_in_button.grid(row=0, column=95, pady=10, columnspan=3, sticky='nsew')
            self.zoom_out_button = ttk.Button(self.tab, text='-', command=lambda: self.zoom('-'))
            self.zoom_out_button.grid(row=0, column=92, pady=10, columnspan=3, sticky='nsew')
        else:
            self.zoom_in_button.lift()
            self.zoom_out_button.lift()

        self.canvas_widgets.append(self.zoom_in_button)
        self.canvas_widgets.append(self.zoom_out_button)

        self.trajectory_gridlines_check = tk.BooleanVar(self.tab, value=gridlines)
        show_trajectory_gridlines = tk.Checkbutton(self.tab, text='Show Gridlines', selectcolor='black',variable=self.trajectory_gridlines_check, font=font.Font(size=12), command=lambda: self.show_data(None, dpi=dpi, gridlines=self.trajectory_gridlines_check.get()))
        show_trajectory_gridlines.grid(row=1, column=89, columnspan=10)
        self.canvas_widgets.append(show_trajectory_gridlines)

        if 'heading_deg' not in data:
            data['heading_deg'] = get_heading_deg(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])
        if 'velocity' not in data:
            data['velocity'] = get_velocity_m_s(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])

        overlay = self.overlay.get()
        if not overlay:
            for ax in self.axs:
                ax.clear()
            self.prev_data = []
        self.prev_data.append(data)

        self.axs[0].plot(data['elapsed_time_s'], data['distance_m'])
        self.axs[1].plot(data['traj_x'], data['traj_y'])
        self.axs[1].set_aspect('equal', adjustable='datalim')

        if gridlines:
            self.axs[1].grid(True)
            if max(data['traj_x']) - min(data['traj_x']) > 8:
                tick_spacing = math.ceil((max(data['traj_x']) - min(data['traj_x']))/8)
            else:
                tick_spacing = math.ceil(max(data['traj_x']) - min(data['traj_x']))/8
            self.axs[1].xaxis.set_major_locator(MultipleLocator(tick_spacing))  # Set x-axis major tick spacing to 2 for the second subplot
            self.axs[1].yaxis.set_major_locator(MultipleLocator(tick_spacing))  # Set y-axis major tick spacing to 2 for the second subplot

        self.axs[2].plot(data['elapsed_time_s'], data['heading_deg'])
        self.axs[3].plot(data['elapsed_time_s'], data['velocity'])

        self.set_subplot_labels(self.axs)

        self.canvas.draw()
        self.canvas.flush_events()  
        # self.axs[1].set_aspect('equal')

        self.canvas.get_tk_widget().grid(row=1, column=3, columnspan=100, rowspan=100, padx=0, pady=0, sticky='nsew')

        self.populate_metadata(data)

        def scale(vals):
            self.last_scale_update = time.time()
            overlay = self.overlay.get()
            # if not overlay:
            for ax in self.axs:
                ax.clear()

            for data_list in self.prev_data:
                left_elem = bisect.bisect_left(data['elapsed_time_s'], vals[0])
                right_elem = bisect.bisect_right(data['elapsed_time_s'], vals[1])

                self.axs[0].plot(data_list['elapsed_time_s'][left_elem:right_elem], data_list['distance_m'][left_elem:right_elem])
                self.axs[1].plot(data_list['traj_x'][left_elem:right_elem], data_list['traj_y'][left_elem:right_elem])
                self.axs[2].plot(data_list['elapsed_time_s'][left_elem:right_elem], data_list['heading_deg'][left_elem:right_elem])
                self.axs[3].plot(data_list['elapsed_time_s'][left_elem:right_elem], data_list['velocity'][left_elem:right_elem])

                if self.trajectory_gridlines_check.get():
                    self.axs[1].grid(True)
                    if max(data_list['traj_x']) - min(data_list['traj_x']) > 8:
                        tick_spacing = math.ceil((max(data_list['traj_x']) - min(data_list['traj_x']))/8)
                    else:
                        tick_spacing = math.ceil(max(data_list['traj_x']) - min(data_list['traj_x']))/8
                    self.axs[1].xaxis.set_major_locator(MultipleLocator(tick_spacing))
                    self.axs[1].yaxis.set_major_locator(MultipleLocator(tick_spacing))

            self.set_subplot_labels(self.axs)

            for ax in self.axs:
                ax.relim()
                ax.autoscale()
            self.canvas.draw()
            self.canvas.flush_events()    

        max_time = 0
        min_time = 1000000
        for data_list in self.prev_data:
            if data['elapsed_time_s'][-1] > max_time:
                max_time = data['elapsed_time_s'][-1]
            if data['elapsed_time_s'][0] < min_time:
                min_time = data['elapsed_time_s'][0]

        slider = Slider(
            self.tab,
            width=1400,
            height=40,
            min_val=min_time,
            max_val= max_time,
            init_lis=[min_time, max_time],
            show_value=True,
            removable=False,
            addable=False,
        )
        slider.setValueChangeCallback(scale)
        slider.grid(row=102, rowspan=3, column=3, columnspan=100, sticky='nsew')
        Label(self.tab, text='Time Range (sec)', font=font.Font(size=14)).grid(row=101, column=3, columnspan=100, sticky='nsew')
        self.canvas_widgets.append(slider)

        # draw_grid_lines(self.tab)

    def load_csv(self):

        filename = tk.filedialog.askopenfilename(title='Select a CSV file', filetypes=[('CSV files', '*.csv')])
        if filename == '':
            return

        # data = pd.read_csv(filename)
        # data['heading_deg'] = get_heading_deg(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])
        # data['velocity'] = get_velocity_m_s(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])

        # data['elapsed_time_s'] = data['elapsed_time_s']
        # data['distance_m'] = get_displacement_m(data['gyro_left'], data['gyro_right'], data['elapsed_time_s'])
        # (data['traj_x'], data['traj_y']) = get_top_traj(data['distance_m'], data['velocity'], data['heading_deg'], data['elapsed_time_s'])
        def convert_value(value):
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return value
        
        data = {}
        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            for header in headers:
                data[header] = []

            for row in reader:
                for header, value in zip(headers, row):
                    data[header].append(convert_value(value))

        for key, value in data.items():
            if value[1] == '':
                data[key] = value[0]
       

        # self.prev_data.append(data)

        self.show_data(True, data=data)     


    def initialize_tab(self, auto=False):

        ttk.Label(self.tab, text="Select User ID: ", justify='center', font=font.Font(size=14))\
            .grid(row=0, column=0, pady=10, columnspan=2)

        select_user_id = ttk.Entry(self.tab, width=10, font=font.Font(size=12))
        select_user_id.grid(row=1, column=0, pady=10, sticky='nsew')

        ttk.Button(self.tab, text='Enter', command=lambda: self.find_test_runs(select_user_id.get())).grid(row=1, column=1, pady=10, sticky='nsew')

        select_user_id.bind('<Return>', lambda event: self.find_test_runs(select_user_id.get()))

        ttk.Button(self.tab, text='Load CSV', command=lambda: self.load_csv()).grid(row=1, column=2, pady=10, padx=10, sticky='nse')

        username = cred.username
        password = cred.password

        # uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
        # self.client = MongoClient(uri, server_api=ServerApi('1'))
        # smarthub_db = self.client.Smarthub
        # self.test_collection = smarthub_db.test_collection

        if auto:
            self.find_test_runs('654321', auto=True)
                            