import asyncio
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

address = "9D:C3:CE:33:0F:13"

def update_data(ch, data, side):
    print(f"{side} Smarthub: {data}")

async def connect_to_device():
    try:
        async with BleakClient(address) as client:
            while True:
                if await client.is_connected():
                    print("Device is connected")
                    ch = "00002a56-0000-1000-8000-00805f9b34fb"

                    await client.start_notify(ch, lambda ch, data: update_data(ch, data, 'left'))
                else:
                    print("Device is not connected")
                # await asyncio.sleep(5)  # Wait a few seconds before checking again

    except BleakError as e:
        print(f"Failed to connect: {e}")

async def main():
    devices = await BleakScanner.discover(timeout=5.0)
    smarthub_id = "9999"
    for d in devices:
        print(d)
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

# asyncio.run(main())
asyncio.run(connect_to_device())