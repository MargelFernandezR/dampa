# pyright: reportUndefinedVariable=false
# pyright: reportUndefinedVariable=false
if __name__ == "__main__" and not globals().get("_GAME_PARTS_LOADING"):
    from pathlib import Path as _Path
    import runpy as _runpy
    _runpy.run_path(str(_Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
    raise SystemExit

import pygame
import sys
import json
import os
import random
import math
from array import array

try:
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
except (NameError, OSError):
    pass

# small audio buffer = snappy sound effects (safe to fail on machines with no audio)
try:
    pygame.mixer.pre_init(22050, -16, 1, 512)
except pygame.error:
    pass
pygame.init()

# MOUSE CLICK SOUND
pygame.mixer.init()

click_sound = pygame.mixer.Sound("button-click.mp3")
click_sound.set_volume(0.2)
menu_click_sound = pygame.mixer.Sound("click_in_menu_selection.mp3")
menu_click_sound.set_volume(0.5)
gamemode_click_sound = pygame.mixer.Sound("click_in_gamemode_picking.mp3")
gamemode_click_sound.set_volume(0.5)
logo_appear_sound = pygame.mixer.Sound("logo_appear.mp3")
logo_appear_sound.set_volume(0.6)
timer_sound = pygame.mixer.Sound("gametimer.mp3")
timer_sound.set_volume(0.5)
go_sound = pygame.mixer.Sound("GO.mp3")
go_sound.set_volume(0.6)

BGM_PLAYLIST = ["Game_BGM.mp3", "GameMode1_BGM.mp3", "BGM1.mp3", "BGM2.mp3", "BGM3.mp3",
                "music4.mp3", "bgmusic1.mp3", "bgmusic2.mp3", "bgmusic3.mp3"]
BGM_VOLUME = 0.10
MUSIC_END = pygame.USEREVENT + 1
_last_bgm = [None]
_bgm_started = [False]

def play_next_bgm(fade_ms=0):
    choices = [t for t in BGM_PLAYLIST if os.path.exists(t) and t != _last_bgm[0]]
    random.shuffle(choices)
    for track in choices:
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.set_volume(min(1.0, BGM_VOLUME))
            pygame.mixer.music.play(fade_ms=fade_ms)
            pygame.mixer.music.set_endevent(MUSIC_END)
            _last_bgm[0] = track
            return
        except pygame.error as e:
            print(f"Could not load BGM '{track}':", e)

# BACKGROUND MUSIC SWITCHER
def play_bgm(track):
    if not _bgm_started[0] or not pygame.mixer.music.get_busy():
        _bgm_started[0] = True
        play_next_bgm()

# HOME PAGE BACKGROUND MUSIC: starts when the opening intro is finished (see main())
WIDTH, HEIGHT = 1300, 700
HALF = WIDTH // 2


# ---------------------------------------------------------------------
#  CUSTOM BLACK TITLE BAR (kapalit ng blue na title bar ng Windows)
#  Ilagay ang "Capture-removebg-preview.png" sa parehong folder ng main.py
# ---------------------------------------------------------------------
TITLE_H = 32                    # taas ng black title bar
TITLE_BG = (0, 0, 0)
TB_BTN_W = 46                   # lapad ng minimize / close button
TITLE_ICON = None


def set_window_icon(filename="Capture-removebg-preview.png"):
    """icon ng taskbar + maliit na icon sa black title bar (dapat tawagin BAGO ang set_mode)"""
    global TITLE_ICON
    try:
        icon = pygame.image.load(filename)
        rect = icon.get_bounding_rect()                       # alisin ang transparent na gilid
        if rect.width and rect.height:
            icon = icon.subsurface(rect).copy()
        side = max(icon.get_size())                           # gawing square para hindi pipi
        sq = pygame.Surface((side, side), pygame.SRCALPHA)
        sq.blit(icon, ((side - icon.get_width()) // 2, (side - icon.get_height()) // 2))
        pygame.display.set_icon(pygame.transform.smoothscale(sq, (64, 64)))
        TITLE_ICON = pygame.transform.smoothscale(sq, (18, 18))
    except (pygame.error, FileNotFoundError):
        print(f"[dampa] could not load window icon '{filename}'")


set_window_icon()
# NOFRAME = walang Windows title bar, pero RESIZABLE pa rin: pwede pa ring i-drag ang gilid,
# i-maximize at palakihin ang window. Kailangan ng SDL hint na ito, kung hindi hindi
# naglalagay ng resize frame (WS_THICKFRAME) ang SDL sa borderless window.
os.environ["SDL_BORDERLESS_RESIZABLE_STYLE"] = "1"
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT + TITLE_H), pygame.NOFRAME | pygame.RESIZABLE)
# WIN = laging 1300x700 ang laro; ini-scale lang ito sa laki ng window (tingnan ang present()).
WIN = pygame.Surface((WIDTH, HEIGHT))
pygame.display.set_caption("DAMPA")
TB_FONT = pygame.font.Font(None, 24)      # (TB_FONT, hindi TITLE_FONT: may TITLE_FONT na sa 02_assets_ui)
_SCALED = None


def tb_close_rect():
    return pygame.Rect(SCREEN.get_width() - TB_BTN_W, 0, TB_BTN_W, TITLE_H)


def tb_max_rect():
    return pygame.Rect(SCREEN.get_width() - TB_BTN_W * 2, 0, TB_BTN_W, TITLE_H)


def tb_min_rect():
    return pygame.Rect(SCREEN.get_width() - TB_BTN_W * 3, 0, TB_BTN_W, TITLE_H)


def is_maximized():
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        return bool(ctypes.windll.user32.IsZoomed(hwnd))
    except Exception:
        return False


def toggle_maximize():
    """i-maximize / i-restore ang window (Windows lang)"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = pygame.display.get_wm_info()["window"]
        user32.ShowWindow(hwnd, 9 if user32.IsZoomed(hwnd) else 3)   # SW_RESTORE / SW_MAXIMIZE
    except Exception as e:
        print("[dampa] could not maximize window:", e)


def drag_window():
    """hayaang i-drag ang window gamit ang black title bar (Windows)"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        hwnd = pygame.display.get_wm_info()["window"]
        user32.ReleaseCapture()
        user32.SendMessageW(hwnd, 0x00A1, 2, 0)               # WM_NCLBUTTONDOWN + HTCAPTION
    except Exception as e:
        print("[dampa] could not drag window:", e)


_RESIZE_PROC = None          # hawakan ang reference para hindi i-free ng Python ang callback
_RESIZE_OLD_PROC = None


def enable_edge_resize():
    """NOFRAME window = walang resize border. Sariling WM_NCHITTEST para kayang hilahin ang gilid."""
    global _RESIZE_PROC, _RESIZE_OLD_PROC
    if sys.platform != "win32" or _RESIZE_PROC is not None:
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM)
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                           wintypes.WPARAM, wintypes.LPARAM]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.IsZoomed.argtypes = [wintypes.HWND]

        hwnd = pygame.display.get_wm_info()["window"]
        GWLP_WNDPROC = -4
        WM_NCHITTEST = 0x0084
        BORDER = 6

        def wndproc(h, msg, wparam, lparam):
            if msg == WM_NCHITTEST and not user32.IsZoomed(h):
                x = ctypes.c_short(lparam & 0xFFFF).value
                y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                left, right = x < r.left + BORDER, x >= r.right - BORDER
                top, bottom = y < r.top + BORDER, y >= r.bottom - BORDER
                if top and left:
                    return 13                       # HTTOPLEFT
                if top and right:
                    return 14                       # HTTOPRIGHT
                if bottom and left:
                    return 16                       # HTBOTTOMLEFT
                if bottom and right:
                    return 17                       # HTBOTTOMRIGHT
                if left:
                    return 10                       # HTLEFT
                if right:
                    return 11                       # HTRIGHT
                if top:
                    return 12                       # HTTOP
                if bottom:
                    return 15                       # HTBOTTOM
            return user32.CallWindowProcW(_RESIZE_OLD_PROC, h, msg, wparam, lparam)

        _RESIZE_PROC = WNDPROC(wndproc)
        _RESIZE_OLD_PROC = user32.SetWindowLongPtrW(
            hwnd, GWLP_WNDPROC, ctypes.cast(_RESIZE_PROC, ctypes.c_void_p))
    except Exception as e:
        print("[dampa] edge resize not available:", e)


enable_edge_resize()


def handle_titlebar_event(event):
    """Tinatawag sa bawat event. Returns "close", "skip" o None.
    - "close" = pinindot ang X
    - "skip"  = nasa title bar ang mouse, huwag nang ipasa sa game
    Ibinababa rin nito ang mouse position ng TITLE_H para tama pa rin ang lahat ng click sa game."""
    if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
        return None
    x, y = event.pos
    if y < TITLE_H:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if tb_close_rect().collidepoint(x, y):
                return "close"
            if tb_max_rect().collidepoint(x, y):
                toggle_maximize()
            elif tb_min_rect().collidepoint(x, y):
                pygame.display.iconify()
            else:
                drag_window()
        return "skip"
    event.pos = window_to_canvas((x, y))
    return None


def get_game_mouse():
    """mouse position na nakabase sa game area (wala ang title bar, naka-scale sa window)"""
    return window_to_canvas(pygame.mouse.get_pos())


def present():
    """i-scale ang 1300x700 na WIN sa ilalim ng title bar (umaayon sa laki ng window)"""
    global _SCALED
    sw, sh = SCREEN.get_size()
    area = (max(1, sw), max(1, sh - TITLE_H))
    if _SCALED is None or _SCALED.get_size() != area:
        _SCALED = pygame.Surface(area)
    pygame.transform.scale(WIN, area, _SCALED)
    SCREEN.blit(_SCALED, (0, TITLE_H))


def draw_titlebar():
    mx, my = pygame.mouse.get_pos()
    w = SCREEN.get_width()
    tb_min, tb_max, tb_close = tb_min_rect(), tb_max_rect(), tb_close_rect()
    pygame.draw.rect(SCREEN, TITLE_BG, (0, 0, w, TITLE_H))
    x = 10
    if TITLE_ICON:
        SCREEN.blit(TITLE_ICON, (x, (TITLE_H - TITLE_ICON.get_height()) // 2))
        x += TITLE_ICON.get_width() + 8
    label = TB_FONT.render("DAMPA", True, (255, 255, 255))
    SCREEN.blit(label, (x, (TITLE_H - label.get_height()) // 2))
    if tb_min.collidepoint(mx, my):
        pygame.draw.rect(SCREEN, (55, 55, 55), tb_min)
    if tb_max.collidepoint(mx, my):
        pygame.draw.rect(SCREEN, (55, 55, 55), tb_max)
    if tb_close.collidepoint(mx, my):
        pygame.draw.rect(SCREEN, (232, 17, 35), tb_close)

    cy = TITLE_H // 2
    # minimize: maliit na guhit
    pygame.draw.line(SCREEN, (255, 255, 255), (tb_min.centerx - 6, cy), (tb_min.centerx + 5, cy), 1)
    # maximize / restore: maliit na parisukat
    mx_c, my_c = tb_max.centerx, cy
    if is_maximized():
        pygame.draw.rect(SCREEN, (255, 255, 255), (mx_c - 5, my_c - 6, 9, 9), 1)
        pygame.draw.rect(SCREEN, (255, 255, 255), (mx_c - 1, my_c - 2, 9, 9), 1)
    else:
        pygame.draw.rect(SCREEN, (255, 255, 255), (mx_c - 5, my_c - 5, 10, 10), 1)
    # close: X
    cx = tb_close.centerx
    pygame.draw.line(SCREEN, (255, 255, 255), (cx - 6, cy - 6), (cx + 5, cy + 5), 1)
    pygame.draw.line(SCREEN, (255, 255, 255), (cx - 6, cy + 5), (cx + 5, cy - 6), 1)


CLOCK = pygame.time.Clock()


def window_to_canvas(pos):
    """window mouse position -> 1300x700 game coordinates (umaayon sa laki ng window)"""
    display_width, display_height = SCREEN.get_size()
    if display_width <= 0 or display_height <= TITLE_H:
        return 0, 0
    x = int(pos[0] * WIDTH / display_width)
    y = int((pos[1] - TITLE_H) * HEIGHT / (display_height - TITLE_H))
    return (max(0, min(WIDTH - 1, x)), max(0, min(HEIGHT - 1, y)))


# =====================================================================
#  HELPERS
# =====================================================================
def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def ease_out(u):
    return 1 - (1 - u) ** 3


def ease_in_out(u):
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def load_image(name, size=None, alpha=True):
    """Load an image, return None if the file is missing (so the game still runs)."""
    try:
        img = pygame.image.load(name)
        img = img.convert_alpha() if alpha else img.convert()
    except (pygame.error, FileNotFoundError):
        print(f"[dampa] could not load '{name}' - using a placeholder instead "
              f"(put it in the same folder as this script)")
        return None
    if size:
        img = pygame.transform.scale(img, size)
    return img


def scaled_to_width(img, width):
    h = int(img.get_height() * width / img.get_width())
    return pygame.transform.scale(img, (width, h))


def silhouette(img, alpha=70):
    """a soft black copy of an image's shape - used as a drop shadow"""
    m = pygame.mask.from_surface(img, 10)
    return m.to_surface(setcolor=(0, 0, 0, alpha), unsetcolor=(0, 0, 0, 0))


def blur_surface(surf, k=14):
    """cheap strong blur: shrink the picture, then enlarge it smoothly"""
    small = pygame.transform.smoothscale(surf, (WIDTH // k, HEIGHT // k))
    return pygame.transform.smoothscale(small, (WIDTH, HEIGHT))


# =====================================================================
#  HIT RING  (the little ring when a "HIT!" circle is clicked in Dampa Pogs)
#    waves [x, y, age, life, max_radius]
# =====================================================================
def fx_step(waves, dt):
    for w in waves:
        w[2] += dt
    waves[:] = [w for w in waves if w[2] < w[3]]


def draw_waves(layer, waves):
    for x, y, age, life, maxr in waves:
        if age < 0:
            continue
        k = age / life
        r = int(15 + maxr * ease_out(k))
        pygame.draw.circle(layer, (255, 255, 255, int(190 * (1 - k))), (int(x), int(y)), r, 4)




# =====================================================================
#  PIXEL FONT  (chunky pixel text without needing a .ttf file)
#  Renders small with no anti-aliasing, then scales up with hard edges.
#  Same .render(text, True, color) call as a normal pygame font.
# =====================================================================
class PixelFont:
    def __init__(self, size):
        self.scale = 3 if size >= 80 else 2 if size >= 26 else 1
        self.font = pygame.font.Font(None, max(8, size // self.scale))
        self.cache = {}

    def render(self, text, antialias, color):
        key = (text, tuple(color))
        img = self.cache.get(key)
        if img is None:
            small = self.font.render(text, False, color).convert_alpha()
            if self.scale > 1:
                small = pygame.transform.scale(
                    small, (small.get_width() * self.scale, small.get_height() * self.scale))
            if len(self.cache) > 500:
                self.cache.clear()
            img = self.cache[key] = small
        return img


# =====================================================================
#  SOUND EFFECTS  (made in code - no sound files needed)
# =====================================================================
def _tone(notes, dur_each, vol=0.22, noise=False):
    init = pygame.mixer.get_init()
    if not init or init[1] != -16:
        return None
    rate, _, ch = init
    buf = array("h")
    for f in notes:
        n = int(rate * dur_each)
        for i in range(n):
            env = 1 - i / n
            if noise:
                s = random.uniform(-1, 1) * env * env
            else:
                s = (1.0 if (i * f / rate) % 1.0 < 0.5 else -1.0) * env
            v = int(s * vol * 32767)
            for _ in range(ch):
                buf.append(v)
    try:
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except pygame.error:
        return None


def _twang():
    """elastic snap: a quick high 'thwip' that falls in pitch (a flicked rubber band)"""
    init = pygame.mixer.get_init()
    if not init or init[1] != -16:
        return None
    rate, _, ch = init
    n = int(rate * 0.20)
    buf = array("h")
    for i in range(n):
        t = i / rate
        env = math.exp(-18.0 * t)
        freq = 150.0 + 900.0 * math.exp(-30.0 * t)
        s = math.sin(2 * math.pi * freq * t) * env
        s += random.uniform(-1, 1) * 0.35 * math.exp(-60.0 * t)
        v = int(max(-1.0, min(1.0, s)) * 0.30 * 32767)
        for _ in range(ch):
            buf.append(v)
    try:
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except pygame.error:
        return None


SOUNDS = {}
try:
    if pygame.mixer.get_init():
        SOUNDS = {
            "click": _tone([660, 880], 0.04),
            "twang": _twang(),
            "lock": _tone([520, 780], 0.05),
            "smash": _tone([0], 0.28, 0.5, noise=True),
            "pop": _tone([300, 520, 700], 0.05),
            "round": _tone([660, 880, 1100], 0.08),
            "win": _tone([523, 659, 784, 1046], 0.13),
            "lose": _tone([392, 330, 262], 0.2),
            "tie": _tone([440, 440], 0.14),
            "miss": _tone([220, 150], 0.07),
        }
except pygame.error:
    SOUNDS = {}


def play(name):
    if name == "click":
        gamemode_click_sound.play()
    elif name == "menu_click":
        menu_click_sound.play()
    elif name == "hover":
        click_sound.play()
    else:
        s = SOUNDS.get(name)
        if s:
            s.play()


# =====================================================================
#  VOLUME SETTINGS  (BGM / SFX sliders, saved to settings.json)
#  slider 0.5 (middle) = the volume the game had before. Right = louder, left = quieter.
# =====================================================================
SETTINGS_FILE = "../settings.json"
VOL = {"bgm": 0.5, "sfx": 0.5}
BGM_BASE = 0.10
SFX_BASE = [(click_sound, 0.2), (menu_click_sound, 0.5), (gamemode_click_sound, 0.5),
            (logo_appear_sound, 0.6), (timer_sound, 0.5), (go_sound, 0.6)]


def _curve(v, top):
    """0..0.5 -> 0..1x (quieter), 0.5..1 -> 1x..top x (louder)"""
    return v / 0.5 if v <= 0.5 else 1.0 + (v - 0.5) / 0.5 * (top - 1.0)


def apply_volumes():
    global BGM_VOLUME
    BGM_VOLUME = BGM_BASE * _curve(VOL["bgm"], 4.0)          # max = 0.40
    try:
        pygame.mixer.music.set_volume(min(1.0, BGM_VOLUME))
    except pygame.error:
        pass
    m = _curve(VOL["sfx"], 2.5)
    for snd, base in SFX_BASE:
        snd.set_volume(clamp(base * m))
    for snd in SOUNDS.values():
        if snd:
            snd.set_volume(clamp(m))


def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            d = json.load(f)
        for k in VOL:
            VOL[k] = clamp(float(d.get(k, VOL[k])))
    except (OSError, ValueError, TypeError):
        pass


def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(VOL, f)
    except OSError:
        pass


load_settings()
apply_volumes()


# =====================================================================
#  FUN EXTRAS: confetti + floating rubber-band sparkles
# =====================================================================
LASTIKO_COLORS = [(230, 50, 50), (60, 140, 240), (250, 200, 40), (60, 200, 90), (240, 120, 200), (250, 130, 30)]
CONFETTI = []


def confetti_burst(x, y, n=70):
    for _ in range(n):
        a = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
        s = random.uniform(180, 560)
        CONFETTI.append([x, y, math.cos(a) * s, math.sin(a) * s, random.choice(LASTIKO_COLORS),
                         random.randint(6, 10), random.uniform(1.5, 2.6), 0.0])


def update_confetti(dt):
    for c in CONFETTI:
        c[3] += 900 * dt
        c[0] += c[2] * dt
        c[1] += c[3] * dt
        c[2] *= 0.99
        c[7] += dt
    CONFETTI[:] = [c for c in CONFETTI if c[7] < c[6] and c[1] < HEIGHT + 20]


def draw_confetti(surf):
    for c in CONFETTI:
        pygame.draw.rect(surf, c[4], (int(c[0]), int(c[1]), c[5], c[5]))
        pygame.draw.rect(surf, (30, 15, 5), (int(c[0]), int(c[1]), c[5], c[5]), 1)


class Ambient:
    """little rubber-band squares that float up the menu screens"""

    def __init__(self, n=26):
        self.p = [self._new(True) for _ in range(n)]

    def _new(self, anywhere=False):
        return [random.uniform(0, WIDTH), random.uniform(0, HEIGHT) if anywhere else HEIGHT + 12,
                random.uniform(-12, 12), random.uniform(-50, -22), random.choice(LASTIKO_COLORS),
                random.choice((6, 8, 10)), random.uniform(0, 6.28)]

    def update(self, dt):
        for i, p in enumerate(self.p):
            p[0] += p[2] * dt + math.sin(p[6]) * 0.4
            p[1] += p[3] * dt
            p[6] += dt * 2
            if p[1] < -20:
                self.p[i] = self._new()

    def draw(self, surf):
        for p in self.p:
            r = (int(p[0]), int(p[1]), p[5], p[5])
            pygame.draw.rect(surf, p[4], r, 3)


AMBIENT = Ambient()


def finish_fx(final):
    """sound + confetti when a match ends"""
    if final == "win":
        play("win")
        confetti_burst(WIDTH // 2 - 220, HEIGHT - 40)
        confetti_burst(WIDTH // 2 + 220, HEIGHT - 40)
    elif final == "loss":
        play("lose")
    else:
        play("tie")
