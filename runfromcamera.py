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
import configparser
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

savepath = config['params']['savepath']         # path to save video and log file
savevideo = bool(config['params']['savevideo']) # grayscale video without tracking overlay is saved
logdata = bool(config['params']['logdata'])

# Camera parameters
maxresolution=[int(config['params']['sensor_x']), int(config['params']['sensor_y'])] # full sensor size
framerate = int(config['params']['framerate']) # framerate to use in Hz
exposure = float(config['params']['exposure']) # exposure time in milliseconds
crop = bool(config['params']['crop'])          # crop to ROI or use full sensor size
roi=[int(config['params']['roix']), int(config['params']['roiy']), int(config['params']['roiw']), int(config['params']['roih'])]

# Tail tracking
illumination = config.get('params', 'illumination')     # darkfield or brightfield tail illumination
taildirection = config.getint('params', 'taildirection')# direction the tail is facing. display will be rotated accordingly for tracking 1, 2, 3 or 4.
gainv = config.getfloat('params', 'gainv')              # forward gain to initialize sliders
gainh = config.getfloat('params', 'gainh')              # turning gain to initialize sliders
tail_tracking_nsteps = config.getint('params', 'tail_tracking_nsteps')  # number of points to track, excluding the stationary start point at the base of the tail
tail_tracking_step_size = config.getint('params', 'tail_tracking_step_size')    # step size between successive tail tracking points
theta_range = [-config.getfloat('params', 'theta_range'), config.getfloat('params', 'theta_range')] # angular range in radians to search for the tail
dtheta = config.getfloat('params', 'dtheta')            # angular step size to extract a radial intensity profile
start_point_offset = [config.getint('params', 'offset_x'), config.getint('params', 'offest_y')] # offset to position the start point format: [x,y]                                                  
blur = config.getboolean('params', 'blur')              # spatial filter to blur video frames before tail tracking
blur_kernel = [config.getint('params', 'blur_kernel'), config.getint('params', 'blur_kernel')]
show_arc = config.getboolean('params', 'show_arc')      # visualize arcs used to find tail
show_midline = config.getboolean('params', 'show_midline')   # show an imaginary midline

buffer_size = config.getfloat('params', 'buffer_size')  # length of the circular buffer in seconds. velocity and heading plots will go back in time this many seconds  
lowpass_tau = config.getint('params', 'lowpass_tau')    # time constant, in milliseconds, of the lowpass filter to simulate inertial effects of swimming
estimator = config.get('params', 'estimator')           # estimator to use for velocity and heading calculation
estimator_history = config.getfloat('params', 'estimator_history') # history in seconds taken from the buffer to feed into the estimator for velocity and heading calculation
broadcast_udp = config.getboolean('params', 'broadcast_udp') # broadcast UDP message to Panda3D. Same address and port must be used by the listener            
udp_ip = config.get('params','udp_ip')
udp_port = config.getint('params','udp_port')

# GUI
gui_window_size = [config.getint('params', 'gui_window_w'), config.getint('params', 'gui_window_h')] # size of the GUI window
plot_fps = config.getboolean('params', 'plot_fps') # plotting fps reduces performance significantly. use only for diagnostics

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

    if liveview.saveconfig:
        # save updated configuration to file
        config['params']['roix'] =  str(cam.roi[0])
        config['params']['roiy'] =  str(cam.roi[1])
        config['params']['roiw'] =  str(cam.roi[2])
        config['params']['roih'] =  str(cam.roi[3])
        config['params']['gainv'] = str(gainv)
        config['params']['gainh'] = str(gainh)
        config['params']['offset_x'] = str(liveview.start_point_offset[0])
        config['params']['offset_y'] = str(liveview.start_point_offset[1])

        with open(liveview.saveconfigas, 'w') as configfile:
            config.write(configfile)

        liveview.saveconfig = False

cam.close()

if savevideo:
    writer.close()
if logdata:
    datafile.close()