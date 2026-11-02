# pyright: reportUndefinedVariable=false
# pyright: reportUndefinedVariable=false
if __name__ == "__main__" and not globals().get("_GAME_PARTS_LOADING"):
    from pathlib import Path as _Path
    import runpy as _runpy
    _runpy.run_path(str(_Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
    raise SystemExit

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
_logo = load_image("Dampa.png")
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

# ---------------------------------------------------------------------
#  CHALK FINISH LINE (replaces the checkered line) - built ONCE, not every frame
# ---------------------------------------------------------------------
def make_chalk_line(width, seed=5):
    """a hand-drawn chalk line in pixel style: wobbly, grainy, with a little dust"""
    rnd = random.Random(seed)
    P = 3                                            # one chalk "pixel" = 3x3 screen pixels
    sw, sh = width // P + 1, 14
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    wob = 0.0
    for x in range(sw):
        wob += rnd.uniform(-0.35, 0.35)              # the line drifts up and down a little
        wob = max(-1.6, min(1.6, wob))
        cy = sh // 2 + int(round(wob))
        thick = rnd.choice((3, 4, 4, 5))
        half = thick // 2
        for dy in range(-half, half + 1):
            edge = abs(dy) == half
            if rnd.random() < (0.55 if edge else 0.93):          # gaps make it look like chalk
                a = rnd.randint(120, 190) if edge else rnd.randint(205, 255)
                small.set_at((x, cy + dy), (245, 245, 238, a))
        if rnd.random() < 0.10:                                  # loose chalk dust
            small.set_at((x, cy + rnd.choice((-4, -3, 3, 4))), (240, 240, 235, rnd.randint(70, 140)))
    return pygame.transform.scale(small, (sw * P, sh * P))


def make_chalk_text(text, font):
    """white chalk writing: normal pixel text with little scratches taken out of it"""
    img = font.render(text, True, (245, 245, 238)).copy()        # copy: the font keeps its own cached picture
    rnd = random.Random(8)
    w, h = img.get_size()
    for _ in range(w * h // 9):
        x, y = rnd.randrange(w), rnd.randrange(h)
        if img.get_at((x, y))[3] > 0:
            img.set_at((x, y), (245, 245, 238, rnd.randint(0, 90)))
    return img


CHALK_LINE = make_chalk_line(HALF)
CHALK_TEXT = make_chalk_text("FINISH", SMALL_FONT)


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

# --- SCORE layout: gold SCORE pill (top-left) + pink paper board + gold BACK (bottom-right)
_hdr_h0, _gap_top, _gap_bot, _back_h = 64, 14, 18, 54
_asp = ui_aspect("score_paper", 2.04)
SCORE_PAPER_W = min(800, int((HEIGHT - 40 - _hdr_h0 - _gap_top - _gap_bot - _back_h) * _asp))   # always fits the screen
_paper_h = int(SCORE_PAPER_W / _asp)
_hdr_w = int(SCORE_PAPER_W * 0.39)
_hdr_h = max(44, min(80, int(_hdr_w / ui_aspect("button", 4.3))))
_back_w = int(SCORE_PAPER_W * 0.29)
SCORE_SHIFT = (0, 0)          # nudge the WHOLE score screen: (+right / -left, +down / -up)
_score_total = _hdr_h + _gap_top + _paper_h + _gap_bot + _back_h

SCORE_TABLE = pygame.Rect(0, 0, SCORE_PAPER_W, _paper_h)                       # the pink paper
SCORE_TABLE.centerx = WIDTH // 2 + SCORE_SHIFT[0]
SCORE_TABLE.y = (HEIGHT - _score_total) // 2 + _hdr_h + _gap_top + SCORE_SHIFT[1]
SCORE_SIGN = pygame.Rect(SCORE_TABLE.x, SCORE_TABLE.y - _gap_top - _hdr_h, _hdr_w, _hdr_h)   # gold SCORE pill
SCORE_BACK = pygame.Rect(SCORE_TABLE.right - _back_w, SCORE_TABLE.bottom + _gap_bot, _back_w, _back_h)
# the cream table that sits on the paper (same proportions as your reference picture)
SCORE_TB = pygame.Rect(SCORE_TABLE.x + int(SCORE_PAPER_W * 0.065), SCORE_TABLE.y + int(_paper_h * 0.06),
                       int(SCORE_PAPER_W * 0.885), int(_paper_h * 0.87))
COL_STREAK = 110
COL_BOT = 70
COL_YOU = 70
COL_GAMEMODES = 270
HEAD_ROW_H = 45
ROW_H = 28
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

# in-game pause menu (matches the reference mockup)
PAUSE_BTN = pygame.Rect(WIDTH - 84, 12, 66, 62)          # the hamburger button (bigger, like the reference)
PAUSE_PANEL = pygame.Rect(WIDTH // 2 - 190, 115, 380, 470)
PAUSE_BUTTONS = {}
for _i, _name in enumerate(("CONTINUE", "SCORE", "MENU", "EXIT")):
    _r = pygame.Rect(0, 0, 277, 62)
    _r.midtop = (PAUSE_PANEL.centerx, PAUSE_PANEL.y + 56 + _i * 79)
    PAUSE_BUTTONS[_name] = _r

# ---- settings gear (main menu = right of EXIT, pause menu = bottom of the paper)
GEAR_MENU = pygame.Rect(0, 0, 64, 64)
GEAR_MENU.center = (MENU_BUTTONS["EXIT"].right + 16 + 32, MENU_BUTTONS["EXIT"].centery)
GEAR_PAUSE = pygame.Rect(0, 0, 60, 60)
GEAR_PAUSE.center = (PAUSE_PANEL.centerx, PAUSE_PANEL.y + 400)

# ---- SETTINGS screen (image 4)
SET_PAPER = pygame.Rect(0, 0, 360, 300)
_set_hh, _set_lap = 60, 12
SET_PAPER.centerx = WIDTH // 2
SET_PAPER.y = (HEIGHT - (_set_hh - _set_lap + SET_PAPER.h)) // 2 + _set_hh - _set_lap
SET_HEADER = pygame.Rect(0, 0, 300, _set_hh)
SET_HEADER.midbottom = (SET_PAPER.centerx, SET_PAPER.y + _set_lap)
SET_SLIDERS = {
    "bgm": pygame.Rect(SET_PAPER.x + 112, SET_PAPER.y + 81 - 16, 219, 32),
    "sfx": pygame.Rect(SET_PAPER.x + 112, SET_PAPER.y + 126 - 16, 219, 32),
}
SET_BACK = pygame.Rect(0, 0, 260, 56)
SET_BACK.center = (SET_PAPER.centerx, SET_PAPER.y + 204)


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



