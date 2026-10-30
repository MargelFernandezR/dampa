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
            pygame.mixer.music.set_volume(BGM_VOLUME)
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
LETTERS = []
_letter_imgs = [load_image(f"DampaLogo_{i}.png") for i in range(1, 6)]
if all(_letter_imgs):
    LETTERS = [pygame.transform.smoothscale(_l, LOGO.get_size()) for _l in _letter_imgs]

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
BANDS = make_bands()          # the whole pile as ONE picture (kept as a fallback)


def _band_ring_image():
    """ONE rubber band on its own (76px wide, transparent)."""
    ring = load_first(BAND_FILES)
    if ring:
        return scaled_to_width(crop_to_content(remove_white_bg(ring)), 76)
    ring = pygame.Surface((64, 26), pygame.SRCALPHA)
    pygame.draw.ellipse(ring, (228, 52, 52), ring.get_rect(), 6)
    pygame.draw.ellipse(ring, (250, 200, 40), ring.get_rect().inflate(-14, -10), 3)
    return ring


def make_band_rings(n=BAND_PILE):
    """The pile, but every ring is its OWN sprite so each one can fly, tumble and bounce
    separately - that is what makes the 'talsik' look real.
    returns [(surface, (dx, dy))] where dx/dy = resting offset from the middle of the pile."""
    ring = _band_ring_image()
    rnd = random.Random(4)
    out = []
    for i in range(max(1, n)):
        r = pygame.transform.rotozoom(ring, rnd.randint(-40, 40) + i * 15, 1.0)
        # bake a thin dark edge under the band so it stays readable on the grey floor
        edged = pygame.Surface((r.get_width() + 3, r.get_height() + 3), pygame.SRCALPHA)
        edged.blit(silhouette(r, 115), (2, 2))
        edged.blit(r, (0, 0))
        r = edged
        out.append((r, (rnd.randint(-10, 10), rnd.randint(-10, 10))))
    mx = sum(o[0] for _, o in out) / len(out)
    my = sum(o[1] for _, o in out) / len(out)
    return [(r, (o[0] - int(round(mx)), o[1] - int(round(my)))) for r, o in out]


def make_soft_shadow(w, h, alpha=150):
    """soft blurred ellipse - a rubber band lying on the floor has no hard shadow edge"""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    steps = max(3, h // 2)
    for i in range(steps, 0, -1):
        k = i / steps
        a = int(alpha * (1 - k) ** 1.1)
        pygame.draw.ellipse(s, (0, 0, 0, a),
                            (int(w * (1 - k) / 2), int(h * (1 - k) / 2),
                             max(2, int(w * k)), max(2, int(h * k))))
    return s


BAND_RINGS = make_band_rings()
BAND_RING_SHADOWS = []
for _ring, _off in BAND_RINGS:
    BAND_RING_SHADOWS.append(
        make_soft_shadow(_ring.get_width(), max(10, int(_ring.get_height() * 0.42)), 105))

# one soft contact shadow for the whole pile (used while it sits still on the floor)
PILE_SHADOW = make_soft_shadow(max(r.get_width() for r, _o in BAND_RINGS) + 8,
                               max(14, int(max(r.get_height() for r, _o in BAND_RINGS) * 0.34)), 75)


def make_puff(radius, color=(226, 219, 204)):
    """soft dust cloud (alpha gradient circle) - the alikabok that flies up on impact"""
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for i in range(radius, 0, -1):
        k = i / radius
        a = int(238 * (1.0 - k) ** 0.65)
        pygame.draw.circle(s, (color[0], color[1], color[2], a), (radius, radius), i)
    return s


DUST_PUFFS = {r: make_puff(r) for r in (9, 14, 20, 27, 34)}
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
MOUSE_MOVED = [False]
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
    if on and cur == 0.0 and MOUSE_MOVED[0]:
        play("hover")
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

# ---------------------------------------------------------------------
#  HAMPAS + TALSIK timing (Dampa Karera)
#  A real slam reads in 5 beats:
#    1) wind-up (hands pull back)  2) accelerate + slam  3) squash on the floor
#    4) damped rebound             5) the pile launches, tumbles, bounces, slides
#  Tweak the numbers here if you want it snappier or heavier.
# ---------------------------------------------------------------------
T_GROW0 = 0.13                       # wind-up starts (hands pull back a little)
T_IMPACT = 0.55                      # the palm hits the floor / the bands
T_SQUASH = 0.07                      # how long the hand stays flattened on contact
T_RECOIL = 0.30                      # springy return to the resting pose
IMPACT_HITSTOP = 0.045               # freeze-frame at contact (this is what gives the hit weight)
STRIKE_MIN, STRIKE_FULL_TIP = 1.20, 300   # weak smash = x1.2 bigger, perfect smash reaches y=300
BAND_TIME = 1.4                      # how long the bands take to fly, bounce and settle
BAND_BOUNCES = [(0.40, 1.00), (0.22, 0.40), (0.14, 0.16), (0.10, 0.06)]   # (airtime, height) per bounce
BAND_HOP_MIN, BAND_HOP_MAX = 18, 74  # how high the pile jumps (weak -> perfect meter)
BAND_STRETCH = 0.40                  # max elastic stretch as the rings leave the hand

BAND_LAND_FRACS = []
_f = 0.0
for _d, _h in BAND_BOUNCES:
    _f += _d
    BAND_LAND_FRACS.append(_f)
BAND_LAND_TIMES = [T_IMPACT + BAND_TIME * f for f in BAND_LAND_FRACS]


def band_hop(u, power):
    """height (px) of the pile above the floor at launch progress u (0..1), plus its peak.
    First jump is the big one, then a few smaller bounces (like a flicked rubber band)."""
    peak = BAND_HOP_MIN + (BAND_HOP_MAX - BAND_HOP_MIN) * power
    if u <= 0.0 or u >= BAND_LAND_FRACS[-1]:
        return 0.0, peak
    acc = 0.0
    for dur, hgt in BAND_BOUNCES:
        if u < acc + dur:
            k = (u - acc) / dur
            return peak * hgt * 4.0 * k * (1.0 - k), peak
        acc += dur
    return 0.0, peak

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
    def __init__(self, pvp=False):
        self.pvp = pvp          # True = Player 1 (Q) vs Player 2 (P), walang bot
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
        self.hitstop = 0.0                                  # freeze-frame on impact
        self.puffs = {"bot": [], "player": []}             # alikabok
        self.crumbs = {"bot": [], "player": []}            # rubber crumbs
        self.ring_fx = {"bot": self._make_ring_fx(), "player": self._make_ring_fx()}
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
        self.hitstop = 0.0
        for key in ("bot", "player"):
            self.puffs[key].clear()
            self.crumbs[key].clear()
        self.ring_fx = {"bot": self._make_ring_fx(), "player": self._make_ring_fx()}
        self.set_phase("meter")                                       # 1) meter first

    # ------------------------------------------------------------ smash effects
    def _make_ring_fx(self):
        """random motion for every ring: it decides how each one scatters, spins and hops"""
        fx = []
        for _ in range(len(BAND_RINGS)):
            fx.append(dict(dx=random.uniform(-1.0, 1.0),                    # sideways scatter direction
                           spread=random.uniform(12, 34),                   # how far it slides sideways
                           spin=random.uniform(150, 430) * random.choice((-1, 1)),
                           hop=random.uniform(0.72, 1.15),                  # this ring jumps a bit higher/lower
                           shrink=random.uniform(0.88, 1.06)))
        return fx

    def _puff(self, key, x, y, n, power, spread=34, speed=1.0, life=(0.30, 0.70)):
        """spawn dust particles (side-local coordinates)"""
        if n <= 0:
            return
        lst = self.puffs[key]
        big = power >= 0.75
        for _ in range(n):
            a = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            sp = random.uniform(22, 95) * speed * (0.7 + 0.7 * power)
            lst.append([x + random.uniform(-spread, spread), y + random.uniform(-5, 9),
                        math.cos(a) * sp, math.sin(a) * sp * 0.5,
                        random.choice((14, 20, 27)) if big else random.choice((9, 14, 20)),
                        0.0, random.uniform(*life)])

    def _crumb(self, key, x, y, n, power):
        """spawn little rubber crumbs that arc up and fall back down"""
        lst = self.crumbs[key]
        for _ in range(n):
            a = random.uniform(-math.pi, 0.0)
            sp = random.uniform(60, 210) * (0.7 + 0.6 * power)
            lst.append([x + random.uniform(-26, 26), y + random.uniform(-4, 6),
                        math.cos(a) * sp, math.sin(a) * sp,
                        random.randint(3, 5), 0.0, random.uniform(0.35, 0.80),
                        random.choice(LASTIKO_COLORS)])

    def _impact_burst(self):
        """the palm lands: alikabok + rubber crumbs on both sides of the screen"""
        for key, side in (("bot", self.bot), ("player", self.player)):
            p = side.power
            _, ground, _, _, _ = self.band_state(side)
            self._puff(key, HALF // 2, ground + 12, 7 + int(9 * p), p, spread=46, speed=1.0)
            self._crumb(key, HALF // 2, ground + 6, 4 + int(8 * p), p)

    def _landing_burst(self, k):
        """the pile touches down again -> a smaller puff of dust"""
        for key, side in (("bot", self.bot), ("player", self.player)):
            p = side.power
            _, ground, _, _, _ = self.band_state(side)
            if k == 0:
                self._puff(key, HALF // 2, ground + 20, 4 + int(5 * p), p * 0.7, spread=34,
                           speed=0.55, life=(0.22, 0.48))
                self._crumb(key, HALF // 2, ground + 8, 2, p * 0.5)
            else:
                self._puff(key, HALF // 2, ground + 18, 2, p * 0.4, spread=22,
                           speed=0.35, life=(0.18, 0.38))

    def _step_fx(self, dt):
        for lst in (self.puffs["bot"], self.puffs["player"]):
            for p in lst:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[2] *= 0.90
                p[3] = p[3] * 0.90 - 26 * dt              # dust floats up then hangs in the air
                p[5] += dt
            lst[:] = [p for p in lst if p[5] < p[6]]
        for lst in (self.crumbs["bot"], self.crumbs["player"]):
            for c in lst:
                c[0] += c[2] * dt
                c[1] += c[3] * dt
                c[3] += 900 * dt
                c[5] += dt
            lst[:] = [c for c in lst if c[5] < c[6] and c[1] < HEIGHT + 20]

    def _draw_fx(self, surf, key):
        for x, y, vx, vy, r, age, life in self.puffs[key]:
            k = clamp(age / life)
            puff = DUST_PUFFS[r]
            puff.set_alpha(int(215 * (1.0 - k) ** 0.9))
            surf.blit(puff, puff.get_rect(center=(int(x), int(y))))
            puff.set_alpha(255)
        for x, y, vx, vy, r, age, life, col in self.crumbs[key]:
            if age > life:
                continue
            pygame.draw.rect(surf, col, (int(x), int(y), r + 1, r))
            pygame.draw.rect(surf, (35, 20, 10), (int(x), int(y), r + 1, r), 1)

    # ------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if self.phase != "meter":
                return None
            if self.pvp:
                if event.key == pygame.K_q and not self.bot.locked:        # PLAYER 1
                    self.bot.lock()
                    play("lock")
                elif event.key == pygame.K_p and not self.player.locked:   # PLAYER 2
                    self.player.lock()
                    play("lock")
            elif event.key == pygame.K_SPACE and not self.player.locked:
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
        if self.hitstop > 0.0:                       # freeze-frame on contact: the hit has weight
            self.hitstop = max(0.0, self.hitstop - dt)
            return
        self.t += dt
        if self.smash_t is not None:
            prev = self.smash_t
            self.smash_t += dt
            if not self.sfx_done and self.smash_t >= T_IMPACT:
                self.sfx_done = True
                play("smash")
                play("twang")
                self.hitstop = IMPACT_HITSTOP
                self._impact_burst()
            for k, t_land in enumerate(BAND_LAND_TIMES):         # puff every time it lands again
                if prev < t_land <= self.smash_t:
                    self._landing_burst(k)
        self._step_fx(dt)

        if self.phase == "meter":
            self.bot.update_meter(dt)
            self.player.update_meter(dt)

            # sa bot mode, ang bot ang kusang humihinto malapit sa target nito
            if not self.pvp:
                b = self.bot
                if not b.locked and self.t >= self.bot_wait:
                    if abs(b.pos - self.bot_target) < b.speed * dt * 1.5 + 0.02 or self.t > 3.5:
                        b.lock()
            if self.t > METER_TIMEOUT:                   # time is up: auto stop
                if self.pvp:
                    self.bot.lock()                      # P1 din
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
            if self.t >= T_IMPACT + BAND_TIME + 0.45:
                self.finish_turn()

        elif self.phase == "result":
            if self.t >= RESULT_TIME:
                if self.round < ROUNDS:
                    self.round += 1
                    self.start_round()
                else:
                    if not self.saved:
                        self.final = self.final_result()
                        if self.pvp:                     # P1 = left/bot slot, P2 = right/player slot
                            res = ("p1" if self.bot_wins > self.player_wins
                                   else "p2" if self.player_wins > self.bot_wins else "ptie")
                            add_result(self.player_wins, self.bot_wins, "DAMPA KARERA", result=res)
                        else:
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
            self.round_msg = "PLAYER 2 WINS!" if self.pvp else "YOU WIN THE ROUND!"
            play("round")
            confetti_burst(HALF + HALF // 2, 330, 45)
        elif winner == "bot":
            self.bot_wins += 1
            self.round_msg = "PLAYER 1 WINS!" if self.pvp else "BOT WINS THE ROUND!"
            if self.pvp:                                   # parehong tao, parehong may confetti
                play("round")
                confetti_burst(HALF // 2, 330, 45)
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

    def hand_pose(self, side, st=None):
        """returns (y_offset, scale_x, scale_y, x_jitter). The whole hands+arms picture is
        scaled up from the bottom edge of the screen, so the fingertips travel up while the
        forearms stay planted. The 5 beats: wind-up -> slam -> squash -> rebound -> rest."""
        st = self.smash_t if st is None else st
        if st is None:
            jitter = 0
            bob = 0
            if self.phase == "timer":                 # tension: tiny shake while waiting
                jitter = random.uniform(-2.5, 2.5)
            elif self.phase in ("meter", "lock"):     # gentle idle bob so the hands feel alive
                bob = 3 * math.sin(self.t * 6)
            return bob, 1.0, 1.0, jitter
        peak = self.peak_scale(side)
        if st < T_GROW0:                              # 1) wind-up: hands pull back a little
            k = ease_out(clamp(st / T_GROW0))
            return 16.0 * k, 1.0 - 0.045 * k, 1.0 + 0.025 * k, 0
        if st < T_IMPACT:                             # 2) the slam: accelerating (ease-in)
            k = clamp((st - T_GROW0) / (T_IMPACT - T_GROW0)) ** 2.1
            scx = lerp(0.955, peak * 1.02, k)
            scy = lerp(1.025, peak * 0.985, k)
            return lerp(16.0, 0.0, k), scx, scy, 0
        if st < T_IMPACT + T_SQUASH:                  # 3) squash: the palm flattens on the floor
            k = (st - T_IMPACT) / T_SQUASH
            sq = math.sin(k * math.pi) * 0.06
            return 5.0 * (1.0 - k), peak * (1.0 + sq), peak * (1.0 - sq * 1.7), 0
        if st < T_IMPACT + T_SQUASH + T_RECOIL:       # 4) damped spring back to rest
            k = clamp((st - T_IMPACT - T_SQUASH) / T_RECOIL)
            wob = math.exp(-4.0 * k) * math.cos(k * math.pi * 2.2)
            sc = 1.0 + (peak - 1.0) * wob
            return 0, sc, sc, 0
        return 0, 1.0, 1.0, 0

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
        elif self.phase == "meter" and not side.locked:
            if self.pvp:
                hint = "[ P ]  stop on the white" if is_player else "[ Q ]  stop on the white"
            elif is_player:
                hint = "[ SPACE ]  stop on the white"
            else:
                hint = ""
            if hint:
                col = GOLD if int(self.t * 3) % 2 == 0 else TEXT_COLOR
                text_center(SMALL_FONT, hint, col, (cx, METER_Y + 30), surf, shadow=True)

    def band_state(self, side):
        """where the pile is right now: (distance, ground y, launch progress u, hop height, hop 0..1)"""
        st = self.smash_t
        D = self.travel(side)
        scroll = max(0.0, D - FOLLOW_AT)
        ground = BAND_START_Y - D + scroll                  # y of the pile while it sits on the floor
        u = 0.0 if st is None or st < T_IMPACT else clamp((st - T_IMPACT) / BAND_TIME)
        h, peak = band_hop(u, side.power)
        return D, ground, u, h, (h / peak if peak > 1.0 else 0.0)

    def draw_impact_ring(self, surf, cx, power, k):
        """white flash + expanding dust ring on the floor where the palm lands"""
        cy = BAND_START_Y + 14
        if k < 0.22:                                        # the flash of the hit
            a = int(150 * (1.0 - k / 0.22))
            flash = pygame.Surface((126, 48), pygame.SRCALPHA)
            pygame.draw.ellipse(flash, (255, 252, 232, a), flash.get_rect())
            surf.blit(flash, flash.get_rect(center=(cx, cy - 4)))
        rw = int(26 + (115 + 65 * power) * ease_out(k))
        rh = int(rw * 0.38)
        ring = pygame.Surface((rw * 2 + 8, rh * 2 + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(ring, (255, 246, 214, int(175 * (1.0 - k) ** 1.5)),
                            (4, 4, rw * 2, rh * 2), max(2, int(7 * (1.0 - k) + 1)))
        surf.blit(ring, ring.get_rect(center=(cx, cy)))

    def draw_hands(self, surf, side, cx):
        """the palms: scaled from the bottom edge, with the slam squash and a motion smear"""
        off, scx, scy, jx = self.hand_pose(side)
        hw = max(2, int(HANDS_TOP_IMG.get_width() * scx))
        hh = max(2, int(HANDS_TOP_IMG.get_height() * scy))
        top = HANDS_TOP_IMG if (hw, hh) == HANDS_TOP_IMG.get_size() else \
            pygame.transform.smoothscale(HANDS_TOP_IMG, (hw, hh))
        shad = HANDS_TOP_SHADOW if (hw, hh) == HANDS_TOP_SHADOW.get_size() else \
            pygame.transform.smoothscale(HANDS_TOP_SHADOW, (hw, hh))
        y = HANDS_TOP + HANDS_H - HANDS_H * scy + off
        wrist_y = int(y + hh - 1)
        arm_h = max(int(HANDS_ARMS_IMG.get_height() * scy), HEIGHT + 8 - wrist_y)
        arms = HANDS_ARMS_IMG if (hw, arm_h) == HANDS_ARMS_IMG.get_size() else \
            pygame.transform.smoothscale(HANDS_ARMS_IMG, (hw, arm_h))
        arm_shad = HANDS_ARMS_SHADOW if (hw, arm_h) == HANDS_ARMS_SHADOW.get_size() else \
            pygame.transform.smoothscale(HANDS_ARMS_SHADOW, (hw, arm_h))
        hx = int(cx + jx - hw // 2)

        surf.blit(arm_shad, (hx + 14, wrist_y + 10))         # forearm shadow
        surf.blit(shad, (hx + 14, int(y) + 10))              # hand shadow

        # motion smear while the hands are still rushing forward (2 ghost frames)
        st = self.smash_t
        if st is not None and T_GROW0 <= st < T_IMPACT:
            for back, a in ((0.022, 80), (0.046, 45)):
                o2, _, y2, _ = self.hand_pose(side, st - back)
                hh2 = max(2, int(HANDS_TOP_IMG.get_height() * y2))
                gh = HANDS_TOP_IMG if hh2 == HANDS_TOP_IMG.get_height() else \
                    pygame.transform.smoothscale(HANDS_TOP_IMG, (hw, hh2))
                gh = gh.copy()
                gh.set_alpha(a)
                surf.blit(gh, (hx, int(HANDS_TOP + HANDS_H - HANDS_H * y2 + o2)))

        surf.blit(arms, (hx, wrist_y))
        surf.blit(top, (hx, int(y)))

    def draw_bands(self, surf, side, cx, is_player):
        """the pile: every ring scatters, tumbles, stretches and bounces on its own"""
        D, ground, u, hop, norm = self.band_state(side)
        persp = 1.0 - 0.16 * clamp(D / FINISH_DIST)          # lumiit habang lumalayo (depth)
        st = self.smash_t

        # elastic deformation: pressed flat under the palm, stretched as it leaves the hand
        h2, _ = band_hop(min(1.0, u + 0.012), side.power)
        speed = abs(h2 - hop) / (0.012 * BAND_TIME)          # px per second
        stretch = clamp(speed / 620.0) * BAND_STRETCH
        press = 0.0
        if st is not None and T_IMPACT <= st < T_IMPACT + 0.06:
            press = 1.0 - (st - T_IMPACT) / 0.06
        sx = (1.0 + 0.40 * press) * (1.0 - 0.40 * stretch)
        sy = (1.0 - 0.45 * press) * (1.0 + stretch)

        ue = clamp(u / BAND_LAND_FRACS[-1]) if BAND_LAND_FRACS else 1.0
        fx = self.ring_fx["player" if is_player else "bot"]

        items = []
        for i, (ring, (ox, oy)) in enumerate(BAND_RINGS):
            f = fx[i % len(fx)]
            img = ring
            w = int(img.get_width() * persp * sx)
            h = int(img.get_height() * persp * sy)
            if (w, h) != img.get_size():
                img = pygame.transform.smoothscale(img, (max(4, w), max(4, h)))
            ang = f["spin"] * ease_out(ue)                   # tumbling in the air
            if abs(ang) > 1.0:
                img = pygame.transform.rotate(img, ang)

            # sideways scatter: they slide apart once and STAY apart (a flick pushes them out)
            drift = ease_out(clamp(u / 0.40))
            rx = cx + ox + f["dx"] * f["spread"] * drift
            ry = ground + oy - hop * f["hop"]                # every ring jumps a little differently
            gy = ground + oy

            sh_scale = persp * (1.0 - 0.45 * norm) * f["shrink"]
            base = BAND_RING_SHADOWS[i]
            sw, shh = int(base.get_width() * sh_scale), int(base.get_height() * sh_scale)
            sh = base if (sw, shh) == base.get_size() else \
                pygame.transform.smoothscale(base, (max(3, sw), max(2, shh)))
            items.append((ry, gy, img, sh, int(rx)))

        # shadows stay on the floor and shrink while the ring is in the air
        if norm <= 0.02:                                    # resting: one soft contact shadow
            ps = PILE_SHADOW if abs(persp - 1.0) < 0.01 else pygame.transform.smoothscale(
                PILE_SHADOW, (max(6, int(PILE_SHADOW.get_width() * persp)),
                              max(4, int(PILE_SHADOW.get_height() * persp))))
            surf.blit(ps, ps.get_rect(center=(cx + 4, ground + 22)))
        else:
            for ry, gy, img, sh, rx in items:
                sh.set_alpha(int(115 * (1.0 - 0.55 * norm)))
                surf.blit(sh, sh.get_rect(center=(rx + 5, gy + 5)))
                sh.set_alpha(255)

        # the rings themselves, far ones first so the overlaps look right
        for ry, gy, img, sh, rx in sorted(items, key=lambda it: it[0]):
            if stretch > 0.10:                               # motion smear while it is fast
                ghost = img.copy()
                ghost.set_alpha(int(85 * stretch))
                surf.blit(ghost, ghost.get_rect(center=(rx, int(ry + 26 * stretch))))
            surf.blit(img, img.get_rect(center=(rx, int(ry))))

    def draw_side(self, side, surf, is_player):
        cx = HALF // 2
        D = self.band_state(side)[0]
        scroll = max(0.0, D - FOLLOW_AT)                         # floor moves down as the bands go far
        st = self.smash_t
        moving = st is not None and T_IMPACT <= st < T_IMPACT + BAND_TIME

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

        # progress bar towards the finish line
        bar = pygame.Rect(HALF - 26 if is_player else 14, 110, 12, 440)
        pygame.draw.rect(surf, (20, 20, 20), bar.inflate(4, 4), border_radius=8)
        fill = int(bar.height * clamp(D / FINISH_DIST))
        pygame.draw.rect(surf, (255, 220, 90), (bar.x, bar.bottom - fill, bar.width, fill), border_radius=6)

        if st is not None and st > T_IMPACT + BAND_TIME and side.base + side.dist >= FINISH_DIST:
            text_center(BIG_FONT, "FINISHED!", GOLD, (cx, 125), surf, shadow=True)

        # ---- impact shockwave on the floor (under the palms) ----
        if st is not None and T_IMPACT <= st < T_IMPACT + 0.34:
            self.draw_impact_ring(surf, cx, side.power, (st - T_IMPACT) / 0.34)

        # ---- hands + flying bands (correct layering) ----
        if st is not None and T_IMPACT <= st < T_IMPACT + 0.12:
            self.draw_bands(surf, side, cx, is_player)       # palm still pressing: hand on top
            self.draw_hands(surf, side, cx)
        elif st is not None and st >= T_IMPACT + 0.12:
            self.draw_hands(surf, side, cx)                  # rings in the air stay visible
            self.draw_bands(surf, side, cx, is_player)
        else:
            self.draw_bands(surf, side, cx, is_player)       # resting pile sits behind the palms
            self.draw_hands(surf, side, cx)

        # ---- alikabok + rubber crumbs (in front of everything) ----
        self._draw_fx(surf, "player" if is_player else "bot")

        self.draw_meter(surf, side, cx, is_player)

    def hud_message(self):
        p = self.phase
        if p == "meter":
            if self.pvp:
                if not self.bot.locked and not self.player.locked:
                    return f"SMASH {self.turn}: P1 [Q]  /  P2 [P]!"
                if self.bot.locked and not self.player.locked:
                    return "WAITING FOR PLAYER 2..."
                if self.player.locked and not self.bot.locked:
                    return "WAITING FOR PLAYER 1..."
                return "BOTH LOCKED IN!"
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
        hud_pill(WIN, HUD_L_LABEL, "P1 WINS" if self.pvp else "ROUND WINS")
        hud_pill(WIN, pygame.Rect(HUD_L_VALUE.right - 140, HUD_L_VALUE.y, 140, 34), f"SCORE:{self.bot_wins}")
        hud_pill(WIN, HUD_ROUND, f"ROUND {n}", TITLE_FONT)
        hud_pill(WIN, HUD_R_LABEL, "P2 WINS" if self.pvp else "ROUND WINS")
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
        if self.pvp:
            title = {"win": "P2 WINS!", "loss": "P1 WINS!", "tie": "IT'S A TIE!"}[self.final]
            line = f"P1 {self.bot_wins}   -   {self.player_wins} P2"
            cheer = "Nice one! Rematch?" if self.final != "tie" else "So close! Rematch?"
        else:
            title = {"win": "YOU WIN!", "loss": "YOU LOSE!", "tie": "IT'S A TIE!"}[self.final]
            line = f"you {self.player_wins}/{self.bot_wins} bot"
            cheer = {"win": "Galing! Great job!", "loss": "Okay lang! Try again!",
                     "tie": "So close! Rematch?"}[self.final]
        pop_text(HUGE_FONT, title, BROWN, (END_PANEL.centerx, END_PANEL.y + 55),
                 ease_out(clamp(self.t / 0.4)))
        text_center(MID_FONT, line, BROWN, (END_PANEL.centerx, END_PANEL.y + 115))
        text_center(DESC_FONT, cheer, LINE_BROWN, (END_PANEL.centerx, END_PANEL.y + 148))
        button(END_AGAIN, "PLAY AGAIN", END_AGAIN.collidepoint(mouse), MID_FONT)
        button(END_MENU, "MENU", END_MENU.collidepoint(mouse), MID_FONT)


CX, CY = WIDTH // 2, 325            # center of the floor where the pogs sit (lower = palm can swallow the pile)

STACK_MIN, STACK_MAX = 15, 30       # every game starts with a different random stack (15 to 30 pogs)
MAX_STACK = STACK_MAX               # the stack can never be bigger than this
TARGET_R = 34                       # radius of the click-circles (px)
TURN_TIME = 5.0                     # seconds each player has to stop the meter
POG_D = 72                          # pog size on screen (px)
POG_FILES = ["pog1.png", "pog2.png", "pog3.png", "pog4.png"]   # every pog in the stack gets one of these

# hand slam timing (same shape as the reference video: still -> grow toward the camera -> hold -> snap back)
POGS_T_GROW0 = 0.13                 # hands start moving (smash phase) - same as Karera
POGS_T_IMPACT = 0.55                # moment the hands hit the pogs (end of the grow)
POGS_T_HOLD = 0.12                  # hands stay pressed down
POGS_T_SNAP = 0.06                  # then snap back to the resting size
SMASH_TIME = 0.95
LOCK_TIME = 0.55
FLIGHT_TIME = 1.35                  # how long the flipped pogs take to scatter
POG_FLIGHT_T = (0.42, 0.62)         # airtime of the first arc (seconds) - mabilis ang hampas
POG_PEAK = (80, 150)                # apex height of the first arc (px) - mas mataas = mas "talsik"
POG_BOUNCES = [(0.34, 0.50), (0.20, 0.22), (0.11, 0.07)]   # (airtime frac, bounce height frac)
POG_SLIDE_T = 0.24                  # huling pag-skid sa sahig bago tumigil
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


# ---------------------------------------------------------------------
#  POG FLIGHT KINEMATICS
#  Isang pog = isang projectile. Unang bugso (buong layo, pinakamataas),
#  tapos paunti nang paunti ang talbog hanggang tumigil sa sahig.
# ---------------------------------------------------------------------
POG_BOUNCE_DAMP = 0.55          # bawat talbog, bumabagal ang takbo sa sahig

# gaano pa kalayo ang tinatakbo pagkatapos ng unang arc (bounces + skid),
# bilang fraction ng unang arc. Ginagamit para tama ang final landing spot.
POG_TAIL = 0.0
_v = 1.0
for _d, _h in POG_BOUNCES:
    POG_TAIL += _d * _v
    _v *= POG_BOUNCE_DAMP
POG_TAIL += (POG_SLIDE_T / 0.50) * _v

HAND_KEEPOUT = pygame.Rect(CX - 205, CY + 15, 410, HEIGHT)   # huwag patungo dito ang mga pog


def _out_of_hands(x, y):
    """ilayo ang landing spot sa mga kamay/braso (nasa foreground kasi ang kamay)"""
    r = HAND_KEEPOUT
    if not r.collidepoint(x, y):
        return x, y
    if y < r.top + 55:                       # malapit sa itaas: itaas na lang
        return x, r.top - 44
    if x < CX:                               # gilid: itulak sa kaliwa
        return r.left - 46, y
    return r.right + 46, y                   # o sa kanan


def pog_depth(gy):
    """mas malayo sa camera (mas mataas sa screen) = mas maliit nang kaunti"""
    return 1.0 - 0.10 * clamp((CY - gy) / 280.0, 0.0, 1.0)


def _pog_segments(p):
    """yield (t_start, t_end, x0, y0, x1, y1, height, angle0, angle1, skid) per arc.
    Isang arc = isang talbog. Ang huling 'skid' ay hindi na tumatalbog - dumudulas
    lang sa sahig habang bumabagal (friction) bago tumigil."""
    T = p["T"]
    sx, sy, ex, ey = p["sx"], p["sy"], p["ex"], p["ey"]
    vx, vy = (ex - sx) / T, (ey - sy) / T        # px per second sa sahig
    ang = p["spin"]
    t0 = 0.0
    # 1) unang bugso: buong layo, pinakamataas na arc, mabilis na pag-flip
    yield t0, T, sx, sy, ex, ey, p["peak"], 0.0, ang, False
    t0 = T
    cx, cy = ex, ey
    for dur_f, h_f in POG_BOUNCES:
        bt = T * dur_f
        nx, ny = cx + vx * bt, cy + vy * bt
        # nakalapat na pagkatapos ng unang flip: hindi na umiikot sa ere,
        # ang design na lang ang umiikot (parang totoong pog na dumudulas)
        yield t0, t0 + bt, cx, cy, nx, ny, p["peak"] * h_f, ang, ang, False
        t0 += bt
        cx, cy = nx, ny
        vx *= POG_BOUNCE_DAMP
        vy *= POG_BOUNCE_DAMP
    # 4) huling skid: friction ang pumipigil, paunti nang paunti ang bilis
    nx, ny = cx + vx * POG_SLIDE_T, cy + vy * POG_SLIDE_T
    yield t0, t0 + POG_SLIDE_T, cx, cy, nx, ny, 0.0, ang, ang, True


def pog_flight_at(p, t):
    """(x, ground_y, z, angle, landed) ng isang lumilipad na pog sa oras t."""
    t = t - p["delay"]
    if t <= 0.0:
        return p["sx"], p["sy"], 0.0, 0.0, False
    for t0, t1, x0, y0, x1, y1, h, a0, a1, skid in _pog_segments(p):
        if t < t1:
            u = (t - t0) / max(1e-6, (t1 - t0))
            if skid:                                # friction: mabilis sa simula, dahan-dahang hinto
                u = 1.0 - (1.0 - u) ** 2.2
            z = 4.0 * h * u * (1.0 - u) if not skid else 0.0
            return (lerp(x0, x1, u),                     # horizontal: tuloy-tuloy
                    lerp(y0, y1, u),                     # depth sa sahig
                    z,                                   # height: parabola (gravity)
                    lerp(a0, a1, u),                     # pag-ikot / pag-flip
                    False)
    rx, ry = p["rest"]
    return rx, ry, 0.0, p["spin"], True


def pog_rest_point(p):
    """saan titigil ang pog pagkatapos ng lahat ng talbog at skid."""
    last = None
    for seg in _pog_segments(p):
        last = seg
    return last[4], last[5]


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
    def __init__(self, on_finish=None, pvp=False):
        """on_finish(player_pogs, bot_pogs, mode_name) is called once when the game ends."""
        self.on_finish = on_finish
        self.pvp = pvp              # True = Player 1 vs Player 2, False = Player vs Bot
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
        if self.pvp:
            self.pogs = {"player1": 0, "player2": 0}
            self.last_flip = {"player1": 0, "player2": 0}
            self.turn = "player1"            # Player 1 always starts
        else:
            self.pogs = {"player": 0, "bot": 0}
            self.last_flip = {"player": 0, "bot": 0}
            self.turn = "player"            # the player always starts
        self.prev = None
        self.flying = []
        self.waves = []          # only the little ring when a "HIT!" circle is clicked
        self.puffs = []          # alikabok: impact + landing
        self.hitstop = 0.0       # freeze-frame sa impact (ramdam ang bigat)
        self.stack_shake = 0.0   # nginig ng pile pagkatapos ng hampas
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
        if not self.pvp:
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
            if self.phase == "meter" and not self.meter.locked:
                if self.pvp:
                    # PvP: P1 = Q, P2 = P (same as Karera PvP controls)
                    if event.key == pygame.K_q and self.turn == "player1":
                        play("lock")
                        self.meter.locked = True
                    elif event.key == pygame.K_p and self.turn == "player2":
                        play("lock")
                        self.meter.locked = True
                elif event.key == pygame.K_SPACE and self.turn == "player":
                    play("lock")
                    self.meter.locked = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.phase == "target" \
                and (self.turn == "player" or (self.pvp and self.turn in ("player1", "player2"))):
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
        if self.hitstop > 0.0:                 # freeze-frame sa impact: ramdam ang bigat
            self.hitstop = max(0.0, self.hitstop - dt)
            return
        if self.shake > 0.0:                   # unti-unting humihinto ang nginig
            self.shake = max(0.0, self.shake - 26 * dt)
        self.t += dt
        self.update_fx(dt)
        self.update_puffs(dt)
        self.update_pog_landings()
        ph = self.phase

        # nginig ng pile pagkatapos ng hampas (damped oscillation)
        if ph == "smash" and self.t >= POGS_T_IMPACT:
            k = clamp((self.t - POGS_T_IMPACT) / 0.40)
            self.stack_shake = 8.0 * (1.0 - k) * math.sin(k * 38.0)
        else:
            self.stack_shake = 0.0

        if ph == "transition":
            if self.t >= TRANS_TIME:
                self.start_meter()

        elif ph == "meter":
            m = self.meter
            m.update(dt)
            if not self.pvp and self.turn == "bot" and not m.locked and self.t >= self.bot_wait:
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
                    if self.pvp:
                        self.turn = "player2" if self.turn == "player1" else "player1"
                    else:
                        self.turn = "bot" if self.turn == "player" else "player"
                    if self.prev == "bot":
                        self.round += 1
                    self.set_phase("transition")

    def finish(self):
        if self.pvp:
            p1, p2 = self.pogs["player1"], self.pogs["player2"]
            self.final = "p1" if p1 > p2 else "p2" if p2 > p1 else "ptie"
            if not self.saved and self.on_finish:
                self.on_finish(p1, p2, "DAMPA POGS", result=self.final)
        else:
            p, b = self.pogs["player"], self.pogs["bot"]
            self.final = "win" if p > b else "loss" if p < b else "tie"
            if not self.saved and self.on_finish:
                self.on_finish(p, b, "DAMPA POGS")
        self.saved = True
        self.set_phase("end")
        finish_fx(self.final)

    # ---------------------------------------------------------- dust / alikabok
    def _puff(self, x, y, n, power, spread=40, speed=1.0, life=(0.30, 0.70)):
        """spawn dust particles (same recipe as Dampa Karera)"""
        if n <= 0:
            return
        big = power >= 0.75
        for _ in range(n):
            a = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            sp = random.uniform(22, 95) * speed * (0.7 + 0.7 * power)
            self.puffs.append([
                x + random.uniform(-spread, spread), y + random.uniform(-5, 9),
                math.cos(a) * sp, math.sin(a) * sp * 0.5,
                random.choice((14, 20, 27)) if big else random.choice((9, 14, 20)),
                0.0, random.uniform(*life)])

    def update_puffs(self, dt):
        for p in self.puffs:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.90
            p[3] = p[3] * 0.90 - 26 * dt              # dust floats up then hangs in the air
            p[5] += dt
        self.puffs[:] = [p for p in self.puffs if p[5] < p[6]]

    def draw_puffs(self, surf):
        for x, y, vx, vy, r, age, life in self.puffs:
            k = clamp(age / life)
            puff = DUST_PUFFS[r]
            puff.set_alpha(int(215 * (1.0 - k) ** 0.9))
            surf.blit(puff, puff.get_rect(center=(int(x), int(y))))
            puff.set_alpha(255)

    def draw_impact_ring(self, surf, cx, cy, power, k):
        """white flash + expanding dust ring sa sahig kung saan lumapat ang palad"""
        if k < 0.0 or k > 1.0:
            return
        if k < 0.22:                                        # the flash of the hit
            a = int(150 * (1.0 - k / 0.22))
            flash = pygame.Surface((150, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(flash, (255, 252, 232, a), flash.get_rect())
            surf.blit(flash, flash.get_rect(center=(cx, cy - 4)))
        rw = int(30 + (130 + 80 * power) * ease_out(k))
        rh = int(rw * 0.38)
        ring = pygame.Surface((rw * 2 + 8, rh * 2 + 8), pygame.SRCALPHA)
        pygame.draw.ellipse(ring, (255, 246, 214, int(175 * (1.0 - k) ** 1.5)),
                            (4, 4, rw * 2, rh * 2), max(2, int(7 * (1.0 - k) + 1)))
        surf.blit(ring, ring.get_rect(center=(cx, cy)))

    def update_pog_landings(self):
        """bawat pog na lumapat sa sahig -> maliit na alikabok (isa-isa, bawat talbog)"""
        if self.phase == "smash":
            ft = max(0.0, self.t - POGS_T_IMPACT)
        elif self.phase == "flip":
            ft = (SMASH_TIME - POGS_T_IMPACT) + self.t
        else:
            return
        for p in self.flying:
            t = ft - p["delay"]
            if t <= 0.0:
                continue
            events = p.get("land_events") or []
            while p.get("bounce_fx", 0) < len(events) and t >= events[p["bounce_fx"]][0]:
                i = p["bounce_fx"]
                _, lx, ly = events[i]
                strong = 1.0 if i == 0 else (0.45 if i == 1 else 0.25)
                self._puff(lx, ly, 4 if i == 0 else 2, self.power * strong,
                           spread=16, speed=0.55 if i == 0 else 0.35,
                           life=(0.18, 0.42) if i == 0 else (0.14, 0.30))
                p["bounce_fx"] = i + 1

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

        # flying pogs - real projectile motion: launch -> arc -> bounce -> skid -> settle
        self.flying = []
        spread = 1.25 if p > 0.95 else 1.0
        K = 1.0 + POG_TAIL                                  # rest = start + (ex-start)*K
        for k in range(flips):
            ang = random.uniform(0, math.tau)
            rad = random.uniform(0.0, 1.0) ** 1.2
            travel = (110 + 440 * rad) * spread             # layo ng final resting spot
            if random.random() < 0.22:                      # ilang pog, malapit lang tumalbog
                travel *= random.uniform(0.30, 0.55)
            rx = clamp(CX + math.cos(ang) * travel, 255, 1045)
            ry = clamp(CY + math.sin(ang) * travel * 0.62, 110, 495)
            rx, ry = _out_of_hands(rx, ry)                  # huwag sa ibabaw ng kamay
            ex = clamp(CX + (rx - CX) / K, 230, 1070)       # dulo ng unang arc
            ey = clamp(CY + (ry - CY) / K, 95, 560)
            T = random.uniform(*POG_FLIGHT_T)
            f = {
                "sx": CX + random.uniform(-5, 5),
                "sy": CY - random.uniform(0, 10),
                "ex": ex,
                "ey": ey,
                "delay": random.uniform(0, 0.13),
                "T": T,
                "peak": random.uniform(*POG_PEAK) * (0.62 + 0.52 * p),
                "spin": math.pi * random.choice((3, 5, 7)) * random.choice((-1, 1)),
                "rot": random.uniform(70, 260) * random.choice((-1, 1)),   # ikot ng design habang lumilipad
                "design": flipped[k],
            }
            f["rest"] = pog_rest_point(f)                     # saan siya titigil
            f["land_events"] = [(s[1], s[4], s[5]) for s in _pog_segments(f)]   # (time, x, y) ng bawat paglapag
            f["land_t"] = f["delay"] + T * (1.0 + sum(d for d, _ in POG_BOUNCES)) + POG_SLIDE_T
            f["bounce_fx"] = 0
            self.flying.append(f)

        # ---- TOTOONG HEAP: ang pog na tumama sa pile o sa kapwa pog ay
        #      hindi flat na nakahiga - nakatagilid ito at dahan-dahang lumalapat.
        occupied = [(float(CX), float(CY), POG_D * 0.52, True)] if self.stack else []
        for f in sorted(self.flying, key=lambda q: q["land_t"]):
            rx, ry = f["rest"]
            raised = []
            for ox, oy, orad, is_raised in occupied:
                if is_raised and math.hypot(rx - ox, ry - oy) < orad + POG_D * 0.33:
                    raised.append((ox, oy))
            if raised:
                ox = sum(s[0] for s in raised) / len(raised)
                oy = sum(s[1] for s in raised) / len(raised)
                layers = min(4, len(raised))
                f["on_heap"] = True
                f["tilt"] = min(0.95, random.uniform(0.38, 0.55) + 0.08 * layers)   # rad
                f["lean"] = math.atan2(ry - oy, rx - ox) + random.uniform(-0.7, 0.7)
                f["lift"] = min(32.0, 6.0 + 8.0 * layers + random.uniform(0, 5))     # taas sa sahig
            else:
                f["on_heap"] = False
                f["tilt"] = f["lean"] = f["lift"] = 0.0
            occupied.append((rx, ry, POG_D * 0.40, f["on_heap"]))

        # flat na pog na tatama sana sa gilid ng pile -> ilayo nang kaunti,
        # para ang mga NAKATAGILID lang ang nasa ibabaw ng pile (hindi sticker-like)
        K = 1.0 + POG_TAIL
        for f in self.flying:
            if f["on_heap"]:
                continue
            rx, ry = f["rest"]
            dx, dy = rx - CX, ry - CY
            d = math.hypot(dx, dy)
            clear = POG_D * 1.15 + 12                       # ~95 px mula sa gitna ng pile
            if d < clear:
                if d < 1e-3:
                    a = random.uniform(0, math.tau)
                    dx, dy, d = math.cos(a), math.sin(a), 1.0
                rx, ry = CX + dx / d * clear, CY + dy / d * clear
                rx, ry = _out_of_hands(rx, ry)
                f["ex"] = clamp(f["sx"] + (rx - f["sx"]) / K, 230, 1070)
                f["ey"] = clamp(f["sy"] + (ry - f["sy"]) / K, 95, 560)
                f["rest"] = pog_rest_point(f)
                f["land_events"] = [(s[1], s[4], s[5]) for s in _pog_segments(f)]

        # alikabok + flash kung saan lumapat ang palad (gaya ng Karera)
        self._puff(CX, CY + 26, 10 + int(10 * p), p, spread=52, speed=1.15)
        self._puff(CX, CY + 26, 6, p * 0.7, spread=84, speed=0.60, life=(0.35, 0.75))
        self.hitstop = IMPACT_HITSTOP                         # freeze-frame: ramdam ang bigat
        self.shake = 5 + 10 * p

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
        if not self.pvp and self.turn == "bot" and tg["hit_at"] is not None and self.tclock >= tg["hit_at"]:
            self.resolve_target(True)
        elif self.tclock >= tg["life"]:
            self.resolve_target(False)

    def apply_penalty(self):
        """every miss can cost power - the more you miss, the more likely and the bigger the loss"""
        m = self.misses
        if self.pvp:
            who = "P1: " if self.turn == "player1" else "P2: "
        else:
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
        fill = (255, 205, 40) if (self.turn == "player" or (self.pvp and self.turn == "player1")) else (255, 130, 100)
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
        """same Karera formula, but the target tip is the top of the pile so the palm
        fully swallows the stack at impact - ito ang 'hampas' na itsura ng Karera."""
        stack_top = CY - 2 - min(45.0, 3.0 * (self.stack - 1)) - POG_D // 2
        tip = clamp(stack_top - 10, 215, STRIKE_FULL_TIP)
        full = clamp((HANDS_TOP + HANDS_H - tip) / HANDS_H, 1.25, 1.45)
        return lerp(STRIKE_MIN, full, self.power)

    def hand_state(self, side, t_override=None):
        """the SAME 5-beat slam as Dampa Karera:
        wind-up -> slam -> squash on the floor -> damped spring back.
        returns (y_offset, scale_x, scale_y, x_jitter)."""
        ph = self.phase
        t = self.t if t_override is None else t_override
        if ph == "transition":
            u = clamp(t / TRANS_TIME)
            if side == self.turn:
                k = clamp((u - 0.45) / 0.55) if self.prev else clamp(u / 0.7)
                return HIDE * (1 - ease_out(k)), 1.0, 1.0, 0
            if side == self.prev:
                return HIDE * ease_in_out(clamp(u / 0.45)), 1.0, 1.0, 0
            return HIDE, 1.0, 1.0, 0
        if ph == "end" or side != self.turn:
            return HIDE, 1.0, 1.0, 0
        if ph == "meter":
            if self.meter.pos > 0.95:                                    # overcharge shakes
                return 0, 1.0, 1.0, random.uniform(-3, 3)
            return 4 * math.sin(t * 6), 1.0, 1.0, 0                      # gentle idle bob
        if ph in ("target", "tresult"):
            return 4 * math.sin(t * 6), 1.0, 1.0, 0
        if ph == "smash":
            peak = self.peak_scale(side)
            if t < POGS_T_GROW0:                              # 1) wind-up: hands pull back a little
                k = ease_out(clamp(t / POGS_T_GROW0))
                return 16.0 * k, 1.0 - 0.045 * k, 1.0 + 0.025 * k, 0
            if t < POGS_T_IMPACT:                             # 2) the slam: accelerating
                k = clamp((t - POGS_T_GROW0) / (POGS_T_IMPACT - POGS_T_GROW0)) ** 2.1
                scx = lerp(0.955, peak * 1.02, k)
                scy = lerp(1.025, peak * 0.985, k)
                return lerp(16.0, 0.0, k), scx, scy, 0
            if t < POGS_T_IMPACT + T_SQUASH:                  # 3) squash: the palm flattens on the floor
                k = (t - POGS_T_IMPACT) / T_SQUASH
                sq = math.sin(k * math.pi) * 0.06
                return 5.0 * (1.0 - k), peak * (1.0 + sq), peak * (1.0 - sq * 1.7), 0
            if t < POGS_T_IMPACT + T_SQUASH + T_RECOIL:       # 4) damped spring back to rest
                k = clamp((t - POGS_T_IMPACT - T_SQUASH) / T_RECOIL)
                wob = math.exp(-4.0 * k) * math.cos(k * math.pi * 2.2)
                sc = 1.0 + (peak - 1.0) * wob
                return 0, sc, sc, 0
        return 0, 1.0, 1.0, 0

    # ---------------------------------------------------------- drawing
    def blit_pog(self, surf, img, x, y, wf=1.0, sc=1.0, rot=0.0, hf=1.0, rim=0):
        w = max(2, int(POG_D * sc * wf))
        h = max(2, int(POG_D * sc * hf))
        s = img if (w, h) == img.get_size() else pygame.transform.scale(img, (w, h))
        if rot:
            s = pygame.transform.rotozoom(s, rot, 1.0)
        if rim:                                  # kapal ng pog: dark edge sa ilalim
            edge = silhouette(s, 150)
            surf.blit(edge, edge.get_rect(center=(int(x), int(y) + rim)))
        surf.blit(s, s.get_rect(center=(int(x), int(y))))

    def shadow(self, surf, x, y, wf=1.0, sc=1.0, alpha=70):
        w, h = max(2, int(POG_D * sc * wf)), max(2, int(POG_D * sc * 0.55))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
        surf.blit(s, s.get_rect(center=(int(x + 4), int(y + 6))))

    def draw_stack(self, surf):
        jolt = self.stack_shake                              # damped nginig pagkatapos ng hampas
        squash = 1.0
        if self.phase == "smash" and self.t >= POGS_T_IMPACT:
            k = clamp((self.t - POGS_T_IMPACT) / 0.18)
            squash = 1.0 - 0.10 * (1.0 - k)                  # naipit sandali ng palad
        for i in range(self.stack):
            ox, oy = self.stack_off[i % MAX_STACK]
            x = CX + ox + jolt
            y = CY + oy - i * min(3.0, 45.0 / max(self.stack, 1)) + (1.0 - squash) * 12
            self.shadow(surf, x, y, alpha=45 if i else 80)
            self.blit_pog(surf, self.A["fronts"][self.pile[i]], x, y,
                          1.0 + (1.0 - squash) * 0.6, 1.0, 0.0, squash)

    def draw_flying(self, surf):
        # BOT is on the left, PLAYER on the right (like the reference HUD); PvP: P1 left / P2 right
        if self.pvp:
            coll = (70, 640) if self.turn == "player1" else (WIDTH - 70, 640)
        else:
            coll = (WIDTH - 70, 640) if self.turn == "player" else (70, 640)
        if not self.flying:
            return
        if self.phase in ("smash", "flip"):
            if self.phase == "smash":
                ft = max(0.0, self.t - POGS_T_IMPACT)
            else:
                ft = (SMASH_TIME - POGS_T_IMPACT) + self.t
        elif self.phase == "collect":
            ft = None
        else:
            return

        # sort by depth para tama ang overlap: mas malayo (taas sa screen) ang unang iginuhit
        items = []
        for p in self.flying:
            st = pog_flight_at(p, ft) if ft is not None else None
            items.append(((st[1] if st else p["rest"][1]), p, st))
        items.sort(key=lambda it: it[0])

        for _, p, st in items:
            if ft is None:                                  # collect: lumilipad papunta sa manlalaro
                ex, ey = p["rest"]
                u = ease_in_out(clamp(self.t / COLLECT_TIME))
                x, y = lerp(ex, coll[0], u), lerp(ey, coll[1], u)
                d = pog_depth(y)
                tilt = p["tilt"] * (1.0 - u) if p["on_heap"] else 0.0
                hf = max(0.5, math.cos(tilt))
                lift = p["lift"] * (1.0 - u) if p["on_heap"] else 0.0
                self.shadow(surf, x, y, sc=d, alpha=int(60 * (1 - u)))
                self.blit_pog(surf, self.A["back"], x, y - lift, 1.0,
                              d * (1.0 - 0.5 * u), p["rot"] + math.degrees(p["lean"]) + 90.0, hf,
                              rim=int(4 * (1.0 - u)))
                continue
            x, gy, z, ang, landed = st
            if landed:                                      # nakalapag na (back side up)
                d = pog_depth(gy)
                if p["on_heap"]:
                    # naka-patong sa pile / kapwa pog: dumadapo pa sya at
                    # dahan-dahang tumatagilid bago tuluyang huminto.
                    age = max(0.0, ft - p["land_t"]) if ft is not None else 9.0
                    wob = 1.0 - math.exp(-7.0 * age) * math.cos(age * 20.0) if age > 0 else 0.0
                    tilt = p["tilt"] * clamp(wob, 0.0, 1.35)
                    lift = p["lift"] * clamp(wob, 0.0, 1.25)
                    hf = max(0.50, math.cos(tilt))
                    lean = p["lean"]
                    self.shadow(surf, x + math.cos(lean) * 5, gy + 6, 0.92, d, 95)
                    self.blit_pog(surf, self.A["back"], x, gy - lift, 1.0, d,
                                  p["rot"] + math.degrees(lean) + 90.0, hf,
                                  rim=max(2, int(5 * d * hf)))
                else:
                    self.shadow(surf, x, gy, sc=d, alpha=70)
                    self.blit_pog(surf, self.A["back"], x, gy, 1.0, d, p["rot"])
                continue
            # shadow: lumalabo at lumalaki habang mataas ang pog
            k = clamp(z / max(1.0, p["peak"]))
            d = pog_depth(gy)
            self.shadow(surf, x, gy, 1.0 + 0.30 * k, sc=d, alpha=int(72 - 44 * k))
            # pog: lumalapit sa camera habang nasa ere, umiikot, at lumalapat sa sahig
            sc = d * (1.0 + z / 620.0)
            wf = max(0.10, abs(math.cos(ang)))
            face = self.A["fronts"][p["design"]] if math.cos(ang) >= 0 else self.A["back"]
            tt = max(0.0, ft - p["delay"])
            rot = p["rot"] * clamp(tt / (p["T"] * 1.7))
            hf = 1.0
            z_prev = pog_flight_at(p, max(0.0, ft - 0.030))[2]
            if 0.01 < z < 18.0:                         # malapit sa sahig: lumalapat (squash)
                q = 1.0 - z / 18.0
                if z < z_prev:                           # pababa: pipi bago tumalbog
                    hf = 1.0 - 0.24 * q
                    wf = wf * (1.0 + 0.12 * q)
                else:                                    # paakyat: bumabalik ang hugis
                    hf = 1.0 - 0.10 * q
            self.blit_pog(surf, face, x, gy - z, wf, sc, rot, hf)

    def draw_fx(self, surf):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        draw_waves(fx, self.waves)
        surf.blit(fx, (0, 0))
        # alikabok (impact + bawat paglapag ng pog) - nasa harap ng kamay
        self.draw_puffs(surf)

    def draw_hands(self, surf):
        """the SAME palm as Dampa Karera: two parts (palm + forearm), squash & stretch,
        motion smear on the way down, and the forearms stay planted on the floor."""
        sides = ("player1", "player2") if self.pvp else ("player", "bot")
        for side in sides:
            off, scx, scy, jx = self.hand_state(side)
            if off >= HIDE:
                continue
            asset_side = ("player" if side == "player1" else "bot") if self.pvp else side
            hw = max(2, int(HANDS_TOP_IMG.get_width() * scx))
            hh = max(2, int(HANDS_TOP_IMG.get_height() * scy))
            top = HANDS_TOP_IMG if (hw, hh) == HANDS_TOP_IMG.get_size() else \
                pygame.transform.smoothscale(HANDS_TOP_IMG, (hw, hh))
            shad = HANDS_TOP_SHADOW if (hw, hh) == HANDS_TOP_SHADOW.get_size() else \
                pygame.transform.smoothscale(HANDS_TOP_SHADOW, (hw, hh))
            if asset_side == "bot":                     # P2 / bot = darker skin (same as before)
                top = top.copy()
                top.fill((170, 120, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            y = HANDS_TOP + HANDS_H - HANDS_H * scy + off
            wrist_y = int(y + hh - 1)
            arm_h = max(int(HANDS_ARMS_IMG.get_height() * scy), HEIGHT + 8 - wrist_y)
            arms = HANDS_ARMS_IMG if (hw, arm_h) == HANDS_ARMS_IMG.get_size() else \
                pygame.transform.smoothscale(HANDS_ARMS_IMG, (hw, arm_h))
            arm_shad = HANDS_ARMS_SHADOW if (hw, arm_h) == HANDS_ARMS_SHADOW.get_size() else \
                pygame.transform.smoothscale(HANDS_ARMS_SHADOW, (hw, arm_h))
            if asset_side == "bot":
                arms = arms.copy()
                arms.fill((170, 120, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
            hx = int(CX + jx - hw // 2)

            surf.blit(arm_shad, (hx + 14, wrist_y + 10))     # forearm shadow
            surf.blit(shad, (hx + 14, int(y) + 10))          # palm shadow

            # motion smear while the palm is still rushing forward (2 ghost frames)
            if self.phase == "smash" and POGS_T_GROW0 <= self.t < POGS_T_IMPACT:
                for back, a in ((0.022, 80), (0.046, 45)):
                    o2, _, y2, _ = self.hand_state(side, self.t - back)
                    hh2 = max(2, int(HANDS_TOP_IMG.get_height() * y2))
                    gh = HANDS_TOP_IMG if hh2 == HANDS_TOP_IMG.get_height() else \
                        pygame.transform.smoothscale(HANDS_TOP_IMG, (hw, hh2))
                    gh = gh.copy()
                    if asset_side == "bot":
                        gh.fill((170, 120, 100, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    gh.set_alpha(a)
                    surf.blit(gh, (hx, int(HANDS_TOP + HANDS_H - HANDS_H * y2 + o2)))

            surf.blit(arms, (hx, wrist_y))
            surf.blit(top, (hx, int(y)))

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
        if self.pvp:
            blink_on_turn = (self.turn == "player1" or self.turn == "player2")
        else:
            blink_on_turn = (self.turn == "player")
        blink = not (blink_on_turn and self.phase == "meter" and int(self.t * 5) % 2 == 0)
        pygame.draw.rect(surf, (255, 235, 90) if blink else (255, 255, 255),
                         (x + int(IDEAL_LO * w), y - 5, int((IDEAL_HI - IDEAL_LO) * w), h + 10), 2)
        pygame.draw.line(surf, (255, 255, 255), (x + fill, y - 4), (x + fill, y + h + 4), 3)
        self.text(surf, self.f_small, f"{int(m.pos * 100)}%", WHITE, (x + w // 2, y + h + 16))
        if blink_on_turn and self.phase == "meter":
            if self.pvp:
                self.text(surf, self.f_small, "[Q] STOP IN GREEN BOX" if self.turn == "player1" else "[P] STOP IN GREEN BOX", WHITE, (x + w // 2, y + h + 38))
            else:
                self.text(surf, self.f_small, "[SPACE] STOP IN GREEN BOX", WHITE, (x + w // 2, y + h + 38))

    def draw_hud(self, surf):
        hud_pill(surf, HUD_ROUND, f"ROUND {self.round}", TITLE_FONT)
        if self.pvp:
            hud_pill(surf, HUD_L_LABEL, "P1")
            hud_pill(surf, HUD_L_VALUE, f"{self.pogs['player1']} POGS")
            hud_pill(surf, HUD_R_LABEL, "P2")
            hud_pill(surf, HUD_R_VALUE, f"{self.pogs['player2']} POGS")
            # the two pills on each side: FLIP + STACK
            for rects, who in ((HUD_SIDE_L, "player1"), (HUD_SIDE_R, "player2")):
                hud_pill(surf, rects[0], f"FLIP: {self.last_flip[who]}")
                hud_pill(surf, rects[1], f"STACK: {self.stack}")
        else:
            hud_pill(surf, HUD_L_LABEL, "BOT")
            hud_pill(surf, HUD_L_VALUE, f"{self.pogs['bot']} POGS")
            hud_pill(surf, HUD_R_LABEL, "PLAYER")
            hud_pill(surf, HUD_R_VALUE, f"{self.pogs['player']} POGS")
            # the two pills on each side: FLIP + STACK
            for rects, who in ((HUD_SIDE_L, "bot"), (HUD_SIDE_R, "player")):
                hud_pill(surf, rects[0], f"FLIP: {self.last_flip[who]}")
                hud_pill(surf, rects[1], f"STACK: {self.stack}")

        # timer pill (under the ROUND pill)
        t_txt = ""
        if self.phase == "transition":
            t_txt = f"TIME: {int(TURN_TIME)}"
        elif self.phase == "meter":
            t_txt = f"TIME: {int(math.ceil(max(0.0, TURN_TIME - self.t)))}"
        hud_pill(surf, HUD_TIMER, t_txt)

        if self.phase in ("end", "transition"):
            return
        # power bar for the current turn
        if self.pvp:
            if self.turn == "player1":
                self.draw_bar(surf, CX - 360, 560, "P1")      # left of the hands
            else:
                self.draw_bar(surf, CX + 130, 560, "P2")      # right of the hands
        else:
            if self.turn == "player":
                self.draw_bar(surf, CX - 360, 560, "YOU")      # left of the hands
            else:
                self.draw_bar(surf, CX + 130, 560, "BOT")      # right of the hands

    def draw_messages(self, surf):
        if self.phase == "transition":
            u = clamp(self.t / TRANS_TIME)
            a = int(255 * min(1, u / 0.2, (1 - u) / 0.2))
            if self.pvp:
                who = "PLAYER 1 TURN" if self.turn == "player1" else "PLAYER 2 TURN"
            else:
                who = "YOUR TURN" if self.turn == "player" else "BOT'S TURN"
            self.text(surf, self.f_huge, who, WHITE, (CX, 225), alpha=max(0, a))
            self.text(surf, self.f_mid, f"stack: {self.stack} pogs", WHITE, (CX, 285), alpha=max(0, a))
        elif self.phase == "target":
            n = len(self.targets)
            if self.pvp:
                title = "CLICK THE CIRCLES!" if self.turn == "player1" else "PLAYER 2 IS CLICKING..."
            else:
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

        # impact ring sa sahig, nasa ilalim ng palad (gaya ng Dampa Karera)
        if self.phase == "smash" and self.t >= POGS_T_IMPACT:
            k = (self.t - POGS_T_IMPACT) / 0.34
            self.draw_impact_ring(c, CX, CY + 34, self.power, k)

        # SAME layering as Karera: habang nakapatong ang palad, kamay ang nasa harap;
        # pagkatapos ng impact, lumilipad ang pogs sa HARAP ng kamay.
        pressing = self.phase == "smash" and self.t < POGS_T_IMPACT + 0.12
        if not pressing:
            self.draw_hands(c)
        self.draw_flying(c)
        if pressing:
            self.draw_hands(c)

        self.draw_fx(c)
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
        if self.pvp:
            title = {"p1": "PLAYER 1 WINS!", "p2": "PLAYER 2 WINS!", "ptie": "IT'S A TIE!"}[self.final]
            line = f"P1 {self.pogs['player1']}   -   {self.pogs['player2']} P2"
            cheer = "Nice one! Rematch?" if self.final != "ptie" else "So close! Rematch?"
        else:
            title = {"win": "YOU WIN!", "loss": "YOU LOSE!", "tie": "IT'S A TIE!"}[self.final]
            line = f"you {self.pogs['player']} / {self.pogs['bot']} bot  (pogs)"
            cheer = {"win": "Galing! Great job!", "loss": "Okay lang! Try again!", "tie": "So close! Rematch?"}[self.final]
        pop_text(self.f_huge, title, BROWN, (END_PANEL.centerx, END_PANEL.y + 55),
                 ease_out(clamp(self.t / 0.4)))
        self.text(self.win, self.f_mid, line, BROWN,
                  (END_PANEL.centerx, END_PANEL.y + 115), shadow=False)
        self.text(self.win, self.f_small, cheer, LINE_BROWN, (END_PANEL.centerx, END_PANEL.y + 148), shadow=False)
        button(END_AGAIN, "PLAY AGAIN", END_AGAIN.collidepoint(mouse), self.f_mid)
        button(END_MENU, "MENU", END_MENU.collidepoint(mouse), self.f_mid)


# =====================================================================
#  MENU / SCORE / EXIT SCREENS
# =====================================================================
REVEAL_SURF = pygame.Surface((WIDTH, HEIGHT))
REVEAL_SURF.fill((0, 0, 0))


def draw_logo(now, amp=1.0):
    if not LETTERS:
        WIN.blit(LOGO, LOGO_POS.move(0, int(math.sin(now / 500) * 6 * amp)))
        return
    for i, img in enumerate(LETTERS):
        WIN.blit(img, LOGO_POS.move(0, int(math.sin(now / 420.0 - i * 0.9) * 8 * amp)))


def draw_menu(mouse, reveal=1.0):
    now = pygame.time.get_ticks()
    WIN.blit(BG, (0, 0))
    AMBIENT.draw(WIN)
    k = ease_in_out(clamp(reveal))
    if reveal >= 1.0:
        draw_logo(now)
    text_center(SMALL_FONT, TIPS[(now // 4000) % len(TIPS)], GOLD, (WIDTH // 2, 26), shadow=True)
    for label, rect in MENU_BUTTONS.items():
        button(rect, "SCORES" if label == "SCORE" else label, rect.collidepoint(mouse))
    y = HEIGHT - 75
    for line in DESCRIPTION:
        text_center(DESC_FONT, line, TEXT_COLOR, (WIDTH // 2, y), shadow=True)
        y += 24
    if reveal < 1.0:
        REVEAL_SURF.set_alpha(int(255 * (1.0 - k)))
        WIN.blit(REVEAL_SURF, (0, 0))
        draw_logo(now, k)


COUNT_FONT = PixelFont(180)


def draw_countdown(c):
    if c < 3.0:
        text, color = str(3 - int(c)), GOLD
        k = ease_out(clamp((c - int(c)) * 4))
        alpha = 255
    else:
        text, color = "GO!", (140, 255, 140)
        k = ease_out(clamp((c - 3.0) * 4))
        alpha = int(255 * clamp((3.7 - c) / 0.4))
    pop_text(COUNT_FONT, text, color, (WIDTH // 2, 430), k, alpha=alpha)


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
        is_pvp_row = str(result).lower() in ("p1", "p2", "ptie")
        if is_pvp_row:                       # PvP row: P1 (left) vs P2 (right)
            res_txt = "TIE" if str(result).lower() == "ptie" else res_upper
            color = BROWN if str(result).lower() == "ptie" else (0, 160, 40)
            left_name, right_name = "P1", "P2"
        else:
            res_txt = res_upper
            if "WIN" in res_upper:
                color = (0, 160, 40)   # Green for WIN
            elif "DEFEAT" in res_upper:
                color = (230, 40, 40)  # Red for DEFEAT
            else:
                color = BROWN          # Brown for TIE
            left_name, right_name = "BOT", "PLAYER"

        short_mode = "GOMA" if "KARERA" in str(mode).upper() else "POGS"
        
        # Mga text sa loob ng bawat row na naka-center sa saktong columns
        text_center(SMALL_FONT, res_txt, color, (cx[0], cy))
        text_center(SMALL_FONT, str(bot), BROWN, (cx[1], cy))
        text_center(SMALL_FONT, left_name, BROWN, (cx[2], cy))
        text_center(SMALL_FONT, str(player), BROWN, (cx[3], cy))
        text_center(SMALL_FONT, right_name, BROWN, (cx[4], cy))
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
PVP = False                     # True = PLAYER VS PLAYER (Q / P), False = PLAYER VS BOT
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

    if PVP:                                          # 2-player controls sa ilalim ng mga card
        text_center(SMALL_FONT, "2-PLAYER:   P1 = Q   |   P2 = P", GOLD,
                    (360, 640), shadow=True)

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
INTRO_DAMPA_IN = 1.1
INTRO_DAMPA_HOLD = 0.6
MENU_REVEAL = 1.2
LETTER_STAGGER = 0.14
T_INTRO_SLIDE = INTRO_PRE + INTRO_RISE + INTRO_HOLD
T_DAMPA = T_INTRO_SLIDE + INTRO_SLIDE + INTRO_POST
INTRO_TOTAL = T_DAMPA + INTRO_DAMPA_IN + INTRO_DAMPA_HOLD

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
    if t >= T_DAMPA:
        if LETTERS:
            for i, img in enumerate(LETTERS):
                a = ease_out(clamp((t - T_DAMPA - i * LETTER_STAGGER) / (INTRO_DAMPA_IN - 4 * LETTER_STAGGER)))
                tmp = img.copy()
                tmp.fill((255, 255, 255, int(255 * a)), special_flags=pygame.BLEND_RGBA_MULT)
                WIN.blit(tmp, LOGO_POS.move(0, int(24 * (1 - a))))
            return
        a = ease_out(clamp((t - T_DAMPA) / INTRO_DAMPA_IN))
        tmp = LOGO.copy()
        tmp.fill((255, 255, 255, int(255 * a)), special_flags=pygame.BLEND_RGBA_MULT)
        WIN.blit(tmp, LOGO_POS)
        return
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
    global scroll_offset, SELECTED_MODE, DIFF_CHOSEN, PVP
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
    reveal = 1.0
    logo_sfx_done = False
    bgm_wait = None
    countdown = None

    while run:
        dt = min(CLOCK.tick(60) / 1000.0, 0.05)
        FX_DT[0] = dt
        if NOTICE[1] > 0:
            NOTICE[1] = max(0.0, NOTICE[1] - dt)
        mouse = pygame.mouse.get_pos()
        MOUSE_MOVED[0] = pygame.mouse.get_rel() != (0, 0)
        AMBIENT.update(dt)
        update_confetti(dt)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                continue
            if event.type == MUSIC_END:
                play_next_bgm()
                continue

            if screen == "intro":                         # any click / key skips the opening
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    intro_t = INTRO_TOTAL
                continue

# ---------------- IN GAME ----------------
            if screen == "game":
                if countdown is not None and countdown < 3.0:
                    continue
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
                        play("menu_click")
                        pygame.mixer.music.set_endevent()
                        pygame.mixer.music.fadeout(400)
                        bgm_wait = 0.5
                        screen = "gamemodes"
                    elif MENU_BUTTONS["SCORE"].collidepoint(pos):
                        play("menu_click")
                        scroll_offset = 0
                        screen = "score"
                    elif MENU_BUTTONS["EXIT"].collidepoint(pos):
                        play("menu_click")
                        screen = "exit"
                elif screen == "gamemodes":
                    if VS_PVP.collidepoint(pos):
                        play("click")
                        PVP = True
                        SELECTED_MODE = "karera"
                        DIFF_CHOSEN = False
                        NOTICE[1] = 0.0
                        screen = "botmodes"
                    elif VS_PVB.collidepoint(pos):
                        play("click")
                        PVP = False
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
                            if key == "pogs" and PVP:
                                # Player vs Player Pogs: no level required, both players play
                                play("click")
                                game = PogsGame(add_result, pvp=True)
                                paused = False
                                screen = "game"
                                play_bgm("pogs")
                            elif key == "pogs":
                                if DIFF_CHOSEN:
                                    play("click")
                                    game = PogsGame(add_result)
                                    paused = False
                                    screen = "game"
                                    play_bgm("pogs")
                                else:
                                    play("miss")
                                    set_notice("PICK A LEVEL FIRST!")
                            elif DIFF_CHOSEN:
                                play("click")
                                game = Game(pvp=PVP) if key == "karera" else PogsGame(add_result)
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
            if not logo_sfx_done and T_DAMPA <= intro_t < INTRO_TOTAL:
                logo_appear_sound.play()
                logo_sfx_done = True
            if intro_t >= INTRO_TOTAL:
                screen = "menu"
                reveal = 0.0
                play_bgm("menu")                          # home page music starts only after the intro

        if bgm_wait is not None:
            bgm_wait -= dt
            if bgm_wait <= 0:
                bgm_wait = None
                play_next_bgm(600)

        if reveal < 1.0:
            reveal = min(1.0, reveal + dt / MENU_REVEAL)
            if screen != "menu":
                reveal = 1.0

        if screen == "game" and prev_screen != "game":
            countdown = 0.0
            timer_sound.play()

        if screen == "game" and countdown is not None and not paused:
            old_count = countdown
            countdown += dt
            if int(countdown) != int(old_count) and countdown < 3.0:
                timer_sound.play()
            if old_count < 3.0 <= countdown:
                go_sound.play()
            if countdown >= 3.7:
                countdown = None

        if screen != prev_screen:
            fade = 0.0 if (prev_screen == "intro" and screen == "menu") else 1.0
            CONFETTI.clear()
            NOTICE[1] = 0.0
            prev_screen = screen

        if screen == "intro":
            draw_intro(intro_t)
        elif screen == "menu":
            draw_menu(mouse, reveal)
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
                counting = countdown is not None and countdown < 3.0
                if not counting:
                    game.update(dt)
                game.draw(mouse)
                if countdown is not None:
                    draw_countdown(countdown)
                if game.phase != "end" and not counting:
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