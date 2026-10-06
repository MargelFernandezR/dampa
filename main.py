import pygame
import sys
import json
import os
import random

pygame.init()
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


# =====================================================================
#  ASSETS
# =====================================================================
BG = pygame.transform.scale(pygame.image.load("PIXELBGPH.png").convert(), (WIDTH, HEIGHT))
_small = pygame.transform.smoothscale(BG, (WIDTH // 14, HEIGHT // 14))
BG_BLUR = pygame.transform.smoothscale(_small, (WIDTH, HEIGHT))

LOGO_RAW = pygame.image.load("DampaLogo.png").convert_alpha()
LOGO_W = 720
LOGO_H = int(LOGO_RAW.get_height() * LOGO_W / LOGO_RAW.get_width())
LOGO = pygame.transform.smoothscale(LOGO_RAW, (LOGO_W, LOGO_H))
LOGO_POS = LOGO.get_rect(center=(WIDTH // 2, 190))

# ----- game assets -----
#   game_bg_pixel.png              -> tall cracked-floor image (scrolls down as the bands travel)
#   arm_pix-removebg-preview.png   -> the clapped hands (transparent PNG)
#   rubber_bands.png               -> the pile of rubber bands (transparent PNG)
# Keep them in the same folder as this script. Missing files get simple placeholders.
HANDS_W = 340        # width of the hands + arms picture on screen
HANDS_CUT = 0.62     # where the picture is split: hands (above) / forearms (below the wrists)


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
    """A TALL floor: the camera scrolls up it as the rubber bands fly forward."""
    if USE_BG_IMAGE:
        img = load_image("game_bg_pixel.png", alpha=False)
        if img:
            h = max(int(img.get_height() * HALF / img.get_width()), HEIGHT + 400)
            return pygame.transform.scale(img, (HALF, h))
    # clean pixel-noise concrete: no cracks, soft speckles so you can still see the floor moving
    rnd = random.Random(7)
    h = HEIGHT + 400
    small = pygame.Surface((HALF // 4 + 1, h // 4 + 1))
    for x in range(small.get_width()):
        for y in range(small.get_height()):
            v = 150 + rnd.randint(-10, 10)
            if rnd.random() < 0.04:
                v += rnd.choice((-22, 22))
            small.set_at((x, y), (v, v, v))
    surf = pygame.transform.scale(small, (small.get_width() * 4, small.get_height() * 4))
    return surf.subsurface((0, 0, HALF, h)).copy()


def make_hands():
    """returns (hands_part, arms_part). They are drawn separately so the forearms can be
    stretched during the smash and the arms always reach the bottom of the screen."""
    img = load_image("arm_pix-removebg-preview.png")
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
    img = load_image("rubber_bands.png")
    if img:
        return scaled_to_width(crop_to_content(remove_white_bg(img)), 100)
    surf = pygame.Surface((70, 70), pygame.SRCALPHA)
    rnd = random.Random(3)
    colors = [(230, 50, 50), (60, 140, 240), (250, 200, 40), (60, 200, 90), (240, 120, 200), (250, 130, 30)]
    for _ in range(45):
        r = rnd.randint(8, 14)
        pos = (35 + rnd.randint(-17, 17), 35 + rnd.randint(-17, 17))
        pygame.draw.circle(surf, rnd.choice(colors), pos, r, 2)
    return surf


FLOOR = make_floor()
FLOOR_FLIP = pygame.transform.flip(FLOOR, False, True)   # flipped copy so repeats line up
HANDS_TOP_IMG, HANDS_ARMS_IMG = make_hands()
HANDS_H = HANDS_TOP_IMG.get_height() + HANDS_ARMS_IMG.get_height()
HANDS_TOP = HEIGHT + 10 - HANDS_H      # the arms end just below the bottom edge of the screen
BANDS = make_bands()
BAND_ICON = scaled_to_width(BANDS, 44)
# ----- card images for GAME MODES screen -----
# Ilagay mo yung mga picture files sa parehong folder ng main.py
# Pangalan: karera_card.png at pogs_card.png
CARD_IMG_W = 220   # 220px lapad
CARD_IMG_H = 280   # taas ng picture

KARERA_IMG = load_image("karera_card.png", (CARD_IMG_W, CARD_IMG_H))
POGS_IMG = load_image("pogs_card.png", (CARD_IMG_W, CARD_IMG_H))

# Kung wala yung files, gumawa ng placeholder (gray background)
if KARERA_IMG is None:
    KARERA_IMG = pygame.Surface((CARD_IMG_W, CARD_IMG_H))
    KARERA_IMG.fill((150, 150, 150))  # gray

if POGS_IMG is None:
    POGS_IMG = pygame.Surface((CARD_IMG_W, CARD_IMG_H))
    POGS_IMG.fill((150, 150, 150))  # gray


# ----- fonts (swap None for a pixel .ttf to get the pixel look) -----
BIG_FONT = pygame.font.Font(None, 56)
BUTTON_FONT = pygame.font.Font(None, 52)
MID_FONT = pygame.font.Font(None, 34)
SMALL_FONT = pygame.font.Font(None, 30)
DESC_FONT = pygame.font.Font(None, 24)
HUGE_FONT = pygame.font.Font(None, 96)

# ----- colors -----
TEXT_COLOR = (255, 255, 255)
BROWN = (82, 32, 8)
LINE_BROWN = (128, 64, 24)
BEIGE = (232, 206, 160, 235)
BEIGE_DARK = (176, 149, 102, 190)
BEIGE_HOVER = (206, 176, 124, 225)
YESNO = (150, 100, 55)
YESNO_HOVER = (176, 124, 72)
HUD_COLOR = (139, 69, 19)  # brown


def panel(rect, color=BEIGE, target=None):
    target = WIN if target is None else target
    surf = pygame.Surface(rect.size, pygame.SRCALPHA)
    surf.fill(color)
    target.blit(surf, rect.topleft)


def text_center(font, text, color, center, target=None, shadow=False):
    target = WIN if target is None else target
    img = font.render(text, True, color)
    rect = img.get_rect(center=center)
    if shadow:
        target.blit(font.render(text, True, (0, 0, 0)), (rect.x + 2, rect.y + 2))
    target.blit(img, rect)


def button(rect, label, hovered, font=BUTTON_FONT):
    panel(rect, BEIGE_HOVER if hovered else BEIGE_DARK)
    text_center(font, label, BROWN, rect.center)



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

PANEL_W = 472
PANEL_X = (WIDTH - PANEL_W) // 2

SCORE_HEADER = pygame.Rect(390, 100, 180, 60)
SCORE_TABLE = pygame.Rect(390, 170, 520, 365)
SCORE_BACK = pygame.Rect(SCORE_TABLE.right - 160, 555, 160, 54)
COL_STREAK = 110
COL_BOT = 70
COL_YOU = 70
COL_GAMEMODES = 270
HEAD_ROW_H = 45
ROW_H = 40
MAX_ROWS = 20
SCROLL_SPEED = 40        # pixels per scroll
scroll_offset = 0        # current scroll position

EXIT_HEADER = pygame.Rect(PANEL_X, 215, 280, 70)
EXIT_PANEL = pygame.Rect(PANEL_X, 295, PANEL_W, 165)
EXIT_YES = pygame.Rect(PANEL_X + 22, 385, 205, 48)
EXIT_NO = pygame.Rect(PANEL_X + PANEL_W - 22 - 205, 385, 205, 48)


# =====================================================================
#  GAME MODES SCREEN LAYOUT
# =====================================================================
CARD_W, CARD_H = 260, 420
CARD_GAP = 40
CARD_Y = 140

TOTAL_CARDS_W = (CARD_W * 2) + CARD_GAP
CARD_START_X = (WIDTH - TOTAL_CARDS_W) // 2

CARD1_RECT = pygame.Rect(CARD_START_X, CARD_Y, CARD_W, CARD_H)
CARD2_RECT = pygame.Rect(CARD_START_X + CARD_W + CARD_GAP, CARD_Y, CARD_W, CARD_H)

MODE_START_W, MODE_START_H = 180, 50
MODE1_START = pygame.Rect(CARD1_RECT.centerx - MODE_START_W // 2, CARD1_RECT.bottom - 70, MODE_START_W, MODE_START_H)
MODE2_START = pygame.Rect(CARD2_RECT.centerx - MODE_START_W // 2, CARD2_RECT.bottom - 70, MODE_START_W, MODE_START_H)

MODE_BACK = pygame.Rect(WIDTH // 2 - 80, HEIGHT - 70, 160, 50)


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


#  GAME SETTINGS

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

T_IMPACT = 0.25                      # moment the hands hit the floor (seconds after smash starts)
BAND_TIME = 1.4                      # how long the bands take to slide up

HUD_LEFT = pygame.Rect(266, 20, 176, 54)
HUD_CENTER = pygame.Rect(452, 10, 382, 72)
HUD_RIGHT = pygame.Rect(842, 20, 176, 54)

END_PANEL = pygame.Rect(WIDTH // 2 - 260, 230, 520, 260)
END_AGAIN = pygame.Rect(WIDTH // 2 - 235, 400, 220, 56)
END_MENU = pygame.Rect(WIDTH // 2 + 15, 400, 220, 56)


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
        self.set_phase("meter")                                       # 1) meter first

    # ------------------------------------------------------------ input
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "menu"
            if event.key == pygame.K_SPACE and self.phase == "meter":
                self.player.lock()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.phase == "end":
            if END_AGAIN.collidepoint(event.pos):
                self.reset()
            elif END_MENU.collidepoint(event.pos):
                return "menu"
        return None

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        if self.smash_t is not None:
            self.smash_t += dt

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
    def hand_pose(self, side):
        """returns (y_offset, scale, x_jitter) for the hands"""
        st = self.smash_t
        if st is None:
            jitter = 0
            if self.phase == "timer":                 # tension: tiny shake while waiting
                jitter = random.uniform(-2, 2)
            return 0, 1.0, jitter
        strike = 45 + 50 * side.power                 # stronger meter = bigger smash
        if st < 0.15:                                 # wind-up (hands pull back)
            return 25 * ease_out(st / 0.15), 1.0, 0
        if st < T_IMPACT:                             # strike
            k = (st - 0.15) / (T_IMPACT - 0.15)
            return 25 - (25 + strike) * k, 1.0 - 0.10 * k, 0
        if st < 0.65:                                 # recover
            k = ease_in_out((st - T_IMPACT) / (0.65 - T_IMPACT))
            return -strike * (1 - k), 0.90 + 0.10 * k, 0
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

        def zone(lo, hi, color):
            pygame.draw.rect(surf, color, (bx + lo * METER_W, METER_Y, (hi - lo) * METER_W + 1, METER_H))

        red, green, white = (240, 60, 40), (60, 230, 50), (255, 255, 255)
        pygame.draw.rect(surf, (40, 10, 10), (bx - 2, METER_Y - 2, METER_W + 4, METER_H + 4))
        zone(0, 0.5 - GREEN_HALF, red)
        zone(0.5 - GREEN_HALF, 0.5 - WHITE_HALF, green)
        zone(0.5 - WHITE_HALF, 0.5 + WHITE_HALF, white)          # the white "perfect" zone
        zone(0.5 + WHITE_HALF, 0.5 + GREEN_HALF, green)
        zone(0.5 + GREEN_HALF, 1, red)

        mx = bx + side.pos * METER_W
        pygame.draw.rect(surf, (0, 0, 0), (mx - 4, METER_Y - 9, 8, METER_H + 18))
        pygame.draw.rect(surf, (255, 210, 60), (mx - 2, METER_Y - 7, 4, METER_H + 14))

        if side.locked:
            perfect = abs(side.pos - 0.5) <= WHITE_HALF
            label = "PERFECT!" if perfect else f"POWER {int(side.power * 100)}%"
            color = (255, 240, 120) if perfect else TEXT_COLOR
            text_center(SMALL_FONT, label, color, (cx, METER_Y + 30), surf, shadow=True)
        elif is_player and self.phase == "meter":
            text_center(SMALL_FONT, "[ SPACE ]  stop on the white", TEXT_COLOR,
                        (cx, METER_Y + 30), surf, shadow=True)

    def draw_side(self, side, surf, is_player):
        cx = HALF // 2
        D = self.travel(side)
        scroll = max(0.0, D - FOLLOW_AT)                         # floor moves down as the bands go far

        # the floor is a tall image repeated (every 2nd copy flipped so the seams line up)
        for k in range(int(scroll // BG_H), int((HEIGHT + scroll) // BG_H) + 1):
            tile = FLOOR if k % 2 == 0 else FLOOR_FLIP
            surf.blit(tile, (0, HEIGHT - BG_H * (k + 1) + scroll))

        # finish line: very far away, off-screen until the floor has scrolled almost all the way
        fy = int(BAND_START_Y - FINISH_DIST + scroll)
        if -30 < fy < HEIGHT:
            for i, x in enumerate(range(0, HALF, 26)):
                for row in range(2):
                    color = (255, 255, 255) if (i + row) % 2 == 0 else (20, 20, 20)
                    pygame.draw.rect(surf, color, (x, fy - 13 + row * 13, 26, 13))
            text_center(SMALL_FONT, "FINISH", TEXT_COLOR, (cx, fy + 26), surf, shadow=True)

        # rubber bands
        by = BAND_START_Y - D + scroll
        surf.blit(BANDS, BANDS.get_rect(center=(cx, by)))

        # progress bar towards the finish line
        bar = pygame.Rect(14, 110, 12, 440)
        pygame.draw.rect(surf, (20, 20, 20), bar.inflate(4, 4))
        fill = int(bar.height * clamp(D / FINISH_DIST))
        pygame.draw.rect(surf, (255, 220, 90), (bar.x, bar.bottom - fill, bar.width, fill))

        st = self.smash_t
        if st is not None and st > T_IMPACT + BAND_TIME and side.base + side.dist >= FINISH_DIST:
            text_center(BIG_FONT, "FINISHED!", (255, 240, 120), (cx, 125), surf, shadow=True)

        # hands + arms (the forearms stretch a little during the smash so they always reach the bottom)
        off, sc, jx = self.hand_pose(side)
        hw = int(HANDS_TOP_IMG.get_width() * sc)
        hh = int(HANDS_TOP_IMG.get_height() * sc)
        top = HANDS_TOP_IMG if sc == 1.0 else pygame.transform.smoothscale(HANDS_TOP_IMG, (hw, hh))
        y = HANDS_TOP + off
        wrist_y = int(y + hh - 1)
        arm_h = max(int(HANDS_ARMS_IMG.get_height() * sc), HEIGHT + 8 - wrist_y)
        if (hw, arm_h) == HANDS_ARMS_IMG.get_size():
            arms = HANDS_ARMS_IMG
        else:
            arms = pygame.transform.smoothscale(HANDS_ARMS_IMG, (hw, arm_h))
        surf.blit(arms, (int(cx + jx - hw // 2), wrist_y))
        surf.blit(top, (int(cx + jx - hw // 2), int(y)))

        # impact ring
        if st is not None and T_IMPACT <= st < T_IMPACT + 0.35:
            k = (st - T_IMPACT) / 0.35
            r = int(15 + 70 * k)
            ring = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 255, 255, int(200 * (1 - k))), (r + 3, r + 3), r, 4)
            surf.blit(ring, ring.get_rect(center=(cx, HANDS_TOP - 60)))

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

        # ===== ROUND WINS LABELS (3px gap lang) =====
        
        # ---- LEFT SIDE (BOT) ----
        # "ROUND WINS" box (taas) - 3px gap mula sa center box
        bot_label = pygame.Rect(WIDTH // 2 - 273, 10, 140, 30)
        pygame.draw.rect(WIN, HUD_COLOR, bot_label)
        text_center(SMALL_FONT, "ROUND WINS", TEXT_COLOR, bot_label.center, shadow=True)
        
        # Bot score box (ibaba) - naka-center sa label
        bot_score = pygame.Rect(WIDTH // 2 - 223, 45, 90, 45)
        pygame.draw.rect(WIN, HUD_COLOR, bot_score)
        text_center(BIG_FONT, str(self.bot_wins), TEXT_COLOR, bot_score.center, shadow=True)

        # ---- CENTER ----
        # "ROUND 1" box (gitna)
        center_box = pygame.Rect(WIDTH // 2 - 130, 10, 260, 80)
        pygame.draw.rect(WIN, HUD_COLOR, center_box)
        text_center(BIG_FONT, f"ROUND {min(self.round, ROUNDS)}", TEXT_COLOR,
                    (center_box.centerx, center_box.y + 28), shadow=True)
        text_center(DESC_FONT, self.hud_message(), TEXT_COLOR,
                    (center_box.centerx, center_box.y + 58), shadow=True)

        # ---- RIGHT SIDE (PLAYER) ----
        # "ROUND WINS" box (taas) - 3px gap mula sa center box
        player_label = pygame.Rect(WIDTH // 2 + 133, 10, 140, 30)
        pygame.draw.rect(WIN, HUD_COLOR, player_label)
        text_center(SMALL_FONT, "ROUND WINS", TEXT_COLOR, player_label.center, shadow=True)
        
        # Player score box (ibaba) - naka-center sa label
        player_score = pygame.Rect(WIDTH // 2 + 133, 45, 90, 45)
        pygame.draw.rect(WIN, HUD_COLOR, player_score)
        text_center(BIG_FONT, str(self.player_wins), TEXT_COLOR, player_score.center, shadow=True)

        if self.phase == "end":
            self.draw_end(mouse)

    def draw_end(self, mouse):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        WIN.blit(dim, (0, 0))

        panel(END_PANEL)
        title = {"win": "YOU WIN!", "loss": "YOU LOSE!", "tie": "IT'S A TIE!"}[self.final]
        text_center(HUGE_FONT, title, BROWN, (END_PANEL.centerx, END_PANEL.y + 55))
        text_center(MID_FONT, f"you {self.player_wins}/{self.bot_wins} bot", BROWN,
                    (END_PANEL.centerx, END_PANEL.y + 115))
        button(END_AGAIN, "PLAY AGAIN", END_AGAIN.collidepoint(mouse), MID_FONT)
        button(END_MENU, "MENU", END_MENU.collidepoint(mouse), MID_FONT)


# =====================================================================
#  MENU / SCORE / EXIT SCREENS
# =====================================================================
def draw_menu(mouse):
    WIN.blit(BG, (0, 0))
    WIN.blit(LOGO, LOGO_POS)
    for label, rect in MENU_BUTTONS.items():
        button(rect, label, rect.collidepoint(mouse))
    y = HEIGHT - 75
    for line in DESCRIPTION:
        text_center(DESC_FONT, line, TEXT_COLOR, (WIDTH // 2, y), shadow=True)
        y += 24


def draw_score(mouse):
    global scroll_offset
    WIN.blit(BG_BLUR, (0, 0))
    
    # SCORE header
    header_surf = pygame.Surface(SCORE_HEADER.size, pygame.SRCALPHA)
    header_surf.fill((232, 206, 160, 200))
    WIN.blit(header_surf, SCORE_HEADER.topleft)
    text_center(BIG_FONT, "SCORE", BROWN, SCORE_HEADER.center)

    # Table
    table_surf = pygame.Surface(SCORE_TABLE.size, pygame.SRCALPHA)
    table_surf.fill((232, 206, 160, 180))
    WIN.blit(table_surf, SCORE_TABLE.topleft)
    
    t = SCORE_TABLE
    
    # Column x positions
    col1_x = t.x + COL_STREAK // 2
    col2_x = t.x + COL_STREAK + COL_BOT // 2
    col3_x = t.x + COL_STREAK + COL_BOT + COL_YOU // 2
    col4_x = t.x + COL_STREAK + COL_BOT + COL_YOU + COL_GAMEMODES // 2
    
    # ===== HEADER ROW (HINDI GUMAGALAW) =====
    text_center(SMALL_FONT, "STREAK", BROWN, (col1_x, t.y + HEAD_ROW_H // 2))
    text_center(SMALL_FONT, "BOT", BROWN, (col2_x, t.y + HEAD_ROW_H // 2))
    text_center(SMALL_FONT, "YOU", BROWN, (col3_x, t.y + HEAD_ROW_H // 2))
    text_center(SMALL_FONT, "GAMEMODES", BROWN, (col4_x, t.y + HEAD_ROW_H // 2))
    
    pygame.draw.line(WIN, LINE_BROWN, (t.x, t.y + HEAD_ROW_H), (t.right, t.y + HEAD_ROW_H), 2)
    
    v1 = t.x + COL_STREAK
    v2 = v1 + COL_BOT
    v3 = v2 + COL_YOU
    pygame.draw.line(WIN, LINE_BROWN, (v1, t.y + 6), (v1, t.y + HEAD_ROW_H), 2)
    pygame.draw.line(WIN, LINE_BROWN, (v2, t.y + 6), (v2, t.y + HEAD_ROW_H), 2)
    pygame.draw.line(WIN, LINE_BROWN, (v3, t.y + 6), (v3, t.y + HEAD_ROW_H), 2)

    # ===== SCROLLABLE LIST (Scores lang) =====
    clip_rect = pygame.Rect(t.x, t.y + HEAD_ROW_H, t.width, t.height - HEAD_ROW_H)
    old_clip = WIN.get_clip()
    WIN.set_clip(clip_rect)
    
    for i, row in enumerate(SCORES[:MAX_ROWS]):
        result, bot, player, mode = row
        cy = t.y + HEAD_ROW_H + i * ROW_H + ROW_H // 2 - scroll_offset
        
        if cy < t.y + HEAD_ROW_H - ROW_H or cy > t.bottom + ROW_H:
            continue
        
        color = (60, 180, 60) if result == "win" else (220, 60, 60) if result == "defeat" else BROWN
        text_center(MID_FONT, result, color, (col1_x, cy))
        text_center(MID_FONT, str(bot), BROWN, (col2_x, cy))
        text_center(MID_FONT, str(player), BROWN, (col3_x, cy))
        text_center(SMALL_FONT, mode, BROWN, (col4_x, cy))
    
    for i in range(MAX_ROWS):
        y = t.y + HEAD_ROW_H + (i + 1) * ROW_H - scroll_offset
        if t.y + HEAD_ROW_H < y < t.bottom:
            pygame.draw.line(WIN, LINE_BROWN, (t.x, y), (t.right, y), 2)
    
    pygame.draw.line(WIN, LINE_BROWN, (v1, t.y + HEAD_ROW_H), (v1, t.bottom), 2)
    pygame.draw.line(WIN, LINE_BROWN, (v2, t.y + HEAD_ROW_H), (v2, t.bottom), 2)
    pygame.draw.line(WIN, LINE_BROWN, (v3, t.y + HEAD_ROW_H), (v3, t.bottom), 2)
    
    WIN.set_clip(old_clip)

    button(SCORE_BACK, "BACK", SCORE_BACK.collidepoint(mouse), MID_FONT)


def draw_exit(mouse):
    WIN.blit(BG_BLUR, (0, 0))
    
    # EXIT header - transparent slight
    header_surf = pygame.Surface(EXIT_HEADER.size, pygame.SRCALPHA)
    header_surf.fill((232, 206, 160, 200))  # alpha 200
    WIN.blit(header_surf, EXIT_HEADER.topleft)
    text_center(BIG_FONT, "EXIT", BROWN, EXIT_HEADER.center)

    # EXIT panel - transparent slight
    panel_surf = pygame.Surface(EXIT_PANEL.size, pygame.SRCALPHA)
    panel_surf.fill((232, 206, 160, 180))  # alpha 180
    WIN.blit(panel_surf, EXIT_PANEL.topleft)
    
    text_center(MID_FONT, "are you sure you", BROWN, (EXIT_PANEL.centerx, EXIT_PANEL.y + 40))
    text_center(MID_FONT, "want to quit?", BROWN, (EXIT_PANEL.centerx, EXIT_PANEL.y + 68))

    for rect, label in ((EXIT_YES, "yes"), (EXIT_NO, "no")):
        pygame.draw.rect(WIN, YESNO_HOVER if rect.collidepoint(mouse) else YESNO, rect)
        text_center(MID_FONT, label, (255, 235, 200), rect.center)
    
    # WALANG BACK BUTTON


def draw_gamemodes(mouse):
    WIN.blit(BG_BLUR, (0, 0))
    
    # ===== CARD 1: DAMPA KARERA =====
    # Brown border
    pygame.draw.rect(WIN, (139, 90, 43), CARD1_RECT)
    # Beige inner background
    inner1 = CARD1_RECT.inflate(-16, -16)
    panel(inner1, BEIGE)
    
    # Picture sa loob ng card
    img1_rect = KARERA_IMG.get_rect(center=(CARD1_RECT.centerx, CARD1_RECT.y + CARD_IMG_H // 2 + 30))
    WIN.blit(KARERA_IMG, img1_rect)
    
    # Label at START button
    text_center(MID_FONT, "DAMPA KARERA", BROWN, (CARD1_RECT.centerx, CARD1_RECT.bottom - 90))
    button(MODE1_START, "START", MODE1_START.collidepoint(mouse), MID_FONT)

    # ===== CARD 2: DAMPA POGS =====
    # Brown border
    pygame.draw.rect(WIN, (139, 90, 43), CARD2_RECT)
    # Beige inner background
    inner2 = CARD2_RECT.inflate(-16, -16)
    panel(inner2, BEIGE)
    
    # Picture sa loob ng card
    img2_rect = POGS_IMG.get_rect(center=(CARD2_RECT.centerx, CARD2_RECT.y + CARD_IMG_H // 2 + 30))
    WIN.blit(POGS_IMG, img2_rect)
    
    # Label at START button
    text_center(MID_FONT, "DAMPA POGS", BROWN, (CARD2_RECT.centerx, CARD2_RECT.bottom - 90))
    button(MODE2_START, "START", MODE2_START.collidepoint(mouse), MID_FONT)

    # ===== BACK BUTTON =====
    button(MODE_BACK, "BACK", MODE_BACK.collidepoint(mouse), MID_FONT)

# =====================================================================
#  MAIN LOOP
# =====================================================================
def main():
    screen = "menu"          # "menu" | "score" | "exit" | "gamemodes" | "game"
    game = None
    run = True

    while run:
        dt = min(CLOCK.tick(60) / 1000.0, 0.05)
        mouse = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
                continue

            if screen == "game":
                if game.handle_event(event) == "menu":
                    screen = "menu"
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if screen == "menu":
                    screen = "exit"
                elif screen == "gamemodes":
                    screen = "menu"
                else:
                    screen = "menu"
                                # Scroll event para sa SCORE screen
            if screen == "score" and event.type == pygame.MOUSEWHEEL:
                global scroll_offset
                scroll_offset -= event.y * SCROLL_SPEED
                # Limit: 0 hanggang (MAX_ROWS * ROW_H) - table height
                max_scroll = max(0, MAX_ROWS * ROW_H - (SCORE_TABLE.height - HEAD_ROW_H))
                scroll_offset = max(0, min(scroll_offset, max_scroll))

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if screen == "menu":
                    if MENU_BUTTONS["GAMEMODES"].collidepoint(pos):
                        screen = "gamemodes"
                    elif MENU_BUTTONS["SCORE"].collidepoint(pos):
                        screen = "score"
                    elif MENU_BUTTONS["EXIT"].collidepoint(pos):
                        screen = "exit"
                elif screen == "gamemodes":
                    if MODE1_START.collidepoint(pos):
                        game = Game()
                        screen = "game"
                    elif MODE2_START.collidepoint(pos):
                        print("Pogs game is not yet implemented!")
                    elif MODE_BACK.collidepoint(pos):
                        screen = "menu"
                elif screen == "score":
                    if SCORE_BACK.collidepoint(pos):
                        screen = "menu"
                elif screen == "exit":
                    if EXIT_YES.collidepoint(pos):
                        run = False
                    elif EXIT_NO.collidepoint(pos):
                        screen = "menu"

        if screen == "menu":
            draw_menu(mouse)
        elif screen == "score":
            draw_score(mouse)
        elif screen == "exit":
            draw_exit(mouse)
        elif screen == "gamemodes":
            draw_gamemodes(mouse)
        else:
            game.update(dt)
            game.draw(mouse)

        pygame.display.update()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()