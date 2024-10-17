from view_data_tab import ViewData
from record_data_tab import RecordData

from scipy.optimize import minimize, fsolve

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

import asyncio
import tkinter as tk
from tkinter import font, ttk, Label
import threading
import pandas as pd
import struct
import numpy as np
import time
import json
from bleak import BleakScanner, BleakClient, BleakError

from base_ble.params import DATE_DIR, DATE_NOW, left_gain, left_offset, right_gain, right_offset

from base_ble.calibrate import minimize_function

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

class Calibrate:

    def __init__(self, tab, database):
        self.tab = tab
        self.test_config = database.test_config

        self.create_widgets()

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
            'trajectory': []
        }

        self.recording_started = False
        self.recording_stopped = True

        self.calibration_sequence = []
        self.current_calibration_step = 0

        self.set_calibration_sequence()

    def set_calibration_sequence(self):
        self.calibration_sequence.append({'name': 'start', 
                                          'text': 'Move the wheelchair to the starting position.  Set the left wheel on the end tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'pause1', 
                                          'text': 'Wait for at least 5 seconds with the left wheel on the tape.  Do not move the wheelchair.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'forward1', 
                                          'text': 'Move the wheelchair forward 10 meters. Keep the the left wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'turnleft1',
                                          'text': 'Turn the wheelchair 180 degrees, keeping the left wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'forward2',
                                          'text': 'Move the wheelchair forward 10 meters. Keep the the left wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'turnleft2',
                                          'text': 'Turn the wheelchair 180 degrees, keeping the left wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'setposition',
                                          'text': 'The wheelchair should currently be in the starting position.  Set the right wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'pause2',
                                          'text': 'Wait for at least 5 seconds with the right wheel on the tape.  Do not move the wheelchair.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'forward3',
                                          'text': 'Move the wheelchair forward 10 meters. Keep the the right wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'turnright1',
                                          'text': 'Turn the wheelchair 180 degrees, keeping the right wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'forward4',
                                          'text': 'Move the wheelchair forward 10 meters. Keep the the right wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'turnright2',
                                          'text': 'Turn the wheelchair 180 degrees, keeping the right wheel on the tape.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
        self.calibration_sequence.append({'name': 'end',
                                          'text': 'The wheelchair should be in the starting position.  Press "END" to save calibration.',
                                          'time_from_start': [],
                                          'gyro_left': [],
                                          'gyro_right': []})
        
    def next_calibration_step(self):
        self.current_calibration_step += 1
        self.update_calibration_display()
        pass

    def update_calibration_display(self):
        self.calibration_title['text'] = self.calibration_sequence[self.current_calibration_step]['text']


    async def connect_to_device(self, left_address, right_address):
        try:
            async with BleakClient(left_address) as left_client:
                self.left_smarthub_connection['text'] = 'Connected'
                self.left_smarthub_connection['foreground'] = '#217346'
                async with BleakClient(right_address) as right_client:
                    self.right_smarthub_connection['text'] = 'Connected'
                    self.right_smarthub_connection['foreground'] = '#217346'

                    ch = "00002a56-0000-1000-8000-00805f9b34fb"

                    # await left_client.start_notify(ch, self.update_data, side='left')
                    self.start_recording_button['state'] = 'normal'

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
                            pass

                    async def start_notifications(self, left_client, right_client, ch):
                        await left_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'left'))
                        await right_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'right'))

                    initial_loop = True
                    while True:
                        if self.recording_started == False:
                            self.recording_stopped = False
                            await asyncio.sleep(0)
                            continue

                        if self.recording_stopped == True:
                            self.recording_started = False
                            await left_client.stop_notify(ch)
                            await right_client.stop_notify(ch)

                            # update_graphs_thread.join()
                            break
                        else:
                            await left_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'left'))
                            await right_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'right'))

                        if initial_loop:
                            self.start_time = time.time()
                            initial_loop = False

                            # update_graphs_thread = threading.Thread(target=self.update_graphs, daemon=True)
                            # update_graphs_thread.start()

                        # await left_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'left'))
                        # await right_client.start_notify(ch, lambda ch, data: update_data(ch, data, 'right'))

                        # read_message_left = await left_client.read_gatt_char(ch)
                        # read_message_right = await right_client.read_gatt_char(ch)

                        # self.parse_data(read_message_left, read_message_right)
                        await start_notifications(self, left_client, right_client, ch)
                        await asyncio.sleep(1)

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
            return
        except TimeoutError as e:
            print(f"Timeout error: {e}")
            if self.left_smarthub_connection['text'] != 'Connected' and self.right_smarthub_connection['text'] != 'Connected':
                self.missing_smarthubs(left=True, right=True)
            if self.left_smarthub_connection['text'] != 'Connected':
                self.missing_smarthubs(left=True)
            if self.right_smarthub_connection['text'] != 'Connected':
                self.missing_smarthubs(right=True)
        except OSError as e:
            print(f"OS error (devices are most likely disconnected): {e}")

        # self.perform_calibration()

        # self.save_data()


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


        self.calibration_sequence[self.current_calibration_step]['gyro_left'].extend(left_gyro_data)
        self.calibration_sequence[self.current_calibration_step]['gyro_right'].extend(right_gyro_data)
        self.calibration_sequence[self.current_calibration_step]['time_from_start'].extend(time_vals)

        # print(f"Left: {left_gyro_data}")
        # print(f"Right: {right_gyro_data}")
        # print()

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

        devices = await BleakScanner.discover(timeout=10.0)
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


            self.start_recording_button['text'] = 'Next Step'

        elif self.start_recording_button['text'] == 'Next Step':
            print('next step')
            # self.recording_stopped = True

            if self.current_calibration_step == len(self.calibration_sequence) - 1:
                self.start_recording_button['text'] = 'End Calibration'

            else:
                self.next_calibration_step()

        if self.start_recording_button['text'] == 'End Calibration':
            self.recording_stopped = True
            # self.start_recording_button['state'] = 'disabled'
            self.perform_calibration()

    def perform_calibration(self):
        res = fsolve(minimize_function, [20,20,1,1], args=self.calibration_sequence)

        print(res)

        diameter = res[0]
        wheel_dist = res[1]
        left_gain = res[2]
        right_gain = res[3]

        popup = tk.Toplevel()

        screen_width = tk.Tk().winfo_screenwidth()
        screen_height = tk.Tk().winfo_screenheight()

        # popup.geometry("300x150")
        popup.geometry(f"+{int(screen_width/2-250)}+{int(screen_height/2-250)}")

        ttk.Label(popup, text=f"Calibration Results", font=font.Font(size=14)).grid(row=0, column=0, pady=10, padx=50, columnspan=3)
        ttk.Label(popup, text=f"Diameter: {diameter:2f}", font=font.Font(size=14)).grid(row=1, column=0, pady=10, padx=50, columnspan=3)
        ttk.Label(popup, text=f"Wheel Distance: {wheel_dist:2f}", font=font.Font(size=14)).grid(row=2, column=0, pady=10, padx=50, columnspan=3)
        ttk.Label(popup, text=f"Left Gain: {left_gain:2f}", font=font.Font(size=14)).grid(row=3, column=0, pady=10, padx=50, columnspan=3)
        ttk.Label(popup, text=f"Right Gain: {right_gain:2f}", font=font.Font(size=14)).grid(row=4, column=0, pady=10, padx=50, columnspan=3)
        calibration_name = ttk.Entry(popup, width=10)
        calibration_name.grid(row=5, column=0, pady=10, padx=50, columnspan=3)
        ttk.Button(popup, text="Save Calibration", command=lambda: self.save_calibration(popup, diameter, wheel_dist, left_gain, right_gain, calibration_name.get())).grid(row=6, column=0, pady=10, padx=50, columnspan=3)
        ttk.Button(popup, text="Don't Save", command=popup.destroy).grid(row=6, column=1, pady=10, padx=50, columnspan=3)

    def save_calibration(self, popup, diameter, wheel_dist, left_gain, right_gain, calibration_name):
        # save dictionary to json
        popup.destroy()

        with open("data.json", "w") as json_file:
            json.dump(self.calibration_sequence, json_file, indent=4)

        post = {
            'smarthub_id': self.smarthub_id,
            'calibration_name': calibration_name,
            'diameter': diameter,
            'wheel_dist': wheel_dist,
            'left_gain': left_gain,
            'right_gain': right_gain,
            'date': DATE_NOW,
            'calibration_sequence': self.calibration_sequence
        }

        id = self.test_config.insert_one(post).inserted_id

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
        if not hasattr(self, 'fig'):
            screen_width = self.tab.winfo_screenwidth()
            screen_height = self.tab.winfo_screenheight()

            self.fig = Figure(figsize=((screen_width-400)/dpi, (screen_height-200)/dpi), dpi=dpi)

            # self.fig.tick_params(colors='white')
            # ax.set_facecolor(str(ttk.Style().lookup('TFrame', 'foreground')))
            self.fig.set_facecolor('whitesmoke')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab)

        self.tab.columnconfigure(3, minsize=100)

        self.canvas.get_tk_widget().grid(row=2, column=4, columnspan=100, rowspan=100, padx=0, pady=0, sticky='nsew')

        

