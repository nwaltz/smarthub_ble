import os
import argparse
import pandas as pd
# from libraries.bokeh.models import (
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    Panel,
    Tabs
)
# from libraries.bokeh.plotting import figure, output_file, save
from bokeh.plotting import figure, output_file, save
# from libraries.bokeh.plotting.figure import Figure
from bokeh.plotting.figure import Figure


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_file", '-f',
                        help='Path to data output file',
                        required=True,
                        type=str)
    return vars(parser.parse_args())


def x_accel_plot(x_accel,time_from_start) -> Figure:
    src = ColumnDataSource(data={
        'time_s': time_from_start,
        'accel_x': x_accel
    })
    dist_p = figure(sizing_mode="scale_both")
    dist_p.line('time_s',
                'accel_x',
                source=src,
                line_width=3)
    dist_p.add_tools(
        HoverTool(
            tooltips=[
                ('time_s', '@time_s'),
                ('accel_x', '@accel_x'),
            ]
        )
    )
    dist_p.xaxis.axis_label = 'time_s'
    dist_p.yaxis.axis_label = 'accel_x'
    return dist_p


def y_accel_plot(y_accel,time_from_start) -> Figure:
    src = ColumnDataSource(data={
        'time_s': time_from_start,
        'accel_y': y_accel
    })
    dist_p = figure(sizing_mode="scale_both")
    dist_p.line('time_s',
                'accel_y',
                source=src,
                line_width=3)
    dist_p.add_tools(
        HoverTool(
            tooltips=[
                ('time_s', '@time_s'),
                ('accel_y', '@accel_y'),
            ]
        )
    )
    dist_p.xaxis.axis_label = 'time_s'
    dist_p.yaxis.axis_label = 'accel_y'
    return dist_p


def z_accel_plot(z_accel,time_from_start) -> Figure:
    src = ColumnDataSource(data={
        'time_s': time_from_start,
        'accel_z': z_accel
    })
    dist_p = figure(sizing_mode="scale_both")
    dist_p.line('time_s',
                'accel_z',
                source=src,
                line_width=3)
    dist_p.add_tools(
        HoverTool(
            tooltips=[
                ('time_s', '@time_s'),
                ('accel_z', '@accel_z'),
            ]
        )
    )
    dist_p.xaxis.axis_label = 'time_s'
    dist_p.yaxis.axis_label = 'accel_z'
    return dist_p


def plotting_main(time_from_start, x_accel, y_accel, z_accel) -> None:
    # set output file path
    path = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(path, 'testPlots.html')
    # set output file
    output_file(filepath)

    # distance plot
    x_p = x_accel_plot(x_accel,time_from_start)

    # velocity plot
    y_p = y_accel_plot(y_accel,time_from_start)

    # trajectory plot
    z_p = z_accel_plot(z_accel,time_from_start)

    # setup tabs
    x_tab = Panel(child=x_p, title='X Accleration')
    y_tab = Panel(child=y_p, title='Y Accleration')
    z_tab = Panel(child=z_p, title='Z Accleration')
    tabs = Tabs(tabs=[x_tab, y_tab, z_tab])
    # log
    print(f'saving to {filepath}')
    # Save as html to the output path
    save(tabs)
    # show(tabs)


if __name__ == "__main__":
    args = parse_args()
    # inputs
    data_file = args['data_file']
    # read in data from csv file
    df = pd.read_csv(data_file)
    # pull data from data file
    time_from_start = df['elapsed_time_s']
    x_accel = df['x_accel']
    y_accel = df['y_accel']
    z_accel = df['z_accel']
    # send data to plot the calculated metrics
    plotting_main(time_from_start, x_accel, y_accel, z_accel)
