# pyright: reportUndefinedVariable=false
# pyright: reportUndefinedVariable=false
if __name__ == "__main__" and not globals().get("_GAME_PARTS_LOADING"):
    from pathlib import Path as _Path
    import runpy as _runpy
    _runpy.run_path(str(_Path(__file__).resolve().parents[1] / "main.py"), run_name="__main__")
    raise SystemExit

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


INVENTORY_FILE = "../inventory.json"
INVENTORY_DEFAULT = {
    "player1": {"goma": 100, "pogs": 100},
    "player2": {"goma": 100, "pogs": 100},
}
BET_INFO_FONT = PixelFont(18)


def load_inventory():
    if not os.path.exists(INVENTORY_FILE):
        return {player: values.copy() for player, values in INVENTORY_DEFAULT.items()}
    try:
        with open(INVENTORY_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"[dampa] could not load inventory '{INVENTORY_FILE}': {e}")
        return {player: values.copy() for player, values in INVENTORY_DEFAULT.items()}

    inventory = {}
    for player, defaults in INVENTORY_DEFAULT.items():
        inventory[player] = {}
        player_data = data.get(player, {}) if isinstance(data, dict) else {}
        if not isinstance(player_data, dict):
            print(f"[dampa] invalid inventory entry for {player}; using defaults")
            player_data = {}
        for resource, default in defaults.items():
            amount = player_data.get(resource, default)
            if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                print(f"[dampa] invalid {player} {resource} balance; using {default}")
                amount = default
            inventory[player][resource] = amount
    return inventory


def save_inventory():
    try:
        with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(INVENTORY, f)
    except OSError as e:
        print(f"[dampa] could not save inventory '{INVENTORY_FILE}': {e}")
        return False
    return True


INVENTORY = load_inventory()


def draw_match_hud(target, pvp, mode):
    sides = (("player1", "P1", 8), ("player2", "P2", WIDTH - 178)) if pvp else \
        (("player2", "YOU", 8),)
    for account, label, x in sides:
        for row, name in enumerate(("goma", "pogs")):
            rect = pygame.Rect(x, 8 + row * 38, 170, 32)
            hud_pill(target, rect, f"{label} {name.upper()}: {INVENTORY[account][name]}", DESC_FONT)

    resource_label = "GOMA" if mode == "karera" else "POGS"
    if mode == "karera":
        x, y = WIDTH // 2 - 74, HEIGHT - 78
    else:
        x, y = WIDTH - 168, HEIGHT - 78
    pot_rect = pygame.Rect(x, y, 148, 34)
    bet_rect = pygame.Rect(x, y + 38, 148, 34)
    hud_pill(target, pot_rect, f"{MATCH_BET['total']} {resource_label}", SMALL_FONT)
    hud_pill(target, bet_rect, "BET", SMALL_FONT)


def draw_bet_popup(mouse, mode, pvp, amounts, submitted):
    resource = "goma" if mode == "karera" else "pogs"
    resource_label = resource.upper()
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((0, 0, 0, 115))
    WIN.blit(veil, (0, 0))
    paper_box(BET_PANEL)
    hud_pill(WIN, BET_HEADER, "PLACE A BET", BIG_FONT)

    labels = ("PLAYER 1", "PLAYER 2") if pvp else ("BOT (MATCH)", "PLAYER")
    accounts = ("player1", "player2") if pvp else (None, "player2")
    for i, (label, account) in enumerate(zip(labels, accounts)):
        hud_pill(WIN, BET_PLAYER_RECTS[i], label, SMALL_FONT)
        if account:
            balance_text = f"BALANCE: {INVENTORY[account][resource]} {resource_label}"
        else:
            balance_text = "AUTO MATCH"
        text_center(BET_INFO_FONT, balance_text, BROWN,
                    (BET_AMOUNT_RECTS[i].centerx, BET_AMOUNT_RECTS[i].top - 12))
        hud_box(WIN, BET_AMOUNT_RECTS[i], (128, 69, 27))
        shown_amount = amounts[i] if pvp or i == 1 else amounts[1]
        text_center(TITLE_FONT, str(shown_amount), WHITE, BET_AMOUNT_RECTS[i].center)
        if not pvp and i == 0:
            button(BET_SUBMIT_RECTS[i], "AUTO MATCH", False, DESC_FONT)
            continue
        is_locked = submitted[i]
        button(BET_MINUS_RECTS[i], "-", not is_locked and BET_MINUS_RECTS[i].collidepoint(mouse))
        button(BET_PLUS_RECTS[i], "+", not is_locked and BET_PLUS_RECTS[i].collidepoint(mouse))
        button(BET_SUBMIT_RECTS[i], "SUBMITTED" if is_locked else "SUBMIT",
               not is_locked and BET_SUBMIT_RECTS[i].collidepoint(mouse), DESC_FONT)

    button(BET_BACK, "BACK", BET_BACK.collidepoint(mouse))
    ready = all(submitted) if pvp else submitted[1]
    button(BET_START, "START", ready and BET_START.collidepoint(mouse))
    if ready:
        total = sum(amounts) if pvp else amounts[1] * 2
        text_center(DESC_FONT, f"TOTAL POT: {total} {resource_label}", BROWN,
                    (BET_PANEL.centerx, BET_PANEL.bottom - 74))
    elif pvp and submitted[0]:
        text_center(DESC_FONT, "PASS TO PLAYER 2 TO SUBMIT", BROWN,
                    (BET_PANEL.centerx, BET_PANEL.bottom - 74))
    else:
        text_center(DESC_FONT, "SUBMIT YOUR BET TO CONTINUE", BROWN,
                    (BET_PANEL.centerx, BET_PANEL.bottom - 74))
    draw_notice((WIDTH // 2, HEIGHT - 26))


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
    draw_gear(GEAR_MENU, "menu", mouse)                      # settings gear (right of EXIT)
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
    TB = SCORE_TB

    # pink paper board (your score_boarder.png)
    paper = ui_img("score_paper", SCORE_TABLE.size)
    if paper is not None:
        WIN.blit(paper, SCORE_TABLE.topleft)
    else:
        paper_box(SCORE_TABLE)

    # gold SCORE pill, top-left
    hud_pill(WIN, SCORE_SIGN, "SCORE", BIG_FONT)

    x0, uw = TB.x, TB.w
    xr = x0 + uw
    GREEN_TXT, RED_TXT = (0, 160, 40), (255, 70, 70)
    MODE_SHORT = {"DAMPA KARERA": "GOMA", "DAMPA POGS": "POGS"}   # change "GOMA" to "KARERA" if you prefer

    # 6 columns: STREAK | score | name | score | name | GAME MODES
    cw = [int(uw * 0.25), int(uw * 0.05), int(uw * 0.27), int(uw * 0.05), int(uw * 0.24)]
    cw.append(uw - sum(cw))
    edges = [x0 + sum(cw[:i]) for i in range(7)]
    cx = [edges[i] + cw[i] // 2 for i in range(6)]

    def fit(text, col_w, color, center):
        font = SMALL_FONT
        if font.render(text, True, color).get_width() > col_w - 8:
            font = DESC_FONT
        text_center(font, text, color, center)

    # cream sheet
    pygame.draw.rect(WIN, (250, 238, 226), TB)

    # header (does not scroll)
    hy = TB.y + HEAD_ROW_H // 2
    text_center(SMALL_FONT, "STREAK", BROWN, (cx[0], hy))
    text_center(SMALL_FONT, "ENEMYMODE", BROWN, ((edges[1] + edges[5]) // 2, hy))
    text_center(DESC_FONT, "GAME", BROWN, (cx[5], hy - 10))
    text_center(DESC_FONT, "MODES", BROWN, (cx[5], hy + 10))
    pygame.draw.line(WIN, LINE_BLUE, (x0, TB.y + HEAD_ROW_H), (xr, TB.y + HEAD_ROW_H), 2)

    # vertical lines: the two outer ones go through the header, the inner three start below it
    for v in (edges[1], edges[5]):
        pygame.draw.line(WIN, LINE_BLUE, (v, TB.y), (v, TB.bottom), 2)
    for v in (edges[2], edges[3], edges[4]):
        pygame.draw.line(WIN, LINE_BLUE, (v, TB.y + HEAD_ROW_H), (v, TB.bottom), 2)

    # scrollable rows
    old_clip = WIN.get_clip()
    WIN.set_clip(pygame.Rect(x0, TB.y + HEAD_ROW_H + 1, uw, TB.h - HEAD_ROW_H - 1))

    for i, row in enumerate(SCORES[:MAX_ROWS]):
        if len(row) != 4:
            continue
        result, left, right, mode = row
        cy = TB.y + HEAD_ROW_H + i * ROW_H + ROW_H // 2 - scroll_offset
        line_y = TB.y + HEAD_ROW_H + (i + 1) * ROW_H - scroll_offset
        pygame.draw.line(WIN, LINE_BLUE, (x0, line_y), (xr, line_y), 2)
        if cy < TB.y + HEAD_ROW_H - ROW_H or cy > TB.bottom + ROW_H:
            continue

        res = str(result).lower()
        if res in ("p1", "p2", "ptie"):                  # PLAYER VS PLAYER
            left_name, right_name = "PLAYER1", "PLAYER2"
            res_txt = {"p1": "PLAYER1 WIN", "p2": "PLAYER2 WIN", "ptie": "P1 TIE P2"}[res]
            color = BROWN if res == "ptie" else GREEN_TXT
        else:                                            # PLAYER VS BOT
            left_name, right_name = "BOT", "PLAYER"
            res_txt = {"win": "WIN", "defeat": "DEFEAT", "tie": "TIE"}.get(res, res.upper())
            color = GREEN_TXT if res == "win" else RED_TXT if res == "defeat" else BROWN

        fit(res_txt, cw[0], color, (cx[0], cy))
        text_center(SMALL_FONT, str(left), BROWN, (cx[1], cy))
        text_center(DESC_FONT, left_name, BROWN, (cx[2], cy))
        text_center(SMALL_FONT, str(right), BROWN, (cx[3], cy))
        text_center(DESC_FONT, right_name, BROWN, (cx[4], cy))
        fit(MODE_SHORT.get(str(mode).upper(), "GOMA"), cw[5], BROWN, (cx[5], cy))

    WIN.set_clip(old_clip)

    # little brown scroll thumb on the right edge (only when there are more rows than fit)
    content_h = len(SCORES[:MAX_ROWS]) * ROW_H
    view_h = TB.h - HEAD_ROW_H
    if content_h > view_h:
        track_y, track_h = TB.y + 6, TB.h - 12
        th = max(30, int(track_h * view_h / content_h))
        max_scroll = content_h - view_h
        ty = track_y + int((track_h - th) * scroll_offset / max_scroll)
        pygame.draw.rect(WIN, (125, 85, 70), (TB.right - 4, ty, 8, th), border_radius=3)

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
#  SETTINGS GEAR  (hover = grows + turns + brightens, click = squash + snap-turn,
#                  mouse pointer turns into a hand)
# ---------------------------------------------------------------------
GEAR_FILES = ["settings_logo.png", "settings_logo.png", "settings_logo.png", "settings_logo.png",
              "settings_logo.png", "settings_logo.png", "settings_logo.png"]   # put YOUR file name first
_GEAR = {}
GEAR_DOWN = [None]
GEAR_ANIM = {}
HAND_HOT = [False]
_CUR = [False]
SET_DRAG = [None]


def gear_raw():
    if "img" not in _GEAR:
        img = None
        fname = find_file(GEAR_FILES)
        if fname:
            pic = load_image(fname)
            if pic is not None:
                img = crop_to_content(pic)
        if img is None:                                   # drawn fallback
            img = pygame.Surface((96, 96), pygame.SRCALPHA)
            c = (48, 48)
            pygame.draw.circle(img, (70, 28, 8), c, 46)
            pygame.draw.circle(img, (226, 128, 36), c, 43)
            pygame.draw.circle(img, (250, 196, 64), c, 36)
            for k in range(8):
                a = k * math.pi / 4
                pygame.draw.circle(img, (255, 244, 214), (int(48 + math.cos(a) * 21), int(48 + math.sin(a) * 21)), 7)
            pygame.draw.circle(img, (255, 244, 214), c, 20)
            pygame.draw.circle(img, (226, 128, 36), c, 9)
        _GEAR["img"] = img
    return _GEAR["img"]


def draw_gear(rect, tag, mouse):
    hov = rect.collidepoint(mouse)
    a = hover_amt(("gear", tag), hov)
    if hov:
        HAND_HOT[0] = True
    pressed = GEAR_DOWN[0] == tag and hov
    p = GEAR_ANIM.get(tag, 0.0)
    p += ((1.0 if pressed else 0.0) - p) * min(1.0, FX_DT[0] * 24)
    GEAR_ANIM[tag] = p

    scale = 1.0 + 0.14 * a - 0.24 * p                     # hover grows, click squashes
    base = gear_raw()
    w = max(8, int(rect.w * scale))
    h = max(8, int(w * base.get_height() / base.get_width()))
    img = pygame.transform.smoothscale(base, (w, h))
    ang = -(45.0 * a + 70.0 * p)                          # hover turns the cog, click snaps it further
    if abs(ang) > 0.5:
        img = pygame.transform.rotozoom(img, ang, 1.0)
    if a > 0.02:                                          # brighter on hover
        img = img.copy()
        g = int(55 * a)
        img.fill((g, g, g, 0), special_flags=pygame.BLEND_RGB_ADD)
    sh = silhouette(img, 90)
    WIN.blit(sh, sh.get_rect(center=(rect.centerx + 3, rect.centery + 4)))
    WIN.blit(img, img.get_rect(center=rect.center))


def update_cursor(hand):
    if _CUR[0] != hand:
        _CUR[0] = hand
        try:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND if hand else pygame.SYSTEM_CURSOR_ARROW)
        except (pygame.error, AttributeError):
            pass


# ---------------------------------------------------------------------
#  SETTINGS SCREEN
# ---------------------------------------------------------------------
def _slider_lohi(r):
    return r.x + 22, r.right - 22


def _slider_value(name, x):
    lo, hi = _slider_lohi(SET_SLIDERS[name])
    return clamp((x - lo) / float(hi - lo))


def draw_slider(r, value, hot):
    img = ui_img("button", r.size)
    if img is not None:
        WIN.blit(img, r.topleft)
    else:
        s = btn_surface(r.w, r.h, "gold")
        WIN.blit(s, s.get_rect(center=r.center))
    g = pygame.Rect(r.x + 14, 0, r.w - 28, 9)
    g.centery = r.centery
    pygame.draw.rect(WIN, (52, 44, 44), g, border_radius=5)
    pygame.draw.rect(WIN, (30, 22, 20), g, 2, border_radius=5)
    lo, hi = _slider_lohi(r)
    kx, ky = int(lo + (hi - lo) * value), r.centery
    rad = 12 if hot else 11
    pygame.draw.circle(WIN, (60, 30, 20), (kx + 2, ky + 3), rad)
    pygame.draw.circle(WIN, (70, 28, 8), (kx, ky), rad)
    pygame.draw.circle(WIN, (252, 236, 200), (kx, ky), rad - 2)
    pygame.draw.circle(WIN, (255, 252, 240), (kx - 3, ky - 3), 3)


def draw_settings(mouse, bg=None):
    if bg is None:
        WIN.blit(BG_BLUR, (0, 0))
    else:
        backdrop(bg)
    paper = ui_img("pause_panel", SET_PAPER.size)
    if paper is not None:
        WIN.blit(paper, SET_PAPER.topleft)
    else:
        paper_box(SET_PAPER)
    banner = ui_img("button", SET_HEADER.size)
    if banner is not None:
        WIN.blit(banner, SET_HEADER.topleft)
    else:
        s = btn_surface(SET_HEADER.w, SET_HEADER.h, "gold")
        WIN.blit(s, s.get_rect(center=SET_HEADER.center))
    text_center(BIG_FONT, "SETTINGS", BTN_PAL["gold"][0], SET_HEADER.center)

    for name, label in (("bgm", "BGM"), ("sfx", "SFX")):
        r = SET_SLIDERS[name]
        img = MID_FONT.render(label, True, BROWN)
        WIN.blit(img, img.get_rect(midleft=(SET_PAPER.x + int(SET_PAPER.w * 0.09), r.centery)))
        hot = SET_DRAG[0] == name or r.inflate(0, 16).collidepoint(mouse)
        if hot:
            HAND_HOT[0] = True
        draw_slider(r, VOL[name], hot)
    button(SET_BACK, "BACK", SET_BACK.collidepoint(mouse), MID_FONT, key="set_back")


def settings_event(event):
    """returns 'back' when the settings should close"""
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        save_settings()
        return "back"
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for name, r in SET_SLIDERS.items():
            if r.inflate(0, 16).collidepoint(event.pos):
                SET_DRAG[0] = name
                VOL[name] = _slider_value(name, event.pos[0])
                apply_volumes()
                return None
        if SET_BACK.collidepoint(event.pos):
            play("click")
            save_settings()
            return "back"
    elif event.type == pygame.MOUSEMOTION and SET_DRAG[0]:
        VOL[SET_DRAG[0]] = _slider_value(SET_DRAG[0], event.pos[0])
        apply_volumes()
    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and SET_DRAG[0]:
        if SET_DRAG[0] == "sfx":
            play("click")                      # let the player hear the new SFX volume
        SET_DRAG[0] = None
        save_settings()
    return None


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
    elif view == "settings":
        draw_settings(mouse, snap)
    else:
        backdrop(snap)
        pic = ui_img("pause_panel", PAUSE_PANEL.size)
        if pic is not None:
            WIN.blit(pic, PAUSE_PANEL.topleft)                        # YOUR pause panel picture
        else:
            paper_box(PAUSE_PANEL)
        for name, r in PAUSE_BUTTONS.items():
            button(r, name, r.collidepoint(mouse), MID_FONT)
        draw_gear(GEAR_PAUSE, "pause", mouse)


def scroll_scores(dy):
    global scroll_offset
    scroll_offset -= dy * SCROLL_SPEED
    max_scroll = max(0, len(SCORES[:MAX_ROWS]) * ROW_H - (SCORE_TB.height - HEAD_ROW_H))
    scroll_offset = max(0, min(scroll_offset, max_scroll))


# =====================================================================
#  OPENING INTRO  (the first thing you see when the game starts)
#  black screen -> the DAMPA letters fade in one by one -> menu + the home page music starts.
#  Click or press any key to skip it.
# =====================================================================
INTRO_PRE = 0.4          # black screen before the DAMPA logo appears
INTRO_DAMPA_IN = 1.1
INTRO_DAMPA_HOLD = 0.6
MENU_REVEAL = 1.2
LETTER_STAGGER = 0.14
T_DAMPA = INTRO_PRE
INTRO_TOTAL = T_DAMPA + INTRO_DAMPA_IN + INTRO_DAMPA_HOLD


def draw_intro(t):
    WIN.fill((0, 0, 0))
    if t < T_DAMPA:
        return
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


# =====================================================================
#  MAIN LOOP
# =====================================================================
def main():
    global scroll_offset, SELECTED_MODE, DIFF_CHOSEN, PVP
    screen = "intro"         # "intro" | "menu" | "score" | "exit" | "settings" | "gamemodes" | "game"
    intro_t = 0.0
    prev_screen = screen
    game = None
    paused = False
    pause_view = "menu"      # "menu" | "score" | "exit" | "settings"
    snapshot = None
    run = True
    fade = 1.0               # quick fade-in whenever the screen changes
    fade_surf = pygame.Surface((WIDTH, HEIGHT))
    fade_surf.fill((0, 0, 0))
    reveal = 1.0
    logo_sfx_done = False
    bgm_wait = None
    countdown = None
    bet_snapshot = None
    bet_mode = None
    bet_pvp = False
    bet_amounts = [0, 0]
    bet_submitted = [False, False]
    bet_settled = True

    def open_bet(match, mode):
        nonlocal game, screen, bet_snapshot, bet_mode, bet_pvp
        nonlocal bet_amounts, bet_submitted, bet_settled
        game = match
        bet_mode = mode
        bet_pvp = PVP
        resource = "goma" if mode == "karera" else "pogs"
        bet_amounts = [
            min(1, INVENTORY["player1"][resource]),
            min(1, INVENTORY["player2"][resource]),
        ]
        bet_submitted = [False, False] if bet_pvp else [True, False]
        bet_settled = False
        MATCH_BET["resource"] = resource.upper()
        MATCH_BET["total"] = 0
        game.draw((0, 0))
        bet_snapshot = blur_surface(WIN)
        screen = "bet"

    def start_bet_match():
        nonlocal screen
        resource = "goma" if bet_mode == "karera" else "pogs"
        accounts = ("player1", "player2") if bet_pvp else (None, "player2")
        stakes = bet_amounts[:] if bet_pvp else [bet_amounts[1], bet_amounts[1]]
        old_balances = {
            account: INVENTORY[account][resource]
            for account in accounts if account is not None
        }
        for i, account in enumerate(accounts):
            if account is not None:
                if stakes[i] > INVENTORY[account][resource]:
                    set_notice(f"NOT ENOUGH {resource.upper()}!")
                    return
                INVENTORY[account][resource] -= stakes[i]
        if not save_inventory():
            for account, balance in old_balances.items():
                INVENTORY[account][resource] = balance
            set_notice("BET NOT STARTED: INVENTORY COULD NOT BE SAVED")
            return

        MATCH_BET["total"] = sum(stakes)
        screen = "game"
        play_bgm("karera" if bet_mode == "karera" else "pogs")

    def settle_bet():
        nonlocal bet_settled
        if bet_settled or game.phase != "end":
            return
        resource = "goma" if bet_mode == "karera" else "pogs"
        before = {
            account: INVENTORY[account][resource]
            for account in ("player1", "player2")
        }
        result = game.final
        if result in ("tie", "ptie"):
            if bet_pvp:
                INVENTORY["player1"][resource] += bet_amounts[0]
                INVENTORY["player2"][resource] += bet_amounts[1]
            else:
                INVENTORY["player2"][resource] += bet_amounts[1]
        elif bet_pvp:
            winner = "player1" if result in ("p1", "loss") else "player2"
            INVENTORY[winner][resource] += MATCH_BET["total"]
        elif result in ("win", "p2"):
            INVENTORY["player2"][resource] += MATCH_BET["total"]

        if not save_inventory():
            for account, balance in before.items():
                INVENTORY[account][resource] = balance
            set_notice("BET SETTLEMENT COULD NOT BE SAVED")
        bet_settled = True

    while run:
        dt = min(CLOCK.tick(60) / 1000.0, 0.05)
        FX_DT[0] = dt
        if NOTICE[1] > 0:
            NOTICE[1] = max(0.0, NOTICE[1] - dt)
        mouse = window_to_canvas(pygame.mouse.get_pos())
        MOUSE_MOVED[0] = pygame.mouse.get_rel() != (0, 0)
        AMBIENT.update(dt)
        update_confetti(dt)

        for event in pygame.event.get():
            if hasattr(event, "pos"):
                event = pygame.event.Event(
                    event.type,
                    {**event.dict, "pos": window_to_canvas(event.pos)},
                )
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

            if screen == "bet":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    game = None
                    screen = "botmodes"
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = event.pos
                    if BET_BACK.collidepoint(pos):
                        play("click")
                        game = None
                        screen = "botmodes"
                        continue
                    ready = all(bet_submitted) if bet_pvp else bet_submitted[1]
                    if BET_START.collidepoint(pos) and ready:
                        play("click")
                        start_bet_match()
                        continue

                    for i in range(2):
                        if not bet_pvp and i == 0:
                            continue
                        if bet_submitted[i]:
                            continue
                        account = ("player1", "player2")[i] if bet_pvp else "player2"
                        resource = "goma" if bet_mode == "karera" else "pogs"
                        if BET_MINUS_RECTS[i].collidepoint(pos):
                            bet_amounts[i] = max(0, bet_amounts[i] - 1)
                        elif BET_PLUS_RECTS[i].collidepoint(pos):
                            bet_amounts[i] = min(
                                INVENTORY[account][resource], bet_amounts[i] + 1)
                        elif BET_SUBMIT_RECTS[i].collidepoint(pos):
                            if bet_amounts[i] > INVENTORY[account][resource]:
                                set_notice(f"NOT ENOUGH {resource.upper()}!")
                            else:
                                bet_submitted[i] = True
                                play("click")
                        else:
                            continue
                        break
                continue

            # gear click = press on it, release on it (so the squash animation is visible)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                gd, GEAR_DOWN[0] = GEAR_DOWN[0], None
                if gd == "menu" and screen == "menu" and GEAR_MENU.collidepoint(event.pos):
                    screen = "settings"
                    continue
                if gd == "pause" and screen == "game" and paused and pause_view == "menu" \
                        and GEAR_PAUSE.collidepoint(event.pos):
                    pause_view = "settings"
                    continue

            if screen == "settings":
                if settings_event(event) == "back":
                    screen = "menu"
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

                if pause_view == "settings":
                    if settings_event(event) == "back":
                        pause_view = "menu"
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and pause_view == "menu" \
                        and GEAR_PAUSE.collidepoint(event.pos):
                    play("click")
                    GEAR_DOWN[0] = "pause"
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
                    elif GEAR_MENU.collidepoint(pos):
                        play("menu_click")
                        GEAR_DOWN[0] = "menu"
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
                                paused = False
                                open_bet(PogsGame(add_result, pvp=True), "pogs")
                            elif key == "pogs":
                                if DIFF_CHOSEN:
                                    play("click")
                                    paused = False
                                    open_bet(PogsGame(add_result), "pogs")
                                else:
                                    play("miss")
                                    set_notice("PICK A LEVEL FIRST!")
                            elif DIFF_CHOSEN:
                                play("click")
                                paused = False
                                match = Game(pvp=PVP) if key == "karera" else PogsGame(add_result)
                                open_bet(match, key)
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
        elif screen == "settings":
            draw_settings(mouse)
        elif screen == "gamemodes":
            draw_vs_select(mouse)
        elif screen == "botmodes":
            draw_mode_select(mouse)
        elif screen == "bet":
            WIN.blit(bet_snapshot, (0, 0))
            draw_bet_popup(mouse, bet_mode, bet_pvp, bet_amounts, bet_submitted)
        else:
            if paused:
                draw_pause(mouse, pause_view, snapshot)       # game is frozen: no update()
            else:
                counting = countdown is not None and countdown < 3.0
                if not counting:
                    game.update(dt)
                if game.phase == "end":
                    settle_bet()
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

        update_cursor(HAND_HOT[0])      # mouse pointer becomes a hand over the gear / sliders
        HAND_HOT[0] = False

        display = pygame.display.get_surface()
        if display is not None:
            display_size = display.get_size()
            if display_size[0] > 0 and display_size[1] > 0:
                pygame.transform.scale(WIN, display_size, display)
                pygame.display.update()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()