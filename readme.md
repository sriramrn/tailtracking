# Tail-tracking software for headfixed (zebra) fish 

This software package is linked to the publication 'supercoolfish VR behavior' [LINK].  
If you use use this code for your publication, please cite us.

## Overview
This software package was designed to track the tail of a head-fixed adult zebrafish (*Danio rerio*) to live update a virtual reality (VR) projection [script](https://github.com/sriramrn/fishvr).  

Input is a video stream of the tail of the fish or an example movie. Ouput consists of a UDP broadcast (with the velocity, tail angle, swimming T/F and a hardware frame counter readout), a video file, and a log file with i.a. of velocity, heading, velocity gain, heading gain, velocity threshold, heading threshold, cumulative tail angle and curvature threshold. The VR script can use the UDP broadcast information to create a closed looped VR environment.

<img src="./TT_GUI.png" width="50%">

## System requirements
- A computer with a graphics card supporting multiple displays as needed
- Drivers and python wrapper for Ximea or Alvium camera installed as per the instructions on the manufacturers webpage
- The software has been extensively tested on Windows 10 and 11 and is expected to also run across OS platforms that support the specific requirements of the python environment

## Installation instructions
Create a python environment with the dependencies listed in the environment.yml file. This file includes dependencies needed for both the VR and the tail tracking workflows.

## User manual
The tail-tracking GUI can be instantiated either by running runfromcamera.py (live camera feed) or runfromfile.py (video file such as the example found [here](sample_videos)). The runfromile.py script allows the user to test and troubleshoot the entire VR system conveniently.  

Input parameters such as camera type, illumination, tracking settings and save paths are entered in the corresponding fields in code (runfromfile.py) or can be read from a .ini file (runfromvideo.py). Running either script will show a GUI with position controls for the ROI of the live video stream, sliders with tracking parameters, and two output graphs with the estimated velocity and heading updated in real time. The sliders allow the user to update some tracking parameters live. The resulting tracking is overlaid on the video stream of the fish. An output video file, log file and UDP broadcast are continuously updated. The ROI and tracking configurations can be saved to use again later.  

## GUI controls
| Button | Function |
|-----------|-------|
| end | Closes the GUI. Log files will not be terminated correctly if the session is ended by other methods |
| move | Toggles the ROI positioning mode ON or OFF |
| up, down, left, right | These buttons move the ROI in either of the four directions relative to the current position |
| save | Saves the current parameters to a .ini settings file which can be used to initialize subsequent sessions |

| Slider | Function |
|-----------|-------|
| gain_v | Gain multiplier to scale estimated velocity |
| gain_h | Gain multiplier to scale estimated change in heading |
| thresh_v | Threshold below which the velocity is clamped to zero |
| thresh_h | Threshold absolute change in heading below which the value is set to zero |
| x_tail | x-coordinate of the first tracking point |
| y_tail | y-coordinate of the first tracking point |
| angle | Use to set the angle of the tail at the neutral position to be along the horizontal image dimension |
| thresh_s | Threshold rate of change of cumulative tail angle used to detect when the fish is swimming |

## Tracking
The tracking assumes that the fish is within the ROI and the tail is positioned along the user defined midline when at rest in the neutral position. A preselected point placed on the midline at the base of the tail serves as the starting point for tracking. The next point is placed on the peak of the filtered intensity profile of the cross section of the tail at a fixed distance from the current point. This step is repeated for a predetermined number of points along the length of the tail at uniform spacing between them. Recent history is used to adaptively update the orientation of the tail at the resting position, which is used as the baseline to determine the direction of intended swims for updating the VR.

## Hardware
For the tail tracking, we used a Ximea MQ022RG-CM-S7 USB camera (NIR, 2.2 Mpix, 169FPS). [LINK](https://www.ximea.com/products/usb-vision-industrial/xiq-usb3-compact-cmos-cameras/cmosis-cmv2000-spartan-7-usb3-b-w-nir-compact-camera)  
and a Navitar zoom lens (MVL7000-18-108mm EFL) [LINK](https://www.thorlabs.com/item/MVL7000)  
Besides the Ximea camera, there is also an option provided to use an Alvium camera.
For lightning, two Thorlabs IR 850nm 900mW LEDs, each collimated with a 25mm focal length biconvex lens, were placed on either side of the tail [LINK](https://www.thorlabs.com/item/m850l3?aID=5645d0fab002954043018c3840106dce&aC=1).
A bandpass filter centered around 810nm was used to ensure that only the reflected tail-tracking illumination was captured by the tail tracking camera. [LINK](https://midopt.com/filters/bp810/).  

In our case, we defined an ROI dimensions to 360x480 pixels and set the frame rate and exposure time to 150Hz and 2ms respectively.

## References
Inspiration for parts of this code has been drawn from among others:  
- Štih V, Petrucco L, Kist AM, Portugues R (2019) Stytra: An open-source, integrated system for stimulation, tracking and closed-loop behavioral experiments. PLoS Comput Biol 15(4): e1006699. https://doi.org/10.1371/journal.pcbi.1006699  
- Huang, KH., Rupprecht, P., Frank, T. et al. A virtual reality system to analyze neural activity and behavior in adult zebrafish. Nat Methods 17, 343–351 (2020). https://doi.org/10.1038/s41592-020-0759-2  
- Owen Randlett; pi_tailtrack: A compact, inexpensive and open-source behaviour-tracking system for head-restrained zebrafish. J Exp Biol 15 November 2023; 226 (22): jeb246335. doi: https://doi.org/10.1242/jeb.246335

## Authors
Alexandre Javier, Sriram Narayanan, Lukas Anneser, Jaap van Krugten, Rainer W. Friedrich
