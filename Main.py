import pygame
import sys
import json
import os
import random
import math
import io
import base64
from array import array

try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
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
click_sound.set_volume(0.5)

# BACKGROUND MUSIC SWITCHER
def play_bgm(track):
    try:
        if track == "menu":
            pygame.mixer.music.load("Game_BGM.mp3")
        elif track == "karera":
            pygame.mixer.music.load("GameMode1_BGM.mp3")
        elif track == "pogs":
            pygame.mixer.music.load("BGM2.mp3")
        
        pygame.mixer.music.set_volume(0.10)
        pygame.mixer.music.play(-1) # -1 means loop forever
    except pygame.error as e:
        print(f"Could not load BGM '{track}':", e)

# HOME PAGE BACKGROUND MUSIC: starts when the opening intro is finished (see main())
WIDTH, HEIGHT = 1300, 700
HALF = WIDTH // 2
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("DAMPA")
CLOCK = pygame.time.Clock()


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


SOUNDS = {}
try:
    if pygame.mixer.get_init():
        SOUNDS = {
            "click": _tone([660, 880], 0.04),
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
        click_sound.play() # 👈 Gumamit ng button-click.mp3
    else:
        s = SOUNDS.get(name)
        if s:
            s.play()


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


# ===================================================================== #
#  ASSETS
# ===================================================================== #
def make_placeholder_bg():
    """pixel street at sunset - only used when PIXELBGPH.png is missing"""
    w, h = WIDTH // 5, HEIGHT // 5
    s = pygame.Surface((w, h))
    top, bot = (255, 190, 110), (150, 90, 130)
    for y in range(h):
        u = y / h
        c = tuple(int(lerp(top[i], bot[i], u)) // 12 * 12 for i in range(3))
        pygame.draw.line(s, c, (0, y), (w, y))
    rnd = random.Random(9)
    x = 0
    while x < w:
        bw, bh = rnd.randint(14, 30), rnd.randint(30, 70)
        pygame.draw.rect(s, (70, 45, 70), (x, h - 30 - bh, bw, bh))
        for wx in range(x + 3, x + bw - 3, 6):
            for wy in range(h - 26 - bh, h - 34, 9):
                if rnd.random() < 0.45:
                    pygame.draw.rect(s, (255, 225, 120), (wx, wy, 3, 4))
        x += bw + 2
    pygame.draw.rect(s, (60, 55, 60), (0, h - 30, w, 30))
    for lx in range(0, w, 16):
        pygame.draw.rect(s, (240, 220, 140), (lx, h - 14, 8, 2))
    return pygame.transform.scale(s, (WIDTH, HEIGHT)).convert()


_bg = load_image("PIXELBGPH.png", alpha=False)
BG = pygame.transform.scale(_bg, (WIDTH, HEIGHT)) if _bg else make_placeholder_bg()
_small = pygame.transform.smoothscale(BG, (WIDTH // 14, HEIGHT // 14))
BG_BLUR = pygame.transform.smoothscale(_small, (WIDTH, HEIGHT))

LOGO_W = 720
_logo = load_image("DampaLogo.png")
if _logo:
    LOGO_H = int(_logo.get_height() * LOGO_W / _logo.get_width())
    LOGO = pygame.transform.smoothscale(_logo, (LOGO_W, LOGO_H))
else:
    _f = PixelFont(200)
    _t = _f.render("DAMPA", True, (255, 220, 90))
    _s = _f.render("DAMPA", True, (82, 32, 8))
    LOGO = pygame.Surface((_t.get_width() + 10, _t.get_height() + 10), pygame.SRCALPHA)
    LOGO.blit(_s, (8, 8))
    LOGO.blit(_t, (0, 0))
LOGO_POS = LOGO.get_rect(center=(WIDTH // 2, 190))

# ----- game assets -----
#   game_bg_pixel.png              -> tall cracked-floor image (scrolls down as the bands travel)
#   armplayer-removebg-preview.png   -> the clapped hands (transparent PNG)
#   rubber_bands.png               -> the pile of rubber bands (transparent PNG)
# Keep them in the same folder as this script. Missing files get simple placeholders.
HANDS_W = 340        # width of the hands + arms picture on screen
HANDS_CUT = 0.50     # where the picture is split: hands (above) / forearms (below the wrists)


HAND_FILES = ["hands.png", "armplayer-removebg-preview.png"]          # first one found is used
BAND_FILES = ["rubber_band.png", "rubberband-removebg.png"]
BAND_PILE = 4          # how many rubber bands are piled up in Dampa Karera (1 = a single band)


def load_first(names, alpha=True):
    """load the first picture in the list that exists (None if there is none)"""
    for n in names:
        if os.path.exists(n):
            img = load_image(n, alpha=alpha)
            if img:
                return img
    return None


def make_band_pile(ring):
    """turn ONE rubber band picture into a little pile of bands"""
    # Pinaliit mula 90 papuntang 65
    ring = scaled_to_width(ring, 60)
    
    if BAND_PILE <= 1:
        return ring
        
    # Binawasan ang padding mula 80 papuntang 50
    pile = pygame.Surface((ring.get_width() + 50, ring.get_height() + 50), pygame.SRCALPHA)
    rnd = random.Random(4)
    for i in range(BAND_PILE):
        r = pygame.transform.rotozoom(ring, rnd.randint(-40, 40) + i * 15, 1.0)
        pos = (pile.get_width() // 2 + rnd.randint(-9, 9), pile.get_height() // 2 + rnd.randint(-9, 9))
        pile.blit(r, r.get_rect(center=pos))
    return crop_to_content(pile)


def crop_to_content(img):
    rect = img.get_bounding_rect()
    if rect.width == 0 or rect.height == 0:
        return img
    return img.subsurface(rect).copy()


def remove_white_bg(img):
    """If a PNG has a solid white background instead of transparency, make it transparent."""
    r, g, b, a = img.get_at((0, 0))
    if a == 255 and min(r, g, b) > 240:
        try:
            mask = pygame.mask.from_threshold(img, (r, g, b, 255), (14, 14, 14, 255))
            mask.invert()
            return mask.to_surface(setsurface=img, unsetcolor=(0, 0, 0, 0))
        except (AttributeError, TypeError, pygame.error):
            pass
    return img


USE_BG_IMAGE = False   # True = use game_bg_pixel.png (the cracked floor) instead of the clean floor


def make_floor():
    """A TALL floor: the camera scrolls up it as the rubber bands fly forward.
    Pixel concrete slabs with grout lines, speckles and a few little pebbles."""
    if USE_BG_IMAGE:
        img = load_image("game_bg_pixel.png", alpha=False)
        if img:
            h = max(int(img.get_height() * HALF / img.get_width()), HEIGHT + 400)
            return pygame.transform.scale(img, (HALF, h))
    rnd = random.Random(7)
    h = HEIGHT + 400
    P = 4                                         # one "pixel" = 4x4 screen pixels
    sw, sh = HALF // P + 1, h // P + 1
    small = pygame.Surface((sw, sh))
    SLAB = 32                                     # slab size in pixels (=128 on screen)
    tone = {}
    for x in range(sw):
        for y in range(sh):
            key = (x // SLAB, y // SLAB)
            if key not in tone:
                tone[key] = rnd.randint(-4, 4)
            v = 150 + tone[key] + rnd.randint(-8, 8)
            if rnd.random() < 0.04:
                v += rnd.choice((-22, 22))
            if x % SLAB == 0 or y % SLAB == 0:    # grout lines
                v -= 26
            elif x % SLAB == 1 or y % SLAB == 1:  # soft highlight next to the grout
                v += 7
            small.set_at((x, y), (v, v, v))
    for _ in range(40):                           # tiny pebbles
        px, py = rnd.randrange(sw - 2), rnd.randrange(sh - 2)
        v = rnd.choice((118, 176))
        pygame.draw.rect(small, (v, v, v), (px, py, 2, 2))
    for _ in range(6):                            # a few little cracks
        px, py = rnd.randrange(sw), rnd.randrange(sh)
        for _ in range(rnd.randint(5, 12)):
            small.set_at((px % sw, py % sh), (112, 112, 112))
            px += rnd.choice((-1, 0, 1))
            py += 1
    surf = pygame.transform.scale(small, (sw * P, sh * P))
    return surf.subsurface((0, 0, HALF, h)).copy().convert()


def make_hands():
    """returns (hands_part, arms_part). They are drawn separately so the forearms can be
    stretched during the smash and the arms always reach the bottom of the screen."""
    img = load_first(HAND_FILES)
    if img:
        img = scaled_to_width(crop_to_content(remove_white_bg(img)), HANDS_W)
    else:
        img = pygame.Surface((190, 330), pygame.SRCALPHA)
        skin, dark = (214, 150, 105), (160, 100, 65)
        pygame.draw.rect(img, skin, (55, 190, 80, 140))
        pygame.draw.ellipse(img, dark, (30, 5, 70, 215))
        pygame.draw.ellipse(img, skin, (34, 9, 62, 205))
        pygame.draw.ellipse(img, dark, (90, 5, 70, 215))
        pygame.draw.ellipse(img, skin, (94, 9, 62, 205))
        pygame.draw.line(img, dark, (95, 20), (95, 200), 3)
    w, h = img.get_size()
    cut = int(h * HANDS_CUT)
    return img.subsurface((0, 0, w, cut)).copy(), img.subsurface((0, cut, w, h - cut)).copy()


def make_bands():
    img = load_first(BAND_FILES)
    if img:
        return make_band_pile(crop_to_content(remove_white_bg(img)))
    surf = pygame.Surface((70, 70), pygame.SRCALPHA)
    rnd = random.Random(3)
    for _ in range(45):
        r = rnd.randint(8, 14)
        pos = (35 + rnd.randint(-17, 17), 35 + rnd.randint(-17, 17))
        pygame.draw.circle(surf, rnd.choice(LASTIKO_COLORS), pos, r, 2)
    return surf


FLOOR = make_floor()
FLOOR_FLIP = pygame.transform.flip(FLOOR, False, True)   # flipped copy so repeats line up
HANDS_TOP_IMG, HANDS_ARMS_IMG = make_hands()
HANDS_TOP_SHADOW = silhouette(HANDS_TOP_IMG, 80)
HANDS_ARMS_SHADOW = silhouette(HANDS_ARMS_IMG, 80)       # NEW: forearm shadow (was missing, so the shadow got cut off)
HANDS_H = HANDS_TOP_IMG.get_height() + HANDS_ARMS_IMG.get_height()
HANDS_TOP = HEIGHT + 10 - HANDS_H      # the arms end just below the bottom edge of the screen
BANDS = make_bands()


BAND_SHADOW = pygame.Surface((BANDS.get_width(), 26), pygame.SRCALPHA)
pygame.draw.ellipse(BAND_SHADOW, (0, 0, 0, 70), BAND_SHADOW.get_rect())
SPEED_LINE = pygame.Surface((3, 46), pygame.SRCALPHA)
SPEED_LINE.fill((255, 255, 255, 70))

# ----- card images for GAME MODES screen -----
# Ilagay mo yung mga picture files sa parehong folder ng main.py
# Pangalan: karera_card.png at pogs_card.png
CARD_IMG_W = 270   # 220px lapad
CARD_IMG_H = 340   # taas ng picture


def placeholder_card(kind):
    s = pygame.Surface((CARD_IMG_W, CARD_IMG_H))
    s.fill((150, 150, 150))  # gray
    rnd = random.Random(21 if kind == "karera" else 22)
    for _ in range(26):
        x, y = rnd.randint(30, CARD_IMG_W - 30), rnd.randint(40, CARD_IMG_H - 40)
        if kind == "karera":
            pygame.draw.circle(s, rnd.choice(LASTIKO_COLORS), (x, y), rnd.randint(10, 18), 3)
        else:
            c = rnd.choice(LASTIKO_COLORS)
            pygame.draw.circle(s, c, (x, y), 20)
            pygame.draw.circle(s, (245, 200, 70), (x, y), 12)
            pygame.draw.circle(s, c, (x, y), 5)
            pygame.draw.circle(s, (40, 20, 10), (x, y), 20, 2)
    return s


KARERA_IMG = load_image("Goma_Banner.png", (CARD_IMG_W, CARD_IMG_H)) or placeholder_card("karera")
POGS_IMG = load_image("Pogs_Banner.png", (CARD_IMG_W, CARD_IMG_H)) or placeholder_card("pogs")


# ----- fonts (pixel look, no .ttf needed) ----- #
BIG_FONT = PixelFont(56)
BUTTON_FONT = PixelFont(52)
MID_FONT = PixelFont(34)
SMALL_FONT = PixelFont(30)
DESC_FONT = PixelFont(24)
HUGE_FONT = PixelFont(96)
TITLE_FONT = PixelFont(70)

# ----- colors ----- # 
TEXT_COLOR = (255, 255, 255)
WHITE = (255, 255, 255)
BROWN = (82, 32, 8)
LINE_BROWN = (128, 64, 24)
LINE_BLUE = (40, 80, 200)
BEIGE = (232, 206, 160, 235)
BEIGE_DARK = (176, 149, 102, 190)
BEIGE_HOVER = (206, 176, 124, 225)
YESNO = (150, 100, 55)
YESNO_HOVER = (176, 124, 72)
HUD_COLOR = (139, 69, 19)  # brown
GOLD = (255, 240, 120)


def panel(rect, color=BEIGE, target=None, radius=14):
    """a see-through panel with smooth rounded corners"""
    target = WIN if target is None else target
    surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surf, color, surf.get_rect(), border_radius=radius)
    target.blit(surf, rect.topleft)


def text_center(font, text, color, center, target=None, shadow=False):
    target = WIN if target is None else target
    img = font.render(text, True, color)
    rect = img.get_rect(center=center)
    if shadow:
        target.blit(font.render(text, True, (0, 0, 0)), (rect.x + 2, rect.y + 2))
    target.blit(img, rect)


def pop_text(font, text, color, center, k, target=None, alpha=255):
    """text that pops in (k = 0..1) - used for big friendly messages"""
    target = WIN if target is None else target
    img = font.render(text, True, color)
    sh = font.render(text, True, (0, 0, 0))
    s = 0.6 + 0.4 * k
    size = (max(2, int(img.get_width() * s)), max(2, int(img.get_height() * s)))
    img = pygame.transform.scale(img, size)
    sh = pygame.transform.scale(sh, size)
    if alpha < 255:
        img.set_alpha(alpha)
        sh.set_alpha(alpha)
    r = img.get_rect(center=center)
    target.blit(sh, (r.x + 4, r.y + 4))
    target.blit(img, r)


# ---------------------------------------------------------------------
#  YOUR OWN UI PICTURES
#  Put the files in the SAME folder as main.py and type the file names here.
#  If a file is missing, the game automatically uses the drawn version instead.
# ---------------------------------------------------------------------
UI_FILES = {
    # buttons (no text inside the picture - the game writes the label)
    "button":        "button.png",          # gold button (normal)
    "button_hover":  "hoverbutton.png",    # optional: gold button with the arrows (mouse over)
    "easy":          "easy.png",            # green button
    "normal":        "normal.png",          # blue button
    "hard":          "hard.png",            # red button
    # SCORE screen = 3 separate pictures
    "score_wood":    "score_boarders_boarder.png",      # the big wooden board
    "score_paper":   "score_boarder.png",     # the pink paper the table is written on
    "score_sign":    "score_sign.png",      # the hanging SCORE sign (with its chains)
    # EXIT screen = paper + the gold pill banner (button.png) on top
    "exit_sign":     "exit_sign.png",       # (no longer used - the EXIT banner is the gold button picture)
    "exit_paper":    "board2.png",      # the paper with the question
    # in-game menu
    "pause_panel":   "board2.png",     # paper panel (no buttons)
    "hamburger":     "hamburger.png",       # the menu icon button
    "logo_frame":    "buttonsize1.png",      # optional: empty frame for the level logo (only used if LOGO_HAS_FRAME = False)
}
BTN_KEY = {"gold": "button", "green": "easy", "blue": "normal", "red": "hard"}
_UI_RAW = {}
_UI_CACHE = {}


def ui_raw(key):
    """the original picture (loaded once) or None if the file does not exist"""
    if key not in _UI_RAW:
        img = None
        name = UI_FILES.get(key)
        if name and os.path.exists(name):
            try:
                img = pygame.image.load(name).convert_alpha()
                box = img.get_bounding_rect()                         # cut the transparent border away
                if box.w > 0 and box.h > 0 and box.size != img.get_size():
                    img = img.subsurface(box).copy()
            except pygame.error:
                img = None
        _UI_RAW[key] = img
    return _UI_RAW[key]


def ui_aspect(key, default):
    """width / height of your picture (so it is never stretched out of shape)"""
    img = ui_raw(key)
    return img.get_width() / img.get_height() if img else default


def ui_img(key, size):
    """your picture scaled (hard pixels) to `size`, or None if the file does not exist"""
    k = (key, tuple(size))
    if k not in _UI_CACHE:
        img = ui_raw(key)
        _UI_CACHE[k] = pygame.transform.scale(img, size) if img else None
    return _UI_CACHE[k]


for _k, _n in UI_FILES.items():
    print(f"[dampa] ui picture '{_k}': {'FOUND ' if os.path.exists(_n) else 'missing'} ({_n})")

# ---------------------------------------------------------------------
#  PIXEL UI KIT: buttons, wood signs, paper panels
# ---------------------------------------------------------------------
FX_DT = [1 / 60]          # main loop writes the frame time here (used for hover animation)
HOVER = {}                # smooth hover progress per button (0 -> 1)
_PX_CACHE = {}
PX = 4                    # pixel size for panels / signs
DIM = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
DIM.fill((0, 0, 0, 110))  # darkness over the blurred game behind the pause menu

# outline, ring, fill, shine, shade
BTN_PAL = {
    "gold":  ((70, 28, 8),  (226, 128, 36), (250, 196, 64),  (255, 228, 120), (214, 140, 40)),
    "green": ((16, 70, 30), (40, 150, 60),  (90, 215, 100),  (170, 255, 170), (50, 170, 70)),
    "blue":  ((16, 50, 90), (40, 120, 190), (90, 190, 240),  (180, 235, 255), (50, 140, 200)),
    "red":   ((90, 16, 16), (190, 50, 50),  (240, 100, 100), (255, 190, 190), (200, 60, 60)),
}
DIFF_PAL = {"EASY": "green", "MEDIUM": "blue", "HARD": "red"}


def hover_amt(key, on):
    """smooth 0..1 value that eases towards 1 while the mouse is over a button"""
    cur = HOVER.get(key, 0.0)
    tgt = 1.0 if on else 0.0
    cur += (tgt - cur) * min(1.0, FX_DT[0] * 16)
    if abs(tgt - cur) < 0.01:
        cur = tgt
    HOVER[key] = cur
    return cur


def _clear_corners(small, sw, sh):
    for x, y in ((0, 0), (1, 0), (0, 1), (sw - 1, 0), (sw - 2, 0), (sw - 1, 1),
                 (0, sh - 1), (1, sh - 1), (0, sh - 2), (sw - 1, sh - 1), (sw - 2, sh - 1), (sw - 1, sh - 2)):
        small.set_at((x, y), (0, 0, 0, 0))


def btn_surface(w, h, pal):
    k = ("btn", w, h, pal)
    s = _PX_CACHE.get(k)
    if s:
        return s
    S = 3
    sw, sh = max(10, w // S), max(10, h // S)
    o, ring, fill, light, shade = BTN_PAL[pal]
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    small.fill(o)
    small.fill(ring, (1, 1, sw - 2, sh - 2))
    small.fill(fill, (2, 2, sw - 4, sh - 4))
    small.fill(light, (3, 2, sw - 6, 2))
    small.fill(shade, (3, sh - 4, sw - 6, 2))
    _clear_corners(small, sw, sh)
    for x, y in ((1, 1), (sw - 2, 1), (1, sh - 2), (sw - 2, sh - 2)):
        small.set_at((x, y), o)
    s = pygame.transform.scale(small, (sw * S, sh * S))
    _PX_CACHE[k] = s
    return s


def pixel_box(w, h, outline, fill, light=None, shade=None):
    k = ("box", w, h, outline, fill, light, shade)
    s = _PX_CACHE.get(k)
    if s:
        return s
    sw, sh = max(8, w // PX), max(8, h // PX)
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    small.fill(outline)
    small.fill(fill, (1, 1, sw - 2, sh - 2))
    if light:
        small.fill(light, (2, 2, sw - 4, 1))
        small.fill(light, (2, 2, 1, sh - 4))
    if shade:
        small.fill(shade, (2, sh - 3, sw - 4, 1))
        small.fill(shade, (sw - 3, 2, 1, sh - 4))
    for x, y in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1)):
        small.set_at((x, y), (0, 0, 0, 0))
    s = pygame.transform.scale(small, (sw * PX, sh * PX))
    _PX_CACHE[k] = s
    return s


def wood_box(w, h, base, seed, outline, planks=False):
    """pixel wood texture with a dark border"""
    k = ("wood", w, h, base, seed, outline, planks)
    s = _PX_CACHE.get(k)
    if s:
        return s
    sw, sh = max(8, w // PX), max(8, h // PX)
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    rnd = random.Random(seed)
    plank_h = max(6, sh // 3)

    def tone(v):
        return tuple(max(0, min(255, base[i] + v)) for i in range(3))

    for y in range(sh):
        row = rnd.randint(-6, 6)
        for x in range(sw):
            v = row + rnd.randint(-5, 5)
            if rnd.random() < 0.03:
                v -= 22
            if planks and y % plank_h == 0:
                v -= 34
            small.set_at((x, y), tone(v))
    small.fill(outline, (0, 0, sw, 1))
    small.fill(outline, (0, sh - 1, sw, 1))
    small.fill(outline, (0, 0, 1, sh))
    small.fill(outline, (sw - 1, 0, 1, sh))
    small.fill(tone(26), (1, 1, sw - 2, 1))
    small.fill(tone(26), (1, 1, 1, sh - 2))
    small.fill(tone(-30), (1, sh - 2, sw - 2, 1))
    small.fill(tone(-30), (sw - 2, 1, 1, sh - 2))
    for x, y in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1)):
        small.set_at((x, y), (0, 0, 0, 0))
    s = pygame.transform.scale(small, (sw * PX, sh * PX))
    _PX_CACHE[k] = s
    return s


def nail(x, y):
    pygame.draw.circle(WIN, (60, 55, 60), (x, y), 7)
    pygame.draw.circle(WIN, (170, 170, 180), (x, y), 5)
    pygame.draw.circle(WIN, (235, 235, 245), (x - 1, y - 1), 2)


def paper_box(rect):
    s = pixel_box(rect.w, rect.h, (86, 36, 30), (250, 222, 206), (255, 240, 230), (214, 160, 148))
    WIN.blit(s, s.get_rect(center=rect.center))
    pygame.draw.rect(WIN, (214, 160, 148), (rect.right - 24, rect.y + 10, 8, rect.h - 20))


def draw_sign(rect, text, font=None):
    """hanging wooden sign with chains (SCORE / EXIT)"""
    font = font or BIG_FONT
    for cx in (rect.x + 36, rect.right - 36):
        y = rect.y + 10
        i = 0
        while y > -14:
            wdt = 10 if i % 2 == 0 else 5
            pygame.draw.rect(WIN, (64, 54, 60), (cx - wdt // 2 - 1, y - 16, wdt + 2, 18), 3, border_radius=4)
            pygame.draw.line(WIN, (150, 140, 148), (cx - wdt // 2, y - 13), (cx - wdt // 2, y - 4), 1)
            y -= 14
            i += 1
    s = wood_box(rect.w, rect.h, (140, 84, 40), 3, (56, 26, 8), planks=True)
    WIN.blit(s, s.get_rect(center=rect.center))
    text_center(font, text, (190, 122, 62), (rect.centerx, rect.centery - 2))
    text_center(font, text, (92, 40, 12), (rect.centerx, rect.centery + 2))
    nail(rect.x + 36, rect.y + 14)
    nail(rect.right - 36, rect.y + 14)


def button(rect, label, hovered, font=BUTTON_FONT, dy=0, pal="gold", key=None):
    a = hover_amt(key or (rect.topleft, label), hovered)
    r = rect.move(0, dy).inflate(int(5 * a) * 2, int(3 * a) * 2)      # grows smoothly on hover
    img = ui_img(BTN_KEY[pal] + "_hover", r.size) if a > 0.5 else None
    has_hover_pic = img is not None
    if img is None:
        img = ui_img(BTN_KEY[pal], r.size)
    if img is not None:
        WIN.blit(img, r.topleft)                                      # YOUR button picture
    else:
        surf = btn_surface(r.w, r.h, pal)
        WIN.blit(surf, surf.get_rect(center=r.center))
    col = BTN_PAL[pal][0]
    text_center(font, label, col, r.center)
    if a > 0.25 and not has_hover_pic:                                # arrows slide in
        slide = int((1 - a) * 12)
        cy = r.centery
        ax = r.x + 24 + slide
        bx = r.right - 24 - slide
        pygame.draw.polygon(WIN, col, [(ax, cy - 7), (ax, cy + 7), (ax + 11, cy)])
        pygame.draw.polygon(WIN, col, [(bx, cy - 7), (bx, cy + 7), (bx - 11, cy)])


def backdrop(bg=None):
    """blurred street (normal menus) or the BLURRED paused game (in-game menus)"""
    if bg is None:
        WIN.blit(BG_BLUR, (0, 0))
        AMBIENT.draw(WIN)
    else:
        WIN.blit(bg, (0, 0))
        WIN.blit(DIM, (0, 0))


def hud_box(target, rect, color=HUD_COLOR):
    pygame.draw.rect(target, color, rect, border_radius=10)
    pygame.draw.rect(target, (60, 25, 5), rect, 3, border_radius=10)


def hud_pill(target, rect, text="", font=None):
    """gold pill (your button.png) with dark text - used for the whole in-game HUD"""
    font = font or SMALL_FONT
    img = ui_img("button", rect.size)
    if img is None:
        img = btn_surface(rect.w, rect.h, "gold")
    target.blit(img, img.get_rect(center=rect.center))
    if text:
        text_center(font, text, BTN_PAL["gold"][0], rect.center, target)


# in-game HUD layout (from the reference images)
HUD_ROUND   = pygame.Rect(WIDTH // 2 - 190, 10, 380, 84)      # big ROUND pill
HUD_TIMER   = pygame.Rect(0, 0, 150, 36)
HUD_TIMER.midtop = (WIDTH // 2, 106)                          # the pink-circle spot (timer)
HUD_L_LABEL = pygame.Rect(WIDTH // 2 - 395, 12, 185, 38)
HUD_L_VALUE = pygame.Rect(WIDTH // 2 - 395, 58, 185, 38)
HUD_R_LABEL = pygame.Rect(WIDTH // 2 + 210, 12, 185, 38)
HUD_R_VALUE = pygame.Rect(WIDTH // 2 + 210, 58, 185, 38)
HUD_SIDE_L  = [pygame.Rect(12, 165, 185, 40), pygame.Rect(12, 220, 185, 40)]
HUD_SIDE_R  = [pygame.Rect(WIDTH - 197, 165, 185, 40), pygame.Rect(WIDTH - 197, 220, 185, 40)]


#  MENU / SCORE / EXIT LAYOUT

BTN_W, BTN_H, GAP = 340, 72, 18
BTN_X = (WIDTH - BTN_W) // 2
BTN_Y = 340
MENU_BUTTONS = {
    "GAMEMODES": pygame.Rect(BTN_X, BTN_Y, BTN_W, BTN_H),
    "SCORE": pygame.Rect(BTN_X, BTN_Y + (BTN_H + GAP), BTN_W, BTN_H),
    "EXIT": pygame.Rect(BTN_X, BTN_Y + (BTN_H + GAP) * 2, BTN_W, BTN_H),
}

DESCRIPTION = [
    "Dampa is a traditional Filipino street game where players use air",
    "pressure from tapped hands to move a pile of rubber bands",
    "(lastiko) past a designated line",
]

TIPS = [
    "TIP: stop the bar on the WHITE zone for full power!",
    "TIP: in Dampa Pogs, aim for the green box (80-90%)!",
    "TIP: too much power in Pogs = you lose control!",
    "TIP: in Pogs, click every circle after the meter or lose power!",
    "TIP: press ESC anytime to pause the game",
]

PANEL_W = 472
PANEL_X = (WIDTH - PANEL_W) // 2

# --- SCORE layout: wood board + paper + sign, each its own picture.
#     The three pieces are placed by ratios of the wood board, so any picture size works.
SCORE_WOOD_W = 720                                           # width of the wooden board on screen
_wood_h = int(SCORE_WOOD_W / ui_aspect("score_wood", 735 / 430))
_sgn_w = int(SCORE_WOOD_W * 0.36)
_sgn_h = int(_sgn_w / ui_aspect("score_sign", 262 / 178))
SCORE_SHIFT = (0, 0)          # nudge the WHOLE score screen: (+right / -left, +down / -up)
_sign_over = max(0, _sgn_h - int(_wood_h * 0.15) + 6)        # how far the sign sticks out above the wood
_score_total = _sign_over + _wood_h + 20 + 54                # sign top -> bottom of the BACK button
SCORE_BOARD = pygame.Rect(0, 0, SCORE_WOOD_W, _wood_h)
SCORE_BOARD.centerx = WIDTH // 2 + SCORE_SHIFT[0]
SCORE_BOARD.y = max(8, (HEIGHT - _score_total) // 2) + _sign_over + SCORE_SHIFT[1]   # whole group centred
SCORE_TABLE = pygame.Rect(SCORE_BOARD.x + int(SCORE_WOOD_W * 0.11), SCORE_BOARD.y + int(_wood_h * 0.15),
                          int(SCORE_WOOD_W * 0.79), int(_wood_h * 0.70))      # the paper
SCORE_SIGN = pygame.Rect(SCORE_BOARD.x + int(SCORE_WOOD_W * 0.07), SCORE_TABLE.y + 6 - _sgn_h, _sgn_w, _sgn_h)
SCORE_PLANK = pygame.Rect(SCORE_SIGN.x, SCORE_SIGN.y + int(_sgn_h * 0.30), _sgn_w, int(_sgn_h * 0.70))  # (drawn version only)
SCORE_BACK = pygame.Rect(SCORE_TABLE.right - 160, SCORE_BOARD.bottom + 20, 160, 54)
COL_STREAK = 110
COL_BOT = 70
COL_YOU = 70
COL_GAMEMODES = 270
HEAD_ROW_H = 45
ROW_H = 40
MAX_ROWS = 20
SCROLL_SPEED = 40        # pixels per scroll
scroll_offset = 0        # current scroll position

# --- EXIT layout: gold pill banner on top of a paper panel (matches the reference)
EXIT_PAPER_W = 300                                            # whole dialog is about 1/4 of the screen width
_ex_ph = int(EXIT_PAPER_W / ui_aspect("exit_paper", 210 / 260))
_ex_bw = EXIT_PAPER_W                                         # banner is as wide as the paper
_ex_bh = max(44, min(72, int(_ex_bw / ui_aspect("button", 4.3))))
_ex_lap = 8                                                   # banner overlaps the paper top by this much
EXIT_SHIFT = (0, 0)                                           # nudge the WHOLE exit screen (+right / +down)
_ex_total = _ex_bh - _ex_lap + _ex_ph
EXIT_PANEL = pygame.Rect(0, 0, EXIT_PAPER_W, _ex_ph)
EXIT_PANEL.centerx = WIDTH // 2 + EXIT_SHIFT[0]
EXIT_PANEL.y = (HEIGHT - _ex_total) // 2 + _ex_bh - _ex_lap + EXIT_SHIFT[1]
EXIT_HEADER = pygame.Rect(0, 0, _ex_bw, _ex_bh)
EXIT_HEADER.midbottom = (EXIT_PANEL.centerx, EXIT_PANEL.y + _ex_lap)
_btn_w, _btn_h = int(EXIT_PAPER_W * 0.62), max(40, int(_ex_ph * 0.11))
EXIT_YES = pygame.Rect(0, 0, _btn_w, _btn_h)
EXIT_YES.center = (EXIT_PANEL.centerx, EXIT_PANEL.y + int(_ex_ph * 0.55))
EXIT_NO = pygame.Rect(0, 0, _btn_w, _btn_h)
EXIT_NO.center = (EXIT_PANEL.centerx, EXIT_YES.centery + _btn_h + 14)

# in-game pause menu
PAUSE_BTN = pygame.Rect(WIDTH - 84, 12, 66, 62)          # the hamburger button (bigger, like the reference)
PAUSE_PANEL = pygame.Rect(WIDTH // 2 - 190, 140, 380, 420)
PAUSE_BUTTONS = {name: pygame.Rect(WIDTH // 2 - 150, 192 + i * 84, 300, 64)
                 for i, name in enumerate(("CONTINUE", "SCORE", "MENU", "EXIT"))}


# =====================================================================
#  GAME MODE SCREENS LAYOUT
#    screen "gamemodes" = PLAYER VS PLAYER / PLAYER VS BOT
#    screen "botmodes"  = DAMPA KARERA / DAMPA POGS + description + level
# =====================================================================
MODE_HEADER = pygame.Rect(WIDTH // 2 - 160, 40, 320, 62)   # small gold sign, like the reference

# --- screen 1: pick the kind of match (cards are wider than tall, like the reference)
VS_W, VS_H, VS_GAP = 470, 405, 50
VS_X = (WIDTH - (VS_W * 2 + VS_GAP)) // 2
VS_Y = 135
VS_PVP = pygame.Rect(VS_X, VS_Y, VS_W, VS_H)
VS_PVB = pygame.Rect(VS_X + VS_W + VS_GAP, VS_Y, VS_W, VS_H)
VS_BACK = pygame.Rect(WIDTH // 2 - 85, HEIGHT - 105, 170, 54)

# --- screen 2: pick the game, read about it, pick the level
CARD_W, CARD_H = 300, 500
CARD_GAP = 30
CARD_Y = 100
CARD1_RECT = pygame.Rect(60, CARD_Y, CARD_W, CARD_H)
CARD2_RECT = pygame.Rect(60 + CARD_W + CARD_GAP, CARD_Y, CARD_W, CARD_H)
MODE_START_W, MODE_START_H = 200, 50
START_DY = 200                                  # start button sits this far under the card centre
MODE1_START = pygame.Rect(0, 0, MODE_START_W, MODE_START_H)
MODE1_START.center = (CARD1_RECT.centerx, CARD1_RECT.centery + START_DY)
MODE2_START = pygame.Rect(0, 0, MODE_START_W, MODE_START_H)
MODE2_START.center = (CARD2_RECT.centerx, CARD2_RECT.centery + START_DY)

INFO_PANEL = pygame.Rect(740, 80, 520, 520)
INFO_X = INFO_PANEL.x + 24
LEVEL_NAMES = ("EASY", "MEDIUM", "HARD")
LEVEL_RECTS = {name: pygame.Rect(INFO_X + 10, 420 + i * 60, 240, 50) for i, name in enumerate(LEVEL_NAMES)}
LOGO_FRAME = pygame.Rect(0, 0, 140, 176)
# fits inside the info panel: top lines up with EASY, bottom lines up with HARD, centred between the buttons and the panel edge
LOGO_FRAME.centery = (LEVEL_RECTS['EASY'].top + LEVEL_RECTS['HARD'].bottom) // 2
LOGO_FRAME.centerx = (LEVEL_RECTS['EASY'].right + INFO_PANEL.right) // 2     # spot (right of the level buttons) that shows the level logo
LOGO_HAS_FRAME = None     # None = AUTO (the game checks if your picture already has the brown border + yellow background)
                          # True / False = force it
MODE_BACK = pygame.Rect(INFO_PANEL.right - 190, 618, 170, 54)



#  SCORE DATA

SCORE_FILE = "scores.json"
DEFAULT_SCORES = [
    ["win", 1, 3, "DAMPA KARERA"],
    ["win", 1, 3, "DAMPA KARERA"],
    ["defeat", 3, 1, "DAMPA POGS"],
    ["defeat", 0, 4, "DAMPA POGS"],
    ["tie", 2, 2, "DAMPA POGS"],
    ["defeat", 3, 1, "DAMPA POGS"],
]


def load_scores():
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE) as f:
                data = json.load(f)
            # Siguraduhing 4 elements ang bawat row
            fixed = []
            for row in data:
                if len(row) == 3:
                    # Lumang format: [result, player, bot] -> gawing [result, bot, player, mode]
                    fixed.append([row[0], row[2], row[1], "DAMPA KARERA"])
                elif len(row) == 4:
                    fixed.append(row)
            return fixed if fixed else list(DEFAULT_SCORES)
        except (json.JSONDecodeError, OSError):
            pass
    return list(DEFAULT_SCORES)


def add_result(player, bot, mode="DAMPA KARERA", result=None):
    if result is None:
        result = "win" if player > bot else "defeat" if player < bot else "tie"
    # Idagdag sa UNANG position (top), hindi sa dulo
    SCORES.insert(0, [result, bot, player, mode])
    del SCORES[MAX_ROWS:]  # tanggalin ang sobrang rows sa dulo
    try:
        with open(SCORE_FILE, "w") as f:
            json.dump(SCORES, f)
    except OSError:
        pass


SCORES = load_scores()


#  GAME SETTINGS  (DAMPA KARERA)

ROUNDS = 4
BANDS_COUNT = 50                     # the "x50" in the HUD
SWEEP_TIMES = [0.6, 0.5, 0.4, 0.3]  # seconds for the meter to go 0 -> 1 (faster each round)
METER_TIMEOUT = 4.0                  # meter auto-stops if the player never presses
LOCK_PAUSE = 0.8                     # short pause after both meters are locked
TIMER_MIN, TIMER_MAX = 1.0, 3.0      # random wait before the smash
RESULT_TIME = 2.2                    # how long the round result is shown
TIE_MARGIN = 6                       # px difference that still counts as a tie

BAND_START_Y = 330                   # where the bands sit on screen at the start of the match
BG_H = FLOOR.get_height()
FOLLOW_AT = 100                      # bands rise this many px, then the floor starts scrolling
MIN_DIST, MAX_DIST = 60, 230         # how far ONE smash sends the bands (weak -> perfect meter)
FINISH_SMASHES = 2.5                 # finish line = this many PERFECT smashes away (bigger = longer rounds)
FINISH_DIST = int(MAX_DIST * FINISH_SMASHES)   # distance is kept between smashes, resets every round
WHITE_HALF = 0.08                    # half-width of the white (perfect) zone of the meter
GREEN_HALF = 0.25                    # half-width of the green zone
BOT_SPREAD = 0.6                    # bot accuracy: smaller = better aim at the white zone
METER_W, METER_H, METER_Y = 260, 12, 610
METER_MASK = pygame.Surface((METER_W, METER_H), pygame.SRCALPHA)
pygame.draw.rect(METER_MASK, (255, 255, 255, 255), METER_MASK.get_rect(), border_radius=6)

# hand slam timing (copied from the reference video): the hands sit still, then GROW toward the
# camera (slow start -> fast middle -> soft landing), hold for a moment at the bands, then snap back.
T_GROW0 = 0.12                       # hands start moving (seconds after smash starts)
T_IMPACT = 0.55                      # moment the hands hit the bands (end of the grow)
T_HOLD = 0.12                        # hands stay pressed down for this long
T_SNAP = 0.06                        # then snap back to the resting size this fast
STRIKE_MIN, STRIKE_FULL_TIP = 1.20, 300   # weak smash = x1.2 bigger, perfect smash reaches y=300
BAND_TIME = 1.4                      # how long the bands take to slide up

HUD_LEFT = pygame.Rect(266, 20, 176, 54)
HUD_CENTER = pygame.Rect(452, 10, 382, 72)
HUD_RIGHT = pygame.Rect(842, 20, 176, 54)

END_PANEL = pygame.Rect(WIDTH // 2 - 260, 230, 520, 260)
END_AGAIN = pygame.Rect(WIDTH // 2 - 235, 400, 220, 56)
END_MENU = pygame.Rect(WIDTH // 2 + 15, 400, 220, 56)


# ---------------------------------------------------------------------
#  DIFFICULTY (Dampa Karera) - change the numbers here to tune the game
#    BOT_SPREAD     how wrong the bot's aim is (smaller = the bot hits the white zone more often)
#    SWEEP_TIMES    seconds for the meter to cross, per round (smaller = faster = harder to stop)
#    WHITE_HALF     half-width of the white "perfect" zone (smaller = harder to hit)
#    METER_TIMEOUT  seconds before your meter auto-stops (smaller = less time to aim)
#    FINISH_SMASHES race length in perfect smashes (bigger = longer rounds, luck evens out)
# ---------------------------------------------------------------------
DIFFICULTIES = {
    "EASY":   dict(BOT_SPREAD=0.60, SWEEP_TIMES=[0.60, 0.50, 0.40, 0.30], WHITE_HALF=0.08,
                   METER_TIMEOUT=4.0, FINISH_SMASHES=2.5,
                   POGS_BOT_SPREAD=0.20, POGS_SWEEP_MUL=1.25, POGS_BOT_HIT=0.65),
    "MEDIUM": dict(BOT_SPREAD=0.25, SWEEP_TIMES=[0.50, 0.42, 0.35, 0.28], WHITE_HALF=0.06,
                   METER_TIMEOUT=3.0, FINISH_SMASHES=3.0,
                   POGS_BOT_SPREAD=0.11, POGS_SWEEP_MUL=1.0, POGS_BOT_HIT=0.88),
    "HARD":   dict(BOT_SPREAD=0.12, SWEEP_TIMES=[0.42, 0.34, 0.27, 0.22], WHITE_HALF=0.045,
                   METER_TIMEOUT=2.5, FINISH_SMASHES=3.5,
                   POGS_BOT_SPREAD=0.05, POGS_SWEEP_MUL=0.8, POGS_BOT_HIT=0.97),
}
#    POGS_BOT_SPREAD  how wrong the bot's meter aim is in Pogs (smaller = better bot)
#    POGS_SWEEP_MUL   Pogs meter speed (smaller = faster = harder)
#    POGS_BOT_HIT     how often the bot hits its click-circles in Pogs
DIFFICULTY = "MEDIUM"
POGS_BOT_SPREAD, POGS_SWEEP_MUL, POGS_BOT_HIT = 0.11, 1.0, 0.88


def set_difficulty(name):
    global DIFFICULTY, BOT_SPREAD, SWEEP_TIMES, WHITE_HALF, METER_TIMEOUT, FINISH_SMASHES, FINISH_DIST
    global POGS_BOT_SPREAD, POGS_SWEEP_MUL, POGS_BOT_HIT
    DIFFICULTY = name
    d = DIFFICULTIES[name]
    BOT_SPREAD, SWEEP_TIMES, WHITE_HALF = d["BOT_SPREAD"], d["SWEEP_TIMES"], d["WHITE_HALF"]
    METER_TIMEOUT, FINISH_SMASHES = d["METER_TIMEOUT"], d["FINISH_SMASHES"]
    FINISH_DIST = int(MAX_DIST * FINISH_SMASHES)
    POGS_BOT_SPREAD, POGS_SWEEP_MUL, POGS_BOT_HIT = d["POGS_BOT_SPREAD"], d["POGS_SWEEP_MUL"], d["POGS_BOT_HIT"]


set_difficulty(DIFFICULTY)


def meter_power(pos):
    """White zone (middle of the meter) = full power, weaker the further away."""
    d = abs(pos - 0.5)
    if d <= WHITE_HALF:
        return 1.0
    return max(0.1, 0.9 - 0.8 * (d - WHITE_HALF) / (0.5 - WHITE_HALF))


class Side:
    """One half of the screen: a meter, a pair of hands and a pile of rubber bands."""

    def __init__(self):
        self.base = 0.0        # distance flown in earlier rounds
        self.dist = 0.0        # distance of this round's smash
        self.reset(1.5)

    def reset(self, sweep_time):
        self.pos = random.random()
        self.dir = random.choice((-1, 1))
        self.speed = 1.0 / sweep_time
        self.locked = False
        self.power = 0.0
        self.base += self.dist  # keep the progress from the previous round
        self.dist = 0.0

    def new_round(self):
        """a new race: the bands go back to the start"""
        self.base = 0.0
        self.dist = 0.0

    def update_meter(self, dt):
        if self.locked:
            return
        self.pos += self.dir * self.speed * dt
        if self.pos >= 1:
            self.pos, self.dir = 1.0, -1
        elif self.pos <= 0:
            self.pos, self.dir = 0.0, 1

    def lock(self):
        if not self.locked:
            self.locked = True
            self.power = meter_power(self.pos)
            self.dist = MIN_DIST + self.power * (MAX_DIST - MIN_DIST)


class Game:
    def __init__(self):
        self.reset()

    # ------------------------------------------------------------ state
    def reset(self):
        self.round = 1
        self.bot = Side()
        self.player = Side()
        self.bot_wins = 0
        self.player_wins = 0
        self.saved = False
        self.round_msg = ""
        self.final = "tie"
        self.start_round()

    def set_phase(self, phase):
        self.phase = phase
        self.t = 0.0

    def start_round(self):
        """a new round = a new race to the finish line"""
        self.bot.new_round()
        self.player.new_round()
        self.turn = 1
        self.start_turn()

    def start_turn(self):
        """one meter -> timer -> smash cycle inside the current round"""
        sweep = SWEEP_TIMES[min(self.round, ROUNDS) - 1]
        self.bot.reset(sweep)
        self.player.reset(sweep)
        self.bot_target = clamp(random.gauss(0.5, BOT_SPREAD), 0.02, 0.98)   # bot aims at the middle
        self.bot_wait = random.uniform(0.5, 1.6)                      # bot "reaction" delay
        self.wait = random.uniform(TIMER_MIN, TIMER_MAX)              # the hidden timer
        self.smash_t = None
        self.sfx_done = False
        self.set_phase("meter")                                       # 1) meter first

    # ------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if event.key == pygame.K_SPACE and self.phase == "meter" and not self.player.locked:
                self.player.lock()
                play("lock")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.phase == "end":
            if END_AGAIN.collidepoint(event.pos):
                play("click")
                self.reset()
            elif END_MENU.collidepoint(event.pos):
                play("click")
                return "menu"
        return None

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        if self.smash_t is not None:
            self.smash_t += dt
            if not self.sfx_done and self.smash_t >= T_IMPACT:
                self.sfx_done = True
                play("smash")

        if self.phase == "meter":
            self.bot.update_meter(dt)
            self.player.update_meter(dt)

            # bot stops the meter near its target after its reaction delay
            b = self.bot
            if not b.locked and self.t >= self.bot_wait:
                if abs(b.pos - self.bot_target) < b.speed * dt * 1.5 + 0.02 or self.t > 3.5:
                    b.lock()
            if self.t > METER_TIMEOUT:
                self.player.lock()

            if self.bot.locked and self.player.locked:
                self.set_phase("lock")

        elif self.phase == "lock":
            if self.t >= LOCK_PAUSE:
                self.set_phase("timer")                              # 2) then the timer

        elif self.phase == "timer":
            if self.t >= self.wait:
                self.smash_t = 0.0                                   # 3) then the smash
                self.set_phase("smash")

        elif self.phase == "smash":
            if self.t >= T_IMPACT + BAND_TIME + 0.3:
                self.finish_turn()

        elif self.phase == "result":
            if self.t >= RESULT_TIME:
                if self.round < ROUNDS:
                    self.round += 1
                    self.start_round()
                else:
                    if not self.saved:
                        self.final = self.final_result()
                        add_result(self.player_wins, self.bot_wins, "DAMPA KARERA")
                        self.saved = True
                    self.set_phase("end")
                    finish_fx(self.final)

    def total(self, side):
        return side.base + side.dist

    def finish_turn(self):
        """after every smash: did someone cross the finish line? if not, smash again"""
        pt, bt = self.total(self.player), self.total(self.bot)
        pf, bf = pt >= FINISH_DIST, bt >= FINISH_DIST
        if not pf and not bf:
            self.turn += 1
            self.start_turn()                                # nobody finished yet: meter again
            return

        # first to the line wins the round (1 point)
        if pf and bf and abs(pt - bt) < TIE_MARGIN:
            winner = None
        elif pf and (not bf or pt > bt):
            winner = "player"
        else:
            winner = "bot"

        if winner == "player":
            self.player_wins += 1
            self.round_msg = "YOU WIN THE ROUND!"
            play("round")
            confetti_burst(HALF + HALF // 2, 330, 45)
        elif winner == "bot":
            self.bot_wins += 1
            self.round_msg = "BOT WINS THE ROUND!"
        else:
            self.round_msg = "ROUND TIE!"
        self.set_phase("result")

    def final_result(self):
        """'win' / 'loss' / 'tie' for the player, by rounds won"""
        if self.player_wins > self.bot_wins:
            return "win"
        if self.player_wins < self.bot_wins:
            return "loss"
        return "tie"

    # ------------------------------------------------------------ drawing
    def peak_scale(self, side):
        """how big the hands get at the moment of impact (stronger meter = closer to the camera)"""
        full = clamp((HANDS_TOP + HANDS_H - STRIKE_FULL_TIP) / HANDS_H, 1.25, 1.45)
        return lerp(STRIKE_MIN, full, side.power)

    def hand_pose(self, side):
        """returns (y_offset, scale, x_jitter). The whole hands+arms picture is scaled up from the
        bottom edge of the screen, so the fingertips travel up while the arms stay planted."""
        st = self.smash_t
        if st is None:
            jitter = 0
            bob = 0
            if self.phase == "timer":                 # tension: tiny shake while waiting
                jitter = random.uniform(-2, 2)
            elif self.phase in ("meter", "lock"):     # gentle idle bob so the hands feel alive
                bob = 3 * math.sin(self.t * 6)
            return bob, 1.0, jitter
        peak = self.peak_scale(side)
        if st < T_GROW0:                              # still
            return 0, 1.0, 0
        if st < T_IMPACT:                             # rush toward the bands
            k = (st - T_GROW0) / (T_IMPACT - T_GROW0)
            return 0, lerp(1.0, peak, ease_in_out(k)), 0
        if st < T_IMPACT + T_HOLD:                    # pressed down (tiny tremble)
            return 0, peak, random.uniform(-1.5, 1.5)
        if st < T_IMPACT + T_HOLD + T_SNAP:           # snap back
            k = (st - T_IMPACT - T_HOLD) / T_SNAP
            return 0, lerp(peak, 1.0, ease_out(k)), 0
        return 0, 1.0, 0

    def travel(self, side):
        """total distance (px) this side's bands have flown, including earlier rounds"""
        st = self.smash_t
        if st is None or st < T_IMPACT:
            return side.base
        u = clamp((st - T_IMPACT) / BAND_TIME)
        return side.base + side.dist * ease_out(u)

    def draw_meter(self, surf, side, cx, is_player):
        bx = cx - METER_W // 2

        ms = pygame.Surface((METER_W, METER_H), pygame.SRCALPHA)

        def zone(lo, hi, color):
            pygame.draw.rect(ms, color, (int(lo * METER_W), 0, int((hi - lo) * METER_W) + 1, METER_H))

        red, green, white = (240, 60, 40), (60, 230, 50), (255, 255, 255)
        pygame.draw.rect(surf, (40, 10, 10), (bx - 2, METER_Y - 2, METER_W + 4, METER_H + 4), border_radius=8)
        zone(0, 0.5 - GREEN_HALF, red)
        zone(0.5 - GREEN_HALF, 0.5 - WHITE_HALF, green)
        zone(0.5 - WHITE_HALF, 0.5 + WHITE_HALF, white)          # the white "perfect" zone
        zone(0.5 + WHITE_HALF, 0.5 + GREEN_HALF, green)
        zone(0.5 + GREEN_HALF, 1, red)
        ms.blit(METER_MASK, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(ms, (bx, METER_Y))

        # the white zone blinks so new players know where to aim
        if not side.locked and self.phase == "meter" and int(self.t * 5) % 2 == 0:
            wz = pygame.Rect(bx + (0.5 - WHITE_HALF) * METER_W - 2, METER_Y - 4,
                             2 * WHITE_HALF * METER_W + 5, METER_H + 8)
            pygame.draw.rect(surf, (255, 210, 60), wz, 2, border_radius=5)

        mx = bx + side.pos * METER_W
        pygame.draw.rect(surf, (0, 0, 0), (mx - 4, METER_Y - 9, 8, METER_H + 18), border_radius=4)
        pygame.draw.rect(surf, (255, 210, 60), (mx - 2, METER_Y - 7, 4, METER_H + 14), border_radius=2)

        if side.locked:
            perfect = abs(side.pos - 0.5) <= WHITE_HALF
            label = "PERFECT!" if perfect else f"POWER {int(side.power * 100)}%"
            color = GOLD if perfect else TEXT_COLOR
            text_center(SMALL_FONT, label, color, (cx, METER_Y + 30), surf, shadow=True)
        elif is_player and self.phase == "meter":
            col = GOLD if int(self.t * 3) % 2 == 0 else TEXT_COLOR
            text_center(SMALL_FONT, "[ SPACE ]  stop on the white", col,
                        (cx, METER_Y + 30), surf, shadow=True)

    def draw_side(self, side, surf, is_player):
        cx = HALF // 2
        D = self.travel(side)
        scroll = max(0.0, D - FOLLOW_AT)                         # floor moves down as the bands go far
        st = self.smash_t
        moving = st is not None and T_IMPACT <= st < T_IMPACT + BAND_TIME
        u_move = clamp((st - T_IMPACT) / BAND_TIME) if moving else 1.0

        # the floor is a tall image repeated (every 2nd copy flipped so the seams line up)
        for k in range(int(scroll // BG_H), int((HEIGHT + scroll) // BG_H) + 1):
            tile = FLOOR if k % 2 == 0 else FLOOR_FLIP
            surf.blit(tile, (0, HEIGHT - BG_H * (k + 1) + scroll))

        # speed lines while the bands zoom forward
        if moving:
            for i in range(9):
                lx = (i * 73 + 31) % (HALF - 3)
                ly = (i * 191 + int(st * 1400)) % HEIGHT
                surf.blit(SPEED_LINE, (lx, ly))

        # finish line: very far away, off-screen until the floor has scrolled almost all the way
        fy = int(BAND_START_Y - FINISH_DIST + scroll)
        if -30 < fy < HEIGHT:
            for i, x in enumerate(range(0, HALF, 26)):
                for row in range(2):
                    color = (255, 255, 255) if (i + row) % 2 == 0 else (20, 20, 20)
                    pygame.draw.rect(surf, color, (x, fy - 13 + row * 13, 26, 13))
            text_center(SMALL_FONT, "FINISH", TEXT_COLOR, (cx, fy + 26), surf, shadow=True)

        # rubber bands (with a shadow and a little wobble while flying)
        by = BAND_START_Y - D + scroll
        sway = math.sin(st * 18) * 5 * (1 - u_move) if moving else 0
        surf.blit(BAND_SHADOW, BAND_SHADOW.get_rect(center=(cx + 6, by + BANDS.get_height() // 2 + 4)))
        surf.blit(BANDS, BANDS.get_rect(center=(cx + sway, by)))

        # progress bar towards the finish line
        bar = pygame.Rect(14, 110, 12, 440)
        pygame.draw.rect(surf, (20, 20, 20), bar.inflate(4, 4), border_radius=8)
        fill = int(bar.height * clamp(D / FINISH_DIST))
        pygame.draw.rect(surf, (255, 220, 90), (bar.x, bar.bottom - fill, bar.width, fill), border_radius=6)

        if st is not None and st > T_IMPACT + BAND_TIME and side.base + side.dist >= FINISH_DIST:
            text_center(BIG_FONT, "FINISHED!", GOLD, (cx, 125), surf, shadow=True)

        # hands + arms: the picture grows from the bottom edge (arms stay planted, fingertips rush up)
        off, sc, jx = self.hand_pose(side)
        hw = int(HANDS_TOP_IMG.get_width() * sc)
        hh = int(HANDS_TOP_IMG.get_height() * sc)
        top = HANDS_TOP_IMG if sc == 1.0 else pygame.transform.smoothscale(HANDS_TOP_IMG, (hw, hh))
        shad = HANDS_TOP_SHADOW if sc == 1.0 else pygame.transform.smoothscale(HANDS_TOP_SHADOW, (hw, hh))
        y = HANDS_TOP + HANDS_H - HANDS_H * sc + off
        wrist_y = int(y + hh - 1)
        arm_h = max(int(HANDS_ARMS_IMG.get_height() * sc), HEIGHT + 8 - wrist_y)
        if (hw, arm_h) == HANDS_ARMS_IMG.get_size():
            arms = HANDS_ARMS_IMG
        else:
            arms = pygame.transform.smoothscale(HANDS_ARMS_IMG, (hw, arm_h))
        if (hw, arm_h) == HANDS_ARMS_SHADOW.get_size():
            arm_shad = HANDS_ARMS_SHADOW
        else:
            arm_shad = pygame.transform.smoothscale(HANDS_ARMS_SHADOW, (hw, arm_h))
        hx = int(cx + jx - hw // 2)
        surf.blit(arm_shad, (hx + 14, wrist_y + 10))             # forearm shadow (no longer cut off)
        surf.blit(shad, (hx + 14, int(y) + 10))                  # hands shadow
        surf.blit(arms, (hx, wrist_y))
        surf.blit(top, (hx, int(y)))

        self.draw_meter(surf, side, cx, is_player)

    def hud_message(self):
        p = self.phase
        if p == "meter":
            return f"SMASH {self.turn}: PRESS SPACE!" if not self.player.locked else "WAITING FOR BOT..."
        if p == "lock":
            return "LOCKED IN!"
        if p == "timer":
            return "WAIT FOR IT" + "." * (int(self.t * 3) % 4)
        if p == "smash":
            return "SMASH!"
        return self.round_msg

    def draw(self, mouse):
        WIN.fill((0, 0, 0))
        for side, ox, is_player in ((self.bot, 0, False), (self.player, HALF, True)):
            surf = pygame.Surface((HALF, HEIGHT))
            self.draw_side(side, surf, is_player)
            sx = sy = 0
            st = self.smash_t
            if st is not None and T_IMPACT <= st < T_IMPACT + 0.2:     # screen shake on impact
                amp = (2 + 6 * side.power) * (1 - (st - T_IMPACT) / 0.2)
                sx, sy = random.uniform(-amp, amp), random.uniform(-amp, amp)
            WIN.blit(surf, (ox + sx, sy))
        pygame.draw.line(WIN, (15, 15, 15), (HALF, 0), (HALF, HEIGHT), 3)

        # ===== NEW HUD (gold pills, same layout as the reference image) =====
        n = min(self.round, ROUNDS)
        # left = BOT, right = PLAYER
        hud_pill(WIN, HUD_L_LABEL, "ROUND WINS")
        hud_pill(WIN, pygame.Rect(HUD_L_VALUE.right - 140, HUD_L_VALUE.y, 140, 34), f"SCORE:{self.bot_wins}")
        hud_pill(WIN, HUD_ROUND, f"ROUND {n}", TITLE_FONT)
        hud_pill(WIN, HUD_R_LABEL, "ROUND WINS")
        hud_pill(WIN, pygame.Rect(HUD_R_VALUE.x, HUD_R_VALUE.y, 140, 34), f"SCORE:{self.player_wins}")

        # timer pill (the pink-circle spot under the ROUND pill)
        timer_txt = ""
        if self.phase == "meter" and not self.player.locked:
            timer_txt = f"TIME: {int(math.ceil(max(0.0, METER_TIMEOUT - self.t)))}"
        hud_pill(WIN, HUD_TIMER, timer_txt)
        text_center(SMALL_FONT, self.hud_message(), TEXT_COLOR, (WIDTH // 2, 172), shadow=True)

        # ---- friendly pop-up messages ----
        if self.phase == "meter" and self.turn == 1 and self.t < 1.0:
            k = ease_out(clamp(self.t / 0.25))
            pop_text(HUGE_FONT, f"ROUND {min(self.round, ROUNDS)}!", WHITE, (WIDTH // 2, 300), k,
                     alpha=int(255 * clamp((1.0 - self.t) / 0.3)))
        elif self.phase == "result":
            k = ease_out(clamp(self.t / 0.3))
            pop_text(HUGE_FONT, self.round_msg, GOLD, (WIDTH // 2, 330), k,
                     alpha=int(255 * clamp((RESULT_TIME - self.t) / 0.4)))

        if self.phase == "end":
            self.draw_end(mouse)

    def draw_end(self, mouse):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        WIN.blit(dim, (0, 0))

        panel(END_PANEL)
        pygame.draw.rect(WIN, LINE_BROWN, END_PANEL, 4, border_radius=14)
        title = {"win": "YOU WIN!", "loss": "YOU LOSE!", "tie": "IT'S A TIE!"}[self.final]
        pop_text(HUGE_FONT, title, BROWN, (END_PANEL.centerx, END_PANEL.y + 55),
                 ease_out(clamp(self.t / 0.4)))
        text_center(MID_FONT, f"you {self.player_wins}/{self.bot_wins} bot", BROWN,
                    (END_PANEL.centerx, END_PANEL.y + 115))
        cheer = {"win": "Galing! Great job!", "loss": "Okay lang! Try again!", "tie": "So close! Rematch?"}[self.final]
        text_center(DESC_FONT, cheer, LINE_BROWN, (END_PANEL.centerx, END_PANEL.y + 148))
        button(END_AGAIN, "PLAY AGAIN", END_AGAIN.collidepoint(mouse), MID_FONT)
        button(END_MENU, "MENU", END_MENU.collidepoint(mouse), MID_FONT)


CX, CY = WIDTH // 2, 300            # center of the floor where the pogs sit

STACK_MIN, STACK_MAX = 15, 30       # every game starts with a different random stack (15 to 30 pogs)
MAX_STACK = STACK_MAX               # the stack can never be bigger than this
TARGET_R = 34                       # radius of the click-circles (px)
TURN_TIME = 5.0                     # seconds each player has to stop the meter
POG_D = 72                          # pog size on screen (px)
POG_FILES = ["pog1.png", "pog2.png", "pog3.png", "pog4.png"]   # every pog in the stack gets one of these

# hand slam timing (same shape as the reference video: still -> grow toward the camera -> hold -> snap back)
POGS_T_GROW0 = 0.12                 # hands start moving (smash phase)
POGS_T_IMPACT = 0.55                # moment the hands hit the pogs (end of the grow)
POGS_T_HOLD = 0.12                  # hands stay pressed down
POGS_T_SNAP = 0.06                  # then snap back to the resting size
SMASH_TIME = 0.95
LOCK_TIME = 0.55
FLIGHT_TIME = 1.7                   # how long the flipped pogs take to scatter
COLLECT_TIME = 0.75
TRANS_TIME = 1.5                    # turn-change transition
HIDE = 430                          # how far the hands slide down when hidden
REST_TOP = 430                      # y of the fingertips when resting
HAND_W = 280
HAND_X = {"player": CX, "bot": CX}  # both hands sit in the middle-bottom

IDEAL_LO, IDEAL_HI = 0.80, 0.90     # the "sweet spot" of the power meter

# strength -> chance that each pog in the stack flips
#   0-25% weak | 26-50% normal | 51-75% strong | 76-95% powerful (80-90 best) | 96-100% overcharge
FLIP_CURVE = [(0.00, 0.03), (0.25, 0.15), (0.50, 0.30), (0.75, 0.50),
              (0.80, 0.62), (0.85, 0.68), (0.90, 0.62), (0.95, 0.45),
              (0.96, 0.30), (1.00, 0.18)]


def flip_chance(p):
    """chance (0-1) for ONE pog to flip at meter strength p (0-1)."""
    for (x0, y0), (x1, y1) in zip(FLIP_CURVE, FLIP_CURVE[1:]):
        if p <= x1:
            return lerp(y0, y1, (p - x0) / (x1 - x0)) if x1 > x0 else y1
    return FLIP_CURVE[-1][1]


def strike_name(p):
    if IDEAL_LO <= p <= IDEAL_HI:
        return "PERFECT POWER!"
    if p <= 0.25:
        return "WEAK STRIKE"
    if p <= 0.50:
        return "NORMAL STRIKE"
    if p <= 0.75:
        return "STRONG STRIKE"
    if p <= 0.95:
        return "POWERFUL STRIKE"
    return "OVERCHARGE!"


def _load(name):
    try:
        return pygame.image.load(name).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return None


def _circle_mask(img):
    mask = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (img.get_width() // 2, img.get_height() // 2),
                       img.get_width() // 2)
    img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return img


def _fit_square(img):
    """trim the empty edges, centre the picture in a square and fit it to the pog size"""
    rect = img.get_bounding_rect()
    if rect.width and rect.height:
        img = img.subsurface(rect).copy()
    w, h = img.get_size()
    side = max(w, h)
    sq = pygame.Surface((side, side), pygame.SRCALPHA)
    sq.blit(img, ((side - w) // 2, (side - h) // 2))
    if side >= POG_D:
        return pygame.transform.smoothscale(sq, (POG_D, POG_D))
    return pygame.transform.scale(sq, (POG_D, POG_D))             # small picture: keep the pixels crisp


def _extend_down(img, need):
    """make an arm picture taller WITHOUT stretching it: the bottom rows are repeated"""
    w, h = img.get_size()
    out = pygame.Surface((w, need), pygame.SRCALPHA)
    out.blit(img, (0, 0))
    strip_h = max(1, min(8, h))
    strip = img.subsurface((0, h - strip_h, w, strip_h)).copy()
    y = h
    while y < need:
        out.blit(strip, (0, y))
        y += strip_h
    return out


_ASSETS = {}


def _assets():
    """pogs images, built once"""
    if _ASSETS:
        return _ASSETS

    # ---- floor (pixel asphalt with slabs, speckles and a chalk circle around the stack)
    floor = _load("pogs_floor.png")
    if floor:
        floor = pygame.transform.scale(floor.convert(), (WIDTH, HEIGHT))
    else:
        rnd = random.Random(11)
        P = 4
        sw, sh = WIDTH // P + 1, HEIGHT // P + 1
        small = pygame.Surface((sw, sh))
        SLAB = 40
        for x in range(sw):
            for y in range(sh):
                v = 128 + rnd.randint(-10, 10)
                if rnd.random() < 0.05:
                    v += rnd.choice((-30, 30))
                if x % SLAB == 0 or y % SLAB == 0:
                    v -= 22
                small.set_at((x, y), (v, v + 2, v + 4))
        for _ in range(60):
            px, py = rnd.randrange(sw - 2), rnd.randrange(sh - 2)
            v = rnd.choice((100, 160))
            pygame.draw.rect(small, (v, v + 2, v + 4), (px, py, 2, 2))
        floor = pygame.transform.scale(small, (sw * P, sh * P))
        floor = floor.subsurface((0, 0, WIDTH, HEIGHT)).copy()

    # chalk circle: dashed ring so players see where the pogs sit
    chalk = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ring_rect = pygame.Rect(0, 0, 250, 150)
    ring_rect.center = (CX, CY + 10)
    for i in range(0, 360, 12):
        a0, a1 = math.radians(i), math.radians(i + 7)
        p0 = (ring_rect.centerx + math.cos(a0) * ring_rect.w / 2, ring_rect.centery + math.sin(a0) * ring_rect.h / 2)
        p1 = (ring_rect.centerx + math.cos(a1) * ring_rect.w / 2, ring_rect.centery + math.sin(a1) * ring_rect.h / 2)
        pygame.draw.line(chalk, (255, 255, 255, 120), p0, p1, 4)
    floor.blit(chalk, (0, 0))
    _ASSETS["floor"] = floor

    # ---- pog front (artwork side)
    arts = [img for img in (_load(n) for n in POG_FILES) if img]
    if not arts:
        single = _load("pog.png")
        if single:
            arts = [single]
    fronts = []
    for art in arts:
        f = _circle_mask(_fit_square(art))
        pygame.draw.circle(f, (30, 30, 60), (POG_D // 2, POG_D // 2), POG_D // 2, 2)
        fronts.append(f)
    if not fronts:                                           # no pictures found: draw a simple pog
        f = pygame.Surface((POG_D, POG_D), pygame.SRCALPHA)
        pygame.draw.circle(f, (50, 80, 200), (POG_D // 2, POG_D // 2), POG_D // 2)
        pygame.draw.ellipse(f, (70, 170, 70), (4, POG_D // 2 + 4, POG_D - 8, POG_D // 2 - 6))
        pygame.draw.circle(f, (240, 110, 40), (POG_D // 2, POG_D // 2 - 4), 11)
        pygame.draw.circle(f, (255, 220, 80), (POG_D // 2 - 3, POG_D // 2 - 7), 4)
        f = _circle_mask(f)
        pygame.draw.circle(f, (30, 30, 60), (POG_D // 2, POG_D // 2), POG_D // 2, 2)
        fronts = [f]
    _ASSETS["fronts"] = fronts
    _ASSETS["front"] = fronts[0]

    # ---- pog back (the side you see after it flips)
    back_art = _load("pog_back.png")                         # optional: your own picture for the flipped side
    if back_art:
        back = _circle_mask(_fit_square(back_art))
    else:
        back = pygame.Surface((POG_D, POG_D), pygame.SRCALPHA)
        pygame.draw.circle(back, (200, 70, 60), (POG_D // 2, POG_D // 2), POG_D // 2)
        for r, c in ((POG_D * 3 // 8, (245, 200, 70)), (POG_D // 4, (200, 70, 60)), (POG_D // 8, (245, 200, 70))):
            pygame.draw.circle(back, c, (POG_D // 2, POG_D // 2), r)
    pygame.draw.circle(back, (60, 20, 20), (POG_D // 2, POG_D // 2), POG_D // 2, 2)
    _ASSETS["back"] = back

    # ---- hands (resting pose, pointing up)
    def make_pogs_hands():
        img = load_first(HAND_FILES)
        if img:
            rect = img.get_bounding_rect()
            if rect.width and rect.height:
                img = img.subsurface(rect).copy()
            h = int(img.get_height() * HAND_W / img.get_width())
            img = pygame.transform.scale(img, (HAND_W, h))
        else:
            img = pygame.Surface((HAND_W, 330), pygame.SRCALPHA)
            skin, dark = (214, 150, 105), (160, 100, 65)
            pygame.draw.rect(img, skin, (90, 180, 100, 150))
            pygame.draw.ellipse(img, dark, (60, 0, 90, 230))
            pygame.draw.ellipse(img, skin, (64, 4, 82, 220))
            pygame.draw.ellipse(img, dark, (130, 0, 90, 230))
            pygame.draw.ellipse(img, skin, (134, 4, 82, 220))
        need = HEIGHT - REST_TOP + 170                      # always reach below the screen
        if img.get_height() < need:
            img = _extend_down(img, need)                   # extend the arms, never stretch the picture
        return img

    player_hands = make_pogs_hands()
    bot_hands = player_hands.copy()
    bot_hands.fill((170, 120, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)   # darker skin tone
    _ASSETS["hands"] = {"player": player_hands, "bot": bot_hands}
    _ASSETS["hand_shadow"] = silhouette(player_hands, 70)
    return _ASSETS


class Meter:
    """the power bar of Dampa Pogs (0 -> 1 -> 0 ...)"""

    def __init__(self, sweep):
        self.pos = random.random()
        self.dir = random.choice((-1, 1))
        self.speed = 1.0 / sweep
        self.locked = False

    def update(self, dt):
        if self.locked:
            return
        self.pos += self.dir * self.speed * dt
        if self.pos >= 1:
            self.pos, self.dir = 1.0, -1
        elif self.pos <= 0:
            self.pos, self.dir = 0.0, 1


class PogsGame:
    def __init__(self, on_finish=None):
        """on_finish(player_pogs, bot_pogs, mode_name) is called once when the game ends."""
        self.on_finish = on_finish
        self.win = WIN
        self.A = _assets()
        self.f_hud = PixelFont(30)
        self.f_mid = PixelFont(34)
        self.f_big = PixelFont(64)
        self.f_huge = PixelFont(96)
        self.f_small = PixelFont(24)
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.fx = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        rnd = random.Random(5)
        self.stack_off = [(rnd.randint(-3, 3), rnd.randint(-2, 2)) for _ in range(MAX_STACK)]
        self.reset()

    # ---------------------------------------------------------- state
    def reset(self):
        self.stack = random.randint(STACK_MIN, STACK_MAX)   # different stack every game
        self.pile = [random.randrange(len(self.A["fronts"])) for _ in range(self.stack)]   # which picture each pog has
        self.targets = []
        self.tidx = 0
        self.tclock = 0.0
        self.misses = 0
        self.popups = []
        self.pen_title = ""
        self.pen_sub = ""
        self.pen_color = WHITE
        self.round = 1
        self.pogs = {"player": 0, "bot": 0}
        self.last_flip = {"player": 0, "bot": 0}
        self.turn = "player"            # the player always starts
        self.prev = None
        self.flying = []
        self.waves = []          # only the little ring when a "HIT!" circle is clicked
        self.shake = 0.0
        self.power = 0.0
        self.msg = ""
        self.msg2 = ""
        self.saved = False
        self.final = "tie"
        self.meter = Meter(1.0)
        self.impacted = False
        self.set_phase("transition")

    def set_phase(self, phase):
        self.phase = phase
        self.t = 0.0

    def start_meter(self):
        sweep = max(0.22, 0.70 - 0.09 * (self.round - 1)) * POGS_SWEEP_MUL     # much faster, and faster every round
        self.meter = Meter(sweep)
        self.bot_target = clamp(random.gauss(0.84, POGS_BOT_SPREAD), 0.05, 1.0)
        self.bot_wait = random.uniform(0.8, 3.0)
        self.impacted = False
        self.msg = self.msg2 = ""
        self.set_phase("meter")

    # ---------------------------------------------------------- input
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if event.key == pygame.K_SPACE and self.phase == "meter" and self.turn == "player":
                if not self.meter.locked:
                    play("lock")
                self.meter.locked = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.phase == "target" \
                and self.turn == "player":
            self.click_target(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.phase == "end":
            if END_AGAIN.collidepoint(event.pos):
                play("click")
                self.reset()
            elif END_MENU.collidepoint(event.pos):
                play("click")
                return "menu"
        return None

    # ---------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        self.update_fx(dt)
        ph = self.phase

        if ph == "transition":
            if self.t >= TRANS_TIME:
                self.start_meter()

        elif ph == "meter":
            m = self.meter
            m.update(dt)
            if self.turn == "bot" and not m.locked and self.t >= self.bot_wait:
                if abs(m.pos - self.bot_target) < m.speed * dt * 1.5 + 0.02:
                    m.locked = True
            if self.t >= TURN_TIME:
                m.locked = True                                # time is up: auto stop
            if m.locked:
                self.power = m.pos
                self.set_phase("lock")

        elif ph == "lock":
            if self.t >= LOCK_TIME:
                self.start_targets()                           # NEW: click the circles before the smash

        elif ph == "target":
            self.update_targets(dt)

        elif ph == "tresult":
            if self.t >= 1.0:
                self.set_phase("smash")

        elif ph == "smash":
            if self.t >= POGS_T_IMPACT and not self.impacted:
                self.do_impact()
            if self.t >= SMASH_TIME:
                self.set_phase("flip")

        elif ph == "flip":
            if self.t >= FLIGHT_TIME:
                self.pogs[self.turn] += len(self.flying)
                self.set_phase("collect")

        elif ph == "collect":
            if self.t >= COLLECT_TIME:
                self.flying = []
                if self.stack <= 0:
                    self.finish()
                else:
                    self.prev = self.turn
                    self.turn = "bot" if self.turn == "player" else "player"
                    if self.prev == "bot":
                        self.round += 1
                    self.set_phase("transition")

    def finish(self):
        p, b = self.pogs["player"], self.pogs["bot"]
        self.final = "win" if p > b else "loss" if p < b else "tie"
        if not self.saved and self.on_finish:
            self.on_finish(p, b, "DAMPA POGS")
        self.saved = True
        self.set_phase("end")
        finish_fx(self.final)

    # ---------------------------------------------------------- the smash
    def do_impact(self):
        self.impacted = True
        play("smash")
        p = self.power
        chance = flip_chance(p)
        if p > 0.95:                                   # overcharge = loss of control
            chance *= random.uniform(0.3, 1.1)
        flipped, keep = [], []
        for d in self.pile:                            # every pog has its own chance to flip
            (flipped if random.random() < chance else keep).append(d)
        self.pile = keep
        flips = len(flipped)
        self.stack = len(self.pile)
        self.last_flip[self.turn] = flips
        if flips:
            play("pop")
        self.msg = strike_name(p)
        self.msg2 = f"{flips} POG{'S' if flips != 1 else ''} FLIPPED!" if flips else "NO POGS FLIPPED..."

        # flying pogs
        self.flying = []
        spread = 1.35 if p > 0.95 else 1.0
        for k in range(flips):
            ang = random.uniform(0, math.tau)
            rad = random.uniform(0.35, 1.0)
            ex = clamp(CX + math.cos(ang) * 300 * rad * spread, 330, 970)
            ey = clamp(CY + math.sin(ang) * 175 * rad * spread, 140, 450)
            self.flying.append({
                "start": (CX + random.randint(-4, 4), CY - random.randint(0, 12)),
                "end": (ex, ey),
                "delay": random.uniform(0, 0.15),
                "dur": random.uniform(0.9, 1.3),
                "arc": random.uniform(110, 200) * (0.5 + p),
                "design": flipped[k],
                "turns": random.choice((3, 5, 7)),             # odd number of half turns = lands flipped
            })

        self.shake = 4 + 9 * p

    # ---------------------------------------------------------- circle-click challenge
    def pick_target_pos(self, prev):
        """a random spot anywhere on screen that does not hide the HUD"""
        avoid = [pygame.Rect(250, 8, 800, 160), pygame.Rect(0, 150, 215, 125),
                 pygame.Rect(WIDTH - 215, 150, 215, 125), pygame.Rect(CX - 300, 150, 600, 140),
                 pygame.Rect(290, 520, 260, 120), pygame.Rect(750, 520, 260, 120),
                 PAUSE_BTN.inflate(40, 40)]
        for _ in range(80):
            x = random.randint(TARGET_R + 40, WIDTH - TARGET_R - 40)
            y = random.randint(TARGET_R + 110, HEIGHT - TARGET_R - 30)
            zone = pygame.Rect(0, 0, TARGET_R * 2 + 60, TARGET_R * 2 + 60)
            zone.center = (x, y)
            if any(zone.colliderect(a) for a in avoid):
                continue
            if prev and math.hypot(x - prev[0], y - prev[1]) < 260:      # keep them scattered
                continue
            return (x, y)
        return (random.randint(300, 1000), random.randint(250, 420))

    def start_targets(self):
        n = min(5, 2 + (self.round + 1) // 2)                           # more circles in later rounds
        life = max(0.6, 1.25 - 0.09 * (self.round - 1))                 # and less time for each one
        p_hit = clamp(POGS_BOT_HIT - 0.03 * (self.round - 1), 0.45, 0.99)        # how well the bot clicks
        self.targets = []
        prev = None
        for i in range(n):
            pos = self.pick_target_pos(prev)
            prev = pos
            lf = life + (0.35 if i == 0 else 0.0)                       # a little extra time for the 1st one
            hit_at = random.uniform(0.35, 0.8) * lf if random.random() < p_hit else None
            self.targets.append({"pos": pos, "life": lf, "hit_at": hit_at, "state": None})
        self.tidx = 0
        self.tclock = -0.3
        self.misses = 0
        self.popups = []
        self.set_phase("target")

    def resolve_target(self, hit):
        tg = self.targets[self.tidx]
        tg["state"] = "hit" if hit else "miss"
        x, y = tg["pos"]
        if hit:
            play("pop")
            self.waves.append([x, y, 0.0, 0.35, 60])
            self.popups.append([x, y - TARGET_R - 10, "HIT!", (90, 255, 130), 0.0])
        else:
            self.misses += 1
            play("miss")
            self.popups.append([x, y, "MISS!", (255, 90, 70), 0.0])
        self.tidx += 1
        self.tclock = -0.2

    def click_target(self, pos):
        if self.tidx >= len(self.targets) or self.tclock < 0:
            return
        tx, ty = self.targets[self.tidx]["pos"]
        if math.hypot(pos[0] - tx, pos[1] - ty) <= TARGET_R + 6:
            self.resolve_target(True)

    def update_targets(self, dt):
        if self.tidx >= len(self.targets):
            self.apply_penalty()
            self.set_phase("tresult")
            return
        self.tclock += dt
        if self.tclock < 0:
            return
        tg = self.targets[self.tidx]
        if self.turn == "bot" and tg["hit_at"] is not None and self.tclock >= tg["hit_at"]:
            self.resolve_target(True)
        elif self.tclock >= tg["life"]:
            self.resolve_target(False)

    def apply_penalty(self):
        """every miss can cost power - the more you miss, the more likely and the bigger the loss"""
        m = self.misses
        who = "" if self.turn == "player" else "BOT: "
        if m == 0:
            self.pen_title, self.pen_sub, self.pen_color = who + "ALL CIRCLES HIT!", "FULL POWER!", (90, 255, 130)
        else:
            chance = min(1.0, 0.35 + 0.25 * m)
            if random.random() < chance:
                lost = min(0.85, 0.12 * m + random.uniform(0.0, 0.10))
                self.power = max(0.02, self.power * (1 - lost))
                self.pen_title, self.pen_sub = who + f"MISSED {m}!", f"POWER -{int(lost * 100)}%"
                self.pen_color = (255, 90, 70)
            else:
                self.pen_title, self.pen_sub = who + f"MISSED {m}... LUCKY!", "NO POWER LOST"
                self.pen_color = (255, 210, 90)
        self.meter.pos = self.power                       # the bar drops to show the new power

    def draw_targets(self, surf):
        if self.phase != "target" or self.tidx >= len(self.targets) or self.tclock < 0:
            return
        tg = self.targets[self.tidx]
        x, y = tg["pos"]
        u = clamp(self.tclock / tg["life"])
        r = max(2, int(TARGET_R * ease_out(clamp(self.tclock / 0.12))))
        ring_r = int(TARGET_R * (1 + 1.6 * (1 - u)))                  # the ring shrinks onto the circle
        fill = (255, 205, 40) if self.turn == "player" else (255, 130, 100)
        pygame.draw.circle(surf, (0, 0, 0), (x + 4, y + 5), r)
        pygame.draw.circle(surf, fill, (x, y), r)
        pygame.draw.circle(surf, (90, 60, 0), (x, y), r, 4)
        pygame.draw.circle(surf, (255, 255, 255), (x, y), max(ring_r, r), 4)
        self.text(surf, self.f_mid, str(self.tidx + 1), (60, 30, 0), (x, y), shadow=False)

    def draw_popups(self, surf):
        for x, y, txt, col, age in self.popups:
            self.text(surf, self.f_mid, txt, col, (int(x), int(y - 30 * age)), alpha=int(255 * clamp(1 - age / 0.8)))

    def update_fx(self, dt):
        for pp in self.popups:
            pp[4] += dt
        self.popups = [pp for pp in self.popups if pp[4] < 0.8]
        fx_step(self.waves, dt)
        self.shake = max(0.0, self.shake - dt * 28)

    # ---------------------------------------------------------- hands pose
    def peak_scale(self, side):
        """how big the hands get at the moment of impact (stronger meter = closer to the camera)"""
        h = self.A["hands"][side].get_height()
        full = clamp((h + 100) / h, 1.2, 1.45)             # fingertips end up ~100px above their rest spot
        return lerp(1.15, full, self.power)

    def hand_state(self, side):
        """returns (y_offset, scale, x_jitter). In the smash the hands are scaled from their bottom edge."""
        ph = self.phase
        if ph == "transition":
            u = clamp(self.t / TRANS_TIME)
            if side == self.turn:
                k = clamp((u - 0.45) / 0.55) if self.prev else clamp(u / 0.7)
                return HIDE * (1 - ease_out(k)), 1.0, 0
            if side == self.prev:
                return HIDE * ease_in_out(clamp(u / 0.45)), 1.0, 0
            return HIDE, 1.0, 0
        if ph == "end" or side != self.turn:
            return HIDE, 1.0, 0
        if ph == "meter":
            if self.meter.pos > 0.95:                                    # overcharge shakes
                return 0, 1.0, random.uniform(-3, 3)
            return 4 * math.sin(self.t * 6), 1.0, 0                      # gentle idle bob
        if ph in ("target", "tresult"):
            return 4 * math.sin(self.t * 6), 1.0, 0
        if ph == "smash":
            t = self.t
            peak = self.peak_scale(side)
            if t < POGS_T_GROW0:                            # still
                return 0, 1.0, 0
            if t < POGS_T_IMPACT:                           # rush toward the pogs (grows from the bottom edge)
                k = (t - POGS_T_GROW0) / (POGS_T_IMPACT - POGS_T_GROW0)
                return 0, lerp(1.0, peak, ease_in_out(k)), 0
            if t < POGS_T_IMPACT + POGS_T_HOLD:             # pressed down (tiny tremble)
                return 0, peak, random.uniform(-1.5, 1.5)
            if t < POGS_T_IMPACT + POGS_T_HOLD + POGS_T_SNAP:     # snap back
                k = (t - POGS_T_IMPACT - POGS_T_HOLD) / POGS_T_SNAP
                return 0, lerp(peak, 1.0, ease_out(k)), 0
        return 0, 1.0, 0

    # ---------------------------------------------------------- drawing
    def blit_pog(self, surf, img, x, y, wf=1.0, sc=1.0):
        w = max(2, int(POG_D * sc * wf))
        h = max(2, int(POG_D * sc))
        s = img if (w, h) == img.get_size() else pygame.transform.scale(img, (w, h))
        surf.blit(s, s.get_rect(center=(int(x), int(y))))

    def shadow(self, surf, x, y, wf=1.0, sc=1.0, alpha=70):
        w, h = max(2, int(POG_D * sc * wf)), max(2, int(POG_D * sc * 0.55))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
        surf.blit(s, s.get_rect(center=(int(x + 4), int(y + 6))))

    def draw_stack(self, surf):
        jolt = 0
        if self.phase == "smash" and POGS_T_IMPACT <= self.t < POGS_T_IMPACT + 0.25:
            jolt = random.randint(-2, 2)                    # little jolt when the hands slam
        for i in range(self.stack):
            ox, oy = self.stack_off[i % MAX_STACK]
            x, y = CX + ox + jolt, CY + oy - i * min(3.0, 45.0 / max(self.stack, 1))   # tall stacks get tighter
            self.shadow(surf, x, y, alpha=45 if i else 80)
            self.blit_pog(surf, self.A["fronts"][self.pile[i]], x, y)

    def draw_flying(self, surf):
        # BOT is on the left, PLAYER on the right (like the reference HUD)
        coll = (WIDTH - 70, 640) if self.turn == "player" else (70, 640)
        for p in self.flying:
            sx, sy = p["start"]
            ex, ey = p["end"]
            if self.phase in ("smash", "flip"):
                # flight starts the moment the hands hit the floor (not before, not later)
                if self.phase == "smash":
                    ft = max(0.0, self.t - POGS_T_IMPACT)
                else:
                    ft = (SMASH_TIME - POGS_T_IMPACT) + self.t
                u = clamp((ft - p["delay"]) / p["dur"])
                x, y = lerp(sx, ex, ease_out(u)), lerp(sy, ey, ease_out(u))
                air = math.sin(math.pi * u) * p["arc"]
                ang = u * math.pi * p["turns"]
                wf = max(0.12, abs(math.cos(ang)))
                face = self.A["fronts"][p["design"]] if math.cos(ang) > 0 else self.A["back"]
                self.shadow(surf, x, y, 0.9, alpha=60)
                self.blit_pog(surf, face, x, y - air, wf, 1.0 + air / 400)
            else:                                           # landed (or being collected)
                u = ease_in_out(clamp(self.t / COLLECT_TIME)) if self.phase == "collect" else 0
                x, y = lerp(ex, coll[0], u), lerp(ey, coll[1], u)
                self.shadow(surf, x, y, alpha=int(60 * (1 - u)))
                self.blit_pog(surf, self.A["back"], x, y, 1.0, 1.0 - 0.5 * u)

    def draw_fx(self, surf):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        draw_waves(fx, self.waves)
        surf.blit(fx, (0, 0))

    def draw_hands(self, surf):
        for side in ("player", "bot"):
            off, sc, jx = self.hand_state(side)
            if off >= HIDE:
                continue
            img = self.A["hands"][side]
            shad = self.A["hand_shadow"]
            w, h = int(img.get_width() * sc), int(img.get_height() * sc)
            if sc != 1.0:
                img = pygame.transform.smoothscale(img, (w, h))
                shad = pygame.transform.smoothscale(shad, (w, h))
            base_h = self.A["hands"][side].get_height()
            px, py = int(HAND_X[side] + jx - w // 2), int(REST_TOP + off + base_h - h)   # bottom edge stays put
            surf.blit(shad, (px + 14, py + 12))               # soft drop shadow on the floor
            surf.blit(img, (px, py))

    def box(self, surf, rect, text, font=None):
        pygame.draw.rect(surf, (0, 0, 0), rect, border_radius=14)
        pygame.draw.rect(surf, (90, 60, 0), rect, 2, border_radius=14)
        font = font or self.f_hud
        img = font.render(text, True, WHITE)
        surf.blit(img, img.get_rect(midleft=(rect.x + 14, rect.centery)))

    def text(self, surf, font, txt, color, center, shadow=True, alpha=255):
        img = font.render(txt, True, color)
        sh = font.render(txt, True, (0, 0, 0))
        if alpha < 255:
            img = img.copy()          # (font surfaces are cached, never change them directly)
            sh = sh.copy()
            img.set_alpha(alpha)
            sh.set_alpha(alpha)
        r = img.get_rect(center=center)
        if shadow:
            surf.blit(sh, (r.x + 3, r.y + 3))
        surf.blit(img, r)

    def draw_bar(self, surf, x, y, label):
        """power bar like the reference: red track + green power fill"""
        m = self.meter
        w, h = 230, 14
        self.text(surf, self.f_mid, label, WHITE, (x + w // 2, y - 20))
        pygame.draw.rect(surf, (0, 0, 0), (x - 3, y - 3, w + 6, h + 6))
        pygame.draw.rect(surf, (240, 60, 40), (x, y, w, h))                 # red track
        fill = int(w * clamp(m.pos))
        if fill > 0:
            col = (255, 150, 40) if m.pos > 0.95 else (60, 230, 50)         # green power fill
            pygame.draw.rect(surf, col, (x, y, fill, h))
        # the sweet spot (80-90%) - blinks while the player is aiming
        blink = not (self.turn == "player" and self.phase == "meter" and int(self.t * 5) % 2 == 0)
        pygame.draw.rect(surf, (255, 235, 90) if blink else (255, 255, 255),
                         (x + int(IDEAL_LO * w), y - 5, int((IDEAL_HI - IDEAL_LO) * w), h + 10), 2)
        pygame.draw.line(surf, (255, 255, 255), (x + fill, y - 4), (x + fill, y + h + 4), 3)
        self.text(surf, self.f_small, f"{int(m.pos * 100)}%", WHITE, (x + w // 2, y + h + 16))
        if self.turn == "player" and self.phase == "meter":
            self.text(surf, self.f_small, "[SPACE] STOP IN GREEN BOX", WHITE, (x + w // 2, y + h + 38))

    def draw_hud(self, surf):
        hud_pill(surf, HUD_ROUND, f"ROUND {self.round}", TITLE_FONT)
        hud_pill(surf, HUD_L_LABEL, "BOT")
        hud_pill(surf, HUD_L_VALUE, f"{self.pogs['bot']} POGS")
        hud_pill(surf, HUD_R_LABEL, "PLAYER")
        hud_pill(surf, HUD_R_VALUE, f"{self.pogs['player']} POGS")

        # timer pill (under the ROUND pill)
        t_txt = ""
        if self.phase == "transition":
            t_txt = f"TIME: {int(TURN_TIME)}"
        elif self.phase == "meter":
            t_txt = f"TIME: {int(math.ceil(max(0.0, TURN_TIME - self.t)))}"
        hud_pill(surf, HUD_TIMER, t_txt)

        # the two pills on each side: FLIP + STACK
        for rects, who in ((HUD_SIDE_L, "bot"), (HUD_SIDE_R, "player")):
            hud_pill(surf, rects[0], f"FLIP: {self.last_flip[who]}")
            hud_pill(surf, rects[1], f"STACK: {self.stack}")

        if self.phase in ("end", "transition"):
            return
        if self.turn == "player":
            self.draw_bar(surf, CX - 360, 560, "YOU")      # left of the hands
        else:
            self.draw_bar(surf, CX + 130, 560, "BOT")      # right of the hands

    def draw_messages(self, surf):
        if self.phase == "transition":
            u = clamp(self.t / TRANS_TIME)
            a = int(255 * min(1, u / 0.2, (1 - u) / 0.2))
            who = "YOUR TURN" if self.turn == "player" else "BOT'S TURN"
            self.text(surf, self.f_huge, who, WHITE, (CX, 225), alpha=max(0, a))
            self.text(surf, self.f_mid, f"stack: {self.stack} pogs", WHITE, (CX, 285), alpha=max(0, a))
        elif self.phase == "target":
            n = len(self.targets)
            title = "CLICK THE CIRCLES!" if self.turn == "player" else "BOT IS CLICKING..."
            self.text(surf, self.f_big, title, GOLD, (CX, 190))
            self.text(surf, self.f_mid, f"CIRCLE {min(self.tidx + 1, n)}/{n}   MISSES: {self.misses}", WHITE, (CX, 235))
        elif self.phase == "tresult":
            self.text(surf, self.f_big, self.pen_title, self.pen_color, (CX, 190))
            self.text(surf, self.f_mid, self.pen_sub, WHITE, (CX, 235))
        elif self.phase in ("lock", "smash") or (self.phase == "meter" and self.meter.locked):
            self.text(surf, self.f_big, strike_name(self.power), GOLD, (CX, 190))
        elif self.phase in ("flip", "collect"):
            self.text(surf, self.f_big, self.msg, GOLD, (CX, 185))
            self.text(surf, self.f_mid, self.msg2, WHITE, (CX, 230))

    def draw(self, mouse):
        c = self.canvas
        c.blit(self.A["floor"], (0, 0))
        self.draw_stack(c)
        self.draw_flying(c)
        self.draw_fx(c)
        self.draw_hands(c)
        self.draw_targets(c)
        self.draw_hud(c)
        self.draw_messages(c)
        self.draw_popups(c)

        self.win.fill((0, 0, 0))
        sx = random.uniform(-self.shake, self.shake) if self.shake else 0
        sy = random.uniform(-self.shake, self.shake) if self.shake else 0
        self.win.blit(c, (sx, sy))
        if self.phase == "end":
            self.draw_end(mouse)

    def draw_end(self, mouse):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        self.win.blit(dim, (0, 0))
        panel(END_PANEL)
        pygame.draw.rect(self.win, LINE_BROWN, END_PANEL, 4, border_radius=14)
        title = {"win": "YOU WIN!", "loss": "YOU LOSE!", "tie": "IT'S A TIE!"}[self.final]
        pop_text(self.f_huge, title, BROWN, (END_PANEL.centerx, END_PANEL.y + 55),
                 ease_out(clamp(self.t / 0.4)))
        self.text(self.win, self.f_mid, f"you {self.pogs['player']} / {self.pogs['bot']} bot  (pogs)", BROWN,
                  (END_PANEL.centerx, END_PANEL.y + 115), shadow=False)
        cheer = {"win": "Galing! Great job!", "loss": "Okay lang! Try again!", "tie": "So close! Rematch?"}[self.final]
        self.text(self.win, self.f_small, cheer, LINE_BROWN, (END_PANEL.centerx, END_PANEL.y + 148), shadow=False)
        button(END_AGAIN, "PLAY AGAIN", END_AGAIN.collidepoint(mouse), self.f_mid)
        button(END_MENU, "MENU", END_MENU.collidepoint(mouse), self.f_mid)


# =====================================================================
#  MENU / SCORE / EXIT SCREENS
# =====================================================================
def draw_menu(mouse):
    now = pygame.time.get_ticks()
    WIN.blit(BG, (0, 0))
    AMBIENT.draw(WIN)
    bob = int(math.sin(now / 500) * 6)                         # the logo floats up and down
    WIN.blit(LOGO, LOGO_POS.move(0, bob))
    text_center(SMALL_FONT, TIPS[(now // 4000) % len(TIPS)], GOLD, (WIDTH // 2, 26), shadow=True)
    for label, rect in MENU_BUTTONS.items():
        button(rect, "SCORES" if label == "SCORE" else label, rect.collidepoint(mouse))
    y = HEIGHT - 75
    for line in DESCRIPTION:
        text_center(DESC_FONT, line, TEXT_COLOR, (WIDTH // 2, y), shadow=True)
        y += 24


def draw_score(mouse, bg=None):
    backdrop(bg)
    t = SCORE_TABLE

    wood = ui_img("score_wood", SCORE_BOARD.size)
    if wood is not None:
        WIN.blit(wood, SCORE_BOARD.topleft)                           # YOUR wood board
    else:
        b = wood_box(SCORE_BOARD.w, SCORE_BOARD.h, (214, 160, 96), 8, (96, 44, 20))
        WIN.blit(b, b.get_rect(center=SCORE_BOARD.center))
        nail(SCORE_BOARD.right - 14, SCORE_BOARD.y + 14)
        nail(SCORE_BOARD.x + 14, SCORE_BOARD.bottom - 14)
        nail(SCORE_BOARD.right - 14, SCORE_BOARD.bottom - 14)
    paper = ui_img("score_paper", t.size)
    if paper is not None:
        WIN.blit(paper, t.topleft)                                    # YOUR paper
    else:
        paper_box(t)
    sign = ui_img("score_sign", SCORE_SIGN.size)
    if sign is not None:
        WIN.blit(sign, SCORE_SIGN.topleft)                            # YOUR SCORE sign
    else:
        draw_sign(SCORE_PLANK, "SCORE")

    # table area = the paper minus a small margin (and the scroll strip on the right)
    x0 = t.x + 20
    uw = t.width - 50
    xr = x0 + uw
    
    # 6 columns distribution para sakto sa reference image
    cw = [int(uw * 0.26), int(uw * 0.08), int(uw * 0.20), int(uw * 0.08), int(uw * 0.20), int(uw * 0.18)]
    cx = [x0 + sum(cw[:i]) + cw[i] // 2 for i in range(6)]
    vx = [x0 + sum(cw[:i+1]) for i in range(5)]

    # header row (does not scroll)
    text_center(SMALL_FONT, "STREAK", BROWN, (cx[0], t.y + HEAD_ROW_H // 2))
    text_center(SMALL_FONT, "ENEMYMODE", BROWN, ((cx[1] + cx[4]) // 2, t.y + HEAD_ROW_H // 2))
    # Stacked ang GAME MODES tulad sa picture
    text_center(DESC_FONT, "GAME", BROWN, (cx[5], t.y + HEAD_ROW_H // 2 - 10))
    text_center(DESC_FONT, "MODES", BROWN, (cx[5], t.y + HEAD_ROW_H // 2 + 10))

    # Horizontal line under headers
    pygame.draw.line(WIN, LINE_BLUE, (x0, t.y + HEAD_ROW_H), (xr, t.y + HEAD_ROW_H), 2)

    # Vertical lines (drawn once, mula sa ilalim ng title area hanggang ibaba)
    for v in vx:
        pygame.draw.line(WIN, LINE_BLUE, (v, t.y + 12), (v, t.bottom - 12), 2)

    # scrollable rows
    clip_rect = pygame.Rect(x0, t.y + HEAD_ROW_H + 1, uw + 2, t.height - HEAD_ROW_H - 14)
    old_clip = WIN.get_clip()
    WIN.set_clip(clip_rect)

    for i, row in enumerate(SCORES[:MAX_ROWS]):
        if len(row) == 4:
            result, bot, player, mode = row
        else:
            result, bot, player, mode = "tie", 0, 0, "GOMA"

        cy = t.y + HEAD_ROW_H + i * ROW_H + ROW_H // 2 - scroll_offset
        line_y = t.y + HEAD_ROW_H + (i + 1) * ROW_H - scroll_offset

        # Draw horizontal lines in between rows (pumapasok ito sa clip area kapag nag-scroll)
        pygame.draw.line(WIN, LINE_BLUE, (x0, line_y), (xr, line_y), 2)

        if cy < t.y + HEAD_ROW_H - ROW_H or cy > t.bottom + ROW_H:
            continue
            
        res_upper = str(result).upper()
        if "WIN" in res_upper:
            color = (0, 160, 40)   # Green for WIN
        elif "DEFEAT" in res_upper:
            color = (230, 40, 40)  # Red for DEFEAT
        else:
            color = BROWN          # Brown for TIE

        short_mode = "GOMA" if "KARERA" in str(mode).upper() else "POGS"
        
        # Mga text sa loob ng bawat row na naka-center sa saktong columns
        text_center(SMALL_FONT, res_upper, color, (cx[0], cy))
        text_center(SMALL_FONT, str(bot), BROWN, (cx[1], cy))
        text_center(SMALL_FONT, "BOT", BROWN, (cx[2], cy))
        text_center(SMALL_FONT, str(player), BROWN, (cx[3], cy))
        text_center(SMALL_FONT, "PLAYER", BROWN, (cx[4], cy))
        text_center(SMALL_FONT, short_mode, BROWN, (cx[5], cy))

    WIN.set_clip(old_clip)

    content_h = len(SCORES[:MAX_ROWS]) * ROW_H
    view_h = t.height - HEAD_ROW_H

    if content_h > view_h:
        text_center(DESC_FONT, "scroll with your mouse wheel", TEXT_COLOR,
                    (t.x + 150, SCORE_BACK.centery), shadow=True)
    button(SCORE_BACK, "BACK", SCORE_BACK.collidepoint(mouse), MID_FONT)


def draw_exit(mouse, bg=None):
    backdrop(bg)

    # paper first, banner on top so it overlaps the paper's top edge
    paper = ui_img("exit_paper", EXIT_PANEL.size)
    if paper is not None:
        WIN.blit(paper, EXIT_PANEL.topleft)
    else:
        paper_box(EXIT_PANEL)

    banner = ui_img("button", EXIT_HEADER.size)
    if banner is not None:
        WIN.blit(banner, EXIT_HEADER.topleft)
    else:
        s = btn_surface(EXIT_HEADER.w, EXIT_HEADER.h, "gold")
        WIN.blit(s, s.get_rect(center=EXIT_HEADER.center))
    text_center(BIG_FONT, "EXIT", BTN_PAL["gold"][0], EXIT_HEADER.center)

    # question, 3 lines like the reference
    y = EXIT_PANEL.y + int(EXIT_PANEL.h * 0.20)
    for line in ("Are you sure", "you want to", "quit?"):
        text_center(MID_FONT, line, BROWN, (EXIT_PANEL.centerx, y))
        y += 30

    # YES / NO stacked. NO is the "selected" one unless the mouse is on YES.
    yes_hot = EXIT_YES.collidepoint(mouse)
    no_hot = EXIT_NO.collidepoint(mouse) or not yes_hot
    button(EXIT_YES, "YES", yes_hot, SMALL_FONT, key="exit_yes")
    button(EXIT_NO, "NO", no_hot, SMALL_FONT, key="exit_no")


# ---------------------------------------------------------------------
#  GAME MODE SCREENS
# ---------------------------------------------------------------------
NOTICE = ["", 0.0]              # little pop-up message: [text, seconds left]
SELECTED_MODE = "karera"        # which game card is selected on the 2nd screen
DIFF_CHOSEN = False             # the player must pick a level before pressing START
_CARD_CACHE = {}
_WRAP = {}

MODE_INFO = {
    "karera": ("DAMPA KARERA", KARERA_IMG, "Gameplay - Dampa Rubber Band",
               "Players compete in a rubber band racing game where the goal is to reach the finish line "
               "first. The game consists of 4 rounds, with each round becoming faster and more "
               "challenging. Players must use good timing and strategy to move their rubber bands "
               "forward and beat their opponents. The first player to cross the finish line wins the round!"),
    "pogs": ("DAMPA POGS", POGS_IMG, "Gameplay - Dampa Pogs",
             "Players control a dampa to smash a stack of pogs using a strength meter. By pressing SPACE "
             "at the right moment, players control the power of their smash. The goal is to flip as many "
             "pogs as possible to win the game. Players must use the right timing and strength to "
             "achieve the highest score and defeat their opponents."),
}


def set_notice(text):
    NOTICE[0], NOTICE[1] = text, 1.8


def draw_notice(center, color=(255, 210, 60)):
    if NOTICE[1] > 0:
        k = ease_out(clamp((1.8 - NOTICE[1]) / 0.2))
        pop_text(MID_FONT, NOTICE[0], color, center, k, alpha=int(255 * clamp(NOTICE[1] / 0.4)))


def wrap_text(font, text, width):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if font.render(t, True, WHITE).get_width() <= width:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def person_icon(color=(70, 35, 30)):
    """a chunky pixel silhouette of a person"""
    s = pygame.Surface((24, 32), pygame.SRCALPHA)
    pygame.draw.circle(s, color, (12, 6), 6)
    pygame.draw.rect(s, color, (3, 14, 18, 18), border_radius=3)
    for gx, gy, gh in ((6, 16, 10), (17, 16, 10), (11, 24, 8)):      # gaps = arms and legs
        pygame.draw.rect(s, (0, 0, 0, 0), (gx, gy, 1 + (gx == 11), gh))
    return pygame.transform.scale(s, (24 * 6, 32 * 6))


# Put your exact file names FIRST in each list. Names are matched ignoring upper/lower case.
# The game looks in the same folder as main.py.
VS_FILES = {
    "PLAYER VS PLAYER": ["2playermode.png", "2players.png", "pvp.png", "playervsplayer.png", "player_vs_player.png"],
    "PLAYER VS BOT":    ["botvsplayermode.png", "playervsbot.png", "pvb.png", "player_vs_bot.png", "bot_vs_player.png"],
}


def find_file(names):
    """case-insensitive search for the first existing file in `names`"""
    try:
        have = {f.lower(): f for f in os.listdir(".")}
    except OSError:
        return None
    for n in names:
        if n.lower() in have:
            return have[n.lower()]
    return None


# ---------------------------------------------------------------------
#  LEVEL LOGOS (visual only): each level has its own logo in the gold frame.
#  EDIT THE FILE NAMES to match your PNGs (put your exact name FIRST in each list).
#  Green = EASY, blue = MEDIUM, red = HARD. If a file is not found, a coloured
#  shield is drawn instead so the game never crashes.
# ---------------------------------------------------------------------
LEVEL_LOGO_FILES = {
    "EASY":   ["easy_logo.png", "easylogo.png", "logo_easy.png", "easy_icon.png", "easy_badge.png"],
    "MEDIUM": ["medium_logo.png", "mediumlogo.png", "logo_medium.png", "medium_icon.png", "medium_badge.png"],
    "HARD":   ["hard_logo.png", "hardlogo.png", "logo_hard.png", "hard_icon.png", "hard_badge.png"],
}
LEVEL_COLORS = {"EASY": (60, 200, 110), "MEDIUM": (60, 150, 230), "HARD": (230, 60, 50)}
_LOGO_CACHE = {}


LOGO_FRAME_FILES = ["buttonsize1.png", "logo_frame.png", "level_frame.png", "frame.png", "logoframe.png", "levelframe.png"]
_LOGO_FRAMED = {}


def _has_frame(pic):
    """AUTO check: a picture that already contains its frame is an almost solid rectangle"""
    if LOGO_HAS_FRAME is not None:
        return LOGO_HAS_FRAME
    m = pygame.mask.from_surface(pic, 10)
    return m.count() / float(pic.get_width() * pic.get_height()) > 0.80


LEVEL_KEYWORDS = {"EASY": ("easy",), "MEDIUM": ("medium", "meduim", "mid"), "HARD": ("hard",)}


def auto_find_logo(name):
    """if none of the names in LEVEL_LOGO_FILES exist, look for ANY png whose name contains the level word
    (easy / medium / hard). The game's own button pictures are skipped."""
    try:
        files = [f for f in os.listdir(".") if f.lower().endswith(".png")]
    except OSError:
        return None
    skip = {v.lower() for v in UI_FILES.values()} | {n.lower() for n in LOGO_FRAME_FILES}
    found = [f for f in files
             if f.lower() not in skip and "button" not in f.lower() and "hover" not in f.lower()
             and any(k in f.lower() for k in LEVEL_KEYWORDS[name])]
    if not found:
        print(f"[dampa] level logo '{name}': no png with {LEVEL_KEYWORDS[name]} in its name. PNG files here: {sorted(files)}")
        return None
    found.sort(key=lambda f: (not any(w in f.lower() for w in ("logo", "icon", "badge", "emblem")), len(f)))
    return found[0]


def level_logo(name):
    """returns the logo picture; _LOGO_FRAMED[name] tells if the picture already includes its frame"""
    if name in _LOGO_CACHE:
        return _LOGO_CACHE[name]
    img = None
    framed = False
    fname = find_file(LEVEL_LOGO_FILES[name]) or auto_find_logo(name)
    if fname:
        pic = load_image(fname)
        if pic is not None:
            pic = crop_to_content(pic)
            framed = _has_frame(pic)
            iw, ih = (LOGO_FRAME.w, LOGO_FRAME.h) if framed else (LOGO_FRAME.w - 40, LOGO_FRAME.h - 40)
            k = min(iw / pic.get_width(), ih / pic.get_height())
            size = (max(1, int(pic.get_width() * k)), max(1, int(pic.get_height() * k)))
            img = pygame.transform.smoothscale(pic, size) if k < 1 else pygame.transform.scale(pic, size)
            print(f"[dampa] level logo '{name}': using {fname} ({'has its own frame' if framed else 'logo only -> frame is drawn'})")
    else:
        print(f"[dampa] level logo '{name}': NOT found, looked for {LEVEL_LOGO_FILES[name]}")
    if img is None:                                   # placeholder shield
        iw, ih = LOGO_FRAME.w - 40, LOGO_FRAME.h - 40
        img = pygame.Surface((iw, ih), pygame.SRCALPHA)
        pts = [(iw // 2, 4), (iw - 6, ih // 5), (iw - 14, ih * 3 // 4),
               (iw // 2, ih - 4), (14, ih * 3 // 4), (6, ih // 5)]
        pygame.draw.polygon(img, LEVEL_COLORS[name], pts)
        pygame.draw.polygon(img, (20, 20, 30), pts, 5)
        text_center(BIG_FONT, name[0], (20, 20, 30), (iw // 2, ih // 2), img)
    _LOGO_CACHE[name] = img
    _LOGO_FRAMED[name] = framed
    return img


def logo_frame_surface():
    """the frame behind a logo-only picture: your logo_frame.png, or a drawn brown + yellow one"""
    fr = LOGO_FRAME
    k = ("logoframe", fr.size)
    if k in _CARD_CACHE:
        return _CARD_CACHE[k]
    fname = find_file(LOGO_FRAME_FILES)
    surf = None
    if fname:
        pic = load_image(fname)
        if pic is not None:
            surf = pygame.transform.scale(crop_to_content(pic), fr.size)
    if surf is None:
        surf = pygame.Surface(fr.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (96, 48, 18), surf.get_rect(), border_radius=14)            # brown border
        pygame.draw.rect(surf, (236, 170, 40), surf.get_rect().inflate(-14, -14), border_radius=8)   # yellow
        pygame.draw.rect(surf, (255, 214, 90), surf.get_rect().inflate(-14, -14), 2, border_radius=8)  # shine
    _CARD_CACHE[k] = surf
    return surf


def draw_level_logo(mouse):
    """visual only: shows the logo of the hovered level, else the chosen level, else '?'"""
    hov = next((n for n, r in LEVEL_RECTS.items() if r.collidepoint(mouse)), None)
    name = hov or (DIFFICULTY if DIFF_CHOSEN else None)
    fr = LOGO_FRAME
    if name is not None:
        img = level_logo(name)
        if _LOGO_FRAMED.get(name):                       # the picture already has its own frame
            WIN.blit(img, img.get_rect(center=fr.center))
            return
    WIN.blit(logo_frame_surface(), fr.topleft)
    if name is None:
        text_center(HUGE_FONT, "?", (86, 40, 14), fr.center)
    else:
        WIN.blit(img, img.get_rect(center=fr.center))


def vs_card_surface(title, sub):
    key = ("vs", title)
    if key in _CARD_CACHE:
        return _CARD_CACHE[key]
    fname = find_file(VS_FILES.get(title, []))
    if fname:
        pic = load_image(fname)
        if pic is not None:
            pic = crop_to_content(pic)
            k = min(VS_W / pic.get_width(), VS_H / pic.get_height())      # keep the picture's shape
            size = (int(pic.get_width() * k), int(pic.get_height() * k))
            pic = pygame.transform.scale(pic, size)                       # hard pixels
            base = pygame.Surface((VS_W, VS_H), pygame.SRCALPHA)
            base.blit(pic, pic.get_rect(center=(VS_W // 2, VS_H // 2)))
            print(f"[dampa] card '{title}': using {fname}")
            _CARD_CACHE[key] = base
            return base
    print(f"[dampa] card '{title}': picture NOT found, PNG files here: "
          f"{[f for f in os.listdir('.') if f.lower().endswith('.png')]}")
    base = pixel_box(VS_W, VS_H, (86, 36, 30), (250, 222, 206), (255, 240, 230), (214, 160, 148)).copy()
    text_center(MID_FONT, title, BROWN, (VS_W // 2, 62), base)
    icon = person_icon()
    cy = 215
    base.blit(icon, icon.get_rect(center=(VS_W // 2 - 125, cy)))
    base.blit(icon, icon.get_rect(center=(VS_W // 2 + 125, cy)))
    text_center(BIG_FONT, "VS", BROWN, (VS_W // 2, cy - 8), base)
    _CARD_CACHE[key] = base
    return base


def draw_vs_select(mouse):
    """SCREEN 1: PLAYER VS PLAYER or PLAYER VS BOT"""
    WIN.blit(BG_BLUR, (0, 0))
    AMBIENT.draw(WIN)
    button(MODE_HEADER, "PICK A MODE", False, BIG_FONT, key="pickheader")   # gold sign like the reference

    for rect, title, sub in ((VS_PVP, "PLAYER VS PLAYER", "play with a friend"),
                             (VS_PVB, "PLAYER VS BOT", "play against the bot")):
        a = hover_amt(("vs", title), rect.collidepoint(mouse))
        s = 1.0 + 0.07 * a
        base = vs_card_surface(title, sub)
        size = (int(rect.w * s), int(rect.h * s))
        img = pygame.transform.scale(base, size)
        r = img.get_rect(center=rect.center)
        sk = ("vsshadow", title)
        if sk not in _CARD_CACHE:
            _CARD_CACHE[sk] = silhouette(base, 80)                        # shadow follows the card's shape
        WIN.blit(pygame.transform.scale(_CARD_CACHE[sk], size), r.move(8, 10))
        WIN.blit(img, r)

    draw_notice((WIDTH // 2, VS_Y + VS_H + 38))
    button(VS_BACK, "BACK", VS_BACK.collidepoint(mouse), MID_FONT)


def mode_card_surface(key):
    ck = ("mode", key)
    if ck not in _CARD_CACHE:
        title, img = MODE_INFO[key][0], MODE_INFO[key][1]
        base = pygame.Surface((CARD_W, CARD_H), pygame.SRCALPHA)
        pygame.draw.rect(base, (139, 90, 43), base.get_rect(), border_radius=20)
        pygame.draw.rect(base, BROWN, base.get_rect(), 3, border_radius=20)
        panel(pygame.Rect(8, 8, CARD_W - 16, CARD_H - 16), BEIGE, base, 14)
        base.blit(img, ((CARD_W - CARD_IMG_W) // 2, 18))
        text_center(MID_FONT, title, BROWN, (CARD_W // 2, 395), base)
        _CARD_CACHE[ck] = base
    return _CARD_CACHE[ck]


def draw_mode_select(mouse):
    """SCREEN 2: pick Karera or Pogs (click a card = description changes), pick the level, press START"""
    WIN.blit(BG_BLUR, (0, 0))
    AMBIENT.draw(WIN)

    # ---- the two cards: selected one is bigger, the one under the mouse grows too
    for key, rect in (("karera", CARD1_RECT), ("pogs", CARD2_RECT)):
        hov = rect.collidepoint(mouse) or (MODE1_START if key == "karera" else MODE2_START).collidepoint(mouse)
        a = hover_amt(("mode", key), hov)
        sa = hover_amt(("modesel", key), SELECTED_MODE == key)
        s = 1.0 + 0.05 * sa + 0.05 * a
        base = mode_card_surface(key)
        img = pygame.transform.scale(base, (int(CARD_W * s), int(CARD_H * s)))
        r = img.get_rect(center=rect.center)
        panel(r.move(8, 10), (0, 0, 0, 70), radius=20)
        WIN.blit(img, r)
        if SELECTED_MODE == key:
            pygame.draw.rect(WIN, WHITE, r.inflate(6, 6), 3, border_radius=22)
        sr = pygame.Rect(0, 0, int(MODE_START_W * s), int(MODE_START_H * s))
        sr.center = (r.centerx, r.centery + int(START_DY * s))
        button(sr, "START", sr.collidepoint(mouse), MID_FONT, key=("start", key))

    # ---- info panel (changes with the selected card)
    panel(INFO_PANEL, (0, 0, 0, 120), radius=18)
    title, _, sub, desc = MODE_INFO[SELECTED_MODE]
    t_img = TITLE_FONT.render(title, True, GOLD)
    WIN.blit(TITLE_FONT.render(title, True, (0, 0, 0)), (INFO_X + 3, INFO_PANEL.y + 23))
    WIN.blit(t_img, (INFO_X, INFO_PANEL.y + 20))
    y = INFO_PANEL.y + 82
    WIN.blit(DESC_FONT.render(sub, True, GOLD), (INFO_X, y))
    y += 28
    if SELECTED_MODE not in _WRAP:
        _WRAP[SELECTED_MODE] = wrap_text(DESC_FONT, desc, INFO_PANEL.w - 50)
    for line in _WRAP[SELECTED_MODE]:
        WIN.blit(DESC_FONT.render(line, True, WHITE), (INFO_X, y))
        y += 22

    # ---- level (the player must choose one)
    if NOTICE[1] > 0:
        draw_notice((INFO_X + 170, 385), (255, 110, 90))
    else:
        text_center(MID_FONT, "LEVEL DIFICULTY", GOLD, (INFO_X + 135, 385), shadow=True)
    for name, r in LEVEL_RECTS.items():
        selected = DIFF_CHOSEN and DIFFICULTY == name
        button(r, name, r.collidepoint(mouse) or selected, MID_FONT)

    draw_level_logo(mouse)                      # visual only: the logo of the level
    button(MODE_BACK, "BACK", MODE_BACK.collidepoint(mouse), MID_FONT)


# =====================================================================
#  IN-GAME MENU (hamburger button + pause screen)
# =====================================================================
def draw_hamburger(mouse):
    a = hover_amt(("hamburger",), PAUSE_BTN.collidepoint(mouse))
    r = PAUSE_BTN.inflate(int(3 * a) * 2, int(2 * a) * 2)
    pic = ui_img("hamburger", r.size)
    if pic is not None:
        WIN.blit(pic, r.topleft)                                      # YOUR hamburger picture
        return
    s = btn_surface(r.w, r.h, "gold")                                 # gold button with dark bars
    WIN.blit(s, s.get_rect(center=r.center))
    for i in range(3):
        pygame.draw.rect(WIN, (30, 15, 5), (r.x + r.w // 5, r.y + r.h // 4 + i * (r.h // 5), r.w * 3 // 5, 5))


def draw_pause(mouse, view, snap):
    """snap = BLURRED copy of the game that was being played"""
    if view == "score":
        draw_score(mouse, snap)
    elif view == "exit":
        draw_exit(mouse, snap)
    else:
        backdrop(snap)
        pic = ui_img("pause_panel", PAUSE_PANEL.size)
        if pic is not None:
            WIN.blit(pic, PAUSE_PANEL.topleft)                        # YOUR pause panel picture
        else:
            paper_box(PAUSE_PANEL)
        for name, r in PAUSE_BUTTONS.items():
            button(r, name, r.collidepoint(mouse), MID_FONT)


def scroll_scores(dy):
    global scroll_offset
    scroll_offset -= dy * SCROLL_SPEED
    max_scroll = max(0, len(SCORES[:MAX_ROWS]) * ROW_H - (SCORE_TABLE.height - HEAD_ROW_H))
    scroll_offset = max(0, min(scroll_offset, max_scroll))


# =====================================================================
#  MAIN LOOP
# =====================================================================
# =====================================================================
#  OPENING INTRO  (the first thing you see when the game starts)
#  black screen -> the logo rises from the bottom-left corner, grows while it flies to the middle,
#  rests for a moment, then speeds off to the right -> menu + the home page music starts.
#  Click or press any key to skip it.
#  All the numbers below were measured from the reference video (1280x720) and are scaled to the window.
# =====================================================================
INTRO_LOGO_FILES = ["python_logo.png", "pythonlogo.png", "Python_Logo.png", "python-logo.png",
                    "PythonLogo.png", "python.png", "logo_python.png"]   # YOUR logo picture: first one found is used
                                                                          # (not found -> the logo built into this file)
INTRO_PRE = 0.4          # black screen before the logo appears
INTRO_RISE = 0.9         # logo flies from the line to the middle
INTRO_HOLD = 0.7         # logo rests in the middle
INTRO_SLIDE = 0.67       # logo speeds off to the right
INTRO_POST = 0.25        # black screen at the end, then the menu fades in
T_INTRO_SLIDE = INTRO_PRE + INTRO_RISE + INTRO_HOLD
INTRO_TOTAL = T_INTRO_SLIDE + INTRO_SLIDE + INTRO_POST

# (seconds, value) keyframes, linearly interpolated.  P = 0..1 progress of the diagonal flight.
_INTRO_RISE_P = [(0, 0), (0.03, .033), (0.10, .094), (0.17, .223), (0.20, .287), (0.23, .357), (0.27, .435),
                 (0.30, .514), (0.33, .582), (0.37, .644), (0.40, .703), (0.47, .773), (0.50, .816),
                 (0.57, .895), (0.60, .919), (0.63, .94), (0.70, .964), (0.77, .988), (0.90, 1.0)]
_INTRO_SLIDE_X = [(0, 641), (0.03, 676), (0.07, 694), (0.10, 718), (0.17, 763), (0.20, 803), (0.27, 936),
                  (0.33, 1077), (0.40, 1217), (0.53, 1333), (0.67, 1400)]

_INTRO_LOGO_B64 = """
iVBORw0KGgoAAAANSUhEUgAAAM0AAADLCAIAAABCh4AjAABAnUlEQVR42u19eZAc13nf73vdPdfeFxaLBUAssQBIQhAJggTFyzqigzosm5ZSVt
nOZcVl2WU5Fcepcsop2VX+I+WUq+yU4yhyOXES21JZVBzLjEjLoik6pChKpEiAIHEDxLVYYBd7z+5c3e/LH6+n501f07M7C+yA28VaLmZme7r7
fe/33b+PcHsdBABg9TsRM4d8hoiIwIKIIIRlWdIwLcsSQuRyuVTfaDqdts1cJpOxurak0+mKyBiGwdqfV3+pOI5TWVlaWVkxiouVSkUW52dmZo
yVeSmltG3btp1yQUpJzAAYjn6FUZd3Wx7mbXY/rIlCdRVTIILIAIDIIZfj4X3m4GCla6/o6pId3chmDcsS6bRhWI5pLgqTiCSbAMpGCoDDhidh
ktmTD0HEzAI2AIsrAEzYwrZNOJVKRZbKlVIJK0tYXua5S5iexuRrWFpiJw/HAYrMIJS9a06yczblbAMgmSZbHk4YhiFS2XQ6bfYNj46ODuzY09
3dvdi5HcCkuQPAUioLgImklEQGMwshABDIO5UHYN7v3is1gFQoyWRZlslkWRYyWQAp7mfm3uKgYRg78rvn5ubmL526ePGiM3+tWCjAeZfAGeg2
RGgiWNuQyWDsvZ2jo/bQ3T09PXPduwzDsMkCIEkAcFgJBsAMJTdEYAYxAEiACJBgBik8kwAAkfTJMgCwOjFLAMKxichgVCqVzMyJlbk5nHoZEx
NYOA0pIefUt/j06SaebUhMM63+/v7uux/Zu3fvTOeIaZrT5lZmXjQMIYS+XDVM8n5Rq6t+kvC/24qrIyIwW5Y1NDTEg4Ojo5mVlZX8kW+fO3uW
5hdZOjoYb+LZRrH0q0cOROi/q3ffvoU9H96yZctCdosQokAZAAxykalmxCkAExpKrf0Iop0EADLgyY0HnFXsFNIBkLbnCwsLxvkfOceP4/J3wA
xnqaXXdusPo913BhFRrmf3vn37P/ZTY2NjpYHdlmUVjCwAm0wNmVjTjFQ7E2lItibo4sDVaa+oLw2cn5iJKC3sVDZ7V3+ud/fu7tLE/NKSqBQY
3P7asl3xTEcgEyDktuf27Fm59x9v2bp1NrudiGxKAWAwiCCUpUU1S2sjqfja9RAAWI4NIFuaX7x2Df/wFVy7hpVTAAjyNrDPjHbbFZ4qMXIdHd
sf+8ihQ4cKW+42TXPZ6AQglc1OFMCYDbNSuvZ0f2cQKR2aJSfb3f3g9sy1cpmvn2WWArfD0Y7+pgkAYx/b+b73XR/7oGVZeaOrLa0Zn7JW/xQE
IG2XSqVS9tU/Lxw5gplXASbYbY1q7WefQZh9W7bs/MjnhoeHp9PDRFQWaRexdKjY+EIWZrGpVyyWlmXd2+vMEOHKMSmlQeB2Vp7tImeCIAACBM
Y+suujP33+jn80mR4pGtmySAHSxWVqH3gWwodnBFK+MSTbwrTJmEpvLW3d32GI8rzgwgRAOqJRWymjNtP+6Uxm5+HDg4ODdRF5akPtzwwhavHh
qu9cU6AAgFQ6/d73vlfs3QvDQCAPsYlnrbQfa+EHa/iOh94/de/PTKeGV0TWITPxXqKNZ9uIEHxSCVPDYEiAHTIdMqbTWytDd2HqMlYs2LMb8l
5uLzwzRkbuuusu0zTJZ9m0bwC9/spZS9Lr76a6ux9+7DF0d2/aZzcD1/jRL/CdD0xaW8sirbY/SAUzCSJmwziABKqfvFUhjMB7Kpzhh26uqNwq
AJAAs20YDolidnhFDOGdl8ECqLSdDm0bPEul0yPj49DLtphbEcdfT5Rq/sLcHKgH2Cqcy2wYRmZ8vKOrCyTqq5428aw1+4AAwBwe3H9o4e5PlV
LdRSPtrQExEaiWOwpfV9bsoYRgs3b8pdXIpXudwgU3V8gIECXKymxvp0WFqTKKlwhGe1lpGx3P3KCRaR44cMCyrDrbRasMC49FNWMbrYuQJfwK
D8B8/2kIp46xsTEMDACi7WJpG1/OwAA6RxayW5bNzrzR4e54IqicJYWuqHT/Y6eKEABAqrpMLaFY8703FKNQ0U8gfMSAdE0CZmbmCnFF4GLPPo
w/BtEF5DblbB2Ojo5UKpXIIvGMtlVrsVvmGYSLKWmGGhHhjjtS6XTbJQzbRM66e8hKSQgJQSyJq3BVt4Tk4hwRyACEwTBAlpSW4wgQMZgEk7iV
cRC9TCMxXnqiNmf0oG8Hj9wDa8umnK3DYZpu2X4MGOgmGjOYpZRSSl/HQDvhWZiSNdLpsbExZbW1kZy1Sd12KmuTqQJLTAIAsagDMmWTMQbLi7
Y9OvH61NSUuXitXC7DSuVyOWdkz+Dg4Om+cQBF0eGdgUmuCZzW40+YWYtrsAaBFRggwaP7kDuF+XcAbpcqlTaRM83nCsElKV2jnnlpaan02mvz
Z17CygrsRTCDxAwROs5f3bIFH+hODw1BR7iNDwp6TwoRM+dyOXR00AIxO5t41koZY2HYICbB1T4ib+cDIBIs+c7S5JUrVzr/4cuVpSVRmmBmft
vWigbmBKbf2Hvw4KUH/plpmjNmXxvpHbd7SgBCLGS3o3+PnHwRLIDypn3W6j0dYWMxM5jn5ubKL700c/UqSiXJkgGk10EwwwEwNzf3WS+/uHDx
YnsZ0T5ta5omuru7WxCX2ZQz/QqrITL3cTOBwUzKvyQItlAmp9D92l/i6ovkXAVfU96oZ/szMyCJGPYl5E/jpf+55+qLlrRTG1bvsFMLAeobjA
FGUezCuleOaKO0oWjHDR0s1uClpYunTsG2482rF9umpiYmJlT8c+Peb+DaWA8NGsZmHn0dDskiVAsdBSB2rszjrdfFyjtwJqKIW+piIsULS288
a5UKOWlvRAuBCEwgw40Iuj61dLNNkszChJWWUrZRS0Sbd9MwqwwG0wPA6dRAGnM8/PzpVLpFlyt918SPAv2e6psm5TV3ze1ZuugTO3aCDESgEh
LCUcJ6hHyynH9f2sLWab8dIdcvtna8DlHHuf01MecXWuUAEEmibaraLwdugOpmWINJY5CCNNsaUwnCVYFCmWbsNU0sVN41l7H7cDjMm+lMDjE7
Nc9HJAw1/Ynk5kO6uxdIWu9PJX48v3FWHoY2wFwAAAAAElFTkSuQmCC
"""
_INTRO_LOGO = []


def _keys(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return keys[-1][1]


def draw_intro(t):
    if not _INTRO_LOGO:
        img = load_first(INTRO_LOGO_FILES)
        if img is None:
            img = pygame.image.load(io.BytesIO(base64.b64decode("".join(_INTRO_LOGO_B64.split())))).convert()
        _INTRO_LOGO.append(img)
    logo = _INTRO_LOGO[0]
    sx, sy = WIDTH / 1280, HEIGHT / 720             # video space -> window space
    WIN.fill((0, 0, 0))
    if t < INTRO_PRE:
        return
    lt = t - INTRO_PRE
    if lt < INTRO_RISE:                                  # fly in from the bottom-left corner
        P = _keys(_INTRO_RISE_P, lt)
        cx, cy, size = 59 + 582 * P, 702 - 328 * P, 58 + 144 * P
    elif t < T_INTRO_SLIDE:                              # rest
        cx, cy, size = 641, 374, 202
    else:                                                # speed off to the right
        cx, cy, size = _keys(_INTRO_SLIDE_X, t - T_INTRO_SLIDE), 374, 202
    w = max(2, int(size * sy))
    h = max(2, int(size * sy * logo.get_height() / logo.get_width()))
    img = pygame.transform.smoothscale(logo, (w, h))
    WIN.blit(img, (int(cx * sx - w / 2), int(cy * sy - h / 2)))


def main():
    global scroll_offset, SELECTED_MODE, DIFF_CHOSEN
    screen = "intro"         # "intro" | "menu" | "score" | "exit" | "gamemodes" | "game"
    intro_t = 0.0
    prev_screen = screen
    game = None
    paused = False
    pause_view = "menu"      # "menu" | "score" | "exit"
    snapshot = None
    run = True
    fade = 1.0               # quick fade-in whenever the screen changes
    fade_surf = pygame.Surface((WIDTH, HEIGHT))
    fade_surf.fill((0, 0, 0))

    while run:
        dt = min(CLOCK.tick(60) / 1000.0, 0.05)
        FX_DT[0] = dt
        if NOTICE[1] > 0:
            NOTICE[1] = max(0.0, NOTICE[1] - dt)
        mouse = pygame.mouse.get_pos()
        AMBIENT.update(dt)
        update_confetti(dt)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                continue

            if screen == "intro":                         # any click / key skips the opening
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    intro_t = INTRO_TOTAL
                continue

# ---------------- IN GAME ----------------
            if screen == "game":
                if not paused:
                    open_pause = (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE) or \
                                 (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                                  and PAUSE_BTN.collidepoint(event.pos))
                    if open_pause:
                        play("click")
                        paused = True
                        pause_view = "menu"
                        snapshot = blur_surface(WIN)          # blurred copy of the game you were playing
                    elif game.handle_event(event) == "menu":
                        screen = "menu"
                        play_bgm("menu")
                    continue

                # paused: CONTINUE / SCORE / MENU / EXIT
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if pause_view == "menu":
                        paused = False
                    else:
                        pause_view = "menu"
                elif pause_view == "score" and event.type == pygame.MOUSEWHEEL:
                    scroll_scores(event.y)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos
                    if pause_view == "menu":
                        for name, r in PAUSE_BUTTONS.items():
                            if r.collidepoint(pos):
                                play("click")
                                if name == "CONTINUE":
                                    paused = False
                                elif name == "SCORE":
                                    scroll_offset = 0
                                    pause_view = "score"
                                elif name == "MENU":
                                    paused = False
                                    screen = "menu"
                                    play_bgm("menu")
                                elif name == "EXIT":
                                    pause_view = "exit"
                                break
                    elif pause_view == "score":
                        if SCORE_BACK.collidepoint(pos):
                            play("click")
                            pause_view = "menu"
                    elif pause_view == "exit":
                        if EXIT_YES.collidepoint(pos):
                            play("click")
                            run = False
                        elif EXIT_NO.collidepoint(pos):
                            play("click")
                            pause_view = "menu"
                continue

            # ---------------- OTHER SCREENS ----------------
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if screen == "menu":
                    screen = "exit"
                elif screen == "botmodes":
                    screen = "gamemodes"          # one step back
                else:
                    screen = "menu"

            if screen == "score" and event.type == pygame.MOUSEWHEEL:
                scroll_scores(event.y)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if screen == "menu":
                    if MENU_BUTTONS["GAMEMODES"].collidepoint(pos):
                        play("click")
                        screen = "gamemodes"
                    elif MENU_BUTTONS["SCORE"].collidepoint(pos):
                        play("click")
                        scroll_offset = 0
                        screen = "score"
                    elif MENU_BUTTONS["EXIT"].collidepoint(pos):
                        play("click")
                        screen = "exit"
                elif screen == "gamemodes":
                    if VS_PVP.collidepoint(pos):
                        play("miss")
                        set_notice("PLAYER VS PLAYER: COMING SOON!")
                    elif VS_PVB.collidepoint(pos):
                        play("click")
                        DIFF_CHOSEN = False                    # pick the level again every time
                        NOTICE[1] = 0.0
                        screen = "botmodes"
                    elif VS_BACK.collidepoint(pos):
                        play("click")
                        screen = "menu"
                elif screen == "botmodes":
                    handled = False
                    for key, crect, srect in (("karera", CARD1_RECT, MODE1_START),
                                              ("pogs", CARD2_RECT, MODE2_START)):
                        if srect.inflate(30, 30).collidepoint(pos):          # START button
                            SELECTED_MODE = key
                            handled = True
                            if DIFF_CHOSEN:
                                play("click")
                                game = Game() if key == "karera" else PogsGame(add_result)
                                paused = False
                                screen = "game"
                                if key == "karera":
                                    play_bgm("karera")
                                else:
                                    play_bgm("pogs")
                            else:
                                play("miss")
                                set_notice("PICK A LEVEL FIRST!")
                            break
                        if crect.inflate(20, 20).collidepoint(pos):          # card = show its description
                            play("click")
                            SELECTED_MODE = key
                            handled = True
                            break
                    if not handled:
                        for name, r in LEVEL_RECTS.items():
                            if r.collidepoint(pos):
                                play("click")
                                set_difficulty(name)
                                DIFF_CHOSEN = True
                                NOTICE[1] = 0.0
                                handled = True
                                break
                    if not handled and MODE_BACK.collidepoint(pos):
                        play("click")
                        screen = "gamemodes"
                elif screen == "score":
                    if SCORE_BACK.collidepoint(pos):
                        play("click")
                        screen = "menu"
                elif screen == "exit":
                    if EXIT_YES.collidepoint(pos):
                        play("click")
                        run = False
                    elif EXIT_NO.collidepoint(pos):
                        play("click")
                        screen = "menu"

        if screen == "intro":
            intro_t += dt
            if intro_t >= INTRO_TOTAL:
                screen = "menu"
                play_bgm("menu")                          # home page music starts only after the intro

        if screen != prev_screen:
            fade = 1.0
            CONFETTI.clear()
            NOTICE[1] = 0.0
            prev_screen = screen

        if screen == "intro":
            draw_intro(intro_t)
        elif screen == "menu":
            draw_menu(mouse)
        elif screen == "score":
            draw_score(mouse)
        elif screen == "exit":
            draw_exit(mouse)
        elif screen == "gamemodes":
            draw_vs_select(mouse)
        elif screen == "botmodes":
            draw_mode_select(mouse)
        else:
            if paused:
                draw_pause(mouse, pause_view, snapshot)       # game is frozen: no update()
            else:
                game.update(dt)
                game.draw(mouse)
                if game.phase != "end":
                    draw_hamburger(mouse)

        draw_confetti(WIN)

        if fade > 0:
            fade_surf.set_alpha(int(255 * fade))
            WIN.blit(fade_surf, (0, 0))
            fade = max(0.0, fade - dt * 4.5)

        pygame.display.update()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()