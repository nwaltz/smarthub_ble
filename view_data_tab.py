import tkinter as tk
from tkinter import font, Label
from tkinter import ttk
# import cred
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
    """
    :param tab: notebook object
    :returns None

    used for inputting ttk separators to show grid areas
    can break if used on too large a grid
    """
    rows, cols = tab.grid_size()
    # for i in range(rows):
    #     ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    
    # for i in range(rows):
    #     ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    for i in range(10):
        ttk.Separator(tab, orient='vertical').grid(row=0, column=i, rowspan=rows, sticky='nse')

class ViewData:

    def __init__(self, tab, record_data_tab, database, filepath, screen_size):
        # notebook object
        self.tab = tab
        # instance of record_data_tab, used to set background
        self.record_data_tab = record_data_tab
        # mongodb client
        self.test_collection = database.Smarthub.test_collection
        # filepath to save data
        self.filepath = filepath

        # screen params
        self.screen_width, self.screen_height = screen_size

        # graph info
        self.last_scale_update = time.time()
        self.overlay = tk.BooleanVar(value=False)

        self.prev_data = []

        # self.initialize_tab(auto=True)
        self.initialize_tab(auto=False)
        
        # make a config file if it doesn't exist
        # read in config file if it does
        if not os.path.exists('config.json'):
            self.config = {}
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
        self.update_config('gridlines', self.trajectory_gridlines_check.get())
        self.client.close()
        sys.exit()


    def find_test_runs(self, user_id, auto=False):
        """
        :param user_id: user id to search for
        :param auto: if True, automatically selects the most recent test run
        :returns None

        used to find all test runs for a given user id
        creates drop down menu to select test run
        can set auto param to be true to bypass selection and open most recent run
        """

        # finds all runs with user_id, returns list of ids and test names
        self.all_ids = self.test_collection.find({'user_id': user_id}, {'_id': 1, 'test_name': 1})

        # _id should be datetime string

        # this contains all _id params
        self.valid_ids = []

        # valid ids is test_name if available, _id if not
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

        # create drop down menu to select test run
        self.select_test_run = ttk.Combobox(self.tab, values=self.new_valid_ids, width=15, font=font.Font(size=14))
        self.select_test_run.grid(row=2, column=0, pady=10, columnspan=2, sticky='nsew')
        # self.select_test_run.set(self.new_valid_ids[0])
        self.select_test_run.bind("<<ComboboxSelected>>", self.show_data)

        self.tab.columnconfigure(2, minsize=150)

        # create button to enable data overlay, initialized to false in __init__
        self.overlay_check = tk.Checkbutton(self.tab, text='Overlay', variable=self.overlay, selectcolor='black')
        self.overlay_check.grid(row=2, column=2, pady=10, columnspan=2, sticky='nsew')

        # populates with most recent test run if auto is true
        if auto:
            self.select_test_run.set(self.new_valid_ids[-1])
            self.show_data(auto)

    def zoom(self, direction):
        """
        :param direction: '+' or '-'
        :returns None

        used to zoom in or out of the graph, dpi doesn't always work this can be removed probably
        """
        if direction == '+':
            if self.dpi < 150: 
                self.dpi += 10
                self.show_data(None, dpi=self.dpi)
        else:
            if self.dpi > 50:
                self.dpi -= 10
                self.show_data(None, dpi=self.dpi)

    def download_metrics(self, data):
        """
        :param data: data to export
        :returns None

        used to export metrics data
        calculates metrics and exports all other data to csv

        """
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

        # ask where to save file
        filename = tk.filedialog.asksaveasfilename(title='Save Metrics', filetypes=[('CSV files', '*.csv')])
        # if user exits without selecting a filename, return
        if filename == '':
            return
        
        # if they don't put the .csv, add it ourselves
        if '.csv' not in filename:
            filename += '.csv'

        # output data to csv, don't include index
        output_data.to_csv(filename, index=False)


    def download_raw_data(self, data):
        """
        :param data: data to export
        :returns None

        same idea as download_metrics, but for only the raw data
        """
        filename = tk.filedialog.asksaveasfilename(title='Save Raw Data', filetypes=[('CSV files', '*.csv')])
        if filename == '':
            return
        
        if '.csv' not in filename:
            filename += '.csv'

        max_length = len(data['elapsed_time_s'])

        # Pad shorter lists with None
        listed_data = {key: [value] if type(value) != list else value for key, value in data.items()}
        output_data = {key: (value + [None] * (max_length - len(value))) for key, value in listed_data.items()}

        # have to do it this way because all our data has variable length
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = output_data.keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for i in range(max_length):
                row = {key: output_data[key][i] for key in fieldnames}
                writer.writerow(row)


    def delete_test(self, data):
        """
        :param data: data to delete
        :returns None

        used to delete a test run
        first deletes it from db, then removes all widgets, then removes all attributes from class except for 
            the private attributes, the notebook and db, and any functions

        """

        # deletes run from db
        self.test_collection.delete_one({'_id': data['_id']})

        # delete all widgets in notebook
        for widget in self.tab.winfo_children():
            widget.destroy()

        # remove all attributes from class except for the ones initialized in setup
        for attr in dir(self):
            if not attr.startswith('__') and attr not in ['tab', 'record_data_tab', 'test_collection'] and not callable(getattr(self, attr)):
                delattr(self, attr)

        self.last_scale_update = time.time()
        self.overlay = tk.BooleanVar(value=False)

        self.prev_data = []

        self.initialize_tab(auto=False)

    # make available to other classes that want to use the subplot labels
    @staticmethod
    def set_subplot_labels(axs):
        """
        :param axs: list of axes
        :returns None

        used to set subplot labels, make it coordinated across all notebook tabs

        """

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
        """
        :param data: data to populate
        :returns None

        makes metadata entry fields, save button, and download buttons
        syncs to database on entry change
        
        """

        def on_entry_change(var, key):
            """
            when entry is changed, make the button say 'Save Metadata' and enable it
            """
            save_metadata_button.config(text='Save Metadata', state='enabled')


        ttk.Separator(self.tab, orient='horizontal').grid(row=10, column=0, columnspan=3, sticky='new')

        # test name entry box setup
        test_name_var = tk.StringVar()
        Label(self.tab, text=f'Test Name: ', font=font.Font(size=14)).grid(row=14, column=0, sticky='nsw')
        test_name_entry = ttk.Entry(self.tab, textvariable=test_name_var, width=15, font=font.Font(size=12))
        if 'test_name' in data:
            test_name_var.set(data['test_name'])
        elif '_id' in data:
            test_name_var.set(data['_id'])
        else:
            # this should never be true
            test_name_var.set('')
        test_name_entry.grid(row=14, column=1, columnspan=2, sticky='nsew')
        # this line checks if there's a state change in the box and calls on_entry_change if so
        test_name_var.trace_add('write', lambda name, index, mode, var=test_name_var: on_entry_change(var, 'test_name'))

        # clinician id entry box setup
        clinician_id_var = tk.StringVar()
        Label(self.tab, text=f'Clinician ID: ', font=font.Font(size=14)).grid(row=18, column=0, sticky='nsw')
        clinician_id_entry = ttk.Entry(self.tab, textvariable=clinician_id_var, width=15, font=font.Font(size=12))
        if 'clinician_id' in data:
            clinician_id_var.set(data['clinician_id'])
        clinician_id_entry.grid(row=18, column=1, columnspan=2, sticky='nsew')
        # this line checks if there's a state change in the box and calls on_entry_change if so
        clinician_id_var.trace_add('write', lambda name, index, mode, var=clinician_id_var: on_entry_change(var, 'clinician_id'))

        # location id entry box setup
        location_id_var = tk.StringVar()
        Label(self.tab, text=f'Location ID: ', font=font.Font(size=14)).grid(row=22, column=0, sticky='nsw')
        location_id_entry = ttk.Entry(self.tab, textvariable=location_id_var, width=15, font=font.Font(size=12))
        if 'location_id' in data:
            location_id_var.set(data['location_id'])
            # location_id_entry.insert(0, data['location_id'])
        location_id_entry.grid(row=22, column=1, columnspan=2, sticky='nsew')
        # this line checks if there's a state change in the box and calls on_entry_change if so
        location_id_var.trace_add('write', lambda name, index, mode, var=location_id_var: on_entry_change(var, 'location_id'))

        ttk.Separator(self.tab, orient='horizontal').grid(row=26, column=0, columnspan=3, sticky='new')

        # additional notes entry box setup
        Label(self.tab, text=f'Additional Information: ', font=font.Font(size=14)).grid(row=30, column=0, columnspan=3, sticky='nsew')
        additional_notes_entry = tk.Text(self.tab, width=30, height=10, font=font.Font(size=12), bg='whitesmoke', fg='black', insertbackground='black')
        if 'additional_notes' in data:
            additional_notes_entry.insert(1.0, data['additional_notes'])
        additional_notes_entry.grid(row=34, column=0, columnspan=3, rowspan=30, sticky='nsew')
        # this line checks if a button was pushed in the box
        additional_notes_entry.bind('<KeyRelease>', lambda event: on_entry_change(additional_notes_entry, 'additional_notes'))


        ttk.Separator(self.tab, orient='horizontal').grid(row=68, column=0, columnspan=3, sticky='new')

        def save_metadata():
            """
            :param: None
            :returns None

            used to save metadata to database
            """

            metadata_entry_updater = {}

            # get data from entry boxes
            metadata_entry_updater['test_name'] = test_name_entry.get()
            metadata_entry_updater['clinician_id'] = clinician_id_entry.get()
            metadata_entry_updater['location_id'] = location_id_entry.get()
            metadata_entry_updater['additional_notes'] = additional_notes_entry.get(1.0, 'end')

            # insert data into database, only update fields that are contained in data
            # data is just a local variable, so it 
            self.test_collection.update_one({'_id': data['_id']}, {'$set': metadata_entry_updater})

            # disable button until we have new data, change text to 'Saved Metadata'
            save_metadata_button.config(text='Saved Metadata', state='disabled')

        # make save button
        style = ttk.Style()
        style.configure('TButton', foreground='whitesmoke')
        style.map('TButton', foreground=[('disabled', 'whitesmoke')])

        save_metadata_button = ttk.Button(self.tab, text='Save Metadata', command=save_metadata)
        save_metadata_button.grid(row=72, column=0, columnspan=3, sticky='nsew')

        # make so pressing enter in any box calls save_metadata
        test_name_entry.bind('<Return>', lambda event: save_metadata())
        clinician_id_entry.bind('<Return>', lambda event: save_metadata())
        location_id_entry.bind('<Return>', lambda event: save_metadata())
        additional_notes_entry.bind('<Return>', lambda event: save_metadata())

        # metrics and raw data download buttons
        download_metrics_button = ttk.Button(self.tab, text='Download Metrics', command=lambda: self.download_metrics(data))
        download_metrics_button.grid(row=76, column=0, columnspan=3, sticky='nsew')

        download_raw_data_button = ttk.Button(self.tab, text='Download Raw Data', command=lambda: self.download_raw_data(data))
        download_raw_data_button.grid(row=80, column=0, columnspan=3, sticky='nsew')

        ttk.Separator(self.tab, orient='horizontal').grid(row=84, column=0, columnspan=3, sticky='new')

        # button to call set background function from record_data_tab
        set_record_background_button = ttk.Button(self.tab, text='Set Record Background', command=lambda: self.set_record_background(data))
        set_record_background_button.grid(row=88, column=0, columnspan=3, sticky='nsew')

        ttk.Separator(self.tab, orient='horizontal').grid(row=92, column=0, columnspan=3, sticky='new')

        # delete test run button, don't do anything on normal click
        delete_test_button = ttk.Button(self.tab, text='Delete Test Run (Ctrl + Click)')
        delete_test_button.grid(row=96, column=0, columnspan=3, sticky='nsew')

        # require control plus click to actually call delete function
        delete_test_button.bind("<Control-Button-1>", lambda event: self.delete_test(data))


    def set_record_background(self, data):
        """
        :param data: data to set background
        :returns None

        used to set background of record_data_tab to the current test run
        interfaces with class instance RecordData
        """
        self.record_data_tab.set_background(data)
        
    
    def show_data(self, event, dpi=100, gridlines=False, data=None):
        """
        :param event: event that triggered the function, unused
        :param dpi: dots per inch for the graph
        :param gridlines: whether to show gridlines on the graph
        :param data: data to plot, if None will get data from database
        :returns None

        used to plot data on the graph
        can manually send data or get it from the database with the selected test run

        populates plots and slider, makes figures if they don't exist
        """

        # update class instance of dpi
        self.dpi = dpi

        # if data wasn't supplied, get it ourself from the value in the drop down menu
        if data is None:
            test_name = self.valid_ids[self.new_valid_ids.index(self.select_test_run.get())]

            # get first entry from database that matches _id
            data = self.test_collection.find({'_id': test_name})[0]

            # sometimes the lengths mismatch, but traj should be shortest
            min_len = len(data['traj_x'])

            # truncate rest of value if longer than traj
            for key, value in data.items():
                if len(value) > min_len:
                    data[key] = value[:min_len]
                

        # if we don't have our graphs made yet
        if not hasattr(self, 'fig'):

            # get screen size
            screen_width = self.tab.winfo_screenwidth()
            screen_height = self.tab.winfo_screenheight()

            # make figure and axes
            self.fig = Figure(figsize=((screen_width-400)/dpi, (screen_height-200)/dpi), dpi=dpi)
            self.fig.set_facecolor(str(ttk.Style().lookup('TFrame', 'background')))
            self.axs=[]
            self.axs.append(self.fig.add_subplot(221))
            self.axs.append(self.fig.add_subplot(222))
            self.axs.append(self.fig.add_subplot(223))
            self.axs.append(self.fig.add_subplot(224))
            for ax in self.axs:
                ax.tick_params(colors='white')
                ax.set_facecolor('whitesmoke')

            # make canvas with matplotlib figure
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab)

        # this is supposed to scale the graphs so theres less overlap
        border = dpi/400
        self.fig.subplots_adjust(left=0.05, right=0.95, bottom=0.075, top=0.95, wspace=border, hspace=border)
        
        # makes list of widgets to remove later
        self.canvas_widgets = []

        self.tab.columnconfigure(2, minsize=150)

        # operator id on top of screen
        operator_id_label = Label(self.tab, text=f'Operator ID: {data["user_id"]}', font=font.Font(size=18))
        operator_id_label.grid(row=0, column=3, columnspan=100, sticky='sew') # centers on grid
        self.canvas_widgets.append(operator_id_label)

        # checks if event is a bool, only case we shouldn't make new buttons is if it is False
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

        # add buttons to canvas widgets
        self.canvas_widgets.append(self.zoom_in_button)
        self.canvas_widgets.append(self.zoom_out_button)

        # checkbox to show gridlines
        self.trajectory_gridlines_check = tk.BooleanVar(self.tab, value=gridlines)
        show_trajectory_gridlines = tk.Checkbutton(self.tab, text='Show Gridlines', selectcolor='black',variable=self.trajectory_gridlines_check, font=font.Font(size=12), command=lambda: self.show_data(None, dpi=dpi, gridlines=self.trajectory_gridlines_check.get()))
        show_trajectory_gridlines.grid(row=1, column=89, columnspan=10)
        self.canvas_widgets.append(show_trajectory_gridlines)

        # if for whatever reason we don't have all our values made yet, create them
        # this should only be the case on super outdated data
        if 'heading_deg' not in data:
            data['heading_deg'] = get_heading_deg(data['elapsed_time_s'], data['gyro_left_smoothed'], data['gyro_right_smoothed'])
        if 'velocity' not in data:
            data['velocity'] = get_velocity_m_s(data['elapsed_time_s'], data['gyro_left_smoothed'], data['gyro_right_smoothed'])

        # check the overlay button, if it's not checked we want to clear the graphs before putting new data on them
        overlay = self.overlay.get()
        if not overlay:
            for ax in self.axs:
                ax.clear()

            self.prev_data = []
        # keep track of all the data we've plotted so far
        self.prev_data.append(data)

        # plot the data, force trajectory to be equally scaled
        self.axs[0].plot(data['elapsed_time_s'], data['distance_m'])
        self.axs[1].plot(data['traj_x'], data['traj_y'])
        self.axs[1].set_aspect('equal', adjustable='datalim')

        # give the option to show gridlines on trajectory plot
        if gridlines:
            self.axs[1].grid(True)
            # supposed to try to make gridlines spaced at 8 intervals, only works for actual wheelchair data
            if max(data['traj_x']) - min(data['traj_x']) > 8:
                tick_spacing = math.ceil((max(data['traj_x']) - min(data['traj_x']))/8)
            else:
                tick_spacing = math.ceil(max(data['traj_x']) - min(data['traj_x']))/8
            self.axs[1].xaxis.set_major_locator(MultipleLocator(tick_spacing))  # Set x-axis major tick spacing to 2 for the second subplot
            self.axs[1].yaxis.set_major_locator(MultipleLocator(tick_spacing))  # Set y-axis major tick spacing to 2 for the second subplot

        self.axs[2].plot(data['elapsed_time_s'], data['heading_deg'])
        self.axs[3].plot(data['elapsed_time_s'], data['velocity'])

        # use function for label setting
        self.set_subplot_labels(self.axs)

        # draw all the plots, clean events
        self.canvas.draw()
        self.canvas.flush_events()  

        # put canvas on grid
        self.canvas.get_tk_widget().grid(row=1, column=3, columnspan=100, rowspan=100, padx=0, pady=0, sticky='nsew')

        # put metadata in widgets
        self.populate_metadata(data)

        
        def scale(vals):
            """
            :param vals: values to scale to
            :returns None

            this scales the graph to the time values from slider

            
            """
            # can make it so this doesn't update too fast
            self.last_scale_update = time.time()
            overlay = self.overlay.get()
            for ax in self.axs:
                ax.clear()

            # iterates through all the data we've stored so far
            for data_list in self.prev_data:

                # find the index of the left and right values in the data
                left_elem = bisect.bisect_left(data['elapsed_time_s'], vals[0])
                right_elem = bisect.bisect_right(data['elapsed_time_s'], vals[1])

                # only plot the data between these indexes
                self.axs[0].plot(data_list['elapsed_time_s'][left_elem:right_elem], data_list['distance_m'][left_elem:right_elem])
                self.axs[1].plot(data_list['traj_x'][left_elem:right_elem], data_list['traj_y'][left_elem:right_elem])
                self.axs[2].plot(data_list['elapsed_time_s'][left_elem:right_elem], data_list['heading_deg'][left_elem:right_elem])
                self.axs[3].plot(data_list['elapsed_time_s'][left_elem:right_elem], data_list['velocity'][left_elem:right_elem])

                # do the same gridline stuff, could prob make this a function
                if self.trajectory_gridlines_check.get():
                    self.axs[1].grid(True)
                    if max(data_list['traj_x']) - min(data_list['traj_x']) > 8:
                        tick_spacing = math.ceil((max(data_list['traj_x']) - min(data_list['traj_x']))/8)
                    else:
                        tick_spacing = math.ceil(max(data_list['traj_x']) - min(data_list['traj_x']))/8
                    self.axs[1].xaxis.set_major_locator(MultipleLocator(tick_spacing))
                    self.axs[1].yaxis.set_major_locator(MultipleLocator(tick_spacing))

            # once we're done plotting, set the labels and draw the canvas
            self.set_subplot_labels(self.axs)

            for ax in self.axs:
                ax.relim()
                ax.autoscale()
            self.canvas.draw()
            self.canvas.flush_events()    

        # set up for slider
        max_time = 0
        min_time = 1000000

        # make end of slider the last value of the last data list
        # make start of slider first value if after 
        for data_list in self.prev_data:
            if data['elapsed_time_s'][-1] > max_time:
                max_time = data['elapsed_time_s'][-1]
            if data['elapsed_time_s'][0] < min_time:
                min_time = data['elapsed_time_s'][0]

        # make slider with info from file
        slider = Slider(
            self.tab,
            width=self.screen_width-350,
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
        """
        :param: None
        :returns None

        used to load a csv file into the window and show plots

        """

        # prompt user to import plot
        filename = tk.filedialog.askopenfilename(title='Select a CSV file', filetypes=[('CSV files', '*.csv')])
        if filename == '':
            return

        # convert values to int or float if possible
        def convert_value(value):
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return value
        
        # read in csv file
        data = {}
        with open(filename, 'r') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)

            # initialize data dictionary
            for header in headers:
                data[header] = []

            # iterate through rows and attempt to convert vals to proper data type
            for row in reader:
                for header, value in zip(headers, row):
                    data[header].append(convert_value(value))

        # if data doesn't have anything after first element, just turn the list into the first element
        for key, value in data.items():
            if value[1] == '':
                data[key] = value[0]
       

        # self.prev_data.append(data)

        self.show_data(True, data=data)     


    def initialize_tab(self, auto=False):
        """
        :param auto: if True, automatically selects user id 654321 for test run, used for debugging
        :returns None

        sets up user id entry and load csv button, should be only thing on screen when loading in
        """

        ttk.Label(self.tab, text="Select User ID: ", justify='center', font=font.Font(size=14))\
            .grid(row=0, column=0, pady=10, columnspan=2)

        select_user_id = ttk.Entry(self.tab, width=10, font=font.Font(size=12))
        select_user_id.grid(row=1, column=0, pady=10, sticky='nsew')

        # calls find_test_runs with value currently in user id box
        ttk.Button(self.tab, text='Enter', command=lambda: self.find_test_runs(select_user_id.get())).grid(row=1, column=1, pady=10, sticky='nsew')

        # let user press enter instead of click enter
        select_user_id.bind('<Return>', lambda event: self.find_test_runs(select_user_id.get()))

        ttk.Button(self.tab, text='Load CSV', command=lambda: self.load_csv()).grid(row=1, column=2, pady=10, padx=10, sticky='nse')

        # for debugging, show runs in 654321
        if auto:
            self.find_test_runs('654321', auto=True)
                            