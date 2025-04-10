# SDK for Alvium cameras: Vimba X
# Vimba X Developer Guide: https://docs.alliedvision.com/Vimba_X/Vimba_X_DeveloperGuide/index.html

from vmbpy import *
import numpy as np

class AlviumCamera:
    def __init__(self, maxresolution=(1920, 1200), framerate=60.0, exposure=10.0, roi=None, crop=False, maxfps=False):
        self.maxresolution = maxresolution
        self.framerate = framerate
        self.exposure = exposure
        self.roi = roi
        self.crop = crop
        self.maxfps = maxfps

        self.frame = None
        self.frame_ready = False
        self._counter = 0

        self.vmb = VmbSystem.get_instance()
        self.vmb.__enter__()  # Enter VmbSystem context manually

        self.cam = self.vmb.get_all_cameras()[0]
        self.cam_ctx = self.cam.__enter__()  # manually open camera context

        if self.crop:
            self.set_roi(self.roi)
        self.configure_camera()

        # Only start streaming if not already started
        if not self.cam.is_streaming():
            self.cam.start_streaming(self._frame_callback)
    def configure_camera(self):
        # Pixel Format
        try:
            self.cam.set_pixel_format(PixelFormat.Mono8)
        except:
            print("Warning: Unable to set Mono8 pixel format.")

        # Exposure time (in µs)
        self.set_exposure(self.exposure)

        # Frame rate
        if self.cam.get_feature_by_name("AcquisitionFrameRateEnable").is_writeable():
            self.cam.get_feature_by_name("AcquisitionFrameRateEnable").set(True)

        self.set_framerate(self.framerate)

    def set_exposure(self, exposure=None):
        if exposure is not None:
            self.exposure = exposure
        exposure_us = int(self.exposure * 1000)
        self.cam.ExposureTime.set(exposure_us)
        print(f"Exposure set to {self.exposure} ms")

    def set_framerate(self, framerate=None):
        if framerate is not None:
            self.framerate = framerate

        #self.set_nearest_value('AcquisitionFrameRate', framerate)

        fps_feature = self.cam.AcquisitionFrameRate
        min_, max_ = fps_feature.get_range()
        print(f"Max FPS allowed: {max_:.2f}")

        if self.maxfps or self.framerate > max_:
            self.framerate = max_

        #fps_feature.set(self.framerate)
        print(f"Framerate set to {self.framerate:.2f} FPS")

    def set_roi(self, roi):
        self.cam.stop_streaming()  # <- stop before changing ROI

        self.roi = roi
        x, y, w, h = roi

        # Set size first
        self.set_nearest_value('Width', w)
        self.set_nearest_value('Height', h)

        # Then set offsets
        self.set_nearest_value('OffsetX', x)
        self.set_nearest_value('OffsetY', y)

        # Update internal state
        self.roi = [
            self.cam.OffsetX.get(),
            self.cam.OffsetY.get(),
            self.cam.Width.get(),
            self.cam.Height.get()
        ]

        print(f"ROI set to: x={self.roi[0]}, y={self.roi[1]}, w={self.roi[2]}, h={self.roi[3]}")

        # Restart streaming
        self.cam.start_streaming(self._frame_callback)  # <- restart stream

    def set_nearest_value(self, feat_name: str, feat_value: int):
        feat = self.cam.get_feature_by_name(feat_name)
        try:
            feat.set(feat_value)
        except VmbFeatureError:
            min_, max_ = feat.get_range()
            inc = feat.get_increment()

            if feat_value <= min_:
                val = min_
            elif feat_value >= max_:
                val = max_
            else:
                val = (((feat_value - min_) // inc) * inc) + min_
            feat.set(val)
        
    def move_roi(self, delta):  # delta = [dx, dy]
        roi = np.array(self.roi)
        roi[0] += delta[0]
        roi[1] += delta[1]
        self.set_roi(roi.tolist())

    def _frame_callback(self, cam, stream, frame: Frame):
        try:
            # Only convert if format is not already Mono8
            if frame.get_pixel_format() != PixelFormat.Mono8:
                print(f"Incoming frame format: {frame.get_pixel_format()}")
                try:
                    frame.convert_pixel_format(PixelFormat.Mono8)
                except VmbFeatureError:
                    print("Warning: Could not convert to Mono8")
            self.last_frame_id = frame.get_id()
            self.frame = frame.as_numpy_ndarray()
            self.frame_ready = True
        finally:
            cam.queue_frame(frame)

    def readframe(self, transpose=False):
        if self.frame_ready and self.frame is not None:
            self.frame_ready = False
            return self.frame.T if transpose else self.frame
        else:
            return None
        
    def get_counter_value(self):
        return self.last_frame_id  
    
    def close(self):
        print("Stopping acquisition and closing camera...")
        self.cam.stop_streaming()
        self.cam.__exit__(None, None, None)
        self.vmb.__exit__(None, None, None)
        print("Camera closed.")