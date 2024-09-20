from view_data_tab import ViewData

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
from bleak import BleakScanner, BleakClient, BleakError

from base_ble.params import DATE_DIR, DATE_NOW, left_gain, left_offset, right_gain, right_offset

from base_ble.calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)

from scipy.fftpack import fftfreq, irfft, rfft

class RecordData:

    def __init__(self, tab):
        self.tab = tab
        self.create_widgets()

        self.operator_id = None

        self.keep_running = True
        self.ble_thread = None

        self.reset_data()

        self.packets = 0


        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self.left_buffer = None
        self.right_buffer = None

    def handle_disconnect(self, _):
        print(f"Disconnected from device")

    def set_operator_id(self, operator_id):
        self.operator_id = operator_id
        operator_id_label = Label(self.tab, text=f'Operator ID: {self.operator_id}', font=font.Font(size=18))
        operator_id_label.grid(row=0, column=3, columnspan=100, sticky='sew')
        self.canvas_widgets.append(operator_id_label)

        if self.right_smarthub_connection['text'] == 'Connected' and self.left_smarthub_connection['text'] == 'Connected':
            self.start_recording_button['state'] = 'normal'

    def convert_from_raw(self, raw_data):

        accel_data = []
        gyro_data = []

        for i in range(4):

            # LSB first
            accel_data.append((raw_data[2*i+2] + raw_data[2*i+3]*256) / 1000)  # bytes 2, 4, 6, 8 convert to true accel data

            gyro_data.append((raw_data[2*i+10] + raw_data[2*i+11]*256) / 100) # bytes 10, 12, 14, 16 convert to true gyro data

            # pull signs from sign byte to modify data
            if (raw_data[0] & (1 << i)) == (1 << i):
                accel_data[i] *= -1

            if (raw_data[1] & (1 << i)) == (1 << i):
                gyro_data[i] *= -1
        return accel_data, gyro_data

    def update_data(self, _, data):

        if self.packets % 50 == 0:
            print(self.packets)
    

        if data[0] == 0:

            side = 'left'
            curr_time = struct.unpack('f', data[1:5])[0]

            if curr_time != self.last_time_right:
                self.last_time_right = curr_time
                self.packets += 1
                return
                
            else:
                return
            
            left_data = struct.unpack('f', data[5:9])[0]

            if self.right_buffer != None:
                data_time, right_data = self.right_buffer

                time_to_save = (data_time + (time.time() - self.start_time) ) / 2
                self.data['gyro_right'].append(right_data)
                self.data['gyro_left'].append(left_data)
                self.data['time_from_start'].append(time_to_save)

                self.left_buffer = None
                self.right_buffer = None
            else:
                self.left_buffer = (time.time() - self.start_time, left_data)

        elif data[0] == 1:

            side = 'right'
            curr_time = struct.unpack('f', data[1:5])[0]
            if curr_time != self.last_time_left:
                self.packets += 1
                self.last_time_left = curr_time
                return
            else:
                return
            
            right_data = struct.unpack('f', data[5:9])[0]

            if self.left_buffer != None:
                data_time, left_data = self.left_buffer

                # average time from the buffer and from now to get approximate time
                time_to_save = (data_time + (time.time() - self.start_time) ) / 2
                self.data['gyro_right'].append(right_data)
                self.data['gyro_left'].append(left_data)
                self.data['time_from_start'].append(time_to_save)

                self.left_buffer = None
                self.right_buffer = None
            else:
                self.right_buffer = (time.time() - self.start_time, right_data)

    def parse_data(self, left_message, right_message):
        time_curr = time.time() - self.start_time
        time_vals = []
        if not hasattr(self, 'last_time'):
            self.last_time = time_curr
            return
        for i in range(1, 5):
            time_vals.append(i * (time_curr - self.last_time) / 4 + self.last_time)

        self.last_time = time_curr

        left_accel_data, left_gyro_data = self.convert_from_raw(left_message)
        right_accel_data, right_gyro_data = self.convert_from_raw(right_message)


        self.data['gyro_left'].extend(left_gyro_data)
        self.data['gyro_right'].extend(right_gyro_data)
        self.data['time_from_start'].extend(time_vals)

    def update_graphs(self):

        if len(self.data['time_from_start']) < 1:
            if not self.recording_stopped:
                self.tab.after(200, self.update_graphs)
            return

        # Filtering with low pass filter
        # filter_freq =  6
        # # Calculate fourier transform of right gyroscope data to convert to frequency domain
        # W_right = fftfreq(len(self.data['gyro_right']), d=self.data['time_from_start'][1]-self.data['time_from_start'][0])
        # f_gyro_right = rfft(self.data['gyro_right'])
        # # Filter out right gyroscope signal above 6 Hz
        # f_right_filtered = f_gyro_right.copy()
        # f_right_filtered[(np.abs(W_right)>filter_freq)] = 0
        # # convert filtered signal back to time domain
        # gyro_right_smoothed = irfft(f_right_filtered)

        # # Calculate fourier transform of right gyroscope data to convert to frequency domain
        # W_left = fftfreq(len(self.data['gyro_left']), d=self.data['time_from_start'][1]-self.data['time_from_start'][0])
        # f_gyro_left = rfft(self.data['gyro_left'])
        # # Filter out right gyroscope signal above 6 Hz
        # f_left_filtered = f_gyro_left.copy()
        # f_left_filtered[(np.abs(W_left)>filter_freq)] = 0
        # # convert filtered signal back to time domain
        # gyro_left_smoothed = irfft(f_left_filtered)

        # Filtering with moving average

        N_win = 15
        # Padding the data
        gyro_right_padded = np.pad(self.data['gyro_right'], (N_win//2, N_win-1-N_win//2), mode='edge')
        # Smoothing using moving average
        gyro_right_smoothed = np.convolve(gyro_right_padded, np.ones(N_win)/N_win, mode='valid')
        
        # Converting back to list
        self.data['gyro_right_smoothed'] = list(gyro_right_smoothed)
        
        
        # Padding the data
        gyro_left_padded = np.pad(self.data['gyro_left'], (N_win//2, N_win-1-N_win//2), mode='edge')
        # Smoothing using moving average
        gyro_left_smoothed = np.convolve(gyro_left_padded, np.ones(N_win)/N_win, mode='valid')
        
        # Converting back to list
        self.data['gyro_left_smoothed'] = list(gyro_left_smoothed)

        # Derive distance based on data:
        self.data['dist_m'][:] = get_distance_m(self.data['time_from_start'], gyro_left_smoothed,
                                            gyro_right_smoothed)
        # Calculate displacement for the data['trajectory']:
        self.data['disp_m'][:] = get_displacement_m(self.data['time_from_start'], gyro_left_smoothed,
                                                gyro_right_smoothed)
        # Find heading angle over time:
        self.data['heading_deg'][:] = get_heading_deg(self.data['time_from_start'], gyro_left_smoothed,
                                                    gyro_right_smoothed)
        # Calculate Velocity over time:
        self.data['velocity'][:] = get_velocity_m_s(self.data['time_from_start'], gyro_left_smoothed,
                                                gyro_right_smoothed)
        # Process data['trajectory']:
        self.data['trajectory'][:] = get_top_traj(self.data['disp_m'], self.data['velocity'], self.data['heading_deg'],
                                                self.data['time_from_start'])  # use displacement

        if not self.axs[0].lines:
        # If there is no line, create a new line
            self.axs[0].plot(self.data['time_from_start'], self.data['dist_m'], label="Distance")
        else:
            # If a line exists, update its data
            self.axs[0].lines[0].set_data(self.data['time_from_start'], self.data['dist_m'])

        if not self.axs[1].lines:
            self.axs[1].plot([i[0] for i in self.data['trajectory']], [i[1] for i in self.data['trajectory']], label="Trajectory")
        else:
            self.axs[1].lines[0].set_data([i[0] for i in self.data['trajectory']], [i[1] for i in self.data['trajectory']])

        # Similarly, update the other subplots
        if not self.axs[2].lines:
           self.axs[2].plot(self.data['time_from_start'], self.data['heading_deg'], label="Heading")
        else:
            self.axs[2].lines[0].set_data(self.data['time_from_start'], self.data['heading_deg'])

        if not self.axs[3].lines:
            self.axs[3].plot(self.data['time_from_start'], self.data['velocity'], label="Velocity")
        else:
            self.axs[3].lines[0].set_data(self.data['time_from_start'], self.data['velocity'])

        print(self.data['dist_m'][-1], self.data['heading_deg'][-1], self.data['velocity'][-1], self.data['trajectory'][-1])

        for ax in self.axs:
            ax.relim()
            ax.autoscale()

        # Redraw the canvas
        # canvas_widget = self.canvas.get_tk_widget()
        self.canvas.draw()
        self.canvas.flush_events()  


        if not self.recording_stopped:
            self.tab.after(0, self.update_graphs)



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

                    initial_loop = True
                    while True:
                        if self.recording_started == False:
                            self.recording_stopped = False
                            await asyncio.sleep(0)
                            continue

                        if self.recording_stopped == True:
                            self.recording_started = False
                            # await left_client.stop_notify(ch)
                            # await right_client.stop_notify(ch)

                            update_graphs_thread.join()
                            break

                        if initial_loop:
                            self.start_time = time.time()
                            initial_loop = False

                            update_graphs_thread = threading.Thread(target=self.update_graphs, daemon=True)
                            update_graphs_thread.start()

                        # await left_client.start_notify(ch, self.update_data, side='left')
                        # await right_client.start_notify(ch, self.update_data, side='right')

                        read_message_left = await left_client.read_gatt_char(ch)
                        read_message_right = await right_client.read_gatt_char(ch)

                        self.parse_data(read_message_left, read_message_right)

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

                        try:
                            pass
                        
                            # read_message1 = await left_client.read_gatt_char(ch)
                            # print('read left')
                            # read_message2 = await right_client.read_gatt_char(ch)
                            # print('read right')
                        except OSError:
                            print('gatt read error')

        except BleakError as e:
            print(f"Failed to connect: {e}")
        except TimeoutError as e:
            print(f"Timeout error: {e}")

        self.save_data()

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

        devices = await BleakScanner.discover(timeout=8.0)
        smarthub_id = "9999"
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

    def start_recording(self):
        if self.start_recording_button['text'] == 'Start Recording':
            print('recording started')
            self.recording_started = True


            self.start_recording_button['text'] = 'Stop Recording'
        elif self.start_recording_button['text'] == 'Stop Recording':
            print('recording stopped')
            self.recording_stopped = True

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
            'trajectory': []
        }

        self.recording_started = False
        self.recording_stopped = True

        self.last_time_left = 0
        self.last_time_right = 0
        self.start_time_left = 0
        self.start_time_right = 0


    def save_data(self):
        max_len = max(len(v) for v in self.data.values())

        # Normalize the lengths of lists by filling with NaN
        for key in self.data:
            self.data[key] += [np.nan] * (max_len - len(self.data[key]))
        df = pd.DataFrame(self.data)

        df.fillna('')

        df.to_csv('test_data.csv', index=False)


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
        ttk.Button(self.tab, text='Connect', command=lambda: self.connect_smarthubs(smarthub_id.get())).grid(row=4, column=2, pady=10, sticky='nsew')
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
