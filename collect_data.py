from tkinter import *
import tkinter as tk
from tkinter import ttk
import cred

import numpy as np
import pandas as pd
from datetime import datetime
import os
import sys
import matplotlib.pyplot as plt
import time
import asyncio
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from bleak import BleakScanner, BleakClient
from params import DATE_DIR, DATE_NOW, left_gain, left_offset, right_gain, right_offset

from main_gui import remove_all_widgets, start_screen

# Import the calculation functions:
from base_ble.calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)

def grab_raw_data(q_send, q_recieve):

    async def read_messages():
        devices = await BleakScanner.discover(timeout=5.0)
        address1 = None
        address2 = None
        for d in devices:
            print(d)
            if d.name == 'Left Smarthub':
                print("Connected to Left")
                address1 = d.address
            if d.name == 'Right Smarthub':
                print("Connected to Right")
                address2 = d.address

        if not address1 or not address2:
            sys.exit()
            

        ch = "00002a56-0000-1000-8000-00805f9b34fb"

        async with BleakClient(address1, cached=False) as client1:
            print(f"Connected to {address1}: {client1.is_connected}")
            async with BleakClient(address2, cached=False) as client2:
                print(f"Connected to {address2}: {client2.is_connected}")

                start_message = None
                while start_message != 'run test':
                    start_message = q_send.get()

                started = False

                start_time = time.time()
                last_time = 0

                while True:
                    # asynchronously gets new data from ble
                    read_message1 = await client1.read_gatt_char(ch)
                    read_message2 = await client2.read_gatt_char(ch)

                    # get time values for data
                    time_curr = time.time() - start_time
                    time_vals = []
                    for i in range(1, 5):
                        time_vals.append(i * (time_curr - last_time) / 4 + last_time)
                    last_time = time_curr

                    if started:
                        # send data to main process
                        q_recieve.put({'left': read_message1, 
                                    'right': read_message2, 
                                    'time': time_vals})
                    
                    started = True
                    
                    ## figure out best way to exit this process    ##############################
                    if (q_send.empty() == False):
                        break
        return
        exit()          

    start_message = None
    while start_message != 'start':
        start_message = q_send.get()
    asyncio.run(read_messages())



def record_data(root, button_user_menu_right, button_user_menu_left, user_select_text, q_send, q_recieve):
    button_user_menu_right.destroy()
    button_user_menu_left.destroy()
    user_select_text.destroy()

    ch = "00002a56-0000-1000-8000-00805f9b34fb"

    # Create vectors to keep track of data over time:
    data = {}
    data['gyro_right'] = []
    data['gyro_left'] = []
    data['gyro_right_smoothed'] = []
    data['gyro_left_smoothed'] = []
    data['accel_right'] = []
    data['accel_left'] = []
    data['time_from_start'] = []
    data['dist_m'] = []
    data['disp_m'] = []
    data['velocity'] = []
    data['heading_deg'] = []
    data['trajectory'] = []

    async def main(button_connect_ble, user_id):
        button_connect_ble.pack_forget()

        fig = Figure(figsize=(8, 7), dpi=100)
        axs = []
        axs.append(fig.add_subplot(221))
        axs.append(fig.add_subplot(222))
        axs.append(fig.add_subplot(223))

        # Set overall title of figure:
        fig.suptitle('Plot of Displacement, Heading, and Trajectory over time')
        # Set x and y axes labels for the first subplot:
        axs[0].set_title('Displacement over time')
        axs[0].set_xlabel('Time (sec)')
        axs[0].set_ylabel('Displacement (m)')

        # Set x and y axes labels for the second subplot:
        axs[1].set_title('Heading over time')
        axs[1].set_xlabel('Time (sec)')
        axs[1].set_ylabel('Heading (deg)')

        # Set x and y axes labels for the third subplot:
        axs[2].set_title('Trajectory')
        axs[2].set_xlabel('X Trajectory (m)')
        axs[2].set_ylabel('Y Trajectory (m)')

        fig.tight_layout()

        # initialize canvas for matplotlib plotting
        canvas = FigureCanvasTkAgg(fig, master=root)

        async def convert_from_raw(raw_data):

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
        
        # still_plotting = True

        # saves data to local csv and to mongodb database
        def end_collect(root, final_data, canvas):

            # canvas.destroy()

            x_traj = [i[0] for i in final_data['trajectory']]
            # Find y values of data['trajectory']:
            y_traj = [i[1] for i in final_data['trajectory']]
            # place data into a data frame to save
            df = pd.DataFrame()
            df['elapsed_time_s'] = pd.Series(final_data['time_from_start'])
            df['gyro_right'] = pd.Series(final_data['gyro_right'])
            df['gyro_left'] = pd.Series(final_data['gyro_left'])
            df['gyro_right_smoothed'] = pd.Series(final_data['gyro_right_smoothed'])
            df['gyro_left_smoothed'] = pd.Series(final_data['gyro_left_smoothed'])
            df['accel_right'] = pd.Series(final_data['accel_right'])
            df['accel_left'] = pd.Series(final_data['accel_left'])
            df['distance_m'] = pd.Series(final_data['dist_m'])
            df['displacement_m'] = pd.Series(final_data['disp_m'])
            df['traj_x'] = pd.Series(x_traj)
            df['traj_y'] = pd.Series(y_traj)

            df.fillna('')
            # Generate output file
            filepath = os.path.join(DATE_DIR, '{0}.csv'.format(DATE_NOW))
            print(f'Saving data to {filepath}')
            # Check if the directory exists
            if not os.path.exists(DATE_DIR):
                # If it doesn't exist, create it
                os.makedirs(DATE_DIR)
            df.to_csv(filepath)

            # upload to cloud, get username/password info from cred file
            ### NEED TO FIGURE OUT HOW TO STORE THIS
            username = cred.username
            password = cred.password

            # rest api string for uploading to mongodb
            uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"

            # set up client, intiate database connection
            client = MongoClient(uri, server_api=ServerApi('1'))
            smarthub_db = client.Smarthub
            test_collection = smarthub_db.test_collection

            # generate id based on current time
            test_datetime = datetime.now()
            datetime_str = f"{test_datetime.month}/{test_datetime.day}/{test_datetime.year}_{test_datetime.hour}:{test_datetime.minute}"

            # new json for pushing to db
            post = {}
            post['_id'] = datetime_str
            post['elapsed_time_s'] = final_data['time_from_start']
            post['gyro_right'] = final_data['gyro_right']
            post['gyro_left'] = final_data['gyro_left']
            post['gyro_right_smoothed'] = final_data['gyro_right_smoothed']
            post['gyro_left_smoothed'] = final_data['gyro_left_smoothed']
            post['accel_right'] = final_data['accel_right']
            post['accel_left'] = final_data['accel_left']
            post['distance_m'] = final_data['dist_m']
            post['displacement_m'] = final_data['disp_m']
            post['traj_x'] = x_traj
            post['traj_y'] = y_traj
            post['user_id'] = user_id

            # insert new json into collection
            id = test_collection.insert_one(post).inserted_id

            # send kill command to other process
            q_send.put('end')
            # destroy window
            remove_all_widgets(root)
            start_screen(root)


        async def start_logging():
            start_time = time.time()
            last_time = 0

            # send start command to other process
            # q_send.put("start")
            q_send.put("run test")

            # create button for stop data recording
            button_frame_end = ttk.Frame(root)
            button_frame_end.pack()
            button_frame_end.place(x=700, y=515)
            button_start = ttk.Button(button_frame_end, text="stop data record", style="user_select.TButton",
                                    command=lambda: end_collect(root, data, canvas))
            button_start.pack()
                

            while True:
                # get all data in the queue, don't plot until the queue is empty
                while not q_recieve.empty():
                    new_data = q_recieve.get()
                    time_vals = [i for i in new_data['time']]
                    # print(time_vals)
                    data_right = [i for i in new_data['right']]
                    data_left = [i for i in new_data['left']]
                    # converts to real data, probably doesn't need to be await
                    accel_right_curr, gyro_right_curr = await convert_from_raw(data_right)
                    accel_left_curr, gyro_left_curr = await convert_from_raw(data_left)

                    # add in gains and offsets to calibrate readings
                    gyro_right_curr = [i*right_gain+right_offset for i in gyro_right_curr]
                    gyro_left_curr = [i*left_gain+left_offset for i in gyro_left_curr]
                    # Zero out small gyroscope readings from noise
                    for i in range(4):
                        if gyro_right_curr[i] < 0.02:
                            gyro_right_curr[i] = 0
                        if gyro_left_curr[i] < 0.02:
                            gyro_left_curr[i] = 0

                    data['gyro_right'].extend(gyro_right_curr)
                    data['accel_right'].extend(accel_right_curr)
                    data['gyro_left'].extend(gyro_left_curr)
                    data['accel_left'].extend(accel_left_curr)

                    data['time_from_start'].extend(time_vals)

                    # ### fix this ###########################################################################

                    # time_curr = time.time() - start_time
                    # for i in range(1, 5):
                    #     data['time_from_start'].append(i * (time_curr - last_time) / 4 + last_time)
                    # last_time = time_curr

                    # ########################################################################################



                if not data['time_from_start']:
                    continue

                # print(data['time_from_start'][-1])

                N_win = 15
                # Padding the data
                gyro_right_padded = np.pad(data['gyro_right'], (N_win//2, N_win-1-N_win//2), mode='edge')
                # Smoothing using moving average
                gyro_right_smoothed = np.convolve(gyro_right_padded, np.ones(N_win)/N_win, mode='valid')

                # Converting back to list
                data['gyro_right_smoothed'] = list(gyro_right_smoothed)

                # Padding the data
                gyro_left_padded = np.pad(data['gyro_left'], (N_win//2, N_win-1-N_win//2), mode='edge')
                # Smoothing using moving average
                gyro_left_smoothed = np.convolve(gyro_left_padded, np.ones(N_win)/N_win, mode='valid')

                # Converting back to list
                data['gyro_left_smoothed'] = list(gyro_left_smoothed)

                # Derive distance based on data:
                data['dist_m'][:] = get_distance_m(data['time_from_start'], gyro_left_smoothed,
                                                   gyro_right_smoothed)
                # Calculate displacement for the data['trajectory']:
                data['disp_m'][:] = get_displacement_m(data['time_from_start'], gyro_left_smoothed,
                                                       gyro_right_smoothed)
                # Find heading angle over time:
                data['heading_deg'][:] = get_heading_deg(data['time_from_start'], gyro_left_smoothed,
                                                         gyro_right_smoothed)
                # Calculate Velocity over time:
                data['velocity'][:] = get_velocity_m_s(data['time_from_start'], gyro_left_smoothed,
                                                       gyro_right_smoothed)
                # Process data['trajectory']:
                data['trajectory'][:] = get_top_traj(data['disp_m'], data['velocity'], data['heading_deg'],
                                                     data['time_from_start'])  # use displacement

                # Update the data in the existing lines without clearing the entire axis
                if not axs[0].lines:
                # If there is no line, create a new line
                    axs[0].plot(data['time_from_start'], data['dist_m'], label="Distance")
                else:
                    # If a line exists, update its data
                    axs[0].lines[0].set_data(data['time_from_start'], data['dist_m'])

                # Similarly, update the other subplots
                if not axs[1].lines:
                    axs[1].plot(data['time_from_start'], data['heading_deg'], label="Heading")
                else:
                    axs[1].lines[0].set_data(data['time_from_start'], data['velocity'])

                if not axs[2].lines:
                    axs[2].plot([i[0] for i in data['trajectory']], [i[1] for i in data['trajectory']], label="Trajectory")
                else:
                    axs[2].lines[0].set_data([i[0] for i in data['trajectory']], [i[1] for i in data['trajectory']])


                # axs[0].legend()
                # axs[1].legend()
                # axs[2].legend()
                    
                for ax in axs:
                    ax.relim()
                    ax.autoscale()

                # Redraw the canvas
                canvas_widget = canvas.get_tk_widget()
                canvas_widget.pack(fill=tk.BOTH, expand=True)
                canvas.draw()
                canvas.flush_events()            

        
        if not q_recieve.empty():
            check_ble = q_recieve.get()
            if check_ble == 'no connection':
                print("No connection to BLE devices")
                button_connect_ble.pack()
                main(button_connect_ble, user_id)

        frame_start_logging = ttk.Frame(root)
        frame_start_logging.pack()
        frame_start_logging.place(x=450,y=500)
        button_start_logging = ttk.Button(connect_ble, text="start logging", style="user_select.TButton", command=lambda: asyncio.run(start_logging()))
        button_start_logging.pack()



    style = ttk.Style()
    style.map("TEntry",
            fieldbackground=[("active", "white"), ("!focus", "gray")],
            foreground=[("active", "black"), ("!focus", "gray")])

    ### set up text box for user id submission
    # style.configure("Background.TLabel", background="gray", foreground='white')
    style.configure("Background.TLabel", background="#313131", foreground='white')
    userid_select_text = ttk.Frame(root)
    userid_select_text.place(x=400,y=254)
    userlabel_select_text = ttk.Label(userid_select_text, text="6 Digit Operator ID:", font=("Verdana", 14), style='Background.TLabel')
    userlabel_select_text.pack()

    userid_box_info_text = "e.g. 654321"
    userid_entry_box = ttk.Frame(root)
    userid_entry_box.pack()
    userid_entry_box.place(x=600,y=250) # place on screen
    userid_entry_var = tk.StringVar()
    userid_entry = ttk.Entry(userid_entry_box, textvariable=userid_entry_var)
    userid_entry.insert(0, userid_box_info_text)    # put instructions in background to include data
    userid_entry.pack()

    def userid_submit(button_connect_ble):
        user_input = userid_entry.get()
        q_send.put("start")

        asyncio.run(main(button_connect_ble, user_input))


        


    connect_ble = ttk.Frame(root)
    connect_ble.pack()
    connect_ble.place(x=450,y=300)
    button_connect_ble = ttk.Button(connect_ble, text="connect ble devices", style="user_select.TButton", command=lambda: userid_submit(button_connect_ble))
    button_connect_ble.pack()

    
