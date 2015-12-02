#!/usr/bin/python
import time
import math
import Pyro4
# import pickle as serialization
import serpent as serialization
from random import uniform
from PIL import Image, ImageDraw
import cv2
import logging

# CONTROL_HOSTNAME = 'localhost'
CONTROL_HOSTNAME = '192.168.0.27'

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.DEBUG)
log = logging.getLogger(__name__)


'''
High-level operations on CNC
'''
class Machine(object):

    def __init__(self, hostname):
        self.uri = 'PYRO:control@{}:5001'.format(hostname)
        self.control = Pyro4.Proxy(self.uri)
        self.x, self.y, self.z, self.e = 0.0, 0.0, 0.0, 0.0
        self.last_pickup_height = None
        try:
            self.control.home()
        except:
            self.control = None

    def lift_up(self):
        if self.last_pickup_height is not None:
            raise Exception('lift_up called, but previous call not cleared using lift_down')
        self.control.vacuum(True)
        time.sleep(1.0)
        h = self.control.pickup()
        assert h
        self.last_pickup_height = h

    def lift_down(self):
        if self.last_pickup_height is None:
            raise Exception('lift_down called without calling lift_up first')
        self.control.go(z=max(self.last_pickup_height - 3, 0))
        self.control.vacuum(False)
        time.sleep(0.1)
        self.control.pickup_top()
        self.last_pickup_height = None

    '''
    Compute difference between center of the vacuum head and center of camera view.
    Relative to camera center. In CNC units = milimeters.
    '''
    def vision_delta(self):
        # length of rotating head (in mm)
        length = 40.0 # distance of vacuum tool to rotation axis (Z center)
        # distance between center of Z axis and center of camera view (both in mm)
        dx, dy = -69.23, -1.88
        angle = math.radians(self.e)
        return (dx + length * math.cos(angle) , dy + length * math.sin(angle))


class Camera(object):

    def __init__(self, index=0):
        self.index = index
        self.resx = 1280.0 # image width (in pixels)
        self.resy = 720.0 # image height (in pixels)
        self.viewx = 128.0 # view width (in cnc units = mm) # FIXME: put real value
        self.viewy = 72.0 # view height (in cnc units = mm) # FIXME: put real value

    # calc distance of perceived pixel from center of the view (in cnc units = mm)
    def pos_to_mm(self, x, y):
        rx = self.viewx * (x / self.resx - 0.5)
        ry = self.viewy * (y / self.resy - 0.5)
        return rx, ry

    def grab(self):
        try:
            cam = cv2.VideoCapture(self.index)
            cam.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, 1280)
            cam.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, 720)
            cam.set(cv2.cv.CV_CAP_PROP_FPS, 15)
            cam.set(cv2.cv.CV_CAP_PROP_BRIGHTNESS, 39)
            ret, frame = cam.read()
            cam.release()
            return frame if ret else None
        except:
            return None


class Stone(object):

    def __init__(self, id, center, size, angle, color_avg, color_dev):
        self.id = id
        self.center = center
        self.size = size
        self.angle = angle
        self.color_avg = color_avg
        self.color_dev = color_dev
        ux = size[0] * math.cos(math.radians(angle))
        uy = size[0] * math.sin(math.radians(angle))
        vx = size[1] * math.cos(math.radians(angle + 90))
        vy = size[1] * math.sin(math.radians(angle + 90))
        self.w = math.sqrt(ux ** 2 + vx ** 2)
        self.h = math.sqrt(uy ** 2 + vy ** 2)
        self.bbox = (center[0] - self.w, center[1] - self.h, center[0] + self.w, center[1] + self.h)

    def overlaps(self, stone):
        return (abs(self.center[0] - stone.center[0]) < (self.w + stone.w)) and (abs(self.center[1] - stone.center[1]) < (self.h + stone.h))

class StoneMap(object):

    def __init__(self, filename):
        self.filename = filename
        self.size = 4000, 2000
        try:
            with open(self.filename, 'rb') as f:
                d = serialization.load(f)
                self.stones = d['stones']
                self.size = d['size']
        except:
            self.stones = {}
            self.save()

    # populate the map with random stones
    def _randomize(self, count=300):
        log.debug('Generating random map of %d stones', count)
        self.stones = {}
        for i in range(count):
            center = (uniform(100, self.size[0] - 100), uniform(100, self.size[1] - 100))
            a = uniform(20, 50)
            b = uniform(20, 50)
            if b > a:
                a, b = b, a
            r = uniform(-90, 90)
            c, d = ((uniform(96, 160), uniform(96, 160), uniform(96, 160)), uniform(10, 40))
            s = Stone(i, center, (a, b), r, c, d)
            bad = False
            for s2 in self.stones.values():
                if s.overlaps(s2):
                    bad = True
                    break
            if not bad:
                self.add_stone(s)
        self._find_workarea()

    def _find_workarea(self):
        pass

    def usage(self):
        log.debug('Creating usage bitmap')
        m = [[0]*self.size[1] for i in range(self.size[0])]
        for s in self.stones.values():
            a, b, c, d = s.bbox
            for x in range(int(math.floor(a)), int(math.ceil(c)) + 1):
                for y in range(int(math.floor(b)), int(math.ceil(d)) + 1):
                    m[x][y] = 1
        return m

    def image(self):
        log.debug('Creating map image')
        im = Image.new('RGB', self.size)
        draw = ImageDraw.Draw(im)
        for s in self.stones.values():
            draw.rectangle(s.bbox, outline='blue')
            size = int(math.ceil(s.size[0] * 2.0)), int(math.ceil(s.size[1] * 2.0))
            t = Image.new('RGBA', size)
            ImageDraw.Draw(t).ellipse(((0, 0), size), outline='red')
            t = t.rotate(s.angle, resample=Image.BILINEAR, expand=True)
            draw.bitmap((s.center[0] - t.size[0] / 2.0, s.center[1] - t.size[1] / 2.0), t)
        im.save('map.png')

    # functions also as replace
    def add_stone(self, stone):
        self.stones[stone.id] = stone
        self.save()

    def save(self):
        with open(self.filename, 'wb') as f:
            d = {'stones': self.stones, 'size': self.size}
            serialization.dump(d, f)


class Brain(object):

    def __init__(self):
        self.machine = Machine(CONTROL_HOSTNAME)
        self.map = StoneMap('stones.data')
        self.cam = Camera()
        # shortcuts for convenience
        self.m = self.machine
        self.c = self.machine.control
        # go home (also test if the machine is initialized and working)
        self.c.home()

    def start(self):
        pass

    def run(self, prgname):
        f = getattr(self, prgname)
        f()

    def scan(self):
        log.debug('Begin scanning')
        self.c.pickup_top()
        self.c.go(e=90)
        self.c.block()
        self.c.feedrate(30000)
        step = 100
        x, y = 1000, 1000 # self.map.size
        for i in range(0, x + 1, step):
            for j in range(0, y + 1, step):
                self.c.go(x=i, y=j)
                self.c.block()
                self.c.light(True)
                log.debug('Taking picture at coords {},{}'.format(i, j))
                frame = self.cam.grab()
                if frame is not None:
                    cv2.imwrite('cam_{:04d}_{:04d}.jpg'.format(i, j), frame)
                    log.debug('Saved as cam_{:04d}_{:04d}.jpg'.format(i, j))
                else:
                    log.error('Error taking picture')
                self.c.light(False)
        log.debug('End scanning')

    def demo1(self):
        # demo program which moves stone back and forth
        while True:
            self._move_stone(0, 0, 0, 500, 250, 90)
            self._move_stone(500, 250, 90, 0, 0, 0)

    def _move_stone(x1, y1, e1, x2, y2, e2):
        self.c.go(e=e1)
        self.c.go(x=x1, y=y1)
        h = self.m.lift_up()
        self.c.go(e=e2)
        self.c.go(x=x2, y=y2)
        self.m.lift_down(h)


if __name__ == '__main__':
    brain = Brain()
    brain.start()
    brain.run('scan')
