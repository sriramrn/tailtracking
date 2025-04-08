import numpy as np
import cv2


class TailTracker():

    def __init__(self, start_point, nsteps, step_size, theta_range, dtheta, illumination='darkfield'):
        
        self.image = None
        self.start_point = start_point
        self.nsteps = nsteps
        self.step_size = step_size
        self.theta_range = theta_range
        self.dtheta = dtheta
        self.illumination = illumination
        self.thetas = np.arange(self.theta_range[0], self.theta_range[1], self.dtheta)

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
            
        intensity_profile.append(self.image[Y,X])
            
        if self.illumination == 'brightfield':
            tailidx = np.argmin(intensity_profile)
        if self.illumination == 'darkfield':
            tailidx = np.argmax(intensity_profile)
        
        tailcoords = np.array([X[tailidx], Y[tailidx]])
        
        return tailcoords, np.array(list(zip(X,Y)))


    def estimator(self, type='cumulative_tail_angle', gain_v=1., gain_t=1., history=None, estimator_frames=1, 
                  adaptive_offset=False, adaptive_offset_frames=1):
        
        velocity = 0
        theta = 0
        offset = None

        if type == 'cumulative_tail_angle':

            if history is not None:

                estimator_history = history[-estimator_frames:]

                if adaptive_offset:
                    offset = np.median(history[-adaptive_offset_frames:])
                    estimator_history = estimator_history - offset
                
                estimator_history = np.array(estimator_history)
                theta = np.sum(estimator_history)

                pos = np.abs(estimator_history[estimator_history>=0])
                neg = np.abs(estimator_history[estimator_history<0])
                if len(pos) == 0:
                    pos = [0]
                if len(neg) == 0:
                    neg = [0]
                velocity = 2 * min([np.sum(pos),np.sum(neg)])

            else:                
                angles_abs = np.abs(self.angles)
                maxangle_abs = np.max(angles_abs)
                meanangle_abs = np.mean(angles_abs)

                velocity = meanangle_abs
                theta = self.cumulative_tail_angle

        return velocity*gain_v, theta*gain_t, offset
    

    def track_tail(self, estimator='cumulative_tail_angle', gain_v=1., gain_t=1., history=None, estimator_frames=1, 
                   adaptive_offset=False, adaptive_offset_frames=1):

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

        self.cumulative_tail_angle = sum(self.angles)

        velocity, theta, offset = self.estimator(type=estimator, gain_v=gain_v, gain_t=gain_t, history=history, estimator_frames=estimator_frames, 
                                                 adaptive_offset=adaptive_offset, adaptive_offset_frames=adaptive_offset_frames)
        
        return tailpoints, pointsonarc, velocity, theta, offset