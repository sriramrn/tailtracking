from ximea import xiapi

class XimeaCamera():

    def __init__(self, maxresolution, framerate, exposure, roi, crop=False, maxfps=False):
        self.cam = xiapi.Camera()
        self.xpixelsmax = maxresolution[0]     #pixels
        self.ypixelsmax = maxresolution[1]     #pixels        
        self.framerate = framerate             #fps
        self.exposure = exposure               #milliseconds 
        self.roi = roi                         #format: x,y,w,h
        self.crop = crop
        self.maxfps = maxfps
        self.xpixels = self.xpixelsmax
        self.ypixels = self.ypixelsmax

    def opencamera(self):

        self.cam.open_device()

        if self.crop:
            self.setROI()

        self.img = xiapi.Image()

        self.cam.start_acquisition()
        self.cam.set_acq_timing_mode("XI_ACQ_TIMING_MODE_FRAME_RATE")
        self.cam.set_imgdataformat("XI_MONO8")
        self.setexposure()

    def setROI(self, roi=None):
        if roi is not None:
            self.roi = roi
        if self.roi[0] + self.roi[2] > self.xpixelsmax:
            self.roi[0] = (self.xpixelsmax - self.roi[2])%4
        if self.roi[0] < 0:
            self.roi[0] = 0 
        if self.roi[1] + self.roi[3] > self.ypixelsmax:
            self.roi[1] = (self.ypixelsmax - self.roi[3])%4
        if self.roi[1] < 0:
            self.roi[1] = 0

        print("ROI moved to: {}".format(self.roi))

        self.xpixels = self.roi[2]
        self.ypixels = self.roi[3]
        self.cam.set_width(self.xpixels)
        self.cam.set_height(self.ypixels)        
        self.cam.set_offsetX(self.roi[0])
        self.cam.set_offsetY(self.roi[1])

    def setexposure(self, exposure=None):
        if exposure is not None:
            self.exposure = exposure
        self.cam.set_exposure(int(self.exposure*1000))
        print('Setting exposure to {}ms'.format(round(self.exposure,2)))
        self.setframerate()

    def setframerate(self, framerate=None):

        if framerate is not None:
            self.framerate = framerate

        maxallowedfps = self.cam.get_framerate_maximum()
        print('max framerate allowed is {}fps'.format(round(maxallowedfps,2)))

        if self.maxfps or self.framerate>maxallowedfps:
            fpstoset = maxallowedfps
        else:
            fpstoset = self.framerate

        print('setting framerate of {}fps'.format(round(fpstoset,2)))
        self.cam.set_framerate(fpstoset)
    
    def readframe(self, transpose=False):
        self.cam.get_image(self.img)
        frame = self.img.get_image_data_numpy()
        if transpose:
            return frame.T
        else:
            return frame
    
    def readgpilevel(self):
        gpilevel = self.cam.get_gpi_level()
        return gpilevel

    def close(self):
        print('Stopping acquisition...')
        self.cam.stop_acquisition()
        self.cam.close_device()
        print('Done.')