from scipy.optimize import minimize, fsolve
import numpy as np
import json
import matplotlib.pyplot as plt

try:
    from base_ble.params import (
        WHEEL_DIAM_IN,
        DIST_WHEELS_IN,
        IN_TO_M
    )
    from base_ble.calc import (
        get_displacement_m,
        get_distance_m,
        get_velocity_m_s,
        get_heading_deg,
        get_top_traj
    )
except ModuleNotFoundError:
    from params import (
        WHEEL_DIAM_IN,
        DIST_WHEELS_IN,
        IN_TO_M
    )
    from calc import (
        get_displacement_m,
        get_distance_m,
        get_velocity_m_s,
        get_heading_deg,
        get_top_traj
    )

def calibration_setup(calibration_list):

    pauses = [val for val in calibration_list if 'pause' in val['name']]
    forwards = [val for val in calibration_list if 'forward' in val['name']]
    turnlefts = [val for val in calibration_list if 'turnleft' in val['name']]
    turnrights = [val for val in calibration_list if 'turnright' in val['name']]

    params = [24, 26, 1, 1, 0, 0]

    readings = [pauses, forwards, turnlefts, turnrights]

    res = minimize(minimize_function, params, args=(readings))
    # res = manual_calibration(params, readings, calibration_list)

    return res


def minimize_function_broken(params, readings):

    D, W, ml, mr, bl, br = params
    pauses, forwards, turnlefts, turnrights = readings

    error = 0

    # for pause in pauses:
    #     times = pause['time_from_start']
    #     gyro_left = pause['gyro_left']
    #     gyro_right = pause['gyro_right']

    #     length = len(times)

    #     error_pause = 0
    #     for i in range(length):
    #         error_pause = mr/length*gyro_right[i] - br + ml/length*gyro_left[i] - bl

    #     error += abs(error_pause)

    for forward in forwards:
        times = np.array(forward['time_from_start'])
        gyro_left = np.array(forward['gyro_left'])
        gyro_right = np.array(forward['gyro_right'])

        length = len(times)

        # distance_left = 0
        # distance_right = 0
        # for i in range(length - 1):
        #     distance_left += (gyro_left[i]*ml + bl) * (times[i+1] - times[i])
        #     distance_right += (gyro_right[i]*mr + br) * (times[i+1] - times[i])

        distance_left = get_distance_m(times, gyro_left*ml+bl, gyro_left*ml+bl, D, W)
        distance_right = get_distance_m(times, gyro_right*mr+br, gyro_right*mr+br, D, W)

        # dist_m = [0]
        # for i in range(len(gyro_right) - 1):
        #     # Wheel rotation in time step:
        #     dx_r = ((gyro_left[i]*ml+bl)+(gyro_right[i]*mr+br))/2 * (times[i + 1] - times[i])
        #     # Change in distance over time step:
        #     dx_m = dx_r * (D * IN_TO_M / 2)
        #     # Append last change to overall distance travelled:
        #     dist_m.append(dx_m + dist_m[-1])


        # print(dist_m[-1])
        # error += abs(dist_m[-1] - 5)
        # print(abs(5 - distance_left[-1]))
        # print(abs(5 - distance_right[-1]))
        error += abs(5 - distance_left[-1])
        error += abs(5 - distance_right[-1])

    left_headings = 0

    for turnleft in turnlefts:
        times = np.array(forward['time_from_start'])
        gyro_left = np.array(forward['gyro_left'])
        gyro_right = np.array(forward['gyro_right'])

        length = len(times)

        heading_left = get_heading_deg(times, gyro_left*ml+bl, gyro_right*mr+br, D, W)

        left_headings += heading_left[-1]

        error += abs(180 + heading_left[-1])

    print('left_headings: ', left_headings)

    right_headings = 0
    for turnright in turnrights:
        times = np.array(forward['time_from_start'])
        gyro_left = np.array(forward['gyro_left'])
        gyro_right = np.array(forward['gyro_right'])

        length = len(times)

        heading_right = get_heading_deg(times, gyro_left*ml+bl, gyro_right*mr+br, D, W)
        print(turnright['name'])
        print('headings: ', heading_right[-1])

        right_headings += heading_right[-1]

        error += abs(180 - heading_right[-1])

    print('right_headings: ', right_headings)

    return error

def manual_calibration(params, calibration_list):

    D, W, ml, mr, bl, br = params

    forwards = [val for val in calibration_list if 'forward' in val['name']]
    turnrights = [val for val in calibration_list if 'turnright' in val['name']]
    turnlefts = [val for val in calibration_list if 'turnleft' in val['name']]
    pauses = [val for val in calibration_list if 'pause' in val['name']]

    headings = []

    print('pauses')
    for pause in pauses:
        times = pause['time_from_start']
        gyro_left = pause['gyro_left']
        gyro_right = pause['gyro_right']

        distance_left = get_distance_m(times, gyro_left, gyro_right, D, W)
        distance_right = get_distance_m(times, gyro_right, gyro_right, D, W)
        heading = get_heading_deg(times, gyro_left, gyro_right, D, W)

        print(distance_left[-1])
        print(distance_right[-1])
        print(heading[-1])
        print()

    print('forwards')
    left_distances = []
    right_distances = []
    for forward in forwards:
        times = forward['time_from_start']
        gyro_left = forward['gyro_left']
        gyro_right = forward['gyro_right']

        left_distances.append(get_distance_m(times, gyro_left*ml, gyro_left*ml, D, W)[-1])
        right_distances.append(get_distance_m(times, gyro_right*mr, gyro_right*mr, D, W)[-1])

        print(left_distances[-1])
        print(right_distances[-1])
        print()

    print('Left Distances: ', np.sum(left_distances))
    print('Right Distances: ', np.sum(right_distances))

    mr = 20/np.sum(right_distances)
    ml = 20/np.sum(left_distances)


    print('Left Headings: ')
    for right_calib in turnrights+forwards[0:2]:
        times = right_calib['time_from_start']
        gyro_left = right_calib['gyro_left']
        gyro_right = right_calib['gyro_right']

        # distance_left = get_distance_m(times, gyro_left, gyro_right, D, W)
        # distance_right = get_distance_m(times, gyro_right, gyro_right, D, W)
        headings.append(get_heading_deg(times, np.array(gyro_left)*ml, np.array(gyro_right)*mr, D, W)[-1])

        print(headings[-1])

        # print(distance_left[-1])
        # print(distance_right[-1])
        print()

    print('Right Headings: ', np.sum(headings))

    W /= -360/np.sum(headings)


    headings = []
    for left_calib in turnlefts+forwards[2:4]:
        times = left_calib['time_from_start']
        gyro_left = left_calib['gyro_left']
        gyro_right = left_calib['gyro_right']

        # distance_left = get_distance_m(times, gyro_left, gyro_right, D, W)
        # distance_right = get_distance_m(times, gyro_right, gyro_right, D, W)
        headings.append(get_heading_deg(times, np.array(gyro_left)*ml, np.array(gyro_right)*mr, D, W)[-1])

        print(headings[-1])

        # print(distance_left[-1])
        # print(distance_right[-1])
        print()

    print(sum(headings))

    return [D, W, ml, mr, bl, br]


def show_calibration_traj(res, calibration_list):
    diam, width, ml, mr, bl, br = res

    print(res)

    fig, ax = plt.subplots()
    
    for cal in calibration_list:

        if len(cal['time_from_start']) == 0:
            continue

        cal['time_from_start'] = np.array(cal['time_from_start'])
        cal['gyro_left'] = ml*np.array(cal['gyro_left'])+bl
        cal['gyro_right'] = mr*np.array(cal['gyro_right'])+bl
        # remove last plot
        ax.clear()
        print('Calibration:', cal['name'])

        distance = get_distance_m(cal['time_from_start'], cal['gyro_left'], cal['gyro_right'], diam, width)
        print("Distance: ", distance[-1])

        # Calculate displacement for the data['trajectory']:
        displacement = get_displacement_m(cal['time_from_start'], cal['gyro_left'], cal['gyro_right'], diam, width)
        print("Displacement: ", displacement[-1])

        # Find heading angle over time:
        heading = get_heading_deg(cal['time_from_start'], cal['gyro_left'], cal['gyro_right'], diam, width)
        print("Heading: ", heading[-1])

        velocity = get_velocity_m_s(cal['time_from_start'], cal['gyro_left'], cal['gyro_right'], diam, width)

        trajectory = get_top_traj(displacement, velocity, heading, cal['time_from_start'], diam, width)

        print(len(trajectory[0]), len(trajectory[1]))

        # plot the trajectory
        # plt.plot([i[0] for i in trajectory], [i[1] for i in trajectory], label="Trajectory")
        # fig, ax = plt.subplots()

        ax.plot([i[0] for i in trajectory], [i[1] for i in trajectory], label="Trajectory")

        # Set the x and y limits
        ax.set_xlim(-2, 8)
        ax.set_ylim(-2, 8)

        # Set the aspect ratio to be equal
        ax.set_aspect('equal')

        # Display the plot
        # plt.show()

        # show plot without blocking
        plt.show(block=False)
        
        # pause until user input
        input("Press Enter to continue...")

    plt.close()

def show_entire_run(res, calibration_list):
    # put all calibration data into single vector and show
    diam, width, ml, mr = res
    bl=0
    br=0

    calibration_list = [c for c in calibration_list if c['name'] != 'setposition']
    calibration_list = [c for c in calibration_list if 'pause' not in c['name']]

    for dict in calibration_list:
        print(dict['name'])

    times = []
    gyro_left = []
    gyro_right = []
    for run in calibration_list:
        # print(run['time_from_start'])
        # print(times)
        times.extend(run['time_from_start'])
        gyro_left.extend(run['gyro_left'])
        gyro_right.extend(run['gyro_right'])

    times = np.array(times)
    gyro_left = ml*np.array(gyro_left)+bl
    gyro_right = mr*np.array(gyro_right)+br

    fig, ax = plt.subplots()
    distance = get_distance_m(times, gyro_left, gyro_right, diam, width)
    print("Distance: ", distance[-1])

    # Calculate displacement for the data['trajectory']:
    displacement = get_displacement_m(times, gyro_left, gyro_right, diam, width)
    print("Displacement: ", displacement[-1])

    # Find heading angle over time:
    heading = get_heading_deg(times, gyro_left, gyro_right, diam, width)
    print("Heading: ", heading[-1])

    velocity = get_velocity_m_s(times, gyro_left, gyro_right, diam, width)

    trajectory = get_top_traj(displacement, velocity, heading, times, diam, width)

    ax.plot([i[0] for i in trajectory], [i[1] for i in trajectory], label="Trajectory")

    # Set the x and y limits
    # ax.set_xlim(-2, 8)
    # ax.set_ylim(-2, 8)

    # Set the aspect ratio to be equal
    # ax.set_aspect('equal')
    plt.show()

def minimize_function(p, calibration_list):
    D, W, ml, mr = p

    br=0
    bl=0

    forwards = [val for val in calibration_list if 'forward' in val['name']]
    turnrights = [val for val in calibration_list if 'turnright' in val['name']]
    turnlefts = [val for val in calibration_list if 'turnleft' in val['name']]
    pauses = [val for val in calibration_list if 'pause' in val['name']]

    left_distances = []
    right_distances = []
    for forward in forwards:
        times = forward['time_from_start']
        gyro_left = forward['gyro_left']
        gyro_right = forward['gyro_right']

        left_distances.append(get_distance_m(times, np.array(gyro_left)*ml+bl, np.array(gyro_left)*ml+bl, D, W)[-1])
        right_distances.append(get_distance_m(times, np.array(gyro_right)*mr+br, np.array(gyro_right)*mr+br, D, W)[-1])

        # print(left_distances[-1])
        # print(right_distances[-1])
        # print()

    eq1 = 20 - np.sum(left_distances)
    eq2 = 20 - np.sum(right_distances)
    # eq1 = 1 - 20/np.sum(left_distances)
    # eq2 = 1 - 20/np.sum(right_distances)

    headings = []
    for right_calib in turnrights+forwards[0:2]:
        times = right_calib['time_from_start']
        gyro_left = right_calib['gyro_left']
        gyro_right = right_calib['gyro_right']

        # distance_left = get_distance_m(times, gyro_left, gyro_right, D, W)
        # distance_right = get_distance_m(times, gyro_right, gyro_right, D, W)
        headings.append(get_heading_deg(times, np.array(gyro_left)*ml+bl, np.array(gyro_right)*mr+br, D, W)[-1])

        # print(headings[-1])

        # # print(distance_left[-1])
        # # print(distance_right[-1])
        # print()

    eq3 = 360 - (-np.sum(headings))
    # eq3 = 1 - 360/-np.sum(headings)

    headings = []
    for left_calib in turnlefts+forwards[2:4]:
        times = left_calib['time_from_start']
        gyro_left = left_calib['gyro_left']
        gyro_right = left_calib['gyro_right']

        headings.append(get_heading_deg(times, np.array(gyro_left)*ml+bl, np.array(gyro_right)*mr+br, D, W)[-1])

        # print(headings[-1])
        # print()

    eq4 = 360 - np.sum(headings)    

    # eq4 = 1 - 360/np.sum(headings)


    eq1 = eq1*18
    eq2 = eq2*18

    return [eq1, eq2, eq3, eq4]

def get_trajectories(res, calibration_list):
    D, W, ml, mr = res

    bl=0
    br=0

    fig, ax = plt.subplots()
    trajectories = []
    times = []
    gyro_left = []
    gyro_right = []
    full_trajectory = []
    for run in calibration_list:
        if run['name'] == 'setposition':
            continue
        times.extend(run['time_from_start'])
        gyro_left.extend([i*ml+bl for i in run['gyro_left']])
        gyro_right.extend([i*mr+br for i in run['gyro_right']])

        # times = np.array(times)
        # gyro_left = ml*np.array(gyro_left)+bl
        # gyro_right = mr*np.array(gyro_right)+br

        displacement = get_displacement_m(times, gyro_left, gyro_right, D, W)
        heading = get_heading_deg(times, gyro_left, gyro_right, D, W)
        velocity = get_velocity_m_s(times, gyro_left, gyro_right, D, W)

        trajectory = get_top_traj(displacement, velocity, heading, times, D, W)
        if len(trajectory) > 0:
            trajectories.append(trajectory[-1])
            full_trajectory = trajectory

        print(run['name'])
        # ax.plot([i[0] for i in trajectories], [i[1] for i in trajectories], label="Trajectory")
        ax.clear()
        ax.plot([i[0] for i in full_trajectory], [i[1] for i in full_trajectory], label="Trajectory")
        plt.show(block=False)
        # ax.set_xlim(-2, 8)
        # ax.set_ylim(-2, 8)

        # Set the aspect ratio to be equal
        ax.set_aspect('equal')
        input("Press Enter to continue...")

    print(trajectories)
    ax.plot([i[0] for i in full_trajectory], [i[1] for i in full_trajectory], label="Trajectory")
    plt.show(block = True)
    # ax.set_xlim(-2, 8)
    # ax.set_ylim(-2, 8)

    # Set the aspect ratio to be equal
    ax.set_aspect('equal')
        # plt.show()




if __name__ == '__main__':
    # show_calibration_traj()
    calibration_list = json.load(open('data_calibrated2.json', 'r'))
    # for cal in calibration_list:
    #     cal['time_from_start'] = np.array(cal['time_from_start'])
    #     cal['gyro_left'] = np.array(cal['gyro_left'])
    #     cal['gyro_right'] = np.array(cal['gyro_right'])

    


    # res = calibration_setup(calibration_list)
    # print(res)

    # diam, width, ml, mr, bl, br = res.x

    # show_calibration_traj(res.x)

    # show_entire_run([24,26,1,1,0,0], calibration_list)
    # show_calibration_traj([24,26,1,1,0,0], calibration_list)
    # print(manual_calibration([24,22.57,1,1,0,0], calibration_list))

    f = fsolve(minimize_function, [24, 22.57, 1, 1], args=(calibration_list))
    print(f)
    get_trajectories(f, calibration_list)

    # show_entire_run(f, calibration_list)
    # show_calibration_traj(f, calibration_list)