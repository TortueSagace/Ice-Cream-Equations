"""
Created by Alexandre Le Mercier on the 16th of March 2025.

This is a simple video game aiming to train highschool students to solve linear equations faster.

You can share and use this program as far as you cite it properly.
Have fun!
"""


import pygame
import random
import math
import time

pygame.init()

##############################################################################
# CONFIGURATION
##############################################################################

SCREEN_WIDTH  = int(1200*(1.15+0.27))
SCREEN_HEIGHT = int(800*1.15)
FPS           = 30
BASICAL_LENGTH_UNIT = int(SCREEN_HEIGHT/(800*1.15)*10)

# Sidebar on the LEFT
SIDEBAR_WIDTH    = 400
GAME_AREA_WIDTH  = SCREEN_WIDTH - SIDEBAR_WIDTH

# We allow X "units" of equation frames. If total > X => game over
MAX_EQUATION_UNITS = 20
MAX_VISIBLE_EQUATIONS_SIDEBAR = 6
INVINCIBLE_MODE = False

# Timers and speeds
INITIAL_SCOOP_INTERVAL = 20.0
RATE_INCREASE_INTERVAL = 15.0
RATE_INCREASE_PERCENT  = 10   # +10% speed => interval *= 0.9
SPRINT_TRIGGER_PROB    = 0.5 # chance to start sprint on score%10=5
SPRINT_SCOOPS_FAST     = 4    # 4 quick scoops + 1 giant
GIANT_SCOOP_BASE_PROB  = 0.1
GIANT_SCOOP_MAX_PROB   = 0.3

# Solutions must be multiples of 0.5 in [-10, 10], excluding 0
VALID_SOLUTIONS = []
val = -10.0
while val <= 10.0:
    if abs(val) > 1e-9:  # exclude 0
        VALID_SOLUTIONS.append(round(val,1))
    val += 0.5

# Fonts
pygame.font.init()
FONT        = pygame.font.SysFont("Arial", int(2.2*BASICAL_LENGTH_UNIT))
MEDIUM_FONT = pygame.font.SysFont("Arial", int(3.2*BASICAL_LENGTH_UNIT))
BIG_FONT    = pygame.font.SysFont("Arial", int(4.8*BASICAL_LENGTH_UNIT))

# Colors
WHITE       = (255,255,255)
BLACK       = (0,0,0)
LIGHT_BLUE  = (135,206,235)
GREEN_FLOOR = (34,139,34)
CONE_BROWN  = (139,69,19)
RED         = (255,0,0)
YELLOW      = (255,255,0)
DARKER_BLUE = (7,10,13)

if INVINCIBLE_MODE:
    MAX_EQUATION_UNITS = 1e9

##############################################################################
# AUDIO
##############################################################################

def load_sounds():
    sounds = {}
    try:
        sounds["10points"]        = pygame.mixer.Sound("10points.mp3")
        sounds["game_over_loose"] = pygame.mixer.Sound("game_over_loose.mp3")
        sounds["game_over_wins"]  = pygame.mixer.Sound("game_over_wins.mp3")
        sounds["applause1"]       = pygame.mixer.Sound("applause1.mp3")
        sounds["applause2"]       = pygame.mixer.Sound("applause2.mp3")
        # We won't load "bgmusic" as a Sound but as music (below).
    except:
        # If there's an error (file not found, etc.), we can pass or print a warning.
        print("[WARNING] Some .mp3 files could not be loaded.")
    return sounds

def play_sound_10points(sounds):
    """Play whenever the user’s score hits a multiple of 10."""
    try:
        sounds["10points"].play()
    except:
        pass

def play_sound_applause(sounds):
    """Randomly pick applause1 or applause2 when giant scoop is solved."""
    try:
        pick = random.choice(["applause1","applause2"])
        sounds[pick].play()
    except:
        pass

def play_sound_game_over_loose(sounds):
    """If the user loses (wrong answer or stack overflow)."""
    try:
        pygame.mixer.music.stop()
        sounds["game_over_loose"].play()
    except:
        pass

def play_sound_game_over_wins(sounds):
    """If the user reaches 120 points => you win."""
    try:
        pygame.mixer.music.stop()
        sounds["game_over_wins"].play()
    except:
        pass

def start_background_music():
    """Loop the background music from start of game until game over."""
    try:
        pygame.mixer.music.load("bgmusic.mp3")
        pygame.mixer.music.play(-1)   # -1 => loop forever
    except:
        print("[WARNING] Could not load bgmusic.mp3")

def stop_background_music():
    """Stop the music on game over."""
    pygame.mixer.music.stop()

##############################################################################
# HELPER FUNCTIONS
##############################################################################

def format_float(num):
    """
    Convert float to a string with up to 8 significant digits,
    thereby avoiding excessive rounding (e.g. .1 instead of .08).
    E.g. 0.25 stays 0.25, 0.333333333 becomes 0.33333333, etc.
    """
    return f"{num:.8g}"


def sky_color_for_interval(interval):
    """
    Darken the sky as the scoop interval shrinks.
    If interval ~5 => near normal sky. If ~1 => quite dark.
    We'll clamp between 1..5 for interpolation.
    """
    tmin, tmax = 1.0, 5.0
    c1 = DARKER_BLUE
    c2 = LIGHT_BLUE
    val = max(tmin, min(tmax, interval))
    # t=1 => darkest, t=5 => light
    frac = (val - tmin)/(tmax - tmin)
    r = int(c1[0]*(1-frac) + c2[0]*frac)
    g = int(c1[1]*(1-frac) + c2[1]*frac)
    b = int(c1[2]*(1-frac) + c2[2]*frac)
    return (r,g,b)

##############################################################################
# EQUATION GENERATION
##############################################################################

def generate_equation(score, is_giant=False):
    """
    Generate a linear equation with a unique solution from VALID_SOLUTIONS.
    If score < 10, we only do 1 transformation step; otherwise 1..3 steps.
    The 'MUL' step can now multiply by ±2, ±3, ±4, or ±5.
    """
    solution = random.choice(VALID_SOLUTIONS)
    print(f"\n[DEBUG] Picked solution: {solution}")

    # Start: LHS = x, RHS = solution
    aL, bL = 1.0, 0.0
    aR, bR = 0.0, float(solution)
    print(f"[DEBUG] Initial: LHS={aL}*x+{bL}, RHS={aR}*x+{bR}  => x=?")

    # Decide how many random steps to do
    giant_bonus = 1 if is_giant else 0
    if score < 50:
        steps = 1
    elif score < 80:
        steps = random.randint(1, 2)
    else:
        steps = random.randint(1, 3)
    steps += giant_bonus

    # We rename "MUL_2" to just "MUL" and allow ±(2..5).
    if score < 10:
        possible_transforms = ["ADD_C"]
    elif score < 25:
        possible_transforms = ["SUB_X"]
    elif score < 35:
        possible_transforms = ["ADD_C","SUB_X"]
    elif score < 65:
        possible_transforms = ["ADD_C","SUB_X","MUL"]
    else:
        possible_transforms = ["ADD_C","SUB_X","MUL","DIV_2"]

    for step_i in range(steps):
        t = random.choice(possible_transforms)
        print(f"[DEBUG] Step {step_i}: transformation='{t}'")
        
        if t == "ADD_C":
            c = random.randint(-5, 5)
            bL += c
            bR += c
            print(f"[DEBUG]  -> ADD_C({c}) => LHS={aL}x+{bL}, RHS={aR}x+{bR}")

        elif t == "SUB_X":
            # subtract c*x from BOTH sides
            c = random.choice([-3,-2,-1,1,2,3])
            aL -= c
            aR -= c
            print(f"[DEBUG]  -> SUB_X({c}) => LHS={aL}x+{bL}, RHS={aR}x+{bR}")

        elif t == "MUL":
            # multiply both sides by ±(2..5)
            sign = random.choice([1,-1])
            factor = random.choice([2,3,4,5]) * sign
            aL *= factor
            bL *= factor
            aR *= factor
            bR *= factor
            print(f"[DEBUG]  -> MUL({factor}) => LHS={aL}x+{bL}, RHS={aR}x+{bR}")

        elif t == "DIV_2":
            # divide both sides by ±2 (as before)
            sign = random.choice([1,-1])
            fac = 2 * sign
            if abs(fac) > 1e-9:
                aL /= fac
                bL /= fac
                aR /= fac
                bR /= fac
            print(f"[DEBUG]  -> DIV_2(1/{fac}) => LHS={aL}x+{bL}, RHS={aR}x+{bR}")

    # Possibly do 1/x => does not preserve solution unless you re-derive a,b 
    # but if you want the "giant scoop" to have a 1/x side, keep it:
    use_inverse_side = None
    #if is_giant and abs(solution) > 1e-9 and (random.random() < 0.5):
    #    use_inverse_side = random.choice(["L", "R"])
    #    print(f"[DEBUG] use_inverse_side={use_inverse_side}")

    eq_text = format_equation(aL, bL, aR, bR, use_inverse_side)
    print(f"[DEBUG] Final eq string: {eq_text}")

    # Evaluate numeric LHS,RHS at x=solution for debug
    lhs_val = evaluate_side(aL,bL, solution, use_inverse=(use_inverse_side=="L"))
    rhs_val = evaluate_side(aR,bR, solution, use_inverse=(use_inverse_side=="R"))
    print(f"[DEBUG] LHS at x={solution} => {lhs_val}, RHS => {rhs_val}")

    correct_answer = solution
    if not is_giant:
        answers = build_normal_answers(correct_answer)
    else:
        answers = build_giant_answers(correct_answer)

    print(f"[DEBUG] Answers => {answers}, correct={correct_answer}")
    return eq_text, correct_answer, answers, is_giant


def evaluate_side(a, b, x_val, use_inverse=False):
    """Compute a*x_val + b or a*(1/x_val)+b."""
    if use_inverse:
        return a*(1.0/x_val) + b
    else:
        return a*x_val + b

def format_equation(aL, bL, aR, bR, side_inv=None):
    """
    Build a string like '2x = -8' or 'x + 2 = 3x - 1'.
    If side_inv='L', treat the LHS as a*(1/x) + b.
    If side_inv='R', treat the RHS as a*(1/x) + b.
    """
    lhs_str = _format_side(aL, bL, use_inverse=(side_inv == 'L'))
    rhs_str = _format_side(aR, bR, use_inverse=(side_inv == 'R'))
    return lhs_str + " = " + rhs_str

def _format_side(a, b, use_inverse=False):
    """
    Format a*x + b or a*(1/x) + b.  E.g. '2x - 1', or '-3*(1/x) + 2'.
    We avoid double negatives like '--8'.
    """
    # We'll build a list of string parts and then join them with spaces
    parts = []

    # 1) The 'a'-term
    if abs(a) > 1e-9:
        if use_inverse:
            # e.g. "2*(1/x)", or "-(1/x)" if a=-1, etc.
            if abs(a - 1.0) < 1e-9:
                parts.append("1/x")
            elif abs(a + 1.0) < 1e-9:
                parts.append("-1/x")
            else:
                parts.append(f"{format_float(a)}*(1/x)")
        else:
            # normal linear
            if abs(a - 1.0) < 1e-9:
                parts.append("x")
            elif abs(a + 1.0) < 1e-9:
                parts.append("-x")
            else:
                parts.append(f"{format_float(a)}x")

    # 2) The 'b'-term
    if abs(b) > 1e-9:
        # We have a non-zero constant
        if not parts:
            # If there's NO a-term, we simply insert e.g. '-8' or '3.5'
            parts.append(format_float(b))
        else:
            # We do the typical " + <num>" or " - <num>"
            if b > 0:
                parts.append(f"+ {format_float(b)}")
            else:
                parts.append(f"- {format_float(abs(b))}")

    # If both a ~ 0 and b ~ 0, just return "0"
    if not parts:
        return "0"
    else:
        return " ".join(parts)

def format_float(num):
    """
    Convert float to a user‐friendly string, e.g. 1.5 => '1.5', 2.0 => '2'.
    """
    if abs(num - int(num)) < 1e-9:
        return str(int(num))
    else:
        return f"{num:.8g}"


def build_normal_answers(correct):
    """
    For normal scoops: 4 answers:
        correct
        -correct
        (correct±1)
        (-correct±1)
    Exclude 0 if it arises, then fill if we have <4. Shuffle.
    """
    ans_set = set()
    def maybe_add(val):
        if abs(val)>1e-9:  # exclude 0
            ans_set.add(val)

    maybe_add(correct)
    maybe_add(-correct)
    if random.random()<0.5:
        maybe_add(correct+1)
    else:
        maybe_add(correct-1)
    if random.random()<0.5:
        maybe_add(-correct+1)
    else:
        maybe_add(-correct-1)

    while len(ans_set)<4:
        c = random.choice(VALID_SOLUTIONS)
        ans_set.add(c)

    answers = list(ans_set)
    random.shuffle(answers)
    return answers[:4]

def build_giant_answers(correct):
    """
    Giant scoops: 12 answers = 6 “primaries” + their opposites.
    Must contain correct & -correct, exclude 0.
    """
    primaries = set()
    primaries.add(correct)
    while len(primaries)<6:
        c = random.choice(VALID_SOLUTIONS)
        primaries.add(c)

    full = set()
    for p in primaries:
        full.add(p)
        full.add(-p)

    # Make sure we have at least 12, fill if needed
    final_list = list(full)
    random.shuffle(final_list)
    while len(final_list)<12:
        c = random.choice(VALID_SOLUTIONS)
        if c not in final_list:
            final_list.append(c)

    final_list = final_list[:12]
    random.shuffle(final_list)
    return final_list


##############################################################################
# CLASSES
##############################################################################

class EquationFrame:
    """One equation in the sidebar (is_giant => 2 units)."""
    def __init__(self, text, correct, answers, is_giant=False):
        self.text = text
        # Use the raw float for 'correct' (no rounding to 1 decimal).
        self.correct = float(correct)
        # Also do not round the individual answers; keep them as floats.
        self.answers = [float(a) for a in answers]
        self.is_giant = is_giant

    @property
    def units(self):
        return 2 if self.is_giant else 1

    def check_answer(self, val):
        # Use a small epsilon to handle float quirks
        return abs(val - self.correct) < 1e-9


class SidebarManager:
    def __init__(self):
        self.frames = []

    def add_equation(self, frame):
        self.frames.append(frame)

    def remove_equation(self, frame):
        if frame in self.frames:
            self.frames.remove(frame)

    def total_units(self):
        return sum(f.units for f in self.frames)

    def draw(self, surface):
        """
        Draw from top to bottom. Each normal frame is 1 “unit,” giant = 2.
        We have ... units visually. If total>... => game over (done in main).
        """
        surface.fill((200,200,200))
        pygame.draw.rect(surface, BLACK, surface.get_rect(), 2)

        unit_h = SCREEN_HEIGHT/float(MAX_VISIBLE_EQUATIONS_SIDEBAR)
        y_off = 0
        for f in self.frames:
            fh = f.units * unit_h
            # Frame background
            frame_rect = pygame.Rect(0, y_off, SIDEBAR_WIDTH, fh)
            color_bg = (220,220,220) if not f.is_giant else (180,220,180)
            pygame.draw.rect(surface, color_bg, frame_rect)
            pygame.draw.rect(surface, BLACK, frame_rect, 1)

            # Equation text in the top half
            eq_surf = FONT.render(f.text, True, BLACK)
            surface.blit(eq_surf, (BASICAL_LENGTH_UNIT, y_off + BASICAL_LENGTH_UNIT/2))

            # We'll define a small "margin" around buttons
            margin = BASICAL_LENGTH_UNIT/2
            # The bottom half of the frame is for answer buttons
            # top_of_buttons:
            top_of_buttons = y_off + (fh * 0.5)

            if not f.is_giant:
                # NORMAL => 4 answers (2x2)
                # We place them in the bottom half with some margins.
                # Let’s define how big each button is:
                #   We want 2 columns horizontally => so each button = (SIDEBAR_WIDTH - 3*margin)/2
                #   We want 2 rows in that half => so each button = (fh/2 - 3*margin)/2

                btn_w = (SIDEBAR_WIDTH - 3*margin) / 2
                btn_h = ((fh/2) - 3*margin) / 2

                for i, ans in enumerate(f.answers):
                    row, col = divmod(i, 2)
                    # button x,y:
                    bx = margin + col*(btn_w + margin)
                    by = top_of_buttons + margin + row*(btn_h + margin)
                    br = pygame.Rect(bx, by, btn_w, btn_h)
                    pygame.draw.rect(surface, (240,240,240), br)
                    pygame.draw.rect(surface, BLACK, br, 1)

                    srf = FONT.render(format_float(ans), True, BLACK)
                    tw, th = srf.get_size()
                    surface.blit(
                        srf,
                        (bx + (btn_w - tw)/2, by + (btn_h - th)/2)
                    )

            else:
                # GIANT => 12 answers (4 columns x 3 rows)
                # We'll do something consistent with the handle_click approach.
                margin = BASICAL_LENGTH_UNIT/2
                btn_w = (SIDEBAR_WIDTH - 5*margin)/4
                # The bottom half is fh/2 in height, we want 3 rows => each row ~ (fh/2 - 4*margin)/3
                btn_h = ((fh/2) - 4*margin)/3
                for i, ans in enumerate(f.answers):
                    row, col = divmod(i, 4)
                    bx = margin + col*(btn_w + margin)
                    by = top_of_buttons + margin + row*(btn_h + margin)
                    br = pygame.Rect(bx, by, btn_w, btn_h)
                    pygame.draw.rect(surface, (240,240,240), br)
                    pygame.draw.rect(surface, BLACK, br, 1)

                    srf = FONT.render(format_float(ans), True, BLACK)
                    tw, th = srf.get_size()
                    surface.blit(
                        srf,
                        (bx + (btn_w - tw)/2, by + (btn_h - th)/2)
                    )

            y_off += fh

    def handle_click(self, mx, my):
        """
        Return (clicked_frame, answer_val) if an answer was clicked, else (None,None).
        We replicate the same geometry as in draw().
        """
        unit_h = SCREEN_HEIGHT / float(MAX_VISIBLE_EQUATIONS_SIDEBAR)
        y_off  = 0
        for f in self.frames:
            fh = f.units * unit_h
            frame_rect = pygame.Rect(0, y_off, SIDEBAR_WIDTH, fh)
            if frame_rect.collidepoint(mx, my):
                # We are inside this frame => check buttons
                top_of_buttons = y_off + (fh * 0.5)
                margin = BASICAL_LENGTH_UNIT/2

                if not f.is_giant:
                    # Normal => 4 answers (2x2)
                    btn_w = (SIDEBAR_WIDTH - 3*margin) / 2
                    btn_h = ((fh/2) - 3*margin) / 2

                    for i, ans in enumerate(f.answers):
                        row, col = divmod(i, 2)
                        bx = margin + col*(btn_w + margin)
                        by = top_of_buttons + margin + row*(btn_h + margin)
                        br = pygame.Rect(bx, by, btn_w, btn_h)

                        # Debug each button
                        # print(...) can help see if we're in the right spot:
                        # print(f"[DEBUG] Checking normal button: eq={f.text}, ans={ans}, rect={br}")

                        if br.collidepoint(mx, my):
                            print(f"[DEBUG] CLICK in eq '{f.text}' => answer chosen: {ans}, correct={f.correct}")
                            return (f, ans)

                else:
                    # Giant => 12 answers (4x3)
                    btn_w = (SIDEBAR_WIDTH - 5*margin)/4
                    btn_h = ((fh/2) - 4*margin)/3

                    for i, ans in enumerate(f.answers):
                        row, col = divmod(i, 4)
                        bx = margin + col*(btn_w + margin)
                        by = top_of_buttons + margin + row*(btn_h + margin)
                        br = pygame.Rect(bx, by, btn_w, btn_h)

                        # print(f"[DEBUG] Checking giant button: eq={f.text}, ans={ans}, rect={br}")

                        if br.collidepoint(mx, my):
                            print(f"[DEBUG] CLICK in eq '{f.text}' => answer chosen: {ans}, correct={f.correct}")
                            return (f, ans)

            y_off += fh

        return (None, None)

##############################################################################
# SCOOPS / BACKGROUND OBJECTS
##############################################################################

class Scoop:
    def __init__(self, index, target_x, target_y, radius, color, is_giant=False, stack_top_y=0):
        self.radius = radius
        self.color  = color
        self.is_giant = is_giant

        # Start from left if index is odd, else right
        if index % 2 == 1:
            self.x = -BASICAL_LENGTH_UNIT*10
        else:
            self.x = SIDEBAR_WIDTH + GAME_AREA_WIDTH + BASICAL_LENGTH_UNIT*10
        self.y = stack_top_y + random.randint(-BASICAL_LENGTH_UNIT*10, BASICAL_LENGTH_UNIT*10)

        self.tx = target_x
        self.ty = target_y
        self.landed = False

        # velocity/accel
        flight_time = 2.0
        dx = self.tx - self.x
        dy = self.ty - self.y
        self.vx = dx/flight_time
        # toss upward a bit
        self.ay = BASICAL_LENGTH_UNIT*30
        self.vy = (dy/flight_time) - 0.5*self.ay*flight_time
        self.ax = 0

    def update(self, dt_millis, game_over=False):
        
        if not self.landed or game_over:
            # Convert milliseconds -> seconds
            dt = dt_millis / 1000.0

            self.vx += self.ax * dt
            self.vy += self.ay * dt
            self.x  += self.vx * dt
            self.y  += self.vy * dt

        if not self.landed:
            # check if close enough to target
            d2 = (self.x - self.tx)**2 + (self.y - self.ty)**2
            if d2 < (self.radius**2 + BASICAL_LENGTH_UNIT):
                self.x = self.tx
                self.y = self.ty
                self.landed = True


    def draw(self, surface, camera_offset):
        cy = self.y + camera_offset
        pygame.draw.circle(surface, self.color, (int(self.x), int(cy)), self.radius)


class Cloud:
    """Simple ellipse cloud in the background (no movement here unless you want)."""
    def __init__(self, x,y,w,h):
        self.x=x
        self.y=y
        self.w=w
        self.h=h
    def draw(self, surface, camera_offset):
        cy = self.y + camera_offset
        rect = pygame.Rect(self.x, cy, self.w, self.h)
        pygame.draw.ellipse(surface, (255,255,255), rect)


##############################################################################
# MAIN GAME
##############################################################################
        
def run_game():

    sounds = load_sounds()
    start_background_music()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Loulou Can't Solve Equations")

    clock = pygame.time.Clock()

    sidebar = SidebarManager()

    new_game_button_rect = pygame.Rect(0,0, BASICAL_LENGTH_UNIT*18, BASICAL_LENGTH_UNIT*5)

    # Moon variables
    moon_visible = False     # becomes True once sky color is fully DARKER_BLUE
    moon_x       = SIDEBAR_WIDTH + GAME_AREA_WIDTH - BASICAL_LENGTH_UNIT*10
    moon_y       = -BASICAL_LENGTH_UNIT*5      # start above top of screen
    moon_speed   = float(BASICAL_LENGTH_UNIT)  # how many pixels per second

    # Floor and "cone" geometry
    floor_y     = SCREEN_HEIGHT - BASICAL_LENGTH_UNIT*5
    cone_top_y  = floor_y - BASICAL_LENGTH_UNIT*15
    person_x    = SIDEBAR_WIDTH + (GAME_AREA_WIDTH // 2) - BASICAL_LENGTH_UNIT*2

    cone_left   = (person_x,     cone_top_y)
    cone_right  = (person_x+BASICAL_LENGTH_UNIT*4,  cone_top_y)
    cone_tip    = (person_x+BASICAL_LENGTH_UNIT*2,  floor_y)

    # Scoops
    stack_top_y = cone_top_y
    scoops      = []
    score       = 0

    # Clouds: start with a few
    clouds = []
    for _ in range(5):
        cx = random.randint(SIDEBAR_WIDTH, SCREEN_WIDTH - BASICAL_LENGTH_UNIT*5)
        cy = random.randint(BASICAL_LENGTH_UNIT*5, floor_y - BASICAL_LENGTH_UNIT*10)
        w  = random.randint(BASICAL_LENGTH_UNIT*6, BASICAL_LENGTH_UNIT*12)
        h  = random.randint(BASICAL_LENGTH_UNIT*2, BASICAL_LENGTH_UNIT*4)
        clouds.append(Cloud(cx, cy, w, h))

    # Camera offset
    camera_offset = 0

    # Timers & sprints
    scoop_interval     = INITIAL_SCOOP_INTERVAL
    last_scoop_time    = time.time()
    last_rate_incr     = time.time()

    in_sprint       = False
    sprint_phase    = 0
    sprints_count   = 0
    giant_prob      = 0.0
    sprint_start_t  = 0
    quick_placed    = 0

    countdown_start      = None
    encouragement_start  = None
    encouragement_msg    = ""

    game_over       = False
    game_over_reason= ""

    # NEW: define so we can fling scoops once on game over
    scoops_flung = False
    # Also define top_threshold once (used below for spawning clouds/camera):
    top_threshold = SCREEN_HEIGHT / 2

    flag_sound_10 = False

    # Helper: place scoop
    def place_scoop(force_giant=False):
        nonlocal score, stack_top_y
        is_giant = False
        if force_giant:
            is_giant = True
        else:
            # after 3 sprints, random giant
            if sprints_count >= 2 and random.random() < giant_prob:
                is_giant = True

        radius = BASICAL_LENGTH_UNIT*6 if is_giant else BASICAL_LENGTH_UNIT*4
        x = person_x + BASICAL_LENGTH_UNIT*2 + random.randint(-BASICAL_LENGTH_UNIT*2, BASICAL_LENGTH_UNIT*2)
        y = stack_top_y - radius
        s = Scoop(len(scoops), x, y, radius, (random.randint(50,255),
                                 random.randint(50,255),
                                 random.randint(50,255)),
                  is_giant, stack_top_y)
        scoops.append(s)
        stack_top_y -= 2*radius

        eq_text, corr, ans, giant_flag = generate_equation(score, is_giant=is_giant)
        frame = EquationFrame(eq_text, corr, ans, giant_flag)
        sidebar.add_equation(frame)

    new_game_button_rect = pygame.Rect(0, 0, BASICAL_LENGTH_UNIT*18, BASICAL_LENGTH_UNIT*5)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return "quit"

            if event.type == pygame.MOUSEBUTTONDOWN and game_over:
                mx, my = pygame.mouse.get_pos()
                if new_game_button_rect.collidepoint(mx, my):
                    return "restart"
                
        dt = clock.tick(FPS)
        now = time.time() + INITIAL_SCOOP_INTERVAL

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            
            if game_over:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    if new_game_button_rect.collidepoint(mx, my):
                        # Return from main, so the user can re-run or you re-call main()
                        return
                    
            if event.type == pygame.MOUSEBUTTONDOWN and not game_over:
                mx, my = pygame.mouse.get_pos()
                if mx < SIDEBAR_WIDTH:
                    # check for answer clicks
                    f, val = sidebar.handle_click(mx, my)
                    if f:
                        if f.check_answer(val) or INVINCIBLE_MODE:
                            score += 1
                            if (not in_sprint) and (score % 10 == 5) and (random.random() < SPRINT_TRIGGER_PROB):
                                in_sprint = True
                                sprint_phase = 1
                                sprints_count += 1
                                if giant_prob > 1e-9:
                                    giant_prob = min(GIANT_SCOOP_MAX_PROB, giant_prob + 0.1)
                                sprint_start_t = time.time()
                                quick_placed = 0

                            if score >= 50 and giant_prob < GIANT_SCOOP_BASE_PROB:
                                giant_prob = GIANT_SCOOP_BASE_PROB

                             # Check if score hits multiple of 10
                            if not (score % 10) == 0:
                                flag_sound_10 = True

                            if score > 0 and flag_sound_10 and (score % 10) == 0:
                                play_sound_10points(sounds)
                                flag_sound_10 = False

                            if score >= 120:
                                game_over = True
                                game_over_reason = "Maximum height reached. Well done!"
                                play_sound_game_over_wins(sounds)

                            # Encourage only if giant solved
                            if f.is_giant:
                                encouragement_start = time.time()
                                encouragement_msg   = random.choice(["Great job!", "Amazing!", "Well done!"])
                                play_sound_applause(sounds)

                            sidebar.remove_equation(f)
                            # if we removed the last frame => place a new scoop automatically
                            if not in_sprint and not game_over and len(sidebar.frames) == 0:
                                place_scoop(force_giant=False)
                                
                        else:
                            game_over = True
                            game_over_reason = "Wrong answer"
                            play_sound_game_over_loose(sounds)

        # Spawn new clouds occasionally
        if not game_over and random.random() < 0.02:
            cx = random.randint(SIDEBAR_WIDTH, SCREEN_WIDTH - BASICAL_LENGTH_UNIT*5)
            # Use top_threshold here
            cy = -BASICAL_LENGTH_UNIT*5 - random.randint(int(top_threshold), int(SCREEN_HEIGHT + top_threshold)*10)
            w  = random.randint(BASICAL_LENGTH_UNIT*6, BASICAL_LENGTH_UNIT*12)
            h  = random.randint(BASICAL_LENGTH_UNIT*2, BASICAL_LENGTH_UNIT*4)
            clouds.append(Cloud(cx, cy, w, h))

        # If we have more than 300 clouds, remove oldest
        if len(clouds) > 300:
            clouds.pop(0)

        # Check eq stack limit
        if not game_over:
            if sidebar.total_units() > MAX_EQUATION_UNITS:
                game_over = True
                game_over_reason = "Too many unsolved equations!"
                play_sound_game_over_loose(sounds)

        # Normal scoop placement
        if not game_over and not in_sprint:
            if (now - last_scoop_time) >= scoop_interval:
                last_scoop_time = now
                place_scoop(force_giant=False)
                # possibly start sprint
                if str(score).endswith("5"):
                    if random.random() < SPRINT_TRIGGER_PROB:
                        in_sprint = True
                        sprint_phase = 1
                        sprints_count += 1
                        if giant_prob > 1e-9:
                            giant_prob = min(GIANT_SCOOP_MAX_PROB, giant_prob + 0.1)
                        sprint_start_t = now
                        quick_placed = 0

        # Sprint
        if not game_over and in_sprint:
            elapsed = now - sprint_start_t
            total_time = scoop_interval * 5
            if sprint_phase == 1:
                # small break 25%
                if len(sidebar.frames) == 0 or elapsed > total_time * (0.25+0.4*4):
                    sprint_phase = 2
            elif sprint_phase == 2:
                # Faster placement of 4 scoops (now within 10% of total_time)
                t_fast_scoops = total_time * 0.1
                frac = min((elapsed / t_fast_scoops), 1)
                needed = int(frac * 4)

                while quick_placed < 4 and quick_placed < needed:
                    place_scoop(force_giant=False)
                    quick_placed += 1

                if quick_placed >= 4:
                    sprint_phase = 3
                    sprint_start_t = now  # Reset again for next phase
            elif sprint_phase == 3:
                # place giant
                place_scoop(force_giant=True)
                sprint_phase = 4
                countdown_start = time.time()
            elif sprint_phase == 4:
                # 3s countdown
                if time.time() - countdown_start > 3.0:
                    sprint_phase = 5
                    #encouragement_start = time.time()
                    #encouragement_msg = random.choice(["Great job!", "Amazing!", "Well done!"])
            elif sprint_phase == 5:
                in_sprint = False
                sprint_phase = 0
                last_scoop_time = time.time()
                    

        # Speed up
        if not game_over and (now - last_rate_incr) > RATE_INCREASE_INTERVAL:
            scoop_interval *= (1.0 - RATE_INCREASE_PERCENT/100.0)
            if scoop_interval < 0.5:
                scoop_interval = 0.5
            last_rate_incr = now

        # CAMERA OFFSET:
        # Move up only when the stack is above halfway. We also do a smooth approach
        # so it doesn't jump.
        desired_offset = 0
        if stack_top_y < top_threshold:
            desired_offset = top_threshold - stack_top_y
        camera_offset += 0.1*(desired_offset - camera_offset)

        # RENDER
        sky_col = sky_color_for_interval(scoop_interval)
        screen.fill(sky_col)

        if score == 80:
            moon_visible = True

        # If moon is visible, move it straight downward and draw
        if moon_visible:
            # Convert dt from ms to seconds
            dt_seconds = dt / 1000.0
            # Move down at moon_speed px/sec
            moon_y += moon_speed * dt_seconds
            
            # We'll just draw a circle for the moon
            # color (240,240,200) for a faint yellowish moon
            pygame.draw.circle(
                screen,
                (240,240,200),
                (int(moon_x), int(moon_y)),
                60  # radius
            )
            pygame.draw.circle(
                screen,
                sky_color_for_interval(scoop_interval),
                (int(moon_x+30), int(moon_y)),
                60  # radius
            )
            if moon_y > SCREEN_HEIGHT + BASICAL_LENGTH_UNIT*5:
                moon_visible = False  # or reset it, e.g. moon_y = -50


        # Draw floor
        floor_draw_y = floor_y + camera_offset
        pygame.draw.rect(
            screen, GREEN_FLOOR,
            (SIDEBAR_WIDTH, floor_draw_y, GAME_AREA_WIDTH, SCREEN_HEIGHT - floor_draw_y)
        )

        # Draw cone
        shift_cone_left  = (cone_left[0],  cone_left[1] + camera_offset)
        shift_cone_right = (cone_right[0], cone_right[1] + camera_offset)
        shift_cone_tip   = (cone_tip[0],   cone_tip[1] + camera_offset)
        pygame.draw.polygon(
            screen, CONE_BROWN,
            [shift_cone_left, shift_cone_right, shift_cone_tip]
        )

        # Clouds
        for c in clouds:
            c.draw(screen, camera_offset)

        # Scoops
        for s in scoops:
            s.update(dt, game_over)  # if your Scoop class has an 'update' method
            s.draw(screen, camera_offset)

        # Score at top
        score_surf = MEDIUM_FONT.render(f"Score: {score}", True, GREEN_FLOOR)
        screen.blit(score_surf, (SIDEBAR_WIDTH + GAME_AREA_WIDTH//2 - 50, 10))

        # Sprint countdown
        if in_sprint and sprint_phase == 4:
            cd_elapsed = time.time() - countdown_start
            secs_left  = 3 - int(cd_elapsed)
            if secs_left < 1:
                secs_left = 1
            txt_surf = BIG_FONT.render(str(secs_left), True, RED)
            sw, sh = txt_surf.get_size()
            screen.blit(
                txt_surf,
                (SIDEBAR_WIDTH + GAME_AREA_WIDTH//2 - sw//2, SCREEN_HEIGHT//2 - sh//2)
            )

        # Show giant-scoop encouragement if <2s
        if encouragement_start is not None:
            now_t = time.time()
            if now_t - encouragement_start < 2.0:
                txt_surf = BIG_FONT.render(encouragement_msg, True, YELLOW)
                sw, sh = txt_surf.get_size()
                screen.blit(
                    txt_surf,
                    (SIDEBAR_WIDTH + GAME_AREA_WIDTH//2 - sw//2, SCREEN_HEIGHT//2 - sh//2)
                )
            else:
                encouragement_start = None

        # Sidebar
        sidebar_surf = pygame.Surface((SIDEBAR_WIDTH, SCREEN_HEIGHT))
        sidebar.draw(sidebar_surf)
        screen.blit(sidebar_surf, (0,0))

        # Remaining equation free spaces
        remaining_units = MAX_EQUATION_UNITS - sidebar.total_units()
        remaining_text = FONT.render(f"Remaining: {remaining_units}", True, BLACK)
        text_rect = remaining_text.get_rect(center=(SIDEBAR_WIDTH // 2, SCREEN_HEIGHT - BASICAL_LENGTH_UNIT*4))
        screen.blit(remaining_text, (BASICAL_LENGTH_UNIT*2, SCREEN_HEIGHT - BASICAL_LENGTH_UNIT*4))


        # Fling scoops once if game over
        if game_over and not scoops_flung:
            scoops_flung = True
            for s in scoops:
                s.landed = False
                s.x  = s.x
                s.y  = s.y
                s.vx = random.uniform(-BASICAL_LENGTH_UNIT*30, BASICAL_LENGTH_UNIT*30)
                s.vy = random.uniform(-BASICAL_LENGTH_UNIT*30, -BASICAL_LENGTH_UNIT*10)
                s.ax = 0
                s.ay = BASICAL_LENGTH_UNIT*40

        # Display name in bottom-right, plus "INVINCIBLE" if needed
        name_surf = MEDIUM_FONT.render("Alexandre Le Mercier", True, (200,200,200))
        nw, nh = name_surf.get_size()
        if INVINCIBLE_MODE:
            inv_surf = MEDIUM_FONT.render("INVINCIBLE", True, (255,100,100))
            iw, ih = inv_surf.get_size()
            screen.blit(inv_surf, (SCREEN_WIDTH - iw - BASICAL_LENGTH_UNIT, SCREEN_HEIGHT - nh - ih - BASICAL_LENGTH_UNIT*2))
        screen.blit(name_surf, (SCREEN_WIDTH - nw - BASICAL_LENGTH_UNIT, SCREEN_HEIGHT - nh - BASICAL_LENGTH_UNIT))

        # If game over => add overlay and game-over text
        if game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill((0,100,0))
            screen.blit(overlay, (0,0))

            go_text = "Game Over!"
            reason  = f"Reason: {game_over_reason}"
            fs_text = f"Final Score: {score}"
            if score < 120:
                s1 = BIG_FONT.render(go_text, True, RED)
            else:
                s1 = BIG_FONT.render(go_text, True, YELLOW)
            s2 = MEDIUM_FONT.render(reason, True, WHITE)
            s3 = MEDIUM_FONT.render(fs_text, True, WHITE)

            sw1, sh1 = s1.get_size()
            sw2, sh2 = s2.get_size()
            sw3, sh3 = s3.get_size()
            cx = SCREEN_WIDTH // 2
            cy = SCREEN_HEIGHT // 2

            screen.blit(s1, (cx - sw1//2, cy - BASICAL_LENGTH_UNIT*8))
            screen.blit(s2, (cx - sw2//2, cy - BASICAL_LENGTH_UNIT*3))
            screen.blit(s3, (cx - sw3//2, cy + BASICAL_LENGTH_UNIT))

            # DRAW "NEW GAME" BUTTON
            new_game_button_rect.center = (cx, cy + BASICAL_LENGTH_UNIT*8)
            pygame.draw.rect(screen, (200,200,200), new_game_button_rect)
            pygame.draw.rect(screen, BLACK, new_game_button_rect, 2)
            btn_label = MEDIUM_FONT.render("New Game", True, BLACK)
            bw, bh = btn_label.get_size()
            screen.blit(btn_label, (
                new_game_button_rect.centerx - bw//2,
                new_game_button_rect.centery - bh//2
            ))

        pygame.display.flip()

def main():
    while True:
        action = run_game()
        if action == "quit":
            break  # exit main loop, quitting the game

if __name__ == "__main__":
    main()