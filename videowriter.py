import av

class VideoWriter():

    def __init__(self, framesize, framerate=100, saveas='video.mp4', 
                 codec='mpeg4', kbit_rate=1000, pix_fmt='yuv420p'):

        self.saveas = saveas
        self.framesize = framesize
        self.codec_name = codec
        self.kbit_rate = kbit_rate
        self.framerate = framerate
        self.pix_fmt = pix_fmt

        self.output = av.open(self.saveas, 'w')
        self.out_stream = self.output.add_stream(self.codec_name, int(self.framerate)) 

        self.out_stream.thread_type = 'AUTO'#"SLICE"
        self.out_stream.bit_rate = self.kbit_rate * 1000
        self.out_stream.bit_rate_tolerance = self.kbit_rate * 200
        self.out_stream.pix_fmt = self.pix_fmt

        self.out_stream.width = self.framesize[0]
        self.out_stream.height = self.framesize[1]

    def write_frame(self, frame, format='gray8'):
        self.av_frame = av.VideoFrame.from_ndarray(frame, format=format)
        out_packet = self.out_stream.encode(self.av_frame)
        self.output.mux(out_packet)

    def close(self):
        self.out_packet = self.out_stream.encode(None)
        self.output.mux(self.out_packet)
        self.output.close()
