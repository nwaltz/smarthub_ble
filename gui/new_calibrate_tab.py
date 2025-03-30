from gui.view_data_tab import ViewData
from gui.record_data_tab import RecordData

import copy

from scipy.optimize import minimize, fsolve
from scipy.fftpack import fftfreq, irfft, rfft

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

import asyncio
import tkinter as tk
from tkinter import font, Label
from tkinter import ttk

import threading
import pandas as pd
import struct
import numpy as np
import time
import json
from bleak import BleakScanner, BleakClient, BleakError
from PIL import Image, ImageTk

from base_ble.params import DATE_DIR, DATE_NOW, left_gain, left_offset, right_gain, right_offset

from base_ble.calibrate import minimize_function
from base_ble.minimize_traj import minimize_turnaround

from base_ble.calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)

def draw_grid_lines(tab):
    rows, cols = tab.grid_size()
    # for i in range(rows):
    #     ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    
    # for i in range(rows):
    #     ttk.Separator(tab, orient='horizontal').grid(row=i, column=0, columnspan=cols, sticky='sew')
    for i in range(100):
        ttk.Separator(tab, orient='vertical').grid(row=0, column=i, rowspan=rows, sticky='nse')

class NewCalibrate:

    def __init__(self, tab, database, filepath, screen_size, config):
        self.tab = tab
        self.test_config = database.Smarthub.test_config
        self.filepath = filepath
        self.screen_width, self.screen_height = screen_size
        self.config = config

        self.data = {
            'gyro_right': [],
            'gyro_left': [],
            'time_from_start': [],
            'gyro_right_smoothed': [],
            'gyro_left_smoothed': [],
        }

        self.recording_started = False
        self.recording_stopped = True

        self.calibration_sequence = []
        self.current_calibration_step = 0

        self.create_widgets()

    async def connect_to_device(self, left_address, right_address):
        try:
            async with BleakClient(left_address) as left_client:
                self.left_smarthub_connection['text'] = 'Connected'
                self.left_smarthub_connection['foreground'] = '#217346'
                async with BleakClient(right_address) as right_client:
                    self.right_smarthub_connection['text'] = 'Connected'
                    self.right_smarthub_connection['foreground'] = '#217346'

                    ch = "00002a56-0000-1000-8000-00805f9b34fb"

                    self.start_recording_button['state'] = 'normal'

                    # once we successfully start our notifications we don't want to start them again
                    self.notifications_started = False

                    # reset data every time we've processed new values
                    self.new_data_left = None
                    self.new_data_right = None

                    def update_data(_, data: bytearray, side: str) -> None:
                        """
                        :param _: not used, given by callback
                                    data: 18 len bytearray of raw data
                                    side: 'left' or 'right' to know which smarthub the data is from
                        :returns None

                        updates the data from the smarthubs
                        can't send data to parse_data until we have both left and right data
                        wait until we've gotten a message from both, if the new data is from a side we already have data from, update the last_{}_message
                        after we send data to parse_data, clear it so we can get new data

                        see thesis for details i have a flowchart there
                        """

                        # this just runs on first function call, kinda like static keyword in C
                        if not hasattr(self, 'last_left_message'):
                            self.last_left_message = None
                            self.last_right_message = None

                        if side == 'left':
                            # if it's actually new data and not just a repeat
                            if self.last_left_message != data:
                                self.last_left_message = data
                                self.new_data_left = data
                                # if there's data on the other side too, send it to parse_data and clear buffers
                                if self.new_data_right is not None:
                                    self.parse_data(self.new_data_left, self.new_data_right)
                                    self.new_data_left = None
                                    self.new_data_right = None
                        elif side == 'right':
                            # if it's actually new data and not just a repeat
                            if self.last_right_message != data:
                                self.last_right_message = data
                                self.new_data_right = data
                                # if there's data on the other side too, send it to parse_data and clear buffers
                                if self.new_data_left is not None:
                                    self.parse_data(self.new_data_left, self.new_data_right)
                                    self.new_data_left = None
                                    self.new_data_right = None

                    async def start_notifications(self, left_client: BleakClient, right_client: BleakClient, ch: str) -> None:
                        """
                        :param left_client: BleakClient object for left smarthub
                                 right_client: BleakClient object for right smarthub
                                 ch: uuid for the characteristic we're reading from
                        :returns None

                        starts notifications for the left and right smarthubs
                        """
                        self.notifications_started = True
                        await left_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'left'))
                        await right_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'right'))

                    # just so we know to only intialize the loop once
                    initial_loop = True

                    # this continually cycles, even if we're not recording
                    while True:

                        # if we haven't started recording, just sit here and wait
                        if self.recording_started == False:
                            self.recording_stopped = False
                            # await asyncio.sleep(0)
                            initial_loop = True
                            continue

                        # if we've stopped recording, stop notifications
                        # this should only run once, since next loop iteration will get stuck in the first if statement
                        if self.recording_stopped == True:
                            self.recording_started = False
                            await left_client.stop_notify(ch)
                            await right_client.stop_notify(ch)

                            self.notifications_started = False

                            # for this we only want to record once, then we'll disconnect
                            break
                            
                        # if we've started recording, start updating our graphs and make sure our data dictionary is empty
                        if initial_loop:
                            self.start_time = time.time()
                            initial_loop = False

                        # if we've started recording, start notifications
                        if not self.notifications_started:
                            await start_notifications(self, left_client, right_client, ch)

                        # all the other stuff is happening asynchronously, so we can just wait here and let the other threads do their thing
                        await asyncio.sleep(1)

                        # this doesn't always work since the is_connected flag doesn't always update properly
                        if time.time() - self.start_time > 2:
                            if not left_client.is_connected:
                                self.left_smarthub_connection['text'] = 'Disconnected'
                                self.left_smarthub_connection['foreground'] = '#a92222'
                                print('left not connected')
                                await right_client.disconnect()
                                break
                            if not right_client.is_connected:
                                self.right_smarthub_connection['text'] = 'Disconnected'
                                self.right_smarthub_connection['foreground'] = '#a92222'
                                print('right not connected')
                                await left_client.disconnect()
                                break

        except BleakError as e:
            print(f"Failed to connect: {e}")
            popup = tk.Toplevel()
            ttk.Label(popup, text="Device went out of range, please retry connection", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
            return
        except OSError as e:
            popup = tk.Toplevel()
            ttk.Label(popup, text="Device went out of range, please retry connection", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
            print(f"OS error (devices are most likely disconnected): {e}")

            return
        except TimeoutError as e:
            print(f"Timeout error: {e}")
            if self.left_smarthub_connection['text'] != 'Connected' and self.right_smarthub_connection['text'] != 'Connected':
                self.missing_smarthubs(left=True, right=True)
            if self.left_smarthub_connection['text'] != 'Connected':
                self.missing_smarthubs(left=True)
            if self.right_smarthub_connection['text'] != 'Connected':
                self.missing_smarthubs(right=True)

        self.right_smarthub_connection['text'] = 'Disconnected'
        self.right_smarthub_connection['foreground'] = '#a92222'
        self.left_smarthub_connection['text'] = 'Disconnected'
        self.left_smarthub_connection['foreground'] = '#a92222'


    def parse_data(self, left_message, right_message):
        time_curr = time.time() - self.start_time
        time_vals = []
        if not hasattr(self, 'last_time'):
            self.last_time = time_curr
            return
        for i in range(1, 5):
            time_vals.append(i * (time_curr - self.last_time) / 4 + self.last_time)

        self.last_time = time_curr

        left_accel_data, left_gyro_data = RecordData.convert_from_raw(left_message)
        right_accel_data, right_gyro_data = RecordData.convert_from_raw(right_message)


        self.data['gyro_left'].extend(left_gyro_data)
        self.data['gyro_right'].extend(right_gyro_data)
        self.data['time_from_start'].extend(time_vals)

    def missing_smarthubs(self, left=False, right=False):
        popup = tk.Toplevel()

        screen_width = tk.Tk().winfo_screenwidth()
        screen_height = tk.Tk().winfo_screenheight()

        # popup.geometry("300x150")
        popup.geometry(f"+{int(screen_width/2-250)}+{int(screen_height/2-250)}")

        if left==True:
            ttk.Label(popup, text="Left Smarthub not found", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
        if right==True:
            ttk.Label(popup, text="Right Smarthub not found", font=font.Font(size=14)).grid(row=1, column=0, pady=10, padx=50, columnspan=3)

        close_button = ttk.Button(popup, text="Close", command=popup.destroy)
        close_button.grid(row=2, column=0, pady=10, columnspan=3)

    async def _find_smarthubs(self, smarthub_id):
        self.left_smarthub_connection['text'] = 'Disconnected'
        self.left_smarthub_connection['foreground'] = '#a92222'
        self.right_smarthub_connection['text'] = 'Disconnected'
        self.right_smarthub_connection['foreground'] = '#a92222'

        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)

        left_address = None
        right_address = None

        for d, val in devices.items():
            device, adv = val
            if adv.local_name is None:
                continue
            print(d, adv.local_name)
            if isinstance(adv.local_name, str):
                if f'Left Smarthub: {smarthub_id}' == adv.local_name:
                    print("Left Smarthub Identified")
                    left_address = d
                if f'Right Smarthub: {smarthub_id}' == adv.local_name:
                    print("Right Smarthub Identified")
                    right_address = d
        
        if left_address is None or right_address is None:
            self.missing_smarthubs(left=left_address is None, right=right_address is None)
            print('smarthub not found')
            if left_address is not None:
                self.left_smarthub_connection['text'] = 'Connected'
                self.left_smarthub_connection['foreground'] = '#217346'
            
            if right_address is not None:
                self.right_smarthub_connection['text'] = 'Connected'
                self.right_smarthub_connection['foreground'] = '#217346'
            return
        try:
            self.smarthub_id = smarthub_id
            await self.connect_to_device(left_address, right_address)
        except BleakError:
            print("Device went out of range, retrying...")
            await asyncio.sleep(10)  # Wait before retrying

    def connect_smarthubs(self, smarthub_id):
        def ble_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._find_smarthubs(smarthub_id))
            loop.close()

        ble_thread = threading.Thread(target=ble_task, daemon=True)
        ble_thread.start()

    def start_calibration(self):
        if self.start_recording_button['text'] == 'Start Calibration':
            print('calibration started')
            self.recording_started = True

            self.start_recording_button['text'] = 'End Calibration'

        elif self.start_recording_button['text'] == 'End Calibration':
            self.recording_stopped = True
            self.perform_calibration()

            self.start_recording_button['text'] = 'Calibrating...'

            self.recording_started = False


    def smooth_data(self):
        data = {'time_from_start': copy.deepcopy(self.data['time_from_start']),
                'gyro_left': copy.deepcopy(self.data['gyro_left']),
                'gyro_right': copy.deepcopy(self.data['gyro_right'])}
        
        # find shortest array
        min_len = min(len(data['gyro_left']), len(data['gyro_right']), len(data['time_from_start']))
        data['gyro_left'] = data['gyro_left'][:min_len]
        data['gyro_right'] = data['gyro_right'][:min_len]
        data['time_from_start'] = data['time_from_start'][:min_len]

        # Filtering with low pass filter
        filter_freq =  6
        # Calculate fourier transform of right gyroscope data to convert to frequency domain
        W_right = fftfreq(len(data['gyro_right']), d=data['time_from_start'][1]-data['time_from_start'][0])
        f_gyro_right = rfft(data['gyro_right'])
        # Filter out right gyroscope signal above 6 Hz
        f_right_filtered = f_gyro_right.copy()
        f_right_filtered[(np.abs(W_right)>filter_freq)] = 0
        # convert filtered signal back to time domain
        gyro_right_smoothed = irfft(f_right_filtered)

        self.data['gyro_right_smoothed'] = list(gyro_right_smoothed)

        # Calculate fourier transform of right gyroscope data to convert to frequency domain
        W_left = fftfreq(len(data['gyro_left']), d=data['time_from_start'][1]-data['time_from_start'][0])
        f_gyro_left = rfft(data['gyro_left'])
        # Filter out right gyroscope signal above 6 Hz
        f_left_filtered = f_gyro_left.copy()
        f_left_filtered[(np.abs(W_left)>filter_freq)] = 0
        # convert filtered signal back to time domain
        gyro_left_smoothed = irfft(f_left_filtered)

        self.data['gyro_left_smoothed'] = list(gyro_left_smoothed)

    def perform_calibration(self):

        self.smooth_data()

        with open("data.json", "w") as json_file:
            json.dump(self.data, json_file, indent=4)

        self.left_gain, self.right_gain, self.wheel_dist = fsolve(minimize_turnaround, [20,20,20], args=self.data)

        self.show_calibration_results()


    def show_calibration_results(self):

        ttk.Separator(self.tab, orient='horizontal').grid(row=11, column=0, pady=10, columnspan=3, sticky='sew')

        
        ttk.Label(self.tab, text=f"Left Gain: {self.left_gain:.2f}", justify='center', font=font.Font(size=14))\
            .grid(row=13, column=2, pady=10, columnspan=2)
        ttk.Label(self.tab, text=f"Right Gain: {self.right_gain:.2f}", justify='center', font=font.Font(size=14))\
            .grid(row=14, column=2, pady=10, columnspan=2)
        ttk.Label(self.tab, text=f"Wheel Distance: {self.wheel_dist:.2f}", justify='center', font=font.Font(size=14))\
            .grid(row=15, column=2, pady=10, columnspan=2)

        ttk.Label(self.tab, text="Enter Calibration Name: ", justify='center', font=font.Font(size=14))\
            .grid(row=16, column=0, pady=10, columnspan=3)
        calibration_name = ttk.Entry(self.tab, width=15, font=font.Font(size=12))
        calibration_name.grid(row=17, column=0, pady=10, columnspan=3, sticky='nsew')

        save_calibration_button = ttk.Button(self.tab, text='Save Calibration', command=lambda: self.save_calibration(save_calibration_button, self.wheel_dist, self.left_gain, self.right_gain, calibration_name.get()), style='Custom.TButton')
        save_calibration_button.grid(row=18, column=0, pady=10, columnspan=3, sticky='nsew')
        
        self.start_recording_button['text'] = 'Start Calibration'

    

    def save_calibration(self, button, wheel_dist, left_gain, right_gain, calibration_name):
        # save dictionary to json

        post = {
            'smarthub_id': self.smarthub_id,
            'calibration_name': calibration_name,
            'wheel_dist': wheel_dist,
            'left_gain': left_gain,
            'right_gain': right_gain,
            'date': DATE_NOW,
            'raw_data': self.data
        }

        id = self.test_config.insert_one(post).inserted_id

        button['state'] = 'disabled'
        button['text'] = 'Calibration Saved'

        print('successfully saved calibration')

    


    def create_widgets(self):
        style = ttk.Style()

        ttk.Label(self.tab, text="Input SmartHub ID: ", justify='center', font=font.Font(size=14))\
            .grid(row=0, column=0, pady=10, columnspan=3)
        smarthub_id = ttk.Entry(self.tab, width=10, font=font.Font(size=12))
        smarthub_id.grid(row=1, column=0, pady=10, columnspan=2, sticky='nsew')
        ttk.Button(self.tab, text='Connect', command=lambda: self.connect_smarthubs(smarthub_id.get())).grid(row=1, column=2, pady=10, sticky='nsew')
        smarthub_id.bind('<Return>', lambda event: self.connect_smarthubs(smarthub_id.get()))

        ttk.Label(self.tab, text="Left Smarthub: ", justify='center', font=font.Font(size=14))\
            .grid(row=2, column=0, pady=10, columnspan=2)
        ttk.Label(self.tab, text="Right Smarthub: ", justify='center', font=font.Font(size=14))\
            .grid(row=3, column=0, pady=10, columnspan=2)

        self.left_smarthub_connection = ttk.Label(self.tab, text="Disconnected", justify='center', font=font.Font(size=14), foreground='#a92222')
        self.left_smarthub_connection.grid(row=2, column=2, pady=10, columnspan=1)
        self.right_smarthub_connection = ttk.Label(self.tab, text="Disconnected", justify='center', font=font.Font(size=14), foreground='#a92222')
        self.right_smarthub_connection.grid(row=3, column=2, pady=10, columnspan=1)

        ttk.Separator(self.tab, orient='horizontal').grid(row=4, column=0, pady=10, columnspan=3, sticky='sew')

        style.configure('Custom.TButton', font=('Helvetica', 14), background='#217346', foreground='whitesmoke')
        style.map('Custom.TButton', background=[('disabled', '#a9a9a9'), ('!disabled', '#217346')], foreground=[('disabled', 'gray'),('!disabled', 'whitesmoke')])

        self.start_recording_button = ttk.Button(self.tab, text='Start Calibration', command=lambda: self.start_calibration(), state='disabled', style='Custom.TButton')
        self.start_recording_button.grid(row=9, column=0, pady=10, columnspan=3, sticky='nsew')

        self.tab.columnconfigure(0, minsize=50)
        self.tab.columnconfigure(1, minsize=100)
        self.tab.columnconfigure(2, minsize=100)

        self.create_graphs()

        self.calibration_title = ttk.Label(self.tab, text="Connect Smarthubs to Start Calibration", justify='center', font=font.Font(size=14))
        self.calibration_title.grid(row=0, column=4, pady=10, columnspan=100, rowspan=2)

        # draw_grid_lines(self.tab)

    def create_graphs(self):
        dpi = 100

        self.image_width = self.tab.winfo_screenwidth() - 400
        self.image_height = self.tab.winfo_screenheight() - 200
        
        print('canvas size: ', self.image_width, self.image_height)

        self.canvas = tk.Canvas(master=self.tab, width = self.image_width, height = self.image_height)

        self.tab.columnconfigure(3, minsize=100)

        self.canvas.grid(row=2, column=4, columnspan=100, rowspan=100, padx=0, pady=0, sticky='nsew')
        

