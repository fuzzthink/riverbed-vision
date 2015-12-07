from log import log
import math
import numpy as np
from random import uniform, choice
from coloranalysis import compare_colors
from structure import compare_histograms
from utils import map_value, constrain

STAGE = 0

MAX_STAGE = 2

THRESH = 2500

flower_seeds = []

for i in range(9):
    y = map_value(i, 0, 8, 300, MAX_Y - 300)

    if i % 2 == 0:
        x = MAX_X - 300.0
    else:
        x = MAX_X - 800.0

    flower_seeds.append((x, y))


def find_flower_pos(map, stone, center):
    radius, angle = 0.0, 0
    stone2 = stone.copy()
    while True:
        x, y = center[0] + math.cos(math.radians(angle)) * radius, center[1] + math.sin(math.radians(angle)) * radius
        stone2.center = x, y
        stone2.angle = angle % 180
        if map.can_put(stone2): # TODO: optimize by checking only against workarea stones?
            return (x, y), angle % 180
        angle += 137.50776405
        if angle > 360:
            angle -= 360
            radius += 2.0

def in_workarea(stone):
    return stone.center[0] > THRESH

stage1_y = None
stage1_last = None
stage_step = 0
min_l, max_l = None, None

def art_step(map):
    global STAGE
    global stage1_y, stage1_last
    global stage_step

    if map.stage:
        stage_step = map.stage

    # Color range
    global min_l, max_l
    if min_l is None:
        min_l = min(map.stones, key=lambda x: x.color[0]).color[0]
    if max_l is None:
        max_l = max(map.stones, key=lambda x: x.color[0]).color[0]

    index, new_center, new_angle = None, None, None

    # clean unusable holes
    map.holes = [h for h in map.holes if not in_workarea(h) and h.center[0] + h.size <= THRESH - (map.maxstonesize + 10) * (stage_step + 1)]

    if STAGE == 0:
        sel = [s for s in map.stones if not in_workarea(s) and s.center[0] + s.size[0] > THRESH - (map.maxstonesize + 10) * (stage_step + 1) and not s.done]
        if sel:
            s = sel[0]
            index = s.index
<<<<<<< HEAD

            bucket = map_value(s.color[0], min_l, max_l, 0, len(flower_seeds) + 1)
            bucket = constrain(int(bucket), 0, len(flower_seeds) - 1)
=======
            bucket = int(s.color[0] * 7 / 255)
>>>>>>> 98cdfb5c52cfad576d8f1f2db0a199d5b186a7fc
            new_center, new_angle = find_flower_pos(map, s, flower_seeds[bucket])

    elif STAGE == 1:
        sel = [s for s in map.stones if in_workarea(s) or s.center[0] + s.size[0] <= THRESH - (map.maxstonesize + 10) * (stage_step + 1)]
        if sel:
            if stage1_y is None:
                # first run of this stage
                stage1_y = 50
                # pick random stone
                s = choice(sel)
                stage1_last = s
            else:
                s = min(sel, key=lambda x: compare_colors(x.color, stage1_last.color) * compare_histograms(x.structure, stage1_last.structure) )
                stage1_y += stage1_last.size[1] + s.size[1] + 5
                stage1_last = s
            s.done = True
            index = s.index
            new_angle = 0
            x = THRESH - (map.maxstonesize + 10) * (stage_step + 0.5)
            new_center = x, stage1_y
            if stage1_y > 1650:
                stage1_y = None
                stage_step += 1
                STAGE = 0

    elif STAGE == 2:
        pass

    if index is not None:
        log.debug('Art stage %d: stone %s => new center: %s, new angle: %s', STAGE, index, str(new_center), str(new_angle))
    else:
        STAGE = min(STAGE + 1, MAX_STAGE)
        log.debug('Art stage %d: None', STAGE)

    map.stage = stage_step

    return index, new_center, new_angle
