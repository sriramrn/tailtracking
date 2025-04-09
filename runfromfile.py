import cv2
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
root.update()


"""
INPUT PARAMETERS
"""

videosource = 'sample_videos/test_vid_from_exp_short.mp4'#'sample_videos/test_vid_large.mp4' # path to video file
savepath = 'log/' # path to save video and log file
savevideo = True # grayscale video without tracking overlay is saved
logdata = True

illumination = 'darkfield'      # darkfield or brightfield tail illumination
taildirection = 2               # direction the tail is facing. display will be rotated accordingly for tracking 1, 2, 3 or 4. 
gainv = 0.001                   # forward gain to initialize sliders
gainh = 0.05                    # turning gain to initialize sliders
threshold_v = 0.001             # threshold to detect forward swims from the scaled estimate
threshold_h = 0.02              # threshold to detect turns from the scaled estimate
tail_tracking_nsteps = 7        # number of points to track, excluding the stationary start point at the base of the tail
tail_tracking_step_size = 35    # step size between successive tail tracking points
theta_range = [-1.,1.]          # angular range in radians to search for the tail, center of the range is rotated based on the angle of the previous segment
dtheta = 0.12                   # angular step size to extract a radial intensity profile
start_point_offset = [5,0]      # offset to position the start point format: [x,y], x can only be positive, y can have negative or positive values relative to 0.5x frame height
angle_offset = 0                # tilt in tail position w.r.t horizontal
blur = True                     # spatial filter to blur video frames before tail tracking
blur_kernel = [3,3]             # kernel size to apply blur (stackBlur function from opencv, similar to a Gaussian blur, speed independent of kernel size)
show_arc = True                 # visualize arcs used to find tail
show_midline = True             # show an imaginary line down the middle of the frame to aid with tail positioning

buffer_size = 30.               # length of the circular buffer in seconds. velocity and heading plots will go back in time this many seconds  
lowpass_tau = 200               # time constant, in milliseconds, of the lowpass filter to simulate inertial effects of swimming 
estimator_history = 0.5         # history in seconds taken from the buffer to feed into the estimator for velocity and heading calculation
estimator = 'cumulative_tail_angle' # estimator to use for velocity and heading calculation
adaptive_offset = True          # correct for tail position changes over time
adaptive_offset_history = 20.   # history in seconds taken from the buffer for adaptive offset calculation

broadcast_udp = True            # broadcast UDP message to Panda3D. Same address and port must be used by the listener            
udp_ip = '127.0.0.1'
udp_port = 5005

gui_window_size = [800,500]     # size of the GUI window
gui_window_position = [100,100] # initial position on the screen
plot_fps = False                # plotting fps reduces performance significantly. use only for diagnostics

# Use to slow down video processing to simulate camera capture rates
clampfps = False   # clamp framerate to simulate a real recording.  
maxfps = 150       # fps to set when clampfps is true, the displayed fps value will not be accurate but will be close to this value, irrespective.

"""
INPUT PARAMETERS END HERE
"""

if savevideo or logdata:

    videofile = filedialog.asksaveasfilename(initialdir=savepath, initialfile='_tracking', title='Save video as', defaultextension='.mp4', filetypes=[('MP4 files', '*.mp4')])

    if len(videofile) == 0:
        print("No file selected, will continue without saving")
        savevideo = False
        logdata = False
    else:
        logfile = videofile.split('.')[0] + '.csv'     


cap = cv2.VideoCapture(videosource)
framerate = cap.get(cv2.CAP_PROP_FPS)
width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

def get_start_point(framesize, offset):
    start_point = [offset[0], int(framesize[1]/2 + offset[1])]
    return start_point

if taildirection == 3 or taildirection == 4:
    framesize = [height, width]
elif taildirection == 1 or taildirection == 2:
    framesize = [width, height]

start_point = get_start_point(framesize, start_point_offset)

markersize = int(min(width,height)//100)+1

buffer_frames = int(buffer_size*framerate)
lptau_frames = int(lowpass_tau*framerate/1000.0)
estimator_frames = int(estimator_history*framerate)
adaptive_offset_frames = int(adaptive_offset_history*framerate)

cumulative_tail_angle_buffer = FifoBuffer(buffer_frames)
velocity_buffer = FifoBuffer(buffer_frames, lptau_frames, threshold=threshold_v)
theta_buffer = FifoBuffer(buffer_frames, lptau_frames, threshold=threshold_h)
fpsbuffer = FifoBuffer(buffer_frames)

if savevideo:
    writer = VideoWriter(framesize=framesize, framerate=framerate, saveas=videofile)

if logdata:
    tail_points_header = ['pt_{}'.format(x) for x in range(tail_tracking_nsteps+1)]
    datafile = open(logfile, 'w', encoding='utf-8',  newline='')
    logger = csv.writer(datafile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
    logger.writerow(['framecount', 'velocity', 'heading', 'gain_v', 'gain_h', 'threshold_v', 'threshold_h', 'cumulative tail angle', 'offset', *tail_points_header])    

if broadcast_udp:
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP socket

liveview = TailTrackView(framesize=framesize, windowsize=gui_window_size, windowposition=gui_window_position, gainv=gainv, gainh=gainh,
                         thresh_v=threshold_v, thresh_h=threshold_h, plotfps=plot_fps, start_point_offset=start_point_offset, angle_offset=angle_offset)

tracker = TailTracker(start_point=start_point, nsteps=tail_tracking_nsteps, step_size=tail_tracking_step_size, 
                      theta_range=theta_range, dtheta=dtheta, illumination=illumination)

framecount = 0
velocity = 0
theta = 0

consecutive_skips = 0
max_consec_skips = 10

clampdt = 1./maxfps
frametime = time.time()
prevframetime = time.time()

while True:

    ret, frame = cap.read()

    if ret:

        framecount += 1
        frametime = time.time()

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        tracker.image = frame

        frame = tracker.fix_tail_direction(taildirection, angle_offset)

        if blur:
            frame = cv2.stackBlur(frame,ksize=blur_kernel)            

        tail, arc, vel, th, offs = tracker.track_tail(estimator=estimator, gain_v=gainv, gain_t=gainh, history=cumulative_tail_angle_buffer.buffer, 
                                                      estimator_frames=estimator_frames, adaptive_offset=adaptive_offset, adaptive_offset_frames=adaptive_offset_frames)

        velocity_buffer.update(vel)
        theta_buffer.update(th)
        cumulative_tail_angle_buffer.update(tracker.cumulative_tail_angle)
        fpsbuffer.update(liveview.fps)
    
        velocity = velocity_buffer.buffer[-1]
        theta = theta_buffer.buffer[-1]

        if broadcast_udp:
            message = struct.pack('>ddi', velocity, theta, framecount)
            udp_socket.sendto(message, (udp_ip, udp_port))

        liveview.velocity = velocity_buffer.buffer
        liveview.heading = theta_buffer.buffer
        liveview.fpsbuffer = fpsbuffer.buffer

        imtoshow = copy.deepcopy(frame)
        imtoshow = cv2.cvtColor(imtoshow, cv2.COLOR_GRAY2BGR)

        if show_midline:
            cv2.line(imtoshow, [0,tail[0][1]], [int(framesize[0]),tail[0][1]], (64,11,11), markersize)

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
        velocity_buffer.threshold = threshold_v
        theta_buffer.threshold = threshold_h

        if savevideo:
            writer.write_frame(frame)

        if logdata:
            logger.writerow([framecount, velocity, theta, gainv, gainh, threshold_v, threshold_h, tracker.cumulative_tail_angle, offs, *tail])

        if liveview.end:
            break

        if liveview.update_offsets:
            start_point = get_start_point(framesize, liveview.start_point_offset)
            angle_offset = liveview.angle_offset
            tracker.start_point = start_point
            liveview.update_offsets = False

        consecutive_skips = 0
    else:
        consecutive_skips += 1
        if consecutive_skips >= max_consec_skips:
            break

    if clampfps:
        dt = frametime - prevframetime
        prevframetime = frametime
        if dt < clampdt:
            waitfor = clampdt - dt
            now = time.time()
            while True:
                if time.time() - now >= waitfor:
                    break

cap.release()

if savevideo:
    writer.close()
if logdata:
    datafile.close()