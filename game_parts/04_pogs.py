# pyright: reportUndefinedVariable=false
# pyright: reportUndefinedVariable=false
if __name__ == "__main__" and not globals().get("_GAME_PARTS_LOADING"):
    from pathlib import Path as _Path
    import runpy as _runpy
    _runpy.run_path(str(_Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
    raise SystemExit


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

# ---- Dampa Pogs HUD layout (gold pills, copied from the Canva mockup) ----
#     (pogs-only: the Karera's HUD_ROUND / HUD_TIMER in 02_assets_ui are left untouched)
HUD_BOT_NAME    = pygame.Rect(CX - 382, 10, 180, 36)
HUD_BOT_POGS    = pygame.Rect(CX - 382, 50, 180, 36)
HUD_PG_ROUND    = pygame.Rect(CX - 190, 10, 380, 76)
HUD_PG_TIMER    = pygame.Rect(CX - 70, 92, 140, 28)
HUD_PLAYER_NAME = pygame.Rect(CX + 202, 10, 180, 36)
HUD_PLAYER_POGS = pygame.Rect(CX + 202, 50, 180, 36)
HUD_STACK       = pygame.Rect(WIDTH - 340, HEIGHT - 84, 320, 64)
BAR_W, BAR_H, BAR_Y = 220, 18, 530    # power bar (sits beside the hands)
BAR_GAP = 160                         # space between the bar and the hands

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

def pog_tail_factor(T):
    """exact na layo ng bounces + skid pagkatapos ng unang arc,
    bilang fraction ng unang arc. Nakadepende ito sa flight time T."""
    v = 1.0
    s = 0.0
    for d, _h in POG_BOUNCES:
        s += d * v
        v *= POG_BOUNCE_DAMP
    return s + (POG_SLIDE_T / max(1e-6, T)) * v

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
                self.on_finish(p2, p1, "DAMPA POGS", result=self.final)
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
        for k in range(flips):
            ang = random.uniform(0, math.tau)
            rad = random.uniform(0.0, 1.0) ** 1.2
            travel = (110 + 440 * rad) * spread             # layo ng final resting spot
            if random.random() < 0.22:                      # ilang pog, malapit lang tumalbog
                travel *= random.uniform(0.30, 0.55)
            rx = clamp(CX + math.cos(ang) * travel, 255, 1045)
            ry = clamp(CY + math.sin(ang) * travel * 0.62, 110, 495)
            rx, ry = _out_of_hands(rx, ry)                  # huwag sa ibabaw ng kamay
            T = random.uniform(*POG_FLIGHT_T)
            sx = CX + random.uniform(-5, 5)                 # tunay na simula (may jitter)
            sy = CY - random.uniform(0, 10)
            K = 1.0 + pog_tail_factor(T)                    # exact: rest = start + (ex-start)*K
            ex = clamp(sx + (rx - sx) / K, 230, 1070)       # dulo ng unang arc
            ey = clamp(sy + (ry - sy) / K, 95, 560)
            f = {
                "sx": sx,
                "sy": sy,
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
                K = 1.0 + pog_tail_factor(f["T"])
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
        avoid = [pygame.Rect(CX - 390, 0, 780, 130),            # top pills (BOT / ROUND / TIMER / PLAYER)
                 HUD_STACK.inflate(20, 20),                      # STACK pill
                 pygame.Rect(150, 480, 270, 140),                # player power bar
                 pygame.Rect(880, 480, 270, 140),                # bot power bar
                 pygame.Rect(CX - 250, 115, 500, 110),           # big messages (PERFECT POWER! etc.)
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

    def pill(self, surf, rect, text, font=None):
        """gold pixel pill (same look as the menu buttons) with centered dark-brown text"""
        font = font or self.f_hud
        img = btn_surface(rect.w, rect.h, "gold")
        surf.blit(img, img.get_rect(center=rect.center))
        self.text(surf, font, text, BTN_PAL["gold"][0], rect.center, shadow=False)

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

    def draw_bar(self, surf, side):
        """power bar: YOU / BOT label on top, red bar, green fill, blinking sweet-spot box"""
        m = self.meter
        w, h, y = BAR_W, BAR_H, BAR_Y
        x = HAND_X[side] - BAR_GAP - w if side == "player" else HAND_X[side] + BAR_GAP
        if self.pvp:
            self.text(surf, self.f_mid, "P1" if side == "player" else "P2", WHITE, (x + w // 2, y - 22))
        else:
            self.text(surf, self.f_mid, "YOU" if side == "player" else "BOT", WHITE, (x + w // 2, y - 22))
        pygame.draw.rect(surf, (0, 0, 0), (x - 3, y - 3, w + 6, h + 6), border_radius=4)
        pygame.draw.rect(surf, (235, 60, 40), (x, y, w, h))                  # red = empty part
        fill = int(w * clamp(m.pos))
        if fill > 0:
            col = (255, 140, 30) if m.pos > 0.95 else (60, 230, 50)          # orange = overcharge
            pygame.draw.rect(surf, col, (x, y, fill, h))
        # the sweet spot (80-90%) - blinks while the player is aiming
        blink = self.turn == "player" and self.phase == "meter" and int(self.t * 5) % 2 == 0
        pygame.draw.rect(surf, WHITE if blink else (255, 215, 60),
                         (x + int(IDEAL_LO * w) - 1, y - 4, int((IDEAL_HI - IDEAL_LO) * w) + 2, h + 8), 2)
        pygame.draw.line(surf, WHITE, (x + fill, y - 5), (x + fill, y + h + 5), 3)
        self.text(surf, self.f_small, f"{int(m.pos * 100)}%", WHITE, (x + w // 2, y + h + 18))
        if self.turn == "player" and self.phase == "meter":
            self.text(surf, self.f_small, "[SPACE] stop in the box!", WHITE, (x + w // 2, y + h + 40))
        elif self.pvp and self.phase == "meter":
            self.text(surf, self.f_small, "[Q] stop in the box!" if self.turn == "player1" else "[P] stop in the box!",
                      WHITE, (x + w // 2, y + h + 40))

    def draw_hud(self, surf):
        def pogs_txt(n):
            return f"{n} POG" if n == 1 else f"{n} POGS"

        if self.pvp:                       # PvP: P1 left, P2 right (same layout as the mockup)
            l_name, l_pogs = "P1", self.pogs["player1"]
            r_name, r_pogs = "P2", self.pogs["player2"]
        else:
            l_name, l_pogs = "BOT", self.pogs["bot"]
            r_name, r_pogs = "PLAYER", self.pogs["player"]

        # top-left: BOT / P1
        self.pill(surf, HUD_BOT_NAME, l_name)
        self.pill(surf, HUD_BOT_POGS, pogs_txt(l_pogs))
        # top-right: PLAYER / P2
        self.pill(surf, HUD_PLAYER_NAME, r_name)
        self.pill(surf, HUD_PLAYER_POGS, pogs_txt(r_pogs))
        # top-center: ROUND + TIMER
        self.pill(surf, HUD_PG_ROUND, f"ROUND {self.round}", self.f_big)
        if self.phase == "meter":
            timer_txt = f"TIMER: {int(math.ceil(max(0.0, TURN_TIME - self.t)))}"
        else:
            timer_txt = "TIMER"
        self.pill(surf, HUD_PG_TIMER, timer_txt, self.f_small)
        # bottom-right: STACK
        self.pill(surf, HUD_STACK, f"STACK: {self.stack}", self.f_big)
        # power bar beside the hands of whoever is playing
        if self.phase not in ("end", "transition"):
            side = "player" if self.turn in ("player", "player1") else "bot"
            self.draw_bar(surf, side)

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
