import numpy as np
import statistics
import cv2
from ringbuffer import FifoBuffer

class TailTracker():

    def __init__(self, start_point, nsteps, step_size, theta_range, dtheta, illumination='darkfield', ncaudalpoints=4, 
                 buffer_frames_tracking=None, buffer_frames_adaptive_offset=None, adaptive_offset = False, 
                 exclude_swims_from_offset=True, softclamp=False, maxv=None, maxh=None):
        
        self.image = None
        self.start_point = start_point
        self.nsteps = nsteps
        self.step_size = step_size
        self.theta_range = theta_range
        self.dtheta = dtheta
        self.illumination = illumination
        self.thetas = np.arange(self.theta_range[0], self.theta_range[1], self.dtheta)
        self.softclamp = softclamp
        self.maxv = maxv
        self.maxh = maxh

        self.smoothen_intensity_profile = True
        self.smoothing_window = len(self.thetas) // 3
        self.smoothing_iterations = 2
        self.ncaudalpoints = ncaudalpoints

        self.adaptive_offset = adaptive_offset
        self.exclude_swims_from_offset = exclude_swims_from_offset
        self.use_history = False
        if buffer_frames_tracking is not None:
            self.cumulative_tail_angle_buffer = FifoBuffer(buffer_frames_tracking)
            self.swim_state_buffer = FifoBuffer(buffer_frames_tracking*2) #consider having an input parameter for this
            self.adaptive_offset_buffer = FifoBuffer(buffer_frames_adaptive_offset)
            self.use_history = True


    def smoothen(self, signal, window, iterations=2):
        """
        Iterative moving average filter.
        """
        w = np.ones(window)/window
        
        for i in range(iterations):
            signal = np.convolve(signal,w,'same')
        
        return signal
       

    def soft_clamp(self, signal, max_value, softness=0.):
        """
        Soft clamps a signal using the tanh function with controllable softness.

        Parameters:
        - signal: A scalar or NumPy array input signal.
        - max_value: The maximum (absolute) value the signal should be softly clamped to.
        - softness: Controls how soft the clamp is. Higher = softer, Lower = closer to hard clamp.
                    Must be > 0. and < 1.

        Returns:
        - Soft-clamped signal with values approaching ±max_value.
        """
        
        if softness < 0. or softness > 1. :
            raise ValueError("Softness must be in the range [0.,1.]")

        softness = 1. + softness
        
        return max_value * np.tanh(signal / (max_value * softness))


    def rotate_bound(self, angle):
        #function from https://www.pyimagesearch.com/2017/01/02/rotate-images-correctly-with-opencv-and-python/
        (h, w) = self.image.shape[:2]
        (cX, cY) = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D((cX, cY), -angle, 1.0)
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
    
        # compute the new bounding dimensions of the image
        nW = int((h * sin) + (w * cos))
        nH = int((h * cos) + (w * sin))
    
        # adjust the rotation matrix to take into account translation
        M[0, 2] += (nW / 2) - cX
        M[1, 2] += (nH / 2) - cY
    
        # perform the actual rotation and return the image
        return cv2.warpAffine(self.image, M, (nW, nH))


    def fix_tail_direction(self, taildirection, offset=0):
        
        if taildirection == 1:
            self.image = self.rotate_bound(180 + offset)
        elif taildirection == 2:
            self.image = self.rotate_bound(offset)
        elif taildirection == 3:
            self.image = self.rotate_bound(90 + offset)
        elif taildirection == 4:
            self.image = self.rotate_bound(270 + offset)
                    
        return self.image


    def get_points_on_arc(self, current_point, previous_point):
        
        angle_offset = np.arctan2((current_point[1] - previous_point[1]), (current_point[0] - previous_point[0]))

        intensity_profile = []

        imshape = self.image.shape

        X = []
        Y = []
        for a in self.thetas+angle_offset:
            x = current_point[0] + self.step_size*np.cos(a)
            y = current_point[1] + self.step_size*np.sin(a)

            #prevent arc from going out of bounds
            if x >= imshape[1]:
                x = imshape[1]-1
            if y >= imshape[0]:
                y = imshape[0]-1
            
            X.append(int(x))
            Y.append(int(y))
            
        intensity_profile = self.image[Y,X]
        if self.smoothen_intensity_profile:
            intensity_profile = self.smoothen(intensity_profile, window=self.smoothing_window, iterations=self.smoothing_iterations)
            
        if self.illumination == 'brightfield':
            tailidx = np.argmin(intensity_profile)
        if self.illumination == 'darkfield':
            tailidx = np.argmax(intensity_profile)
        
        tailcoords = np.array([X[tailidx], Y[tailidx]])
        
        return tailcoords, np.array(list(zip(X,Y)))


    def estimator(self, type='cumulative_tail_angle', gain_v=1., gain_t=1., adaptive_offset=False):
        
        velocity = 0
        theta = 0
        offset = None

        if type == 'cumulative_tail_angle':

            if self.use_history:

                estimator_history = self.cumulative_tail_angle_buffer.buffer

                if adaptive_offset:
                    offset = statistics.median(self.adaptive_offset_buffer.buffer)                    
                    estimator_history = estimator_history - offset

                estimator_history = np.array(estimator_history)
                theta = sum(estimator_history)

                pos = np.abs(estimator_history[estimator_history>=0])
                neg = np.abs(estimator_history[estimator_history<0])
                if len(pos) == 0:
                    pos = [0]
                if len(neg) == 0:
                    neg = [0]
                velocity = 2 * min([sum(pos),sum(neg)])

            else:                
                angles_abs = np.abs(self.angles[-self.ncaudalpoints:])
                maxangle_abs = np.max(angles_abs)
                meanangle_abs = np.mean(angles_abs)

                velocity = meanangle_abs
                theta = self.cumulative_tail_angle

        return velocity*gain_v, theta*gain_t, offset
    

    def track_tail(self, estimator='cumulative_tail_angle', gain_v=1., gain_t=1., curvature_threshold=0.15):

        tailpoints = [np.array(self.start_point)]
        prev_point = self.start_point
        self.angles = []
        pointsonarc = []

        for i in range(self.nsteps):
            tail, arc = self.get_points_on_arc(tailpoints[-1], prev_point)
            self.angles.append(np.arctan2((tail[1] - tailpoints[-1][1]), 
                                          (tail[0] - tailpoints[-1][0])))
            
            tailpoints.append(tail)
            prev_point = tail
            if len(tailpoints) > 1:
                prev_point = tailpoints[-2]

            pointsonarc.append(arc)

        self.tailpoints = tailpoints

        self.cumulative_tail_angle = sum(self.angles[-self.ncaudalpoints:])

        if self.use_history:
            self.cumulative_tail_angle_buffer.update(self.cumulative_tail_angle)
            self.swim_state_buffer.update(self.cumulative_tail_angle)

        # if np.std(self.angles) > curvature_threshold:
        #     self.swimming = True
        # else:
        #     self.swimming = False
        #     self.adaptive_offset_buffer.update(self.cumulative_tail_angle)

        if max(np.abs(np.diff(self.swim_state_buffer.buffer))) > curvature_threshold:
            self.swimming = True
        else:
            self.swimming = False

        if not self.swimming and self.exclude_swims_from_offset:
            self.adaptive_offset_buffer.update(self.cumulative_tail_angle)
        elif not self.exclude_swims_from_offset:
            self.adaptive_offset_buffer.update(self.cumulative_tail_angle)            
        
        velocity, theta, offset = self.estimator(type=estimator, gain_v=gain_v, gain_t=gain_t, adaptive_offset=self.adaptive_offset)
        
        if self.softclamp:
            velocity = self.soft_clamp(velocity, self.maxv)
            theta = self.soft_clamp(theta, self.maxh)
        
        return tailpoints, pointsonarc, velocity, theta, offset