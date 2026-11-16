import sys, ctypes
from PIL import Image
from materialyoucolor.quantize import QuantizeCelebi
from materialyoucolor.score.score import Score
from materialyoucolor.hct import Hct
from materialyoucolor.scheme.scheme_tonal_spot import SchemeTonalSpot
from materialyoucolor.dynamiccolor.material_dynamic_colors import MaterialDynamicColors

def wallpaper_path():
    buf = ctypes.create_unicode_buffer(520)
    ctypes.windll.user32.SystemParametersInfoW(0x73, 520, buf, 0)  # SPI_GETDESKWALLPAPER
    return buf.value

def palette(path=None, dark=True):
    path = path or wallpaper_path()
    im = Image.open(path).convert("RGB"); im.thumbnail((128, 128))
    pixels = [[r, g, b] for r, g, b in im.getdata()]
    ranked = Score.score(QuantizeCelebi(pixels, 128))
    scheme = SchemeTonalSpot(Hct.from_int(ranked[0]), dark, 0.0)
    out = {}
    for n in dir(MaterialDynamicColors):
        c = getattr(MaterialDynamicColors, n)
        if hasattr(c, "get_hct"):
            v = c.get_hct(scheme).to_int() & 0xFFFFFF
            out[n] = "#%06x" % v
    return out, path

if __name__ == "__main__":
    p, path = palette(sys.argv[1] if len(sys.argv) > 1 else None)
    print(path); print({k: p[k] for k in ("primary","on_surface","surface","secondary","tertiary") if k in p}); print(len(p))
