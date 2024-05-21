## file descriptions
main_gui.py -> initializes gui, run this to see gui capability  
collect_data.py -> functions to collect all smarthub data, handles multiprocessing  
retrieve_data.py -> calls mongodb database to view previously collected data

cred.py -> stores mongodb credentials (DO NOT SHARE)  
params.py -> wheelchair parameters  
base_ble folder -> contains all functions to process gyro into usable metrics

dist/smarthub_executable.exe -> single file executable, will not reference any python files.  Can be generated from command line with ```pyinstaller smarthub_executable.spec```
