## file descriptions
main_test.py -> main entry point into gui

view_data_tab.py -> view data from database, edit metadata, download metrics

record_data_tab.py -> run tests, save data to gui

calibrate_tab.py -> generate calibration file based on small test run


base_ble folder: metrics calculations

dist/smarthub_executable.exe -> single file executable, will not reference any python files.  Can be generated from command line with ```pyinstaller smarthub_executable.spec```
