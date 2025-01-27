from view_data_tab import ViewData

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

import asyncio
import tkinter as tk
import copy
from tkinter import font, Label
from tkinter import ttk
import threading
import pandas as pd
import struct
import numpy as np
import time
from datetime import datetime
from bleak import BleakScanner, BleakClient, BleakError

from base_ble.params import DATE_DIR, DATE_NOW, left_gain, left_offset, right_gain, right_offset, WHEEL_DIAM_IN, DIST_WHEELS_IN

from base_ble.calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)

from scipy.fftpack import fftfreq, irfft, rfft

class RecordData:

    def __init__(self, tab, database, filepath, screen_size):
        self.tab = tab
        self.test_collection = database.test_collection
        self.test_config = database.test_config
        self.filepath = filepath
        self.screen_width, self.screen_height = screen_size
        self.create_widgets()


        # have we set a background for the graph yet?
        self.background_set = False

        # track how many backgrounds we've set
        self.line_pos = 0

        # diameter of the wheels (default if no calibration set)
        self.diameter = WHEEL_DIAM_IN
        # distance between the wheels (default if no calibration set)
        self.dist_wheels = DIST_WHEELS_IN

        # gain for the wheels (default if no calibration set)
        self.left_gain = left_gain
        self.right_gain = right_gain

        # 6 digit operator id (not set by default) (not regulated, it can be whatever string you want)
        self.operator_id = None

        # self.ble_thread = None

        # have we started recording? this will be set to true once we have
        self.recording_started = False
        # have we stopped recording? this will be set to false once we start recording
        self.recording_stopped = True
        # reason for two of these is so we can cycle through one if statement while we haven't started recording, then 
        # go through the other if statement once when we've stopped.  logic is handled in connect_to_device


        # initialize empty dictionary to store data
        self.reset_data()


    def handle_disconnect(self, _):
        print(f"Disconnected from device")

    def set_operator_id(self, operator_id):
        """
        param -> operator_id: 6 digit operator id (or whatever string you want)
        returns -> None

        sets the operator id for the test in the title on top of all the graphs
        also checks to see if we've connected to smarthubs yet, if we have then enable the start recording button
        """
        self.operator_id = operator_id
        operator_id_label = Label(self.tab, text=f'Operator ID: {self.operator_id}', font=font.Font(size=18))
        operator_id_label.grid(row=0, column=3, columnspan=100, sticky='sew')
        self.canvas_widgets.append(operator_id_label)

        if self.right_smarthub_connection['text'] == 'Connected' and self.left_smarthub_connection['text'] == 'Connected':
            self.start_recording_button['state'] = 'normal'

    @staticmethod
    def convert_from_raw(raw_data):
        """
        param -> raw_data: raw data as 18 len bytearray
        returns ->  accel_data: list of 4 acceleration data floats
                    gyro_data: list of 4 gyro data floats

        converts raw data from smarthub to true acceleration and gyro data
        set as @staticmethod so we can call it from other classes

        format of raw data:
        ┏---┓
        ┃ 0 ┃ sign bits for accel data  0b00001111 if all 4 negative
        ┗---┛
        ┏---┓
        ┃ 1 ┃ sign bits for gyro data  0b00001111 if all 4 negative
        ┗---┛
        ┏---┓┏---┓
        ┃ 2 ┃┃ 3 ┃ accel data 1 (LSB first) | unsigned value, divide by 1000 to get true accel data
        ┗---┗┗---┛
        ┏---┓┏---┓
        ┃ 4 ┃┃ 5 ┃ accel data 2
        ┗---┗┗---┛
        ┏---┓┏---┓
        ┃ 6 ┃┃ 7 ┃ accel data 3
        ┗---┗┗---┛
        ┏---┓┏---┓
        ┃ 8 ┃┃ 9 ┃ accel data 4
        ┗---┗┗---┛
        ┏----┓┏----┓
        ┃ 10 ┃┃ 11 ┃ gyro data 1 (LSB first) | unsigned value, divide by 100 to get true gyro data
        ┗----┗┗----┛
        ┏----┓┏----┓
        ┃ 12 ┃┃ 13 ┃ gyro data 2
        ┗----┗┗----┛
        ┏----┓┏----┓
        ┃ 14 ┃┃ 15 ┃ gyro data 3
        ┗----┗┗----┛
        ┏----┓┏----┓
        ┃ 16 ┃┃ 17 ┃ gyro data 4
        ┗----┗┗----┛

        1 refers to oldest data, 4 refers to newest data

        """

        accel_data = []
        gyro_data = []

        for i in range(4):

            # LSB first
            accel_data.append((raw_data[2*i+2] + raw_data[2*i+3]*256) / 1000)  # bytes 2, 4, 6, 8 convert to true accel data

            gyro_data.append((raw_data[2*i+10] + raw_data[2*i+11]*256) / 100) # bytes 10, 12, 14, 16 convert to true gyro data

            # pull signs from sign bytes to modify data
            if (raw_data[0] & (1 << i)) == (1 << i):
                accel_data[i] *= -1

            if (raw_data[1] & (1 << i)) == (1 << i):
                gyro_data[i] *= -1
        return accel_data, gyro_data

    def parse_data(self, left_message, right_message):
        """
        param -> left_message: 18 len bytearray of raw data from left smarthub
                 right_message: 18 len bytearray from right smarthub
        returns -> None

        parses raw data from smarthubs and appends to data dictionary
        handles 
        
        
        """
        time_curr = time.time() - self.start_time
        time_vals = []
        if not hasattr(self, 'last_time'):
            self.last_time = time_curr
            return

        for i in range(3, -1, -1):

            time_vals.append(time_curr - i * 1/68)
            # time_vals.append(i * (time_curr - self.last_time) / 4 + self.last_time)

        self.last_time = time_curr

        left_accel_data, left_gyro_data = self.convert_from_raw(left_message)
        right_accel_data, right_gyro_data = self.convert_from_raw(right_message)

        self.data['gyro_left'].extend(left_gyro_data)
        self.data['gyro_right'].extend(right_gyro_data)
        self.data['time_from_start'].extend(time_vals)

    def update_graphs(self):

        update_frequency = 400

        if len(self.data['time_from_start']) < 1:
            if not self.recording_stopped:
                self.tab.after(200, self.update_graphs)
            return
        
        # set value of time and gyros so we don't get a race condition, other data is being updated in real time
        data = {'time_from_start': copy.deepcopy(self.data['time_from_start']),
                'gyro_left': copy.deepcopy(self.data['gyro_left']),
                'gyro_right': copy.deepcopy(self.data['gyro_right'])}
        
        if len(data['time_from_start']) != len(data['gyro_left']):
            print('Data length mismatch at time', data['time_from_start'][-1])
            self.tab.after(int(update_frequency/4), self.update_graphs)
            return
        if len(data['time_from_start']) != len(data['gyro_right']):
            print('Data length mismatch at time', data['time_from_start'][-1])
            self.tab.after(int(update_frequency/4), self.update_graphs)
            return
        if len(data['gyro_left']) != len(data['gyro_right']):
            print('Data length mismatch at time', data['time_from_start'][-1])
            self.tab.after(int(update_frequency/4), self.update_graphs)
            return

        try:
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

            self.data['gyro_right_smoothed'] = gyro_right_smoothed

            # Calculate fourier transform of right gyroscope data to convert to frequency domain
            W_left = fftfreq(len(data['gyro_left']), d=data['time_from_start'][1]-data['time_from_start'][0])
            f_gyro_left = rfft(data['gyro_left'])
            # Filter out right gyroscope signal above 6 Hz
            f_left_filtered = f_gyro_left.copy()
            f_left_filtered[(np.abs(W_left)>filter_freq)] = 0
            # convert filtered signal back to time domain
            gyro_left_smoothed = irfft(f_left_filtered)

            self.data['gyro_left_smoothed'] = gyro_left_smoothed
        except ValueError:
            print('Value error in filtering, retrying')
            self.tab.after(int(update_frequency/4), self.update_graphs)
            return

        # Filtering with moving average

        # N_win = 15
        # # Padding the data
        # gyro_right_padded = np.pad(data['gyro_right'], (N_win//2, N_win-1-N_win//2), mode='edge')
        # # Smoothing using moving average
        # gyro_right_smoothed = np.convolve(gyro_right_padded, np.ones(N_win)/N_win, mode='valid')
        
        # gyro_right_smoothed *= self.right_gain
        # # Converting back to list
        # self.data['gyro_right_smoothed'] = list(gyro_right_smoothed)
        
        
        # # Padding the data
        # gyro_left_padded = np.pad(data['gyro_left'], (N_win//2, N_win-1-N_win//2), mode='edge')
        # # Smoothing using moving average
        # gyro_left_smoothed = np.convolve(gyro_left_padded, np.ones(N_win)/N_win, mode='valid')
        
        # gyro_left_smoothed *= self.left_gain
        # # Converting back to list
        # self.data['gyro_left_smoothed'] = list(gyro_left_smoothed)

        # Derive distance based on data:
        self.data['dist_m'][:] = get_distance_m(data['time_from_start'], gyro_left_smoothed,
                                            gyro_right_smoothed, diameter=self.diameter, dist_wheels=self.dist_wheels)
        # Calculate displacement for the data['trajectory']:
        self.data['disp_m'][:] = get_displacement_m(data['time_from_start'], gyro_left_smoothed,
                                                gyro_right_smoothed, diameter=self.diameter, dist_wheels=self.dist_wheels)
        # Find heading angle over time:
        self.data['heading_deg'][:] = get_heading_deg(data['time_from_start'], gyro_left_smoothed,
                                                    gyro_right_smoothed, diameter=self.diameter, dist_wheels=self.dist_wheels)
        # Calculate Velocity over time:
        self.data['velocity'][:] = get_velocity_m_s(data['time_from_start'], gyro_left_smoothed,
                                                gyro_right_smoothed, diameter=self.diameter, dist_wheels=self.dist_wheels)
        # Process data['trajectory']:
        self.data['trajectory'][:] = get_top_traj(self.data['disp_m'], self.data['velocity'], self.data['heading_deg'],
                                                data['time_from_start'], diameter=self.diameter, dist_wheels=self.dist_wheels)  # use displacement

        # update subplots, if there's a background make sure we update the right graphs
        print(self.line_pos)
        if not self.axs[0].lines or (self.background_set and len(self.axs[0].lines) == 1):
            self.axs[0].plot(data['time_from_start'], self.data['dist_m'])
        elif self.background_set:
            self.axs[0].lines[self.line_pos].set_data(data['time_from_start'], self.data['dist_m'])
        else:
            self.axs[0].lines[0].set_data(data['time_from_start'], self.data['dist_m'])

        if not self.axs[1].lines or (self.background_set and len(self.axs[1].lines) == 1):
            self.axs[1].plot([i[0] for i in self.data['trajectory']], [i[1] for i in self.data['trajectory']])
        elif self.background_set:
            self.axs[1].lines[self.line_pos].set_data([i[0] for i in self.data['trajectory']], [i[1] for i in self.data['trajectory']])
        else:
            self.axs[1].lines[0].set_data([i[0] for i in self.data['trajectory']], [i[1] for i in self.data['trajectory']])

        if not self.axs[2].lines or (self.background_set and len(self.axs[2].lines) == 1):
            self.axs[2].plot(data['time_from_start'], self.data['heading_deg'])
        elif self.background_set:
            self.axs[2].lines[self.line_pos].set_data(data['time_from_start'], self.data['heading_deg'])
        else:
            self.axs[2].lines[0].set_data(data['time_from_start'], self.data['heading_deg'])

        if not self.axs[3].lines or (self.background_set and len(self.axs[3].lines) == 1):
            self.axs[3].plot(data['time_from_start'], self.data['velocity'])
        elif self.background_set:
            self.axs[3].lines[self.line_pos].set_data(data['time_from_start'], self.data['velocity'])
        else:
            self.axs[3].lines[0].set_data(data['time_from_start'], self.data['velocity'])

        # print(data['dist_m'][-1], data['heading_deg'][-1], data['velocity'][-1], data['trajectory'][-1])

        # print(len(data['time_from_start'])/data['time_from_start'][-1])

        for ax in self.axs:
            ax.relim()
            ax.autoscale()

        # Redraw the canvas
        # canvas_widget = self.canvas.get_tk_widget()
        self.canvas.draw()
        self.canvas.flush_events()  


        if not self.recording_stopped:
            self.tab.after(update_frequency, self.update_graphs)

    def set_background(self, data):
        self.background_set = True
        if not self.recording_started:
            self.line_pos = len(self.axs[0].lines) + 1

        
        self.axs[0].plot(data['elapsed_time_s'], data['distance_m'], label="Distance")
        self.axs[1].plot(data['traj_x'], data['traj_y'], label="Trajectory")
        self.axs[2].plot(data['elapsed_time_s'], data['heading_deg'], label="Heading")
        self.axs[3].plot(data['elapsed_time_s'], data['velocity'], label="Velocity")

        for ax in self.axs:
            ax.relim()
            ax.autoscale()
        self.canvas.draw()
        self.canvas.flush_events()  
        

    def select_calibration(self):
        ttk.Separator(self.tab, orient='horizontal').grid(row=15, column=0, pady=10, columnspan=3, sticky='sew')

        ttk.Label(self.tab, text="Select Calibration: ", justify='center', font=font.Font(size=14))\
            .grid(row=17, column=0, pady=10, columnspan=3)

        self.all_ids = self.test_config.find({'smarthub_id': self.smarthub_id}, {'calibration_name': 1})

        select_calibration = ttk.Combobox(self.tab, values=[i['calibration_name'] for i in self.all_ids])
        select_calibration.grid(row=19, column=0, pady=10, columnspan=3, sticky='nsew')
        select_calibration.bind("<<ComboboxSelected>>", self.update_calibration)

    def update_calibration(self, event):
        calibration_name = event.widget.get()
        calibration = self.test_config.find_one({'calibration_name': calibration_name, 'smarthub_id': self.smarthub_id})

        self.diameter = calibration['diameter']
        self.dist_wheels = calibration['wheel_dist']
        self.left_gain = calibration['left_gain']
        self.right_gain = calibration['right_gain']


    async def connect_to_device(self, left_address, right_address):
        try:
            async with BleakClient(left_address) as left_client:
                self.left_smarthub_connection['text'] = 'Connected'
                self.left_smarthub_connection['foreground'] = '#217346'
                async with BleakClient(right_address) as right_client:
                    self.right_smarthub_connection['text'] = 'Connected'
                    self.right_smarthub_connection['foreground'] = '#217346'

                    self.connect_button['text'] = 'Connected'

                    if self.operator_id is not None:
                        self.start_recording_button['state'] = 'normal'

                    ch = "00002a56-0000-1000-8000-00805f9b34fb"

                    self.select_calibration()

                    self.notifications_started = False

                    self.new_data_left = None
                    self.new_data_right = None
                    def update_data(_, data, side):
                        if not hasattr(self, 'last_left_message'):
                            self.last_left_message = None
                            self.last_right_message = None
                            self.last_time = time.time()

                        if side == 'left':
                            if self.last_left_message != data:
                                self.last_left_message = data
                                self.new_data_left = data
                                if self.new_data_right is not None:
                                    self.parse_data(self.new_data_left, self.new_data_right)
                                    self.new_data_left = None
                                    self.new_data_right = None
                        elif side == 'right':
                            if self.last_right_message != data:
                                self.last_right_message = data
                                self.new_data_right = data
                                if self.new_data_left is not None:
                                    self.parse_data(self.new_data_left, self.new_data_right)
                                    self.new_data_left = None
                                    self.new_data_right = None

                    async def start_notifications(self, left_client, right_client, ch):
                        # left_rssi = await left_client.get_rssi()
                        # right_rssi = await right_client.get_rssi()
                        # print("Left Strength:", left_rssi)
                        # print("Right Strength:", right_rssi)
                        self.notifications_started = True
                        await left_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'left'))
                        await right_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'right'))

                    initial_loop = True

                    while True:
                        if self.recording_started == False:
                            self.recording_stopped = False
                            await asyncio.sleep(0)
                            initial_loop = True
                            continue

                        if self.recording_stopped == True:
                            self.recording_started = False
                            await left_client.stop_notify(ch)
                            await right_client.stop_notify(ch)

                            self.notifications_started = False

                            # update_graphs_thread.join()
                            continue
                            

                        if initial_loop:
                            self.start_time = time.time()
                            initial_loop = False
                            self.reset_data()
                            print('started loop')

                            self.tab.after(0, self.update_graphs)

                            # update_graphs_thread = threading.Thread(target=self.update_graphs, daemon=True)
                            # update_graphs_thread.start()

                        if not self.notifications_started:
                            await start_notifications(self, left_client, right_client, ch)
                        await asyncio.sleep(1)

                        
                                # self.update_data(_, right_client)

                        # read_message_left = await left_client.read_gatt_char(ch)
                        # read_message_right = await right_client.read_gatt_char(ch)


                        # self.parse_data(read_message_left, read_message_left)

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
            ttk.Label(popup, text=f"Device went out of range, please retry connection: BleakError {e}", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
            return
        except OSError as e:
            print(e)
            popup = tk.Toplevel()
            ttk.Label(popup, text=f"Device went out of range, please retry connection: OSERrror {e}", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
            return

        except TimeoutError as e:
            print(f"Timeout error: {e}")
            return

        self.save_data()

    def missing_smarthubs(self, left=False, right=False):
        popup = tk.Toplevel()

        screen_width = tk.Tk().winfo_screenwidth()
        screen_height = tk.Tk().winfo_screenheight()

        # popup.geometry("300x150")
        # popup.geometry(f"+{int(screen_width/2-250)}+{int(screen_height/2-250)}")

        if left==True:
            ttk.Label(popup, text="Left Smarthub not found", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
        if right==True:
            ttk.Label(popup, text="Right Smarthub not found", font=font.Font(size=14)).grid(row=1, column=0, pady=10, padx=50, columnspan=3)

        # close_button = ttk.Button(popup, text="Close", command=popup.destroy)
        # close_button.grid(row=2, column=0, pady=10, columnspan=3)



    async def _find_smarthubs(self, smarthub_id):
        self.left_smarthub_connection['text'] = 'Disconnected'
        self.left_smarthub_connection['foreground'] = '#a92222'
        self.right_smarthub_connection['text'] = 'Disconnected'
        self.right_smarthub_connection['foreground'] = '#a92222'

        devices = await BleakScanner.discover(timeout=8.0)
        # smarthub_id = "9999"
        left_address = None
        right_address = None
        for d in devices:
            print(d)
            if isinstance(d.name, str):
                if f'Left Smarthub: {smarthub_id}' == d.name:
                    print("Left Smarthub Identified")
                    left_address = d.address
                if f'Right Smarthub: {smarthub_id}' == d.name:
                    print("Right Smarthub Identified")
                    right_address = d.address
        
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
        self.connect_button['text'] = 'Connecting...'

        def ble_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._find_smarthubs(smarthub_id))
            loop.close()

        ble_thread = threading.Thread(target=ble_task, daemon=True)
        ble_thread.start()

    def start_recording(self):
        if self.start_recording_button['text'] == 'Start Recording':
            print('recording started')
            self.recording_started = True


            self.start_recording_button['text'] = 'Stop Recording'
        elif self.start_recording_button['text'] == 'Stop Recording':
            print('recording stopped')
            self.recording_stopped = True
            self.save_data()

            self.start_recording_button['text'] = 'Start Recording'

    def reset_data(self):
        self.data = {
            'gyro_right': [],
            'gyro_left': [],
            'time_from_start': [],
            'gyro_right_smoothed': [],
            'gyro_left_smoothed': [],
            'dist_m': [],
            'disp_m': [],
            'heading_deg': [],
            'velocity': [],
            'trajectory': [],
        }

        self.last_time_left = 0
        self.last_time_right = 0
        self.start_time_left = 0
        self.start_time_right = 0

        self.additional_notes = ''


    def save_data(self):

        if len(self.data['time_from_start']) < 1:
            print('no data recorded')
            return

        test_datetime = datetime.now()
        datetime_str = f"{test_datetime.month}/{test_datetime.day}/{test_datetime.year}_{test_datetime.hour}:{test_datetime.minute}:{test_datetime.second}"

        time.sleep(0.1)
        self.update_graphs()

        # find shortest length of data
        min_len = min(len(v) for v in self.data.values())

        post = {}
        post['_id'] = datetime_str
        post['elapsed_time_s'] = self.data['time_from_start'][:min_len]
        post['gyro_right'] = self.data['gyro_right'][:min_len]
        post['gyro_left'] = self.data['gyro_left'][:min_len]
        post['gyro_right_smoothed'] = list(self.data['gyro_right_smoothed'][:min_len])
        post['gyro_left_smoothed'] = list(self.data['gyro_left_smoothed'][:min_len])
        # post['accel_right'] = self.data['accel_right']
        # post['accel_left'] = self.data['accel_left']
        post['distance_m'] = self.data['dist_m'][:min_len]
        post['heading_deg'] = self.data['heading_deg'][:min_len]
        post['displacement_m'] = self.data['disp_m'][:min_len]
        post['traj_x'] = [i[0] for i in self.data['trajectory']][:min_len]
        post['traj_y'] = [i[1] for i in self.data['trajectory']][:min_len]
        post['user_id'] = self.operator_id

        post['notes'] = self.additional_notes

        print(post['_id'], post['user_id'], post['notes'])

        id = self.test_collection.insert_one(post).inserted_id
        

        # max_len = max(len(v) for v in self.data.values())

        # # Normalize the lengths of lists by filling with NaN
        # for key in self.data:
        #     self.data[key] += [np.nan] * (max_len - len(self.data[key]))
        # df = pd.DataFrame(self.data)

        # df.fillna('')

        # df.to_csv('test_data.csv', index=False)

        self.recording_started = False
        self.recording_stopped = True
        self.reset_data()


    def create_widgets(self):
        style = ttk.Style()
        ttk.Label(self.tab, text="Input User ID: ", justify='center', font=font.Font(size=14))\
            .grid(row=0, column=0, pady=10, columnspan=3)
        select_user_id = ttk.Entry(self.tab, width=10, font=font.Font(size=12))
        select_user_id.grid(row=1, column=0, pady=10, columnspan=2, sticky='nsew')
        ttk.Button(self.tab, text='Enter', command=lambda: self.set_operator_id(select_user_id.get())).grid(row=1, column=2, pady=10, sticky='nsew')
        select_user_id.bind('<Return>', lambda event: self.set_operator_id(select_user_id.get()))

        ttk.Separator(self.tab, orient='horizontal').grid(row=2, column=0, pady=10, columnspan=3, sticky='sew')

        ttk.Label(self.tab, text="Input SmartHub ID: ", justify='center', font=font.Font(size=14))\
            .grid(row=3, column=0, pady=10, columnspan=3)
        smarthub_id = ttk.Entry(self.tab, width=10, font=font.Font(size=12))
        smarthub_id.grid(row=4, column=0, pady=10, columnspan=2, sticky='nsew')
        self.connect_button = ttk.Button(self.tab, text='Connect', command=lambda: self.connect_smarthubs(smarthub_id.get()))
        self.connect_button.grid(row=4, column=2, pady=10, sticky='nsew')
        smarthub_id.bind('<Return>', lambda event: self.connect_smarthubs(smarthub_id.get()))

        ttk.Label(self.tab, text="Left Smarthub: ", justify='center', font=font.Font(size=14))\
            .grid(row=5, column=0, pady=10, columnspan=2)
        ttk.Label(self.tab, text="Right Smarthub: ", justify='center', font=font.Font(size=14))\
            .grid(row=6, column=0, pady=10, columnspan=2)

        self.left_smarthub_connection = ttk.Label(self.tab, text="Disconnected", justify='center', font=font.Font(size=14), foreground='#a92222')
        self.left_smarthub_connection.grid(row=5, column=2, pady=10, columnspan=1)
        self.right_smarthub_connection = ttk.Label(self.tab, text="Disconnected", justify='center', font=font.Font(size=14), foreground='#a92222')
        self.right_smarthub_connection.grid(row=6, column=2, pady=10, columnspan=1)

        ttk.Separator(self.tab, orient='horizontal').grid(row=7, column=0, pady=10, columnspan=3, sticky='sew')

        style.configure('Custom.TButton', font=('Helvetica', 14), background='#217346', foreground='whitesmoke')
        style.map('Custom.TButton', background=[('disabled', '#a9a9a9'), ('!disabled', '#217346')], foreground=[('disabled', 'gray'),('!disabled', 'whitesmoke')])

        self.start_recording_button = ttk.Button(self.tab, text='Start Recording', command=lambda: self.start_recording(), state='disabled', style='Custom.TButton')
        self.start_recording_button.grid(row=12, column=0, pady=10, columnspan=3, sticky='nsew')

        self.tab.columnconfigure(0, minsize=50)
        self.tab.columnconfigure(1, minsize=100)
        self.tab.columnconfigure(2, minsize=100)

        self.create_graphs()

    def create_graphs(self):
        dpi = 100

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

        ViewData.set_subplot_labels(axs=self.axs)

        self.canvas.draw()
        self.canvas.flush_events()  
        # self.axs[1].set_aspect('equal')

        self.canvas.get_tk_widget().grid(row=1, column=3, columnspan=100, rowspan=100, padx=0, pady=0, sticky='nsew')
