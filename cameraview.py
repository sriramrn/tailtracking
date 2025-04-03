from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
from skimage.transform import rescale
from skimage.util import img_as_ubyte
import pyqtgraph as pg
from pyqtgraph.ptime import time
from pyqtgraph.widgets.RawImageWidget import RawImageWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.update()


class LiveViewRaw():

    def __init__(self, framesize, scaling_factor=1.):

        self.scaling_factor = scaling_factor

        self.framesize = framesize
        self.imagesize = (np.array(framesize)*self.scaling_factor).astype(int)

        app = pg.mkQApp()
        self.win = pg.Qt.QtWidgets.QMainWindow()
        self.widget = RawImageWidget()
        self.win.setCentralWidget(self.widget)
        self.win.show()

        if self.imagesize is not None:
            self.win.resize(self.imagesize[1], self.imagesize[0])

    def downscale(self, frame):
        downscaled_frame = rescale(frame, self.scaling_factor, anti_aliasing=False)
        downscaled_frame = img_as_ubyte(downscaled_frame)
        return downscaled_frame

    def update_frame(self, frame):

        if self.scaling_factor != 1:
            frame = self.downscale(frame)

        self.widget.setImage(frame)
        pg.QtGui.QApplication.processEvents()


class LiveView():
        
    def __init__(self, framesize, scaling_factor=1.):

        self.scaling_factor = scaling_factor

        self.framesize = framesize
        self.imagesize = (np.array(framesize)*self.scaling_factor).astype(int)

        ## Create window with GraphicsView widget
        self.win = pg.GraphicsLayoutWidget()
        self.win.show()  ## show widget alone in its own window
        self.win.setWindowTitle('video feed')
        self.view = self.win.addViewBox()
    
        ## Create image item
        self.img = pg.ImageItem(border='w')
        self.view.addItem(self.img)
    
        # ## lock the aspect ratio so pixels are always square
        self.view.setAspectLocked(True)

        ## Set initial view bounds
        if self.imagesize is not None:
            self.view.resize(self.imagesize[1], self.imagesize[0])
            self.view.setRange(QtCore.QRectF(0, 0, self.imagesize[1], self.imagesize[0]))

    def downscale(self, frame):
        downscaled_frame = rescale(frame, self.scaling_factor, anti_aliasing=False)
        downscaled_frame = img_as_ubyte(downscaled_frame)
        return downscaled_frame

    def update_frame(self, frame):

        if self.scaling_factor != 1:
            frame = self.downscale(frame)

        self.img.setImage(frame, autoRange=False, autoLevels=False)
        pg.QtGui.QApplication.processEvents()


class TailTrackView():
        
    def __init__(self, framesize, windowsize=[800,400], windowposition=None, gainv=1., gainh=1., thresh_v=0., thresh_h=0.,
                 start_point_offset=[0,0], angle_offset=0, plotfps=True):

        self.prevframetime = time()
        self.frametime = time()

        self.end = False
        self.update_offsets = False
        self.updateconfig = False
        self.saveconfig = False
        self.configfile = None
        self.saveconfigas = None

        self.gainv = gainv
        self.gainh = gainh
        self.thresh_v = thresh_v
        self.thresh_h = thresh_h
        self.start_point_offset = start_point_offset
        self.angle_offset = angle_offset

        self.velocity = [0]
        self.heading = [0]
        self.fps = 0
        self.fpsbuffer = [self.fps]
        self.plotfps = plotfps

        self.framesize = framesize

        self.app = pg.mkQApp
        ## Create window with GraphicsView widget
        self.win = pg.GraphicsLayoutWidget(border='#646464')
        icon = QIcon("icon.png")
        self.win.setWindowIcon(icon)
        self.win.setFixedSize(*windowsize)
        if windowposition is not None:
            self.win.move(*windowposition)
        # self.win.resize(*windowsize)
        self.win.show()  ## show widget alone in its own window
        self.win.setWindowTitle('Tail Tracker')

        ## Create image item in a view box
        self.view = self.win.addViewBox(lockAspect=True, row=4, col=0, rowspan=3, colspan=1)
        self.img = pg.ImageItem(border='#646464')
        self.view.addItem(self.img)
        
        font = QtGui.QFont("Arial", pointSize=10)
        self.fpstext = pg.TextItem('processed at %i fps' % self.fps)
        self.fpstext.setFont(font)
        self.view.addItem(self.fpstext)

        self.view.setAspectLocked(True)
        
        ## Add plots
        nplots = 2
        plottitles = ['velocity- gain: %0.3f, threshold: %0.3f' % (self.gainv, self.thresh_v),
                      'heading- gain: %0.3f, threshold: %0.3f' % (self.gainh, self.thresh_h)]
        plotrow = [4,5]
        plotcol = [2,2]
        if self.plotfps:
            nplots += 1
            plottitles.append('output fps')
            plotrow.append(6)
            plotcol.append(2)
        
        self.plots = [self.win.addPlot(title=x, row=y, col=z, rowspan=1, colspan=2) for x,y,z in zip(plottitles, plotrow, plotcol)]
        
        [i.setContentsMargins(10,0,0,0) for i in self.plots]
        [i.showGrid(x=True,y=True,alpha=1) for i in self.plots]
        self.plotdata = [i.plot(pen='#ffdb00') for i in self.plots]

        endbutton = QtGui.QPushButton('end')
        self.roiupdatebutton = QtGui.QPushButton('move roi') 
        up = QtGui.QPushButton('up')
        down = QtGui.QPushButton('down')
        left = QtGui.QPushButton('left')
        right = QtGui.QPushButton('right')
        save = QtGui.QPushButton('save')

        buttons = [endbutton, self.roiupdatebutton, up, down, left, right, save]
        button_proxies = [QtGui.QGraphicsProxyWidget() for x in range(7)]
        
        [x.setWidget(y) for x,y in zip(button_proxies,buttons)]

        endbutton.clicked.connect(self.end_button_clicked)
        self.roiupdatebutton.clicked.connect(self.roi_mode)
        save.clicked.connect(self.savebuttonpressed)

        up.pressed.connect(lambda: self.move_roi(b='u'))
        down.pressed.connect(lambda: self.move_roi(b='d'))
        left.pressed.connect(lambda: self.move_roi(b='l'))
        right.pressed.connect(lambda: self.move_roi(b='r'))

        [x.released.connect(self.stop_moving_roi) for x in [up, down, left, right]]
        [x.setAutoRepeat(True) for x in [up, down, left, right]]
        [x.setAutoRepeatInterval(50) for x in [up, down, left, right]]

        button_box = self.win.addLayout(row=0, col=0, rowspan=4, colspan=1)
        button_box.setContentsMargins(20,20,20,20)
        [button_box.addItem(x,row=y,col=z) for x,y,z in zip(button_proxies,[0,0,1,1,2,2,3],[0,1,0,1,0,1,0])]

        # Create sliders
        slider_box = self.win.addLayout(row=0, col=2, rowspan=4, colspan=2)
        slider_box.setContentsMargins(55,10,10,10)

        nsliders = 7
        slider_labels = [pg.LabelItem(x) for x in ['gain_v', 'gain_h', 'thresh_v', 'thresh_h', 'x_tail', 'y_tail', 'angle']]
        slider_ranges = [[0,10], [0,100], [0,20], [0,500], [0,int(framesize[0])], [-int(framesize[1]/2 - 1),int(framesize[1]/2 - 1)], [-20,20]]
        slider_initvals = [int(self.gainv*1000),int(self.gainh*1000), int(self.thresh_v*1000), int(self.thresh_h*1000),
                           self.start_point_offset[0], self.start_point_offset[1], self.angle_offset]

        self.sliders = [pg.Qt.QtWidgets.QSlider(Qt.Horizontal) for x in range(nsliders)]
        [x.setRange(*y) for x,y in zip (self.sliders, slider_ranges)]
        [x.setValue(y) for x,y in zip(self.sliders, slider_initvals)]
        [x.setParentItem(slider_box.graphicsItem()) for x in slider_labels]
        [x.anchor(itemPos=(0.,0.), parentPos=(0.,y)) for x,y in zip(slider_labels, np.linspace(.04, .82, nsliders))]

        styles = "QSlider::groove:horizontal { background: #3b3b3b; position: absolute; left: 0px; right: 0px; border-radius:0px}"
        styles += "QSlider::handle:horizontal { height: 5px; background: #ffa904; margin: 0 -8px; border-style:solid; border-color: grey;border-width:1px;border-radius:3px}"
        # styles += "QSlider::sub-page:horizontal { background: black; border-style:solid; border-color: grey;border-width:1px;border-radius:0px}"
        styles += "QSlider::add-page:horizontal { background: black; border-style:solid; border-color: grey;border-width:1px;border-radius:0px}"        
        [x.setStyleSheet(styles) for x in self.sliders]

        # Add slider to the graphics layout using QGraphicsProxyWidget
        slider_proxies = [pg.QtGui.QGraphicsProxyWidget() for x in range(nsliders)]
        [x.setWidget(y) for x,y in zip(slider_proxies,self.sliders)]
        [slider_box.addItem(x, row=y, col=4, rowspan=1, colspan=1) for x,y in zip(slider_proxies, np.arange(0,nsliders,1))]

        # Connect slider value change to a function
        [x.valueChanged.connect(y) for x,y in zip(self.sliders, [self.slider1_changed, self.slider2_changed, self.slider3_changed, self.slider4_changed,
                                                                 self.offset_changed, self.offset_changed, self.offset_changed])]

        self.toggle_move = False
        self.move_up = False
        self.move_down = False
        self.move_left = False
        self.move_right = False

    def slider1_changed(self):
        self.gainv = self.sliders[0].value()/1000.
        self.plots[0].setTitle('velocity- gain: %0.3f, threshold: %0.3f' % (self.gainv, self.thresh_v))

    def slider2_changed(self):
        self.gainh = self.sliders[1].value()/1000.
        self.plots[1].setTitle('heading- gain: %0.3f, threshold: %0.3f' % (self.gainh, self.thresh_h))

    def slider3_changed(self):
        self.thresh_v = self.sliders[2].value()/1000.
        self.plots[0].setTitle('velocity- gain: %0.3f, threshold: %0.3f' % (self.gainv, self.thresh_v))

    def slider4_changed(self):
        self.thresh_h = self.sliders[3].value()/1000.
        self.plots[1].setTitle('heading- gain: %0.3f, threshold: %0.3f' % (self.gainh, self.thresh_h))

    def offset_changed(self):
        self.start_point_offset = [int(self.sliders[4].value()), int(self.sliders[5].value())]
        self.angle_offset = int(self.sliders[6].value())
        self.update_offsets = True

    def savebuttonpressed(self):
        self.saveconfigas = filedialog.asksaveasfilename(defaultextension='.ini', filetypes =[('INI files', '*.ini')])
        self.saveconfig = True
        
    def end_button_clicked(self):
        self.end = True

    def roi_mode(self):
        self.toggle_move = not(self.toggle_move)
        if self.toggle_move:
            self.roiupdatebutton.setStyleSheet("background-color : #90EE90")
        else:
            self.roiupdatebutton.setStyleSheet("background-color : #f0f0f0")

    def move_roi(self, b):
        if b=='u':
            self.move_up = True
        elif b=='d':
            self.move_down = True
        elif b=='l':
            self.move_left = True
        elif b=='r':
            self.move_right = True

    def stop_moving_roi(self):
        self.move_up = False
        self.move_down = False
        self.move_left = False
        self.move_right = False

    def update_frame(self, frame):

        self.img.setImage(frame, autoRange=False, autoLevels=False)

        self.frametime = time()
        self.fps = 1./(self.frametime-self.prevframetime)

        self.prevframetime = time()

        self.plotdata[0].setData(self.velocity)
        self.plotdata[1].setData(self.heading)
        if self.plotfps:
            self.plotdata[2].setData(self.fpsbuffer)
            self.plots[2].setTitle('output fps')
            self.fpstext.setText('processed at %0.1f +- %0.1f fps' % (np.mean(self.fpsbuffer[-100::]), np.std(self.fpsbuffer[-100::])))

        else:
            if len(self.fpsbuffer) > 1:
                self.fpstext.setText('processed at %0.1f +- %0.1f fps' % (np.mean(self.fpsbuffer[-100::]), np.std(self.fpsbuffer[-100::])))
            else:
                self.fpstext.setText('processed at %0.1f fps' % self.fps)

        pg.QtGui.QApplication.processEvents()