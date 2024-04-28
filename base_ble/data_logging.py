import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
import time
import asyncio
# from libraries.bleak import BleakScanner, BleakClient
from bleak import BleakScanner, BleakClient
from params import DATE_DIR, DATE_NOW
# Import the calculation functions:
from calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)

ch = "00002a56-0000-1000-8000-00805f9b34fb"

# Create vectors to keep track of data over time:
gyro_right = []
gyro_left = []
accel_right = []
accel_left = []
time_from_start = []
dist_m = []
disp_m = []
velocity = []
heading_deg = []
trajectory = []


async def convert_from_raw(data):

    accel_data = []
    gyro_data = []

    for i in range(4):
        # accel_data.append(int.from_bytes(data[2*i+2:2*i+3], 'little')/1000)
        # gyro_data.append(int.from_bytes(data[2*i+10:2*i+11], 'little')/100)

        accel_data.append((data[2*i+2] + data[2*i+3]*256) / 1000)  # bytes 2, 4, 6, 8 convert to true accel data

        gyro_data.append((data[2*i+10] + data[2*i+11]*256) / 100) # bytes 10, 12, 14, 16 convert to true gyro data

        if (data[0] & (1 << i)) == (1 << i):
            accel_data[i] *= -1

        if (data[1] & (1 << i)) == (1 << i):
            gyro_data[i] *= -1
    return accel_data, gyro_data


async def main():
    # Set up default addresses:
    address1 = '657318E9-C1ED-435B-88B4-AD3FCFE75EB7'
    address2 = '5CE4F17B-8694-4C13-AFC0-EF04A477ECDC'
    # Create plot figure and axes:
    fig, axs = plt.subplots(3)

    # Set overall title of figure:
    fig.suptitle('Plot of Displacement, Heading, and Trajectory over time')
    # Set x and y axes labels for first subplot:
    axs[0].set_xlabel('Time (sec)')
    axs[0].set_ylabel('Displacement (m)')
    # axs[0].set_ylabel('Right Angular Velocity (r/s)')
    # Set x and y axes labels for second subplot:
    axs[1].set_xlabel('Time (sec)')
    axs[1].set_ylabel('Heading (deg)')
    # axs[1].set_ylabel('Right Acceleration (m/s2)')
    # Set x and y axes labels for third subplot:
    axs[2].set_xlabel('X Trajectory (m)')
    axs[2].set_ylabel('Y Trajectory (m)')

    # Pull data for time, and wheel gyro data along main axis
    accel_flipper = True
    devices = await BleakScanner.discover(timeout=10.0)
    for d in devices:
        print(d)
        if d.name == 'Left Smarthub':
            print("Connected to Left")
            address1 = d.address
        if d.name == 'Right Smarthub':
            print("Connected to Right")
            address2 = d.address
    # await BleakScanner. find_device_by_filter(match_known_address)
    async with BleakClient(address1, cached=False) as client1:
        print(f"Connected to {address1}: {client1.is_connected}")
        async with BleakClient(address2, cached=False) as client2:
            print(f"Connected to {address2}: {client2.is_connected}")
            start_time = time.time()
            last_time = 0
            while 1:
                read_message1 = await client1.read_gatt_char(ch)
                read_message2 = await client2.read_gatt_char(ch)
                # Pull data out of message for both wheels
                data_right = [i for i in read_message1]
                data_left = [i for i in read_message2]
                # Convert data to acceleration and gyroscope readings
                accel_right_curr, gyro_right_curr = await convert_from_raw(data_right)
                accel_left_curr, gyro_left_curr = await convert_from_raw(data_left)
                # Add data to ongoing vectors:
                gyro_right.extend(gyro_right_curr)
                gyro_left.extend(gyro_left_curr)
                accel_right.extend(accel_right_curr)
                accel_left.extend(accel_left_curr)

                # find time since edata started being logged:
                time_curr = time.time()-start_time
                # Add current values to time vector
                for i in range(1, 5):
                    time_from_start.append(i*(time_curr-last_time)/4+last_time)
                last_time = time_curr

                # Derive distance based on data:
                dist_m[:] = get_distance_m(time_from_start, gyro_left, gyro_right)
                # Calculate displacement for the trajectory:
                disp_m[:] = get_displacement_m(time_from_start, gyro_left, gyro_right)
                # Find heading angle over time:
                heading_deg[:] = get_heading_deg(time_from_start, gyro_left, gyro_right)
                # Calculate Velocity over time:
                velocity[:] = get_velocity_m_s(time_from_start, gyro_left, gyro_right)
                # Process trajectory:
                trajectory[:] = get_top_traj(disp_m, velocity, heading_deg, time_from_start)  # use displacement
                # Clear plots:
                axs[0].clear()
                axs[1].clear()
                axs[2].clear()
                # Create a plot of Distance over time:
                axs[0].plot(time_from_start, dist_m)
                # Create a plot of heading over time:
                axs[1].plot(time_from_start, heading_deg)
                # Create a plot of trajectory:
                axs[2].plot([i[0] for i in trajectory], [i[1] for i in trajectory])
                plt.draw()
                plt.pause(0.1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Find x values of trajectory:
        x_traj = [i[0] for i in trajectory]
        # Find y values of trajectory:
        y_traj = [i[1] for i in trajectory]
        # place data into a data frame to save
        df = pd.DataFrame()
        df['elapsed_time_s'] = pd.Series(time_from_start)
        df['gyro_right'] = pd.Series(gyro_right)
        df['gyro_left'] = pd.Series(gyro_left)
        df['accel_right'] = pd.Series(accel_right)
        df['accel_left'] = pd.Series(accel_left)
        df['distance_m'] = pd.Series(dist_m)
        df['displacement_m'] = pd.Series(disp_m)
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
