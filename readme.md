# Tail-tracking software for headfixed (zebra) fish 

This software package is linked to the publication 'supercoolfish VR behavior' [LINK]

### Overview
This software package was designed to track the tail of a headfixed adult zebrafish (*Danio rerio*) in tandem with the virtual reality (VR) package [LINK].
Input is a video stream of the tail of the fish or an example movie. Ouput consists i.a. of velocity, heading, velocity gain, heading gain, velocity threshold, heading threshold, cumulative tail angle and curvature threshold. This output can be plugged into the VR script to allow for a closed looped VR environment.

<img src="./TT_GUI.png" width="50%">
<br>
### Installation instructions
.yml file
<br>
### User manual
link to short user manual

docstring thing
<br>
### Hardware

allied tech
For the tail tracking, we used an Ximea MQ022RG-CM-S7 USB camera (NIR, 2.2 Mpix, 169FPS). [LINK](https://www.ximea.com/products/usb-vision-industrial/xiq-usb3-compact-cmos-cameras/cmosis-cmv2000-spartan-7-usb3-b-w-nir-compact-camera)  
and a Navitar zoom lens (MVL7000-18-108mm EFL) [LINK](https://www.thorlabs.com/item/MVL7000)  
For lightning, a Thorlabs IR 850nm 900mW LED and T-Cube LED driver were used. [LINK](https://www.thorlabs.com/item/m850l3?aID=5645d0fab002954043018c3840106dce&aC=1))(discontinued), [LINK](https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=2616)  
In our case, we set the exposure time to XXX at 120 fps, which the tail of the fish imaged at approximately 80um/pixel.


<br>
### License
check with FMI
<br>
### Authors
Alex Javier
Sriram Naranayan
Jan Eckhardt
Jaap van Krugten
Rainer Friedrich
