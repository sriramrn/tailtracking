from pathlib import Path
import sys
import numpy as np
import cv2
from ximeacamera import XimeaCamera
from cameraview import TailTrackView
from videowriter import VideoWriter
from tailtracker import TailTracker
from ringbuffer import FifoBuffer
import copy
import socket
import struct
import time
import csv
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()


"""
TODO
1) swap width and height based on taildirection value ----- DONE
2) save tail points, cumulative tail bend angle, gains and framecount to csv file
3) scale marker sizes for overlay based on image dimensions ----- DONE
"""

"""
INPUT PARAMETERS
"""

savepath = 'tailtracking/log/' # path to save video and log file
savevideo = False # grayscale video without tracking overlay is saved
logdata = False

# Camera parameters
maxresolution=[2048,1088]       # full sensor size
framerate = 150                 # framerate to use in Hz. Higher values lead to dropped frames. Use counters to check if the numbers are acceptable
exposure = 1.                   # exposure time in milliseconds
crop = True                     # crop
roi=[4, 4, 180, 240]            # ROI x, y, w, h. Note that rotations to fix tail direction may transpose width and height

# Tail tracking
illumination = 'darkfield'      # darkfield or brightfield tail illumination
taildirection = 2               # direction the tail is facing. display will be rotated accordingly for tracking 1, 2, 3 or 4. 
gainv = 1.                      # forward gain to initialize sliders
gainh = 1.                      # turning gain to initialize sliders
tail_tracking_nsteps = 5        # number of points to track, excluding the stationary start point at the base of the tail
tail_tracking_step_size = 25    # step size between successive tail tracking points
theta_range = [-.8,.8]          # angular range in radians to search for the tail, center of the range is rotated based on the angle of the previous segment
dtheta = 0.12                   # angular step size to extract a radial intensity profile
start_point_offset = [0, 0]     # offset to position the start point format: [x,y], x can only be positive, y can have negative or positive values relative to 0.5x frame height
blur = True                     # spatial filter to blur video frames before tail tracking
blur_kernel = [3,3]             # kernel size to apply blur (stackBlur function from opencv, similar to a Gaussian blur, speed independent of kernel size)
show_arc = True                 # visualize arcs used to find tail
show_midline = True             # show an imaginary line down the middle of the frame to aid with tail positioning

buffer_size = 5.                # length of the circular buffer in seconds. velocity and heading plots will go back in time this many seconds  
lowpass_tau = 100               # time constant, in milliseconds, of the lowpass filter to simulate inertial effects of swimming 
estimator_history = 0.2         # history in seconds taken from the buffer to feed into the estimator for velocity and heading calculation
estimator = 'cumulative_tail_angle' # estimator to use for velocity and heading calculation

broadcast_udp = True            # broadcast UDP message to Panda3D. Same address and port must be used by the listener            
udp_ip = '127.0.0.1'
udp_port = 5005

# GUI
gui_window_size = [800,500]     # size of the GUI window
plot_fps=False                  # plotting fps reduces performance significantly. use only for diagnostics

"""
INPUT PARAMETERS END HERE
"""

if savevideo or logdata:

    videofile = filedialog.asksaveasfilename(initialdir=savepath, title='Save video as', defaultextension='.mp4', filetypes=[('MP4 files', '*.mp4')])

    if len(videofile) == 0:
        print("No file selected, will continue without saving")
        savevideo = False
        logdata = False
    else:
        logfile = videofile.split('.')[0] + '_tracking.csv'
                

cam = XimeaCamera(maxresolution, framerate, exposure, roi, crop=crop, maxfps=False)
cam.opencamera()

"""
# Use these counters to check for dropped frames. 
# Save "XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES" value at each time step when acquiring.
# Compare "XI_CNT_SEL_API_SKIPPED_FRAMES" and "XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES" values 
# at the start and end of a recording when changing settings to assess performance. 
"""
# cam.cam.set_counter_selector("XI_CNT_SEL_API_SKIPPED_FRAMES")         # number of frames skipped at the API layer
# cam.cam.set_counter_selector("XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES")   # number of frames skipped at the transport layer
cam.cam.set_counter_selector("XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES") # frames transferred to buffer


def get_start_point(framesize, offset):
    start_point = [offset[0], int(framesize[1]/2 + offset[1])]
    return start_point

if crop:
    width = roi[2]
    height = roi[3]
else:
    width = maxresolution[0]
    height = maxresolution[1]

if taildirection == 3 or taildirection == 4:
    framesize = [height, width]
elif taildirection == 1 or taildirection == 2:
    framesize = [width, height]

start_point = get_start_point(framesize, start_point_offset)

markersize = int(min(width,height)//150)+1

buffer_frames = int(buffer_size*framerate)
lptau_frames = int(lowpass_tau*framerate/1000.0)
estimator_frames = int(estimator_history*framerate)

cumulative_tail_angle_buffer = FifoBuffer(buffer_frames)
velocity_buffer = FifoBuffer(buffer_frames, lptau_frames)
theta_buffer = FifoBuffer(buffer_frames, lptau_frames)
fpsbuffer = FifoBuffer(buffer_frames)

if savevideo:
    writer = VideoWriter(framesize=framesize, framerate=framerate, saveas=videofile)

if logdata:
    tail_points_header = ['pt_{}'.format(x) for x in range(tail_tracking_nsteps+1)]
    datafile = open(logfile, 'w', encoding='utf-8',  newline='')
    logger = csv.writer(datafile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
    logger.writerow(['framecount', 'velocity', 'heading', 'gain_v', 'gain_h', 'cumulative tail angle', *tail_points_header])    

if broadcast_udp:
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP socket

liveview = TailTrackView(framesize=framesize, windowsize=gui_window_size, gainv=gainv, gainh=gainh, plotfps=plot_fps, start_point_offset=start_point_offset)

tracker = TailTracker(start_point=start_point, nsteps=tail_tracking_nsteps, step_size=tail_tracking_step_size,
                      theta_range=theta_range, dtheta=dtheta, illumination=illumination)

counter = 0
velocity = 0
theta = 0

while True:

    frame = cam.readframe()

    counter = cam.cam.get_counter_value()

    frametime = time.time()

    tracker.image = frame

    frame = tracker.fix_tail_direction(taildirection)

    if blur:
        frame = cv2.stackBlur(frame,ksize=blur_kernel)            

    tail, arc, vel, th = tracker.track_tail(estimator=estimator, gain_v=1, gain_t=3, 
                                            history=cumulative_tail_angle_buffer.buffer[-estimator_frames::])

    velocity_buffer.update(vel*gainv)
    theta_buffer.update(th*gainh)
    cumulative_tail_angle_buffer.update(tracker.cumulative_tail_angle)
    fpsbuffer.update(liveview.fps)

    velocity = velocity_buffer.buffer[-1]
    theta = theta_buffer.buffer[-1]

    if broadcast_udp:
        message = struct.pack('>ddi', velocity, theta, counter)
        udp_socket.sendto(message, (udp_ip, udp_port))

    liveview.velocity = velocity_buffer.buffer
    liveview.heading = theta_buffer.buffer
    liveview.fpsbuffer = fpsbuffer.buffer

    imtoshow = copy.deepcopy(frame)
    imtoshow = cv2.cvtColor(imtoshow, cv2.COLOR_GRAY2BGR)

    if show_midline:
        cv2.line(imtoshow, [0,tail[0][1]], [framesize[0],tail[0][1]], (64,11,11), markersize)

    if show_arc:
        for pts in arc:
            temp = cv2.polylines(imtoshow, pts.reshape(-1,1,2), isClosed=True, color=(0,255,255), thickness=markersize)

    for i in range(len(tail)):
        cv2.circle(imtoshow, tail[i], markersize, (255,219,0), -1)

    liveview.update_frame(imtoshow.transpose(1,0,2))

    gainv = liveview.gainv
    gainh = liveview.gainh

    if savevideo:
        writer.write_frame(frame)

    if logdata:
        logger.writerow([counter, velocity, theta, gainv, gainh, tracker.cumulative_tail_angle, *tail])

    if liveview.end:
        break

    if liveview.update_start_point:
        start_point = get_start_point(framesize, liveview.start_point_offset)
        tracker.start_point = start_point
        liveview.update_start_point = False

    if liveview.toggle_move:
        if liveview.move_up:
            cam.setROI(np.array(cam.roi)+np.array([4,0,0,0]))
        if liveview.move_down:
            cam.setROI(np.array(cam.roi)+np.array([-4,0,0,0]))
        if liveview.move_left:
            cam.setROI(np.array(cam.roi)+np.array([0,-4,0,0]))
        if liveview.move_right:
            cam.setROI(np.array(cam.roi)+np.array([0,4,0,0]))

cam.close()

if savevideo:
    writer.close()
if logdata:
    datafile.close()