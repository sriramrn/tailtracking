import numpy as np
import cv2
# from ximeacamera import XimeaCamera # optional import based on .ini specification
from cameraview import TailTrackView
from videowriter import VideoWriter
from tailtracker import TailTracker
from ringbuffer import FifoBuffer
import copy
import socket
import struct
import time
import csv
import configparser
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.update()


"""
INPUT PARAMETERS
"""

configfile = None
if configfile is None:
    configfile = filedialog.askopenfilename(initialdir='.', title='Select configuration file', filetypes=[('INI files', '*.ini')])

config = configparser.ConfigParser()
config.read(configfile)

savepath = config.get('params', 'savepath') # path to save video and log file
savevideo = config.getboolean('params', 'savevideo') # grayscale video without tracking overlay is saved
logdata = config.getboolean('params', 'logdata')

# Camera parameters
camera_type = config.get('params', 'camera') # ximea or alvium
maxresolution = [config.getint('params', 'sensor_x'), config.getint('params', 'sensor_y')] # maximum resolution of the camera
framerate = config.getint('params', 'framerate') # frame rate in frames per second
exposure = config.getfloat('params', 'exposure') # exposure time in milliseconds
crop = config.getboolean('params', 'crop') # crop the video to the region of interest
roi = [config.getint('params', 'roix'), config.getint('params', 'roiy'), config.getint('params', 'roiw'), config.getint('params', 'roih')] # region of interest

# Tail tracking
illumination = config.get('params', 'illumination')     # darkfield or brightfield tail illumination
taildirection = config.getint('params', 'taildirection')# direction the tail is facing. display will be rotated accordingly for tracking 1, 2, 3 or 4.
gainv = config.getfloat('params', 'gainv')              # forward gain to initialize sliders
gainh = config.getfloat('params', 'gainh')              # turning gain to initialize sliders
threshold_v = config.getfloat('params', 'threshold_v')  # threshold to detect forward swims from the scaled estimate
threshold_h = config.getfloat('params', 'threshold_h')  # threshold to detect turns from the scaled estimate
maxv = config.getfloat('params', 'maxv')                # maximum value allowed for forward velocity
maxh = config.getfloat('params', 'maxh')                # maximum value allowed for heading change (convert)
clamptomax = config.getboolean('params', 'clamptomax')  # clamp velocity and heading to maxv and maxh, respectively.
tail_tracking_nsteps = config.getint('params', 'tail_tracking_nsteps')  # number of points to track, excluding the stationary start point at the base of the tail
tail_tracking_step_size = config.getint('params', 'tail_tracking_step_size')    # step size between successive tail tracking points
theta_range = [-config.getfloat('params', 'theta_range'), config.getfloat('params', 'theta_range')] # angular range in radians to search for the tail
dtheta = config.getfloat('params', 'dtheta')            # angular step size to extract a radial intensity profile
start_point_offset = [config.getint('params', 'offset_x'), config.getint('params', 'offset_y')] # offset to position the start point format: [x,y]
angle_offset = config.getint('params', 'offset_a')      # rotational offset to make tail horizontal                                                  
blur = config.getboolean('params', 'blur')              # spatial filter to blur video frames before tail tracking
blur_kernel = [config.getint('params', 'blur_kernel'), config.getint('params', 'blur_kernel')]
show_arc = config.getboolean('params', 'show_arc')      # visualize arcs used to find tail
show_midline = config.getboolean('params', 'show_midline')  # show an imaginary midline

buffer_size = config.getfloat('params', 'buffer_size')  # length of the circular buffer in seconds. velocity and heading plots will go back in time this many seconds  
lowpass_tau_v = config.getint('params', 'lowpass_tau_v')    # time constant for forward velocity, in milliseconds, of the lowpass filter to simulate inertial effects of swimming
lowpass_tau_h = config.getint('params', 'lowpass_tau_h')    # time constant for heading, in milliseconds
estimator = config.get('params', 'estimator')           # estimator to use for velocity and heading calculation
estimator_history = config.getfloat('params', 'estimator_history') # history in seconds taken from the buffer to feed into the estimator for velocity and heading calculation
n_caudal_points = config.getint('params', 'n_caudal_points') # number of caudal tail points (from the end of tail) to use for velocity estimation
adaptive_offset = config.get('params', 'adaptive_offset')    # correct for tail position changes over time
adaptive_offset_history = config.getfloat('params', 'adaptive_offset_history')  # history in seconds taken from the buffer for adaptive offset calculation
curvature_threshold = config.getfloat('params', 'curvature_threshold')          # standard deviations in radians for the tail segment angles to classify if swimming
broadcast_udp = config.getboolean('params', 'broadcast_udp') # broadcast UDP message to Panda3D. Same address and port must be used by the listener            
udp_ip = config.get('params','udp_ip')
udp_port = config.getint('params','udp_port')

# GUI
gui_window_size = [config.getint('params', 'gui_window_w'), config.getint('params', 'gui_window_h')]        # size of the GUI window
gui_window_position = [config.getint('params', 'gui_window_x'), config.getint('params', 'gui_window_y')]    # size of the GUI window
plot_fps = config.getboolean('params', 'plot_fps')              # plotting fps reduces performance significantly. use only for diagnostics
seconds_to_plot = config.getfloat('params', 'seconds_to_plot')  # seconds to plot in the GUI window (for velocity and heading)


"""
INPUT PARAMETERS END HERE
"""

"""
CAMERA SETUP
"""

if camera_type.lower() == 'ximea':
    from ximeacamera import XimeaCamera
    cam = XimeaCamera(maxresolution, framerate, exposure, roi, crop=crop, maxfps=False)
    cam.opencamera()
    cam.cam.set_counter_selector("XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES")
elif camera_type.lower() == 'alvium':
    from alviumcamera import AlviumCamera
    cam = AlviumCamera(maxresolution, framerate, exposure, roi, crop=crop, maxfps=False)
else:
    raise ValueError(f"Unsupported camera type: {camera_type}")

if savevideo or logdata:

    videofile = filedialog.asksaveasfilename(initialdir=savepath, initialfile='_tracking', title='Save video as', defaultextension='.mp4', filetypes=[('MP4 files', '*.mp4')])

    if len(videofile) == 0:
        print("No file selected, will continue without saving")
        savevideo = False
        logdata = False
    else:
        logfile = videofile.split('.')[0] + '.csv'
                

#cam = XimeaCamera(maxresolution, framerate, exposure, roi, crop=crop, maxfps=False)
#cam.opencamera()

"""
# Use these counters to check for dropped frames. 
# Save "XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES" value at each time step when acquiring.
# Compare "XI_CNT_SEL_API_SKIPPED_FRAMES" and "XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES" values 
# at the start and end of a recording when changing settings to assess performance. 
"""
# cam.cam.set_counter_selector("XI_CNT_SEL_API_SKIPPED_FRAMES")         # number of frames skipped at the API layer
# cam.cam.set_counter_selector("XI_CNT_SEL_TRANSPORT_SKIPPED_FRAMES")   # number of frames skipped at the transport layer
#cam.cam.set_counter_selector("XI_CNT_SEL_TRANSPORT_TRANSFERRED_FRAMES") # frames transferred to buffer


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
lptau_frames_v = int(lowpass_tau_v*framerate/1000.0)
lptau_frames_h = int(lowpass_tau_h*framerate/1000.0)
estimator_frames = int(estimator_history*framerate)
adaptive_offset_frames = int(adaptive_offset_history*framerate)
frames_to_plot = int(seconds_to_plot*framerate)

velocity_buffer = FifoBuffer(buffer_frames, lptau_frames_v, threshold=threshold_v)
theta_buffer = FifoBuffer(buffer_frames, lptau_frames_h, threshold=threshold_h)
fpsbuffer = FifoBuffer(buffer_frames)

if savevideo:
    writer = VideoWriter(framesize=framesize, framerate=framerate, saveas=videofile)

if logdata:
    tail_points_header = ['pt_{}'.format(x) for x in range(tail_tracking_nsteps+1)]
    datafile = open(logfile, 'w', encoding='utf-8',  newline='')
    logger = csv.writer(datafile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
    logger.writerow(['framecount', 'velocity', 'heading', 'gain_v', 'gain_h', 'threshold_v', 'threshold_h', 
                     'cumulative tail angle', 'curvature_threshold', 'swimming', 'offset', *tail_points_header])    

if broadcast_udp:
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP socket

liveview = TailTrackView(framesize=framesize, windowsize=gui_window_size, windowposition=gui_window_position, gainv=gainv, gainh=gainh,
                         thresh_v=threshold_v, thresh_h=threshold_h, plotfps=plot_fps, start_point_offset=start_point_offset, 
                         angle_offset=angle_offset, pointstoplot=frames_to_plot)

tracker = TailTracker(start_point=start_point, nsteps=tail_tracking_nsteps, step_size=tail_tracking_step_size, theta_range=theta_range,
                      dtheta=dtheta, illumination=illumination, ncaudalpoints=n_caudal_points, buffer_frames_tracking=estimator_frames,
                      buffer_frames_adaptive_offset=adaptive_offset_frames, adaptive_offset=adaptive_offset)

counter = 0
velocity = 0
theta = 0

while True:
    frame = cam.readframe()
    if frame is None:
        continue  # skip iteration if no frame yet, might happen with alvium cam 
    if camera_type == "ximea":
        counter = cam.cam.get_counter_value()
    elif camera_type == "alvium":
        counter = cam.get_counter_value() 

    frametime = time.time()

    tracker.image = frame

    frame = tracker.fix_tail_direction(taildirection, angle_offset)

    if blur:
        frame = cv2.stackBlur(frame,ksize=blur_kernel)            

    tail, arc, vel, th, offs = tracker.track_tail(estimator=estimator, gain_v=gainv, gain_t=gainh, curvature_threshold=curvature_threshold,
                                                  softclamp=clamptomax, maxv=maxv, maxh=maxh)

    velocity_buffer.update(vel)
    theta_buffer.update(th)
    fpsbuffer.update(liveview.fps)

    velocity = velocity_buffer.buffer[-1]
    theta = theta_buffer.buffer[-1]

    if broadcast_udp:
        message = struct.pack('>dd?i', velocity, theta, tracker.swimming, counter)
        udp_socket.sendto(message, (udp_ip, udp_port))

    liveview.velocity = velocity_buffer.buffer
    liveview.heading = theta_buffer.buffer
    liveview.fpsbuffer = fpsbuffer.buffer

    imtoshow = copy.deepcopy(frame)
    imtoshow = cv2.cvtColor(imtoshow, cv2.COLOR_GRAY2BGR)

    swcol = [50,50,50]
    if tracker.swimming:
        swcol = [0,255,0]
    cv2.circle(imtoshow, (np.array(framesize)-25).astype(int), 8, swcol, -1)
    
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
    threshold_v = liveview.thresh_v
    threshold_h = liveview.thresh_h
    curvature_threshold = liveview.thresh_s
    velocity_buffer.threshold = threshold_v
    theta_buffer.threshold = threshold_h
    
    if savevideo:
        writer.write_frame(frame)

    if logdata:
            logger.writerow([counter, velocity, theta, gainv, gainh, threshold_v, threshold_h, 
                             tracker.cumulative_tail_angle, curvature_threshold, tracker.swimming, offs, *tail])

    if liveview.end:
        break

    if liveview.update_offsets:
        start_point = get_start_point(framesize, liveview.start_point_offset)
        tracker.start_point = start_point
        angle_offset = liveview.angle_offset
        liveview.update_offsets = False

    if liveview.toggle_move:
        if liveview.move_up:
            cam.setROI(np.array(cam.roi)+np.array([4,0,0,0]))
        if liveview.move_down:
            cam.setROI(np.array(cam.roi)+np.array([-4,0,0,0]))
        if liveview.move_left:
            cam.setROI(np.array(cam.roi)+np.array([0,-4,0,0]))
        if liveview.move_right:
            cam.setROI(np.array(cam.roi)+np.array([0,4,0,0]))

    if liveview.saveconfig:
        # save updated configuration to file
        config['params']['roix'] =  str(cam.roi[0])
        config['params']['roiy'] =  str(cam.roi[1])
        config['params']['roiw'] =  str(cam.roi[2])
        config['params']['roih'] =  str(cam.roi[3])
        config['params']['gainv'] = str(gainv)
        config['params']['gainh'] = str(gainh)
        config['params']['threshold_v'] = str(threshold_v)
        config['params']['threshold_h'] = str(threshold_h)
        config['params']['offset_x'] = str(liveview.start_point_offset[0])
        config['params']['offset_y'] = str(liveview.start_point_offset[1])
        config['params']['offset_a'] = str(angle_offset)
        config['params']['curvature_threshold'] = str(curvature_threshold)

        with open(liveview.saveconfigas, 'w') as configfile:
            config.write(configfile)

        liveview.saveconfig = False

cam.close()

if savevideo:
    writer.close()
if logdata:
    datafile.close()