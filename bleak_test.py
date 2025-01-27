import asyncio
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import time

address = "28E204F5-61B4-ABA9-8483-CC63E00C1C4C"

start_time = 0
i = 0

def update_data(data):
    global i
    i += 1
    print(f'{time.time() - start_time}, {i/(time.time() - start_time)} {len(data)}')


async def connect_to_device():
    try:
        notified = False
        global start_time
        async with BleakClient(address, timeout=15) as client:
            start_time = time.time()
            while True:
                if not notified:
                    notified = True
                    ch = "00002a56-0000-1000-8000-00805f9b34fb"
                    print(client.mtu_size)
                    await client.start_notify(ch, lambda ch, data: update_data(data))

                # else:
                #     print("Device is not connected")
                await asyncio.sleep(5)  # Wait a few seconds before checking again
                # rssi = await client.get_rssi()
                # print(f"RSSI: {rssi}")

    except BleakError as e:
        print(f"Failed to connect: {e}")

async def main():
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
    smarthub_id = "9999"
    # print(devices)
    for d, val in devices.items():
        device, adv = val
        if "Smarthub" in str(device.name):
            print(f"Name: {device.name: <40}|     RSSI (signal strength): {adv.rssi: <10}|       Address: {d}")
            print()
    #     if isinstance(d.name, str):
    #         if f'Left Smarthub: {smarthub_id}' == d.name:
    #             print("Left Smarthub Identified")
    #             address_left = d.address
    #         if f'Right Smarthub: {smarthub_id}' == d.name:
    #             print("Right Smarthub Identified")
    #             address_right = d.address
    # while True:
    #     try:
    #         await connect_to_device(address_left, address_right)
    #     except BleakError:
    #         print("Device went out of range, retrying...")
    #         await asyncio.sleep(10)  # Wait before retrying

asyncio.run(main())
# asyncio.run(connect_to_device())