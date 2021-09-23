# GMC-Terminal
This program can read and change the voltage on Tube 1 of the GMC-500+ Geiger counter and perform timed counts.
The User Guide for the GMC-500+ can be found here: http://www.gqelectronicsllc.com/GMC-500UserGuide.pdf

Using this program requires the GMC-500+ to be connected via a USB port. 

Before trying to access the device via USB port, you must download the USB driver used for all GQ Geiger Counter devices
The USB driver can be found here: http://www.gqelectronicsllc.com/downloads/download.asp?DownloadID=78
(if the link above fails, go to https://www.gqelectronicsllc.com/comersus/store/download.asp and search for "USB Driver")

To access the device via USB, go to Devices>Open Ports, select a port ("COM[1-256]" on windows), and open it.
You can close a port by going to Devices>Close Ports

Opening the port will display Tube1's voltage as a percentage and allow you to change Tube1's voltage
with the "Write Tube Voltage" buttons in the toolbar

Go to Devices>Factory Reset to reset the device to its factory default, and Devices>Export Configuration Data to get the configuration data from the device.
You can also run a timed count on the Terminal, by entering the duration of your count into the spinboxes on the terminal,
then pressing "Run Count".

When a timed count is finished, a record of the total counts that occurred and the duration of the timed count is recorded in a table
(as long as "Logging Counts" is checked). To export this table to a .csv file, go to Files>Export Count Log

The source code is included in this directory. If you have pyinstaller downloaded, run 'pyinstaller --onefile -w GMCterminalv[n].py' on the command line.
This will create a new .exe in the 'dist' directory that reflects changes in the source code

When adding new features to this program, it is important to know the serial communication protocols for GQ Geiger Counters. 
They can be found in 'GQ-RFC1801.txt' in this directory, or here: http://www.gqelectronicsllc.com/download/GQ-RFC1801.txt

Though graphing features can be easily added to the program, other open-source programs are better for this purpose.
Such programs include:
	1. Geigerlog, a python-based program
	2. GQ Geiger Counter Data Viewer Re. 2.63
	3. GQ Geiger Counter Data Logger PRO V5.61 (registering device required for full use)
All can be found here: https://www.gqelectronicsllc.com/comersus/store/download.asp
