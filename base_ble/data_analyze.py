import os
import pandas as pd
import argparse
from typing import List, Dict
import numpy as np
from scipy.signal import find_peaks
import matplotlib.pyplot as plt


def parse_args() -> Dict:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_file", '-f',
                        help='Path to data output file',
                        required=True,
                        type=str)

    # TODO:
    parser.add_argument("--config_file", '-c',
                        help='Path to configuration file',
                        required=False,
                        type=str)
    return vars(parser.parse_args())


class Metrics:
    def __init__(self):
        self.bout = []  # Length of each bout in seconds
        self.bout_dist = []  # Distance traveled in each bout
        self.bout_num = []  # Number of bouts
        self.st_freq_su = []  # stroke frequency in start up for each bout
        self.st_freq_ss = []  # stroke frequency in steady state for each bout
        self.st_l = []  # length of each stroke in seconds
        self.st_l_dist = []  # length of each stroke in meters
        self.st_l_mean_su = []  # Average stroke length in start up for each bout in seconds
        self.st_l_mean_ss = []  # Average stroke length in steady state for each bout
        self.st_l_mean_dist_su = []  # Average stroke length in start up for each bout in meters
        self.st_l_mean_dist_ss = []  # Average stroke length in steady state for each bout in meters
        self.st_num = []  # Number of strokes per bout
        self.push_l = []  # Length of time in the push phase for each stroke
        self.push_l_dist = []  # Distance travelled during the push phase for each stroke
        self.rec_l = []  # Length of time in the recovery phase for each stroke
        self.rec_l_dist = []  # Distance travelled during the push phase for each stroke
        self.roll_resist = []  # Average rolling resistance seen for each bout
        self.rate_rise_ss = []  # rate of rise value in steady state
        self.rate_rise_su = []  # rate of rise value in start up

    def record_bout(self, bout, bout_dist, bout_num):
        self.bout.extend(bout)
        self.bout_dist.extend(bout_dist)
        self.bout_num.append(bout_num)

    def record_strokes(self, st_num, st_l, st_l_dist, push_l, push_l_dist, rec_l, rec_l_dist, roll_resist):
        self.st_num.append(st_num)
        self.st_l.extend(st_l)
        self.st_l_dist.extend(st_l_dist)
        self.push_l.extend(push_l)
        self.push_l_dist.extend(push_l_dist)
        self.rec_l.extend(rec_l)
        self.rec_l_dist.extend(rec_l_dist)
        self.roll_resist.append(roll_resist)

    def record_phases(self, st_l_mean_su, st_l_mean_dist_su, st_l_mean_ss, st_l_mean_dist_ss, rate_rise_su, rate_rise_ss, st_freq_su, st_freq_ss):
        self.st_l_mean_su.append(st_l_mean_su)
        self.st_l_mean_dist_su.append(st_l_mean_dist_su)
        self.st_l_mean_ss.append(st_l_mean_ss)
        self.st_l_mean_dist_ss.append(st_l_mean_dist_ss)
        self.rate_rise_su.append(rate_rise_su)
        self.rate_rise_ss.append(rate_rise_ss)
        self.st_freq_su.append(st_freq_su)
        self.st_freq_ss.append(st_freq_ss)


def data_analyze_main(time_from_start, distance, velocity, heading, traj_x, traj_y):
    # read in data from csv file
    # df = pd.read_csv(filepath)
    # pull data from data file
    # time_from_start = df['elapsed_time_s']
    # distance = df['distance_m']
    # velocity = df['velocity_ms']
    # heading = df['heading_deg']
    # traj_x = df['traj_x']
    # traj_y = df['traj_y']
    # Calculate Stroke and Bout Metrics
    metrics = calculate_bout(time_from_start, distance, velocity)
    # Saves the calculated metrics into a csv file

    analyzed_data = export_metrics(time_from_start, distance, velocity, heading, traj_x, traj_y, metrics)

    return analyzed_data


def calculate_bout(time, distance, velocity):
    # Want to calculate the number of bouts, the length of each bout(s+m), and the strokes per bout
    # Convert from lists to arrays
    velocity = np.array(velocity)
    time = np.array(time)
    distance = np.array(distance)
    # Create boolean array that is true when the negligible velocity threshold is crossed
    moving_endpoints = np.diff(velocity > 0.1, prepend=False)
    # find the indices where the velocity threshold is crossed and the bouts could start or end
    bout_indices = np.argwhere(moving_endpoints)[:, 0]
    # Find when it crosses upward, or where bouts could start
    bout_starts = np.argwhere(moving_endpoints)[::2, 0]
    # Find when it crosses downward, or where bouts could end
    bout_ends = np.argwhere(moving_endpoints)[1::2, 0]
    # If recording ends with a velocity above 0.12 m/s^2, add end point to the end of the bouts
    if len(bout_starts) > len(bout_ends):
        bout_ends = [len(velocity)-1]
    # Check if the potential bouts meet velocity requirement(need max velocity >0.12m/s) and time requirement(>5s)
    for i in range(bout_starts.size):
        # checks to see if the velocity over the "bout" is all less than required or if "bout" is less than 5 secs
        # This loop should be improved using list comprehension
        if all(velocity[bout_starts[i]:bout_ends[i]] < 0.12) or time[bout_ends[i]]-time[bout_starts[i]] < 5:
            if i == len(bout_starts)-1:
                # Removes incomplete bout
                bout_starts[i] = -1
                bout_ends[i] = -1
                bout_starts = np.delete(bout_starts, i)
                bout_ends = np.delete(bout_ends, i)
            else:
                # Removes incomplete bout and combines with next bout
                bout_ends[i] = -1
                bout_starts[i+1] = -1
    bout_starts = np.array([n for n in bout_starts if n != -1])
    bout_ends = np.array([n for n in bout_ends if n != -1])
    # Find the differences in time and distance between possible bout endpoints
    bout = np.subtract(time[bout_ends], time[bout_starts])
    bout_dist = np.subtract(distance[bout_ends], distance[bout_starts])
    # Find total number of bouts
    bout_num = len(bout_starts)

    # plot the velocity curve with the bout endpoints marked
    # plt.plot(time,velocity,time[bout_indices],velocity[bout_indices],'r*')
    # plt.show()
    # create metrics object to store metrics
    metrics = Metrics()
    # Go through all the bouts and record stroke metrics for each
    for i in range(len(bout_starts)):
        metrics = calculate_stroke_metrics(metrics, velocity[bout_starts[i]:bout_ends[i]], time[bout_starts[i]:bout_ends[i]], distance[bout_starts[i]:bout_ends[i]])
    # Record overall bout metrics
    metrics.record_bout(bout, bout_dist, bout_num)
    # return the metrics object so that the values can be saved
    return metrics


def calculate_stroke_metrics(metrics: Metrics, velocity, time, distance):
    # print(f"Bout duration: {time[-1]-time[0]}")
    # Find first and last points to determine start and end of run
    end_points = [0, len(velocity)-1]
    # Find index of all local minima
    stroke_init, _ = find_peaks(-velocity, prominence=0.07)  # originally both 0.07
    # Find index of all local maxima
    stroke_peaks, _ = find_peaks(velocity, prominence=0.07)

    # Find beginning of each stroke
    stroke_init = np.insert(stroke_init, 0, end_points[0])
    stroke_init = np.append(stroke_init, end_points[len(end_points)-1])
    if stroke_init.size == 0:
        raise ValueError("No strokes detected in data")
    # Find time and distances when strokes start and end
    stroke_init_time = time[stroke_init]
    stroke_init_dist = distance[stroke_init]
    # Find time and distances at peak of strokes
    stroke_peak_time = time[stroke_peaks]
    stroke_peak_dist = distance[stroke_peaks]
    # Plot that shows the points of interest in the strokes
    # plt.plot(time, velocity, time[stroke_init], velocity[stroke_init], 'bs', time[stroke_peaks], velocity[stroke_peaks], 'r*')
    # plt.show()

    # Calculate the number of strokes and appends the value to the list of numbers of strokes for each bout
    stroke_num = len(stroke_init_time)-1
    # Calculate the stroke lengths (sec/m)
    st_l = np.diff(stroke_init_time)
    st_l_dist = np.diff(stroke_init_time)

    # Calculate the time and distances of the push and recovery phases
    push_l = np.subtract(stroke_peak_time, stroke_init_time[0:-1])
    push_l_dist = np.subtract(stroke_peak_dist, stroke_init_dist[0:-1])
    rec_l = np.subtract(stroke_init_time[1:], stroke_peak_time)
    rec_l_dist = np.subtract(stroke_init_dist[1:], stroke_peak_dist)

    # Approximation of the acceleration based on gradient of velocity (slightly noisy)
    acc_grad = np.gradient(velocity, time)
    # Approximation of the jerk based on gradient of acceleration (very noisy)
    jerk_grad = np.gradient(acc_grad, time)
    # Create rolling resistance and rate of rise variables to track these metrics for each stroke
    rate_rise = np.zeros(len(stroke_peaks))
    roll_resist = np.zeros(len(stroke_peaks))
    for i in range(len(stroke_peaks)):
        # Determine peak acceleration for each contact phase:
        acc_peak_time = np.argmax(acc_grad[stroke_init[i]:stroke_peaks[i]])
        # Calculate the rate of rise for each contact phase up to maximum acceleration
        rate_rise[i] = np.mean(acc_grad[stroke_init[i]:stroke_init[i]+acc_peak_time])
        # Calculate the rolling resistance for each stroke
        roll_resist[i] = np.mean(acc_grad[stroke_peaks[i]:stroke_init[i+1]])
    # Calculate the overall average rolling resistance for the bout
    roll_resist = np.mean(roll_resist)
    # Record overall stroke metrics for the bout
    metrics.record_strokes(stroke_num,
                           st_l,
                           st_l_dist,
                           push_l,
                           push_l_dist,
                           rec_l,
                           rec_l_dist,
                           roll_resist)
    # Calculate the average stroke length (sec/m) and rate of rise(m/s^2) for the startup and steady state phases
    if len(stroke_init_time)-1 > 3:
        st_l_mean_su = np.mean(st_l[0:3])
        st_l_mean_dist_su = np.mean(st_l_dist[0:3])
        st_l_mean_ss = np.mean(st_l[3:])
        st_l_mean_dist_ss = np.mean(st_l_dist[3:])
        rate_rise_su = np.mean(rate_rise[0:3])
        rate_rise_ss = np.mean(rate_rise[3:])
    else:
        st_l_mean_su = np.mean(st_l)
        st_l_mean_dist_su = np.mean(st_l_dist)
        st_l_mean_ss = 0
        st_l_mean_dist_ss = 0
        rate_rise_su = np.mean(rate_rise)
        rate_rise_ss = 0
    # Calculate the stroke frequency for steady state and start-up(strokes/min)
    st_freq_su = 1/st_l_mean_su*60
    if st_l_mean_ss == 0:
        st_freq_ss = 0
    else:
        st_freq_ss = 1/st_l_mean_ss*60
    # Record steady state and start up metrics
    metrics.record_phases(st_l_mean_su,
                          st_l_mean_dist_su,
                          st_l_mean_ss,
                          st_l_mean_dist_ss,
                          rate_rise_su,
                          rate_rise_ss,
                          st_freq_su,
                          st_freq_ss)

    # return the metrics
    return metrics


def export_metrics(time_from_start, distance, velocity, heading, trajectory_x, trajectory_y, metrics: Metrics):
    # Create the data frame that will be used to build the csv file
    df = pd.DataFrame()
    # Add in each set of data as a column to the data frame
    df['Time (sec)'] = pd.Series(time_from_start)
    df['Distance (m)'] = pd.Series(distance)
    df['Velocity (m/s)'] = pd.Series(velocity)
    df['X Trajectory'] = pd.Series(trajectory_x)
    df['Y Trajectory'] = pd.Series(trajectory_y)
    df['Heading'] = pd.Series(heading)
    df['Stroke Length (sec)'] = pd.Series(metrics.st_l)
    df['SU Average Stroke Length (sec)'] = pd.Series(metrics.st_l_mean_su)
    df['SS Average Stroke Length (sec)'] = pd.Series(metrics.st_l_mean_ss)
    df['Distance per Stroke (m)'] = pd.Series(metrics.st_l_dist)
    df['SU Average Distance per Stroke (m)'] = pd.Series(metrics.st_l_mean_dist_su)
    df['SS Average Distance per Stroke (m)'] = pd.Series(metrics.st_l_mean_dist_ss)
    df['Push Phase Length (sec)'] = pd.Series(metrics.push_l)
    df['Distance per Push Phase (m)'] = pd.Series(metrics.push_l_dist)
    df['Recovery Phase Length (sec)'] = pd.Series(metrics.rec_l)
    df['Distance per Recovery Phase (m)'] = pd.Series(metrics.rec_l_dist)
    df['SU Stroke Frequency (per min)'] = pd.Series(metrics.st_freq_su)
    df['SS Stroke Frequency (per min)'] = pd.Series(metrics.st_freq_ss)
    df['Strokes per Bout (m)'] = pd.Series(metrics.st_num)
    df['Total Number of Strokes'] = pd.Series(np.sum(metrics.st_num))
    df['Number of Bouts'] = pd.Series(metrics.bout_num)
    df['Bout (sec)'] = pd.Series(metrics.bout)
    df['Bout (m)'] = pd.Series(metrics.bout_dist)
    df['SU Rate of rise (m/s^2)'] = pd.Series(metrics.rate_rise_su)
    df['SS Rate of rise (m/s^2)'] = pd.Series(metrics.rate_rise_ss)
    df['Rolling Resistance (m/s^2)'] = pd.Series(metrics.roll_resist)
    # Need to add other metrics

    # Clears all NA cells created when any of the metrics have less data points
    df = df.fillna('')

    return df

    # Puts the metrics data into a file with same name as raw data but with "_metrics" appended
    base = os.path.basename(data_file).replace('.csv', '')
    base = base + '_metrics'
    save_path = os.path.join(os.path.dirname(data_file), f'{base}.csv')
    df.to_csv(save_path)


if __name__ == "__main__":
    args = parse_args()

    # inputs
    data_file = args['data_file']

    data_analyze_main(filepath=data_file)
