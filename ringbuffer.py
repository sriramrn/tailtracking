import numpy as np

class FifoBuffer():

    def __init__(self, length, rc_timeconstant = None):
        self.length = length
        self.buffer = np.array([])
        self.rc_timeconstant = rc_timeconstant            

        if len(self.buffer) == 0:
            self.update(0.)

    def update(self, value):
        if self.rc_timeconstant is not None and len(self.buffer) > 1:
            value = self.lowpass(value)

        if len(self.buffer) == self.length:
            self.buffer = self.buffer[1::]
        if len(self.buffer) < self.length:
            self.buffer = np.concatenate([self.buffer,[value]])

    def lowpass(self, value):
        alpha = 1./(self.rc_timeconstant + 1.)
        filt = self.buffer[-1] + alpha*(value-self.buffer[-1])
        return filt