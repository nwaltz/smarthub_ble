from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import glob
import os
import matplotlib.pyplot as plt
import time
import json
import numpy as np
import math


try:
    from base_ble.calc import get_displacement_m, get_distance_m, get_velocity_m_s, get_top_traj, get_heading_deg
    from gui.view_data_tab import ViewData
except ModuleNotFoundError:
    from calc import get_displacement_m, get_distance_m, get_velocity_m_s, get_top_traj, get_heading_deg
    from ..gui.view_data_tab import ViewData

from scipy.spatial import cKDTree
from scipy.optimize import fsolve


def compute_net_loss(points1, points2):
    """
    Computes the net loss as the sum of the distances between each point in points1
    and its closest point in points2.
    
    :param points1: List of (x, y) tuples representing the first set of points.
    :param points2: List of (x, y) tuples representing the second set of points.
    :return: Net loss (sum of closest point distances).
    """
    # Convert lists to numpy arrays for efficient computation
    points1 = np.array(points1)
    points2 = np.array(points2)

    # Build KDTree for efficient nearest-neighbor search
    tree = cKDTree(points2)

    # Find nearest neighbor distances for all points in points1
    distances, _ = tree.query(points1)

    rms_distance = np.sqrt(np.mean(distances ** 2))

    return rms_distance

def minimize_turnaround(params, test):
    ml, mr, W = params


    if 'elapsed_time_s' in test:
        time_from_start = np.array(test['elapsed_time_s'])
    elif 'time_from_start' in test:
        time_from_start = np.array(test['time_from_start'])
    else:
        raise ValueError("No time data found")
    
    min_len = min(len(time_from_start), len(test['gyro_left_smoothed']), len(test['gyro_right_smoothed']))

    time_from_start = time_from_start[:min_len]
    rot_l = np.array(test['gyro_left_smoothed'])[:min_len]
    rot_r = np.array(test['gyro_right_smoothed'])[:min_len]

    disp_m = np.array(get_displacement_m(time_from_start, rot_l*ml, rot_r*mr, dist_wheels=W, diameter=1))
    heading = np.array(get_heading_deg(time_from_start, rot_l*ml, rot_r*mr, dist_wheels=W, diameter=1))
    velocity = np.array(get_velocity_m_s(time_from_start, rot_l*ml, rot_r*mr, dist_wheels=W, diameter=1))
    traj = np.array(get_top_traj(disp_m, velocity, heading, time_from_start, dist_wheels=W, diameter=1))

    # finds the start and end of the turnaround, make it constant between runs
    if not hasattr(minimize_turnaround, "start_turn"):
        heading_diff = [0]
        for i in range(1, len(heading)):
            heading_diff.append(heading[i] - heading[i-1])

        turning_points = np.where(np.abs(np.array(heading_diff)) > 0.1)
        if turning_points:
            minimize_turnaround.start_turn, minimize_turnaround.end_turn = (largest_consecutive_group(turning_points[0])[0], largest_consecutive_group(turning_points[0])[-1])
            print(time_from_start[minimize_turnaround.start_turn], time_from_start[minimize_turnaround.end_turn])

    start_turn = minimize_turnaround.start_turn
    end_turn = minimize_turnaround.end_turn

    print(10 - (disp_m[start_turn] + (disp_m[-1] - disp_m[end_turn])))

    # net_distance_error = (10 - (disp_m[start_turn] + (disp_m[-1] - disp_m[end_turn])))
    net_distance_error = (10 - disp_m[-1])

    halfway_point = disp_m[-1] / 2

    # quarter_point = disp_m[-1] / 4
    # three_quarter_point = disp_m[-1] * 3 / 4

    distance_error = 5 - halfway_point

    first_half = traj[:start_turn]
    second_half = traj[end_turn:]

    straight_line_start = np.linspace(np.array([0,0]), np.array(first_half[-1]), 3000)
    straight_line_end = np.linspace(np.array(second_half[0]), np.array([0,0]), 3000)

    turn_loss = (compute_net_loss(first_half, straight_line_start) + compute_net_loss(second_half, straight_line_end)) / 2

    # Compute the net loss between the two halves
    net_loss = compute_net_loss(first_half, second_half)

    # print()
    # print(net_loss, distance_error, turn_loss)
    # print(net_loss, net_distance_error, turn_loss)

    # return net_loss, distance_error, heading_diff
    return net_loss, net_distance_error, turn_loss

def minimize_turnaround_bias(params, tests):
    ml, mr, al, ar, W = params

    print(params)

    turnaround, loop = tests


    if 'elapsed_time_s' in turnaround:
        time_from_start = np.array(turnaround['elapsed_time_s'])
    elif 'time_from_start' in turnaround:
        time_from_start = np.array(turnaround['time_from_start'])
    else:
        raise ValueError("No time data found")
    
    min_len = min(len(time_from_start), len(turnaround['gyro_left_smoothed']), len(turnaround['gyro_right_smoothed']))

    time_from_start = time_from_start[:min_len]
    rot_l = np.array(turnaround['gyro_left_smoothed'])[:min_len]
    rot_r = np.array(turnaround['gyro_right_smoothed'])[:min_len]

    left_velocity = np.array(get_velocity_m_s(time_from_start, rot_l, rot_l, dist_wheels=W, diameter=1))
    right_velocity = np.array(get_velocity_m_s(time_from_start, rot_r, rot_r, dist_wheels=W, diameter=1))

    rot_l = rot_l * ml - al * (left_velocity - right_velocity)
    rot_r = rot_r * mr - ar * (right_velocity - left_velocity)

    disp_m = np.array(get_displacement_m(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1))
    heading = np.array(get_heading_deg(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1))
    velocity = np.array(get_velocity_m_s(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1))
    traj = np.array(get_top_traj(disp_m, velocity, heading, time_from_start, dist_wheels=W, diameter=1))

    # finds the start and end of the turnaround, make it constant between runs
    if not hasattr(minimize_turnaround, "start_turn"):
        heading_diff = [0]
        for i in range(1, len(heading)):
            heading_diff.append(heading[i] - heading[i-1])

        turning_points = np.where(np.abs(np.array(heading_diff)) > 0.1)
        minimize_turnaround.start_turn, minimize_turnaround.end_turn = (largest_consecutive_group(turning_points[0])[0], largest_consecutive_group(turning_points[0])[-1])
        print(minimize_turnaround.start_turn, minimize_turnaround.end_turn)

    start_turn = minimize_turnaround.start_turn
    end_turn = minimize_turnaround.end_turn


    net_distance_error = (10 - (disp_m[start_turn] + (disp_m[-1] - disp_m[end_turn]))) / 2

    first_half = traj[:start_turn]
    second_half = traj[end_turn:]
    straight_line_start = np.linspace(np.array([0,0]), np.array(first_half[-1]), 3000)
    straight_line_end = np.linspace(np.array(second_half[0]), np.array([0,0]), 3000)
    turn_loss = (compute_net_loss(first_half, straight_line_start) + compute_net_loss(second_half, straight_line_end)) / 2

    net_loss = compute_net_loss(first_half, second_half)

    # print()
    # print(net_loss, net_distance_error, turn_loss)

    if 'elapsed_time_s' in loop:
        time_from_start = np.array(loop['elapsed_time_s'])
    elif 'time_from_start' in loop:
        time_from_start = np.array(loop['time_from_start'])
    else:
        raise ValueError("No time data found")
    
    min_len = min(len(time_from_start), len(loop['gyro_left_smoothed']), len(loop['gyro_right_smoothed']))

    time_from_start = time_from_start[:min_len]
    rot_l = np.array(loop['gyro_left_smoothed'])[:min_len]
    rot_r = np.array(loop['gyro_right_smoothed'])[:min_len]

    left_velocity = np.array(get_velocity_m_s(time_from_start, rot_l, rot_l, dist_wheels=W, diameter=1))
    right_velocity = np.array(get_velocity_m_s(time_from_start, rot_r, rot_r, dist_wheels=W, diameter=1))

    rot_l = rot_l * ml + al * (left_velocity - right_velocity)
    rot_r = rot_r * mr + ar * (right_velocity - left_velocity)

    disp_m = np.array(get_displacement_m(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1))
    heading = np.array(get_heading_deg(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1))
    velocity = np.array(get_velocity_m_s(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1))
    traj = np.array(get_top_traj(disp_m, velocity, heading, time_from_start, dist_wheels=W, diameter=1))


    traj_loss = (traj[-1][0]**2 + traj[-1][1]**2)**0.5
    # trajectory_error_y = traj[-1][1]/10

    heading_loss = 360 - heading[-1]

    return net_loss, net_distance_error, turn_loss, traj_loss, heading_loss



def connect_to_db_certificate(path_to_cert):
    uri = "mongodb+srv://smarthub.gbdlpxs.mongodb.net/?authSource=$external&authMechanism=MONGODB-X509"
    client = MongoClient(uri, tls=True, tlsCertificateKeyFile=path_to_cert)
    return client


def get_runs(database):
    test_collection = database.Smarthub.test_collection
    test_config = database.Smarthub.test_config

    collections = database.Smarthub.list_collection_names()
    print(collections)

    # for test in test_config.find({'smarthub_id': '2222'}):
    #     print(test['calibration_name'])

    recent_config = test_config.find_one({'smarthub_id': '2222', 'calibration_name': 'traj_trial_3'})

    # print(recent_config['wheel_dist'])
    # print(recent_config['left_gain'])
    # print(recent_config['right_gain'])

    # print(recent_config['raw_data'].keys())

    original_params = [recent_config['left_gain'], recent_config['right_gain'], recent_config['wheel_dist']]

    # loop_nate = test_collection.find_one({'user_id': 'calibration_test', 'test_name': '150m loop nate'})
    # loop_jack = test_collection.find_one({'user_id': 'calibration_test', 'test_name': '150m loop jack'})
    # five_m_straight = test_collection.find_one({'user_id': 'calibration_test', 'test_name': '5m turnaround'})

    # display_trajectory(recent_config['raw_data'], params=original_params)

    # res = fsolve(minimize_turnaround, original_params, args=recent_config['raw_data'])

    # for test in test_collection.find({}):


    user_id = 'renee_trial'
    test_name = '20m_v3'

    # test = test_collection.find({'user_id': user_id, 'test_name': test_name})
    # display_trajectory(test[1], params=original_params)

    # for test in test_collection.find({"user_id": {"$regex": "^ritvik"}}):
    #     print(test['user_id'], test['test_name'])

    for i in range(1, 6):
        test_name = f"20m_v{i}"
        test = test_collection.find({'user_id': user_id, 'test_name': test_name})

        index = 0

        test_data = dict(test[index])

        test_data['velocity'] = get_velocity_m_s(test_data['elapsed_time_s'], np.array(test_data['gyro_left_smoothed'])*original_params[0], np.array(test_data['gyro_right_smoothed'])*original_params[1], dist_wheels=original_params[2], diameter=1)

        # display_trajectory(test_data, params=original_params)

        # print(test_data.keys())



        ViewData.download_metrics(test_data, f"/Users/nwaltz/Documents/smarthub_videos/{user_id.split('_')[0]}_{test_name.split('_')[1]}.csv")
        # ViewData.download_metrics(test_data, f"/Users/nwaltz/Documents/smarthub_videos/{user_id.split('_')[0]}_v{index+1}.csv")

    




    # for i in range(1, 5):
    #     turnaround = test_collection.find_one({'user_id': 'distance_jack_1', 'test_name': f"50m_v{i}"})

    #     display_trajectory(turnaround, params=original_params, show=False)

    # for test in test_collection.find({'user_id': user_id}):
    #     print(test['test_name'])


    # test = test_collection.find_one({'user_id': user_id, 'test_name': test_name})
    # tests = test_collection.find({'user_id': user_id})

    # tests = [test for test in tests]    

    # display_trajectory(five_m_straight)
    # display_trajectory(recent_config['raw_data'], params=original_params)
    # display_trajectory(test, params=original_params, show=False)
    # display_trajectory(loop_jack)
    # minimize_turnaround(original_params, five_m_straight)

    # params = [20,20,20]

    # display_trajectory(recent_config['raw_data'], params=original_params)
    # display_multiple_trajectories(tests, original_params)

    # res = fsolve(minimize_turnaround, original_params, args=recent_config['raw_data'])

    # display_trajectory(test, params=original_params)
    # display_trajectory(recent_config['raw_data'], params=original_params)
    # display_trajectory(tests[-1], params=original_params)
    # display_multiple_trajectories(tests, original_params)

def display_multiple_trajectories(tests, params=None):
    # display all trajectories on the same plot
    fig_width = int((len(tests) ** 0.5))
    fig_height = int(len(tests) // fig_width + 1)
    fig, axs = plt.subplots(fig_height,fig_width)

    if params is not None:
        ml, mr, W = params
    else:
        ml, mr, W = (20, 20, 22.3)

    # bl = 0.05*200
    # br = 0.05*200

    bl = 0
    br = 0
    

    for i, test in enumerate(tests):
        if 'elapsed_time_s' in test:
            time_from_start = np.array(test['elapsed_time_s'])
        elif 'time_from_start' in test:
            time_from_start = np.array(test['time_from_start'])
        else:
            raise ValueError("No time data found")
        
        min_len = min(len(time_from_start), len(test['gyro_left_smoothed']), len(test['gyro_right_smoothed']))

        time_from_start = time_from_start[:min_len]
        # rot_l = np.array(test['gyro_left_smoothed'])[:min_len]
        # rot_r = np.array(test['gyro_right_smoothed'])[:min_len]

        rot_l = np.array(test['gyro_left_smoothed'])[:min_len]
        rot_r = np.array(test['gyro_right_smoothed'])[:min_len]

        original_velocity = get_velocity_m_s(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1)


        rot_l = rot_l * ml + bl
        rot_r = rot_r * mr + br

        

        dist_m = get_distance_m(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1)
        heading = get_heading_deg(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1)
        velocity = get_velocity_m_s(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=1)
        traj = get_top_traj(dist_m, velocity, heading, time_from_start, dist_wheels=W, diameter=1)

        traj_x = [x[0] for x in traj]
        traj_y = [x[1] for x in traj]

        axs[i // fig_width, i % fig_width].plot(traj_x, traj_y, color="blue")

        axs[i // fig_width, i % fig_width].set_aspect('equal', adjustable='datalim')
        axs[i // fig_width, i % fig_width].set_title(test['test_name'], fontsize=5)
    
    plt.show()

# def largest_consecutive_group(nums):
#     longest, current = [], [nums[0]]

#     for i in range(1, len(nums)):
#         if nums[i] == nums[i - 1] + 1:
#             current.append(nums[i])
#         else:
#             if len(current) > len(longest):
#                 longest = current
#             current = [nums[i]]

#     return max(longest, current, key=len)

def largest_consecutive_group(nums, min_size=60, threshold=0.5):
    groups, current = [], [nums[0]]

    for i in range(1, len(nums)):
        if nums[i] == nums[i - 1] + 1:
            current.append(nums[i])
        else:
            if len(current) > min_size and any(x > threshold for x in current):
                groups.extend(current)
            current = [nums[i]]

    if len(current) > min_size and any(x > threshold for x in current):
        groups.extend(current)

    return groups



def display_trajectory(test, params=None, show=True):

    if len(params) == 5:
        ml, mr, bl, br, W = params
    elif len(params) == 3:
        ml, mr, W = params
        bl, br = (0, 0)
    else:
        ml, mr, bl, br, W = (20, 20, 0, 0, 20.907)
    # print(doc['test_name'])

    D = 1

    # ml, mr, W = (20, 20, 20.907)

    fig, axs = plt.subplots(2,2)


    if 'elapsed_time_s' in test:
        time_from_start = np.array(test['elapsed_time_s'])
    elif 'time_from_start' in test:
        time_from_start = np.array(test['time_from_start'])
    else:
        raise ValueError("No time data found")
    
    min_len = min(len(time_from_start), len(test['gyro_left_smoothed']), len(test['gyro_right_smoothed']))

    time_from_start = time_from_start[:min_len]
    rot_l = np.array(test['gyro_left_smoothed'])[:min_len]
    rot_r = np.array(test['gyro_right_smoothed'])[:min_len]

    original_velocity = get_velocity_m_s(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=D)

    # axs[0,0].plot(time_from_start, (np.array(rot_l) - np.array(rot_r)), color="blue")

    rot_l = rot_l * ml + bl
    rot_r = rot_r * mr + br 

    # rot_l = rot_l * ml + bl
    # rot_r = rot_r * mr + br

    

    dist_m = get_distance_m(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=D)
    test['dist_m'] = dist_m
    disp_m = get_displacement_m(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=D)
    test['disp_m'] = disp_m
    heading = get_heading_deg(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=D)
    test['heading'] = heading
    velocity = get_velocity_m_s(time_from_start, rot_l, rot_r, dist_wheels=W, diameter=D)
    test['velocity'] = velocity
    traj = get_top_traj(dist_m, velocity, heading, time_from_start, dist_wheels=W, diameter=D)
    test['traj'] = traj

    axs[0,0].plot(time_from_start, velocity, color="blue")


    heading_diff = [0]
    for i in range(1, len(heading)):
        heading_diff.append(heading[i] - heading[i-1])

    heading_diff_diff = [0]
    for i in range(1, len(heading_diff)):
        heading_diff_diff.append(heading_diff[i] - heading_diff[i-1])
    test['heading_diff'] = heading_diff
    test['heading_diff_diff'] = heading_diff_diff

    # turning_points = np.where(np.abs(np.array(heading_diff)) > 0.1)
    # # print(turning_points)
    # start, end = (largest_consecutive_group(turning_points[0])[0], largest_consecutive_group(turning_points[0])[-1])
    # print(start, end)

    with open("data.json", "w") as json_file:
        json.dump(test, json_file, indent=2)

    traj_x = [x[0] for x in traj]
    traj_y = [x[1] for x in traj]

    # print(disp_m[-1], traj[-1])

    print((traj[-1][0]**2 + traj[-1][1]**2)**0.5)

    # axs[0,0].plot(time_from_start, heading, color="blue")
    axs[1,0].plot(traj_x, traj_y, color="blue")
    axs[0,1].plot(time_from_start, heading_diff, color="blue")
    axs[0,1].plot(time_from_start, 0.0*np.ones(len(time_from_start)), color="red")
    axs[1,1].plot(time_from_start, np.array(test['gyro_left_smoothed'])*ml, color="blue")
    axs[1,1].plot(time_from_start, np.array(test['gyro_right_smoothed'])*mr, color="red")
    axs[1,0].set_aspect('equal', adjustable='datalim')

    # plt.plot(time_from_start, rot_l*ml, color="blue")
    # plt.plot(time_from_start, rot_r*mr, color="red")


    # trajectory_error = (traj_x[-1]**2 + traj_y[-1]**2)**0.5

    # print(f"Total Distance: {disp_m[-1]}, Net Trajectory Error: {trajectory_error}, Error: {trajectory_error/disp_m[-1]}")

    if show:
        plt.show()

    # plt.plot(traj_x, traj_y, color="blue")
    # plt.show()

    # plt.Figure()

    # plt.plot(time_from_start, rot_l*ml)
    # plt.plot(time_from_start, rot_r*mr)

    # plt.show()
    

    


if __name__ == '__main__':
    file_path = '/'.join((os.path.dirname(os.path.abspath(__file__)).split('/'))[:-1])
    print(file_path)

    pem_files = glob.glob(file_path + '/*.pem')
    valid_file = False
    print(pem_files)
    if pem_files:
        for file in pem_files:
            # try:
                print('Authenticating with', file)
                db = connect_to_db_certificate(file)
                get_runs(db)
                # display_trajectory(db, 'calibration_test')
                # do_calibration(db)

                valid_file = True
                break
            # except Exception as e:
            #     print(e)