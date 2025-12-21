import math

class AsymmetricLowpass:
    def __init__(self, dt, tau_rise, tau_fall, y0=0.0):
        """
        dt        : sampling interval (seconds)
        tau_rise  : time constant when signal rises (seconds)
        tau_fall  : time constant when signal falls (seconds)
        y0        : initial output value
        """
        self.alpha_rise = 1.0 - math.exp(-dt / tau_rise)
        self.alpha_fall = 1.0 - math.exp(-dt / tau_fall)
        self.y = y0

    def update(self, x):
        """
        Update filter with current input x.
        Uses only current and past values.
        """
        if x > self.y:
            alpha = self.alpha_rise
        else:
            alpha = self.alpha_fall

        self.y += alpha * (x - self.y)
        return self.y