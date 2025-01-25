import os
import subprocess
import serial.tools.list_ports

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
    command = [
        "arduino-cli", "compile", "--fqbn", "arduino:mbed_nano:nano33ble", output_file_path,
        "&&",
        "arduino-cli", "upload", "-p", port, "--fqbn", "arduino:mbed_nano:nano33ble", output_file_path
    ]
    
    # Execute the command
    subprocess.run(" ".join(command), shell=True)

def main():
    unit_id = input("Enter the unit ID: ")
    unit_side = input("Enter the unit side (l or r): ")
    original_file_path = 'base_ble\\arduino_code_copy\\arduino_code_copy.ino'
    output_file_path = f'base_ble\\arduino_code_{unit_id}\\arduino_code_{unit_id}.ino'
    ports = serial.tools.list_ports.comports()
    # port = ports[-1]
    found_port = False
    for port, desc, _ in sorted(ports):
        if "USB Serial Device" in desc:
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