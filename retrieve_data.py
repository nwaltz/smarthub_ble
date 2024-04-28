from tkinter import *
import tkinter as tk
from tkinter import ttk
import cred

import numpy as np
import pandas as pd
from datetime import datetime
import os
import matplotlib.pyplot as plt
import time
import asyncio
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
# from test_tkinter import *

from base_ble.calc import (
    get_displacement_m,
    get_distance_m,
    get_velocity_m_s,
    get_heading_deg,
    get_top_traj
)

from base_ble.data_analyze import *


def view_data(root):
    from main_gui import remove_all_widgets, start_screen
    from tkinter import PhotoImage

    # button_user_menu_right.destroy()
    # button_user_menu_left.destroy()
    # user_select_text.destroy()

    remove_all_widgets(root)

    # print('here')

    # print('returned')

    username = cred.username
    password = cred.password

    uri = f"mongodb+srv://{username}:{password}@smarthub.gbdlpxs.mongodb.net/?retryWrites=true&w=majority"
    client = MongoClient(uri, server_api=ServerApi('1'))
    smarthub_db = client.Smarthub
    test_collection = smarthub_db.test_collection


    def restart_all():
        remove_all_widgets(root)
        start_screen(root)

    # Create a back arrow button
    restart_box = ttk.Frame(root)
    restart_box.pack()
    restart_box.place(x=0, y=0)
    
    # Create a back arrow button
    back_arrow = "\u2190"  # Unicode character for left arrow

    back_button = ttk.Button(restart_box, text=back_arrow, command=restart_all)
    back_button.pack()

    fig = Figure(figsize=(8, 7), dpi=100)
    axs=[]
    axs.append(fig.add_subplot(221))
    axs.append(fig.add_subplot(222))
    axs.append(fig.add_subplot(223))

    canvas2 = FigureCanvasTkAgg(fig, master=root)

    def plot_recorded_data(id):

        data = test_collection.find({'_id': id})[0]

        # Set overall title of figure:
        fig.suptitle(f'Operator ID: {data["user_id"]}')

        data['heading_deg'] = get_heading_deg(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])
        data['velocity'] = get_velocity_m_s(data['elapsed_time_s'], data['gyro_left'], data['gyro_right'])


        # analyzed_data = data_analyze_main(data['elapsed_time_s'], data['distance_m'], data['velocity'], data['heading_deg'], data['traj_x'], data['traj_y'])

        # keys = analyzed_data.columns.tolist()
        # for key in keys:
        #     print(key)
        #     vals = analyzed_data[key].values.tolist()
        #     print(key)
        #     # for i, val in enumerate(vals):
        #     #     if val == None:# or np.isnan(val):
        #     #         vals.pop(i)
        #     print(vals)
        #     print()
            
        #     print()


        def create_graph(graph_loc, xval, yval):
            set_graph1 = ttk.Frame(root)
            set_graph1.pack()
            set_graph1.place(x=xval, y=yval)

            # Create a drop-down menu for selecting the graph type
            graph_type_var = tk.StringVar()
            if graph_loc == 0:
                main_graph_name = "Displacement"
            elif graph_loc == 1:
                main_graph_name = "Heading"
            elif graph_loc == 2:
                main_graph_name = "Trajectory"

            graph_type_var.set(main_graph_name)
            graph_type_menu = ttk.OptionMenu(set_graph1, graph_type_var, main_graph_name, "Displacement", "Trajectory", "Heading", "Velocity")

            # graph_type_menu = ttk.OptionMenu(set_graph1, graph_type_var, "Displacement", "Trajectory", "Heading")
            # graph_type_menu.place(x=300, y=200)
            graph_type_menu.pack()

            # Function to handle the selection change in the drop-down menu
            def on_graph_type_change(*args):
                selected_graph_type = graph_type_var.get()
                axs[graph_loc].clear()
                if selected_graph_type == "Displacement":
                    # Code for displacement graph
                    axs[graph_loc].set_xlabel('Time (sec)')
                    axs[graph_loc].set_ylabel('Displacement (m)')
                    axs[graph_loc].plot(data['elapsed_time_s'], data['distance_m'])

                elif selected_graph_type == "Trajectory":
                    # Code for trajectory graph
                    axs[graph_loc].set_xlabel('X Trajectory (m)')
                    axs[graph_loc].set_ylabel('Y Trajectory (m)')
                    axs[graph_loc].plot(data['traj_x'], data['traj_y'])

                elif selected_graph_type == "Heading":
                    # Code for heading graph
                    axs[graph_loc].set_xlabel('Time (sec)')
                    axs[graph_loc].set_ylabel('Heading (deg)')
                    axs[graph_loc].plot(data['elapsed_time_s'], data['heading_deg'])

                elif selected_graph_type == "Velocity":
                    # Code for velociy graph
                    axs[graph_loc].set_xlabel('Time (sec)')
                    axs[graph_loc].set_ylabel('Velocity (m/s)')
                    axs[graph_loc].plot(data['elapsed_time_s'], data['velocity'])


                canvas_widget = canvas2.get_tk_widget()
                canvas_widget.pack(fill=tk.BOTH, expand=True)
                canvas2.draw()
                canvas2.flush_events()   

            # Bind the function to the drop-down menu
            graph_type_var.trace("w", on_graph_type_change)

        create_graph(0, 265, 35)
        create_graph(1, 825, 35)
        create_graph(2, 265, 390)


        # Set x and y axes labels for first subplot:
        # axs[0].set_title('Displacement over time')
        axs[0].set_title(' ')
        axs[0].set_xlabel('Time (sec)')
        axs[0].set_ylabel('Displacement (m)')

        axs[1].set_title(' ')
        axs[1].set_xlabel('Time (sec)')
        axs[1].set_ylabel('Heading (deg)')
        # axs[1].set_ylabel('Right Acceleration (m/s2)')
        # Set x and y axes labels for third subplot:
        # axs[2].set_title('Trajectory')
        axs[2].set_title(' ')
        axs[2].set_xlabel('X Trajectory (m)')
        axs[2].set_ylabel('Y Trajectory (m)')
        fig.tight_layout()

        axs[0].plot(data['elapsed_time_s'], data['distance_m'])
        # Create a plot of heading over time:
        axs[1].plot(data['elapsed_time_s'], data['heading_deg'])
        # Create a plot of data['trajectory']:
        axs[2].plot(data['traj_x'], data['traj_y'])

        canvas_widget = canvas2.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)


        style = ttk.Style()
        style.map("TEntry",
                fieldbackground=[("active", "white"), ("!focus", "gray")],
                foreground=[("active", "black"), ("!focus", "gray")])
    

        def go_back_to_select():
            remove_all_widgets(root)
            view_data(root)

        # restart button
        restart_box = ttk.Frame(root)
        restart_box.pack()
        restart_box.place(x=0, y=0)
        # Create a button to submit the input
        
        # Create a back arrow button
        back_arrow = "\u2190"  # Unicode character for left arrow

        back_button = ttk.Button(restart_box, text=back_arrow, command=go_back_to_select)
        back_button.pack()
        


        ########################################################### test run name

        style.configure("Background.TLabel", background="white", foreground='#313131')
        testname_select_text = ttk.Frame(root)
        testname_select_text.place(x=570,y=424)
        testlabel_select_text = ttk.Label(testname_select_text, text="Test run name:", font=("Helvetica", 14), style='Background.TLabel')
        testlabel_select_text.pack()


        def testname_submit(testname_entry, testlabel_current_text, testname_submit_button):
            if testname_submit_button['text'] == "Edit":
                testlabel_current_text.place_forget()
                testname_entry.place(x=740, y=420)
                testname_entry.delete(0, "end")
                testname_submit_button.configure(text="Save")
                testname_entry.insert(0, "e.g. Circle 4")  # Set default text
                # testname_entry.focus_set()  # Set focus to the entry box
        

            elif testname_submit_button['text'] == "Save":
                user_input = testname_entry.get()
                data['test_name'] = user_input

                updater = {
                    "$set": {
                        "test_name": user_input
                    }
                }
                criteria = {'_id': id}

                test_collection.update_one(criteria, updater)

                testlabel_current_text.configure(text=f'{data["test_name"]}')
                testlabel_current_text.place(x=740, y=424)
                testname_entry.place_forget()
                testname_submit_button.configure(text="Edit")

        if 'test_name' in data.keys():
            display_testname = data['test_name']
        else:
            display_testname = data['_id']

        # Create the entry box, label, and submit button
        testname_entry = ttk.Entry(root)
        testname_entry.insert(0, "e.g. Circle 4")
        testlabel_current_text = ttk.Label(root, text=f'{display_testname}', font=("Helvetica", 14), style='Background.TLabel')
        testname_submit_button = ttk.Button(root, text="Edit", command=lambda: testname_submit(testname_entry, testlabel_current_text, testname_submit_button))

        def testname_clear_background_text(event):
            if testname_entry.get() == "e.g. Circle 4":
                testname_entry.delete(0, "end")

        testname_entry.bind("<FocusIn>", testname_clear_background_text)

        # Place widgets initially
        # testname_entry.place(x=700, y=570)
        testlabel_current_text.place(x=740, y=424)
        testname_submit_button.place(x=960, y=420)

        ################################################################# clinician id

        clinician_select_text = ttk.Frame(root)
        clinician_select_text.place(x=570,y=474)
        clinicianlabel_select_text = ttk.Label(clinician_select_text, text="Clinician ID:", font=("Helvetica", 14), style='Background.TLabel')
        clinicianlabel_select_text.pack()


        def clinicianid_submit(clinician_entry, clinicianlabel_current_text, clinician_submit_button):
            if clinician_submit_button['text'] == "Edit":
                clinicianlabel_current_text.place_forget()
                clinician_entry.place(x=740, y=470)
                clinician_entry.delete(0, "end")
                clinician_submit_button.configure(text="Save")
            elif clinician_submit_button['text'] == "Save":
                user_input = clinician_entry.get()
                data['clinician_id'] = user_input

                data['clinician_id'] = user_input

                updater = {
                    "$set": {
                        "clinician_id": user_input
                    }
                }
                criteria = {'_id': id}

                test_collection.update_one(criteria, updater)

                clinicianlabel_current_text.configure(text=f'{data["clinician_id"]}')
                clinicianlabel_current_text.place(x=740, y=474)
                clinician_entry.place_forget()
                clinician_submit_button.configure(text="Edit")

        clinician_id = False
        if 'clinician_id' in data.keys():
            clinician_id = True

        # Create the entry box, label, and submit button
        clinician_entry = ttk.Entry(root)
        clinician_example_text = "e.g. 4321"
        clinician_entry.insert(0, clinician_example_text)
        if clinician_id:
            clinicianlabel_current_text = ttk.Label(root, text=f'{data["clinician_id"]}', font=("Helvetica", 14), style='Background.TLabel')
            clinician_submit_button = ttk.Button(root, text="Edit", command=lambda: clinicianid_submit(clinician_entry, clinicianlabel_current_text, clinician_submit_button))
            clinicianlabel_current_text.place(x=740, y=474)
        else:
            clinicianlabel_current_text = ttk.Label(root, text=f'', font=("Helvetica", 14), style='Background.TLabel')
            clinician_submit_button = ttk.Button(root, text="Save", command=lambda: clinicianid_submit(clinician_entry, clinicianlabel_current_text, clinician_submit_button))
            clinician_entry.place(x=740, y=470)

        def clinician_clear_background_text(event):
            if clinician_entry.get() == clinician_example_text:
                clinician_entry.delete(0, "end")

        clinician_entry.bind("<FocusIn>", clinician_clear_background_text)

        clinician_submit_button.place(x=960, y=470)

        ################################################################# location id

        location_select_text = ttk.Frame(root)
        location_select_text.place(x=570,y=524)
        locationlabel_select_text = ttk.Label(location_select_text, text="location ID:", font=("Helvetica", 14), style='Background.TLabel')
        locationlabel_select_text.pack()


        def locationid_submit(location_entry, locationlabel_current_text, location_submit_button):
            if location_submit_button['text'] == "Edit":
                locationlabel_current_text.place_forget()
                location_entry.place(x=740, y=520)
                location_entry.delete(0, "end")
                location_submit_button.configure(text="Save")
            elif location_submit_button['text'] == "Save":
                user_input = location_entry.get()
                data['location_id'] = user_input

                data['location_id'] = user_input

                updater = {
                    "$set": {
                        "location_id": user_input
                    }
                }
                criteria = {'_id': id}

                test_collection.update_one(criteria, updater)

                locationlabel_current_text.configure(text=f'{data["location_id"]}')
                locationlabel_current_text.place(x=740, y=524)
                location_entry.place_forget()
                location_submit_button.configure(text="Edit")

        location_id = False
        if 'location_id' in data.keys():
            location_id = True

        # Create the entry box, label, and submit button
        location_entry = ttk.Entry(root)
        location_example_text = "e.g. room 1839"
        location_entry.insert(0, location_example_text)
        if location_id:
            locationlabel_current_text = ttk.Label(root, text=f'{data["location_id"]}', font=("Helvetica", 14), style='Background.TLabel')
            location_submit_button = ttk.Button(root, text="Edit", command=lambda: locationid_submit(location_entry, locationlabel_current_text, location_submit_button))
            locationlabel_current_text.place(x=740, y=524)
        else:
            locationlabel_current_text = ttk.Label(root, text=f'', font=("Helvetica", 14), style='Background.TLabel')
            location_submit_button = ttk.Button(root, text="Save", command=lambda: locationid_submit(location_entry, locationlabel_current_text, location_submit_button))
            location_entry.place(x=740, y=520)

        def location_clear_background_text(event):
            if location_entry.get() == location_example_text:
                location_entry.delete(0, "end")

        location_entry.bind("<FocusIn>", location_clear_background_text)

        location_submit_button.place(x=960, y=520)

        ################################################################# additional notes

        # add a horizonatal line
        ttk.Separator(root, orient='horizontal').place(x=560, y=570, width=500)

        # Get the previous additional notes from data dictionary
        previous_notes = data['additional_notes'] if 'additional_notes' in data.keys() else "add notes here..."

        # Create a large user entry field
        user_entry_box = ttk.Frame(root)
        user_entry_box.pack()
        user_entry_box.place(x=560, y=620) # Adjust the position as needed

        additional_notes_label = ttk.Label(root, text="Additional Notes:", font=("Helvetica", 14), style='Background.TLabel')
        additional_notes_label.place(x=560, y=585)  # Adjust the position as needed

        user_entry_var = tk.StringVar()
        user_entry = tk.Text(user_entry_box, width=45, height=5, font=("Helvetica", 14))
        user_entry.insert(tk.END, previous_notes)    # Fill the text box with previous notes
        user_entry.pack()

        def notes_clear_background_text(event):
            print(user_entry.get("1.0", tk.END).strip())
            if user_entry.get("1.0", tk.END).strip() == 'add notes here...':
                user_entry.delete("1.0", tk.END)

        def on_key_release(event):
            if 'additional_notes' in data.keys():
                if user_entry.get("1.0", tk.END).strip() != data['additional_notes']:
                    save_button.configure(text="Save")
                else:
                    save_button.configure(text="Saved!")

        user_entry.bind("<KeyRelease>", on_key_release)

        user_entry.bind("<FocusIn>", notes_clear_background_text)

        def save_data():
            # Get the data from the user input fields
            user_input = user_entry.get("1.0", tk.END).strip()
            # Save the data to the MongoDB database
            updater = {
                "$set": {
                    "additional_notes": user_input
                }
            }
            criteria = {'_id': id}

            test_collection.update_one(criteria, updater)
            data['additional_notes'] = user_input
            # Provide feedback to the user
            save_button.configure(text="Saved!")

        save_button = ttk.Button(root, text="Save", command=save_data)
        save_button.place(x=960, y=580)


    style = ttk.Style()
    style.map("TEntry",
            fieldbackground=[("active", "white"), ("!focus", "gray")],
            foreground=[("active", "black"), ("!focus", "gray")])


    frame_select_text = ttk.Frame(root)
    # frame_select_text.pack()
    frame_select_text.place(x=380,y=120)
    user_select_text = ttk.Label(frame_select_text, text="Test Run Selection", font=("Verdana", 25))
    user_select_text.pack()

    ### set up text box for user id submission
    style.configure("Background.TLabel", background="#313131", foreground='white')
    # style.theme_use('forest-dark')
    userid_select_text = ttk.Frame(root)
    userid_select_text.place(x=260,y=294)
    userlabel_select_text = ttk.Label(userid_select_text, text="6 Digit Operator Id:", font=("Helvetica", 14), style='Background.TLabel')
    userlabel_select_text.pack()

    userid_box_info_text = "e.g. 654321"
    userid_entry_box = ttk.Frame(root)
    userid_entry_box.pack()
    userid_entry_box.place(x=430,y=290) # place on screen
    userid_entry_var = tk.StringVar()
    userid_entry = ttk.Entry(userid_entry_box, textvariable=userid_entry_var)
    userid_entry.insert(0, userid_box_info_text)    # put instructions in background to include data
    userid_entry.pack()

    # background text clear if in focus
    def userid_clear_background_text(event):
        if userid_entry_var.get() == userid_box_info_text:
            userid_entry.delete(0, "end")

    userid_entry.bind("<FocusIn>", userid_clear_background_text)

    def userid_submit():
        userid_input = userid_entry.get()
        # testname_input = testname_entry.get()

        userid_submit_button.configure(text="Entered!")

        valid_ids = test_collection.find({'user_id': userid_input}, {'_id': 1, 'test_name': 1})
        valid_ids_copy = []

        new_valid_ids = []
        for valid_id in valid_ids:
            id_val = valid_id['_id']
            if 'test_name' in valid_id:
                new_valid_ids.append(valid_id['test_name'])
            else:
                new_valid_ids.append(id_val)
            valid_ids_copy.append(id_val)

        print(valid_ids_copy)

        def on_select(event):
            chosen_id = combo.get()

            id_to_send = valid_ids_copy[new_valid_ids.index(chosen_id)]
            print(id_to_send)

            # Remove all label and user entry box widgets
            userid_select_text.destroy()
            userlabel_select_text.destroy()
            userid_entry_box.destroy()
            userid_submit_box.destroy()
            combo_select_text.destroy()
            combolabel_select_text.destroy()
            combo_submit_box.destroy()
            user_select_text.destroy()
            frame_select_text.destroy()

            plot_recorded_data(id_to_send)

            print(chosen_id)

        combo_select_text = ttk.Frame(root)
        combo_select_text.place(x=260,y=344)
        combolabel_select_text = ttk.Label(combo_select_text, text="Test Name:", font=("Helvetica", 14), style='Background.TLabel')
        combolabel_select_text.pack()

        combo_submit_box = ttk.Frame(root)
        combo_submit_box.pack()
        # combo_submit_box.place(x=700, y=290)
        combo_submit_box.place(x=430, y=340)

        # print('here')
        # [print(valid_id) for valid_id in valid_ids]
        # print('here2')
        # valid_ids = [valid_id for valid_id in valid_ids]
        # print(valid_ids)

        global combo
        combo = ttk.Combobox(combo_submit_box, values=new_valid_ids)

        # Set an initial value
        combo.set(new_valid_ids[0])

        # Bind a function to the <<ComboboxSelected>> event (fired when an item is selected)
        combo.bind("<<ComboboxSelected>>", on_select)

        combo.pack()

    

    
    ## submit button for user id
    userid_submit_box = ttk.Frame(root)
    userid_submit_box.pack()
    userid_submit_box.place(x=600, y=290)
    userid_submit_button = ttk.Button(userid_submit_box, text="Select", command=userid_submit)
    userid_submit_button.pack()