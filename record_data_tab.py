import asyncio
import tkinter as tk
from tkinter import font, ttk, Label
import threading
import multiprocessing

from bleak import BleakScanner, BleakClient


class RecordData:

    def __init__(self, tab):
        self.tab = tab
        self.create_widgets()


    def set_operator_id(self, operator_id):
        self.operator_id = operator_id

    # top level connection function
    def connect_smarthubs(self, smarthub_id):

        # subfunction in seperate thread so we can get a new event loop and run async without issues
        def ble_task():
            asyncio.run(self._connect_smarthubs(smarthub_id))

        threading.Thread(target=ble_task).start()

    # private function to run async connection stuff
    async def _connect_smarthubs(self, smarthub_id):
        self.smarthub_id = smarthub_id

        devices = await BleakScanner.discover(timeout=5.0)
        address_left = None
        address_right = None

        for d in devices:
            if type(d.name) != str:
                continue
            if f'Left Smarthub: {self.smarthub_id}' == d.name:
                print("Left Smarthub Identified")
                address_left = d.address
            if f'Right Smarthub: {self.smarthub_id}' == d.name:
                print("Right Smarthub Identified")
                address_right = d.address

        if address_left is not None:
            self.client_left = BleakClient(address_left)
            await self.client_left.connect()
            self.left_smarthub_connection['text'] = 'Connected'
            self.left_smarthub_connection['foreground'] = '#217346'
        if address_right is not None:
            self.client_right = BleakClient(address_right)
            await self.client_right.connect()
            self.right_smarthub_connection['text'] = 'Connected'
            self.right_smarthub_connection['foreground'] = '#217346'

        print("Smarthubs Connected")
        self.start_recording_button['state'] = 'normal'




    def start_recording(self):
        print('recording started')
        pass

    def run_async_task(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
        else:
            loop.create_task(coro)


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
        pass
        
