# Tail-tracking software for headfixed (zebra) fish 

This software package is linked to the publication 'supercoolfish VR behavior' [LINK].  
If you use use this code for your publication, please cite us.

### Overview
This software package was designed to track the tail of a headfixed adult zebrafish (*Danio rerio*) to live update a virtual reality (VR) projection [script](https://github.com/sriramrn/fishvr).  

Input is a video stream of the tail of the fish or an example movie.  
Ouput consists of a UDP broadcast (with the velocity, tail angle, swimming T/F and a hardware framecounter readout), a video file, and a log file with i.a. of velocity, heading, velocity gain, heading gain, velocity threshold, heading threshold, cumulative tail angle and curvature threshold. The VR script can use the UDP broadcast information to create a closed looped VR environment.

<img src="./TT_GUI.png" width="50%">

## System requirements
PC
python

## Installation instructions
.yml file

## User manual
The tail-tracking GUI can either be runfromcamera.py with live video from a fish or runfromfile.py with an example video (example can be found [here](sample_videos)). The latter allows the user to test the entire VR system without using a live fish.  

Input parameters such as camera type, illumination, tracking settings and save paths are entered manually (runfromfile.py) or can be read from a .ini file (for the runfromvideo.py).  
Running either script will show a GUI with position controls for the ROI of the live video stream, sliders with tracking parameters, and two output graphs with the estimated velocity and heading. The sliders allow the user to update some tracking parameters live. The resulting tracking is also plotted on top of the video stream of the fish. An output video file, log file and UDP broadcast are continuously updated. ROI and tracking configurations can be saved to use again later.

### Tracking
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
