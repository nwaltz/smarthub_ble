import os
import subprocess
import serial.tools.list_ports
import platform

def modify_arduino_code(unit_id, unit_side, original_file_path, output_file_path):
    # Read the original Arduino code
    with open(original_file_path, 'r') as file:
        code = file.readlines()

    if unit_side == 'l':
        for i, line in enumerate(code):
            if 'UNIT_SIDE' in line:
                code[i] = f'#define UNIT_SIDE "Left"\n'
                break
    elif unit_side == 'r':
        for i, line in enumerate(code):
            if 'UNIT_SIDE' in line:
                code[i] = f'#define UNIT_SIDE "Right"\n'
                break
    
    for i, line in enumerate(code):
        if 'UNIT_ID' in line:
            code[i] = f'#define UNIT_ID {unit_id}\n'
            break

    # if path doesn't exist
    if not os.path.exists(os.path.dirname(output_file_path)):
        try:
            os.makedirs(os.path.dirname(output_file_path))
        except OSError as exc:
            print('access not allowed')
            exit()
    
    # Write the modified code to a new file
    with open(output_file_path, 'w') as file:
        file.writelines(code)

def upload_code_to_arduino(output_file_path, port):
    # Command to compile and upload the code
    os_name = platform.system()
    if os_name == 'Darwin':
        commands = [
            ["arduino-cli lib install 'Seeed Arduino LSM6DS3'"],
            ["arduino-cli lib install 'ArduinoBLE'"],
            ["arduino-cli config init --overwrite"],
            ["arduino-cli config add board_manager.additional_urls https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json"],
            ["arduino-cli core update-index"],
            ["arduino-cli core install Seeeduino:mbed"],
            [f"arduino-cli compile --fqbn Seeeduino:mbed:xiaonRF52840Sense {output_file_path}"],
            [f"arduino-cli upload -p {port} --fqbn Seeeduino:mbed:xiaonRF52840Sense {output_file_path}"]
        ]
    elif os_name == 'Windows':
        commands = [
            ["arduino-cli.exe", "lib", "install", "Seeed Arduino LSM6DS3"],
            ["arduino-cli.exe", "lib", "install", "ArduinoBLE"],
            ["arduino-cli.exe", "config", "init", "--overwrite"],
            ["arduino-cli.exe", "config", "add", "board_manager.additional_urls", "https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json"],
            ["arduino-cli.exe", "core", "update-index"],
            ["arduino-cli.exe", "core", "install", "Seeeduino:mbed"],
            ["arduino-cli.exe", "compile", "--fqbn", "Seeeduino:mbed:xiaonRF52840Sense", output_file_path],
            ["arduino-cli.exe", "upload", "-p", port, "--fqbn", "Seeeduino:mbed:xiaonRF52840Sense", output_file_path]
        ]
    
    # Execute the command
    for cmd in commands:
        subprocess.run(cmd, shell=True)

def main():
    unit_id = input("Enter the unit ID: ")
    unit_side = input("Enter the unit side (l or r): ")
    original_file_path = 'arduino/xiao_code/xiao_code.ino'
    output_file_path = f'arduino/xiao_code_compiled/xiao_code_{unit_id}/xiao_code_{unit_id}.ino'
    ports = serial.tools.list_ports.comports()
    found_port = False
    
    for port, desc, _ in sorted(ports):
        if "USB Serial Device" in desc or "usbmodem" in port:
            found_port = True
            break
    if not found_port:
        print("No Arduino found")
        exit()
    print('Port:', port)
    # port = 'COM10'  # Replace with the actual port your Arduino is connected to
    
    # Modify the Arduino code with the unit ID
    modify_arduino_code(unit_id, unit_side, original_file_path, output_file_path)

    # Upload the modified code to the Arduino
    upload_code_to_arduino(output_file_path, port)

if __name__ == "__main__":
    main()