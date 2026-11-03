# pyright: reportUndefinedVariable=false
# pyright: reportUndefinedVariable=false
if __name__ == "__main__" and not globals().get("_GAME_PARTS_LOADING"):
    from pathlib import Path as _Path
    import runpy as _runpy
    _runpy.run_path(str(_Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
    raise SystemExit

#  SCORE DATA

SCORE_FILE = "../scores.json"
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

        # finish line: a chalk line drawn on the floor
        fy = int(BAND_START_Y - FINISH_DIST + scroll)
        if -30 < fy < HEIGHT:
            surf.blit(CHALK_LINE, (0, fy - CHALK_LINE.get_height() // 2))
            surf.blit(CHALK_TEXT, CHALK_TEXT.get_rect(center=(cx, fy + 28)))

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
        hud_pill(WIN, HUD_L_LABEL, "PLAYER1" if self.pvp else "ROUND WINS")
        hud_pill(WIN, pygame.Rect(HUD_L_VALUE.right - 140, HUD_L_VALUE.y, 140, 34), f"SCORE:{self.bot_wins}")
        hud_pill(WIN, HUD_ROUND, f"ROUND {n}", TITLE_FONT)
        hud_pill(WIN, HUD_R_LABEL, "PLAYER2" if self.pvp else "ROUND WINS")
        hud_pill(WIN, pygame.Rect(HUD_R_VALUE.x, HUD_R_VALUE.y, 140, 34), f"SCORE:{self.player_wins}")

        # timer pill (the pink-circle spot under the ROUND pill)
        timer_txt = ""
        if self.phase == "meter" and not self.player.locked:
            timer_txt = f"TIME: {int(math.ceil(max(0.0, METER_TIMEOUT - self.t)))}"
        hud_pill(WIN, HUD_TIMER, timer_txt)
        draw_match_hud(WIN, self.pvp, "karera")
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
