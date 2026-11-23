# Dominion I - ParachuteKit textures (system Python: numpy + Pillow), reusing the BuildingKit noise helpers.
#   python pk_textures.py   -> ../textures/T_Ripstop_*, T_Webbing_*
# Ripstop nylon (the reinforcing grid woven every few millimetres, soft creases) and nylon webbing (tight twill).
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'BuildingKit', 'source'))
import bk_textures as bk
from bk_textures import fbm, band, grid, colorize, smooth

OUT = os.path.join(os.path.dirname(HERE), 'textures')
os.makedirs(OUT, exist_ok=True)
bk.OUT = OUT


def ripstop():
    n = 1024
    x, y = grid(n)
    cells = 96
    gx = np.abs(((x / n * cells) % 1.0) - 0.5)
    gy = np.abs(((y / n * cells) % 1.0) - 0.5)
    rib = np.maximum(smooth(0.42, 0.5, gx), smooth(0.42, 0.5, gy))          # the heavier reinforcing threads
    crease = fbm(n, 2.6, 2101, ax=0.4, ay=1.6)                               # soft folds from packing
    weave = band(n, 380, 120, 2102)
    base = colorize(crease * 0.6 + weave * 0.4, (190, 192, 178), (222, 222, 208))
    base *= (1.0 - 0.07 * rib[..., None])
    h = rib * 0.35 + crease * 0.5 + weave * 0.1
    bk.save('Ripstop', base, h, 0.62 - 0.08 * rib, 0.0, 1.4, ao=np.ones((n, n)) - 0.05 * rib)


def webbing():
    n = 512
    x, y = grid(n)
    twill = 0.5 + 0.5 * np.sin((x + y) / n * 2 * np.pi * 64)
    ribs = 0.5 + 0.5 * np.sin(x / n * 2 * np.pi * 24)
    dirt = fbm(n, 2.0, 2201)
    base = colorize(twill * 0.3 + ribs * 0.3 + dirt * 0.4, (170, 170, 160), (210, 208, 196))
    bk.save('Webbing', base, twill * 0.4 + ribs * 0.6, 0.8, 0.0, 2.5, ao_k=1.5)


if __name__ == '__main__':
    ripstop()
    webbing()
