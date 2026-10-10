#!/usr/bin/env python3
"""
DORA DASH!  --  a Pepsi Man-style 3D runner starring Dora (fan prototype).

Run:   pip install pygame
       python dora_dash.py

Controls
    A / D  or  Left / Right   change lane
    W / Up / Space            jump (over gaps and crates)
    S / Down                  slide (under barriers); in mid-air = fast-fall
    P pause    F11 / Alt+Enter fullscreen    Esc back / quit

Everything is drawn with code (no image or sound files). The 3D look is a
pseudo-3D perspective projection, so it runs on any PC.
"""
import array
import math
import os
import random
import shutil
import subprocess
import sys

import pygame

W, H = 960, 540
FPS = 60
HORIZON = 190
CAM_H = 3.3
CAM_BACK = 7.0
LANE_W = 2.0
ROAD_HALF = 3.1
DRAW_DIST = 150
GRAVITY = 48.0
JUMP_V = 14.8
STAND_H, SLIDE_H = 1.7, 0.65
CHECKPOINT_EVERY = 160


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def shade(c, f):
    return tuple(clamp(int(v * f), 0, 255) for v in c)


def mix(a, b, t):
    t = clamp(t, 0.0, 1.0)
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


THEMES = {
    "forest": dict(sky=((35, 30, 75), (150, 95, 130)), ground=((22, 58, 34), (28, 70, 40)),
                   road=((74, 64, 58), (84, 73, 66)), dash=(200, 190, 150), pit=(8, 6, 12),
                   fog=(150, 95, 130), hills=(60, 40, 85)),
    "highway": dict(sky=((70, 150, 225), (205, 235, 250)), ground=((52, 140, 60), (60, 155, 68)),
                    road=((62, 62, 68), (70, 70, 76)), dash=(235, 235, 235), pit=(18, 18, 24),
                    fog=(205, 235, 250), hills=(90, 150, 170)),
    "lake": dict(sky=((250, 120, 90), (255, 215, 140)), ground=((35, 105, 165), (42, 118, 178)),
                 road=((150, 104, 58), (166, 118, 68)), dash=(100, 66, 34), pit=(22, 80, 140),
                 fog=(255, 215, 140), hills=(200, 110, 100)),
}

LEVELS = [
    dict(name="The Spooky Forest", theme="forest", length=1100, v0=12, vmax=21,
         patterns=["crates", "barrier", "gap", "stars", "boulder", "swiper", "troll"],
         weights=[30, 18, 16, 10, 8, 6, 6], blurb="Logs, pits and one very grumpy troll."),
    dict(name="The Chaotic Highway", theme="highway", length=1500, v0=17, vmax=27,
         patterns=["crates", "barrier", "gap", "car", "swiper", "stars", "troll"],
         weights=[16, 16, 14, 28, 12, 6, 8], blurb="Traffic everywhere. Swiper is on the overpass!"),
    dict(name="Crocodile Lake", theme="lake", length=1900, v0=22, vmax=32,
         patterns=["gap", "croc", "troll", "barrier", "swiper", "crates", "boulder"],
         weights=[22, 24, 16, 10, 10, 10, 8], blurb="Snappy crocs and collapsing bridges. Hold on!"),
]

# kind -> (width, depth, y0, top)
KIND = {
    "crate": (1.6, 1.6, 0.0, 1.2), "barrier": (6.4, 0.6, 0.95, 4.0), "boulder": (1.7, 1.7, 0.0, 1.5),
    "junk": (1.1, 1.1, 0.0, 0.9), "car": (4.2, 2.2, 0.0, 1.6), "croc": (1.7, 2.6, 0.0, 0.9),
    "star": (1.0, 1.0, 0.9, 1.4), "map": (1.2, 1.0, 0.9, 1.7), "swiper": (1.2, 1.0, 0.0, 2.0),
    "troll": (1.8, 1.4, 0.0, 2.6), "flag": (6.4, 0.4, 0.0, 4.0),
}
HAZARDS = ("crate", "barrier", "boulder", "junk", "car", "croc")
JUNK_COLORS = [(90, 150, 220), (190, 190, 80), (200, 90, 90), (120, 200, 130)]


class Ent:
    def __init__(self, kind, x, z, y0=None, **kw):
        w, d, ky0, top = KIND[kind]
        self.kind, self.x, self.z = kind, x, z
        self.w, self.d = w, d
        self.y0 = ky0 if y0 is None else y0
        self.top = top if y0 is None else self.y0 + (top - ky0)
        self.dead = False
        self.t = random.random() * 2.4
        self.open = False
        self.__dict__.update(kw)
        self.init = (x, z)
        self.reset()

    def reset(self):
        self.x, self.z = self.init
        self.active = False
        self.state = "idle"
        self.timer = 0.0
        self.throws = 3
        self.vx = 0.0
        self.roll = 0.0
        self.age = 0.0


class Gap:
    def __init__(self, z0, z1, troll=False):
        self.z0, self.z1, self.troll = z0, z1, troll
        self.open = not troll

    def blocks(self):
        return self.open


def gen_level(idx, seed):
    rng = random.Random(seed * 31 + idx)
    L = LEVELS[idx]
    ents, gaps = [], []
    end = L["length"]
    z = 70.0
    maps_at = [end * 0.25, end * 0.55, end * 0.82]
    mi = 0
    for k in range(1, int(end // CHECKPOINT_EVERY) + 1):
        if k * CHECKPOINT_EVERY < end - 40:
            ents.append(Ent("flag", 0, k * CHECKPOINT_EVERY))
    while z < end - 70:
        prog = z / end
        v = lerp(L["v0"], L["vmax"], prog)
        spacing = max(v * 1.05, 18.0) + rng.uniform(0, 8)
        extra = 0.0
        if mi < 3 and z > maps_at[mi]:
            lane = rng.randrange(3)
            ents.append(Ent("crate", (lane - 1) * LANE_W, z))
            ents.append(Ent("map", (lane - 1) * LANE_W, z + 12))
            mi += 1
            z += 12 + spacing
            continue
        kind = rng.choices(L["patterns"], L["weights"])[0]
        if kind == "crates":
            n = 1 if rng.random() < 0.5 else 2
            lanes = rng.sample(range(3), n)
            for ln in lanes:
                ents.append(Ent("crate", (ln - 1) * LANE_W, z))
            free = [i for i in range(3) if i not in lanes]
            fl = rng.choice(free)
            for i in range(3):
                ents.append(Ent("star", (fl - 1) * LANE_W, z + i * 2.5))
            if prog > 0.4 and rng.random() < 0.4:
                lanes2 = rng.sample(range(3), 2)
                for ln in lanes2:
                    ents.append(Ent("crate", (ln - 1) * LANE_W, z + 11))
                extra = 11
        elif kind == "barrier":
            ents.append(Ent("barrier", 0, z))
            ln = rng.randrange(3)
            for i in range(3):
                ents.append(Ent("star", (ln - 1) * LANE_W, z - 2.5 + i * 2.5, y0=0.4))
        elif kind == "gap":
            ln = clamp(int(v * 0.38), 5, 11)
            gaps.append(Gap(z, z + ln))
            lane = rng.randrange(3)
            for i in range(4):
                t = (i + 0.5) / 4
                ents.append(Ent("star", (lane - 1) * LANE_W, z + t * ln, y0=1.0 + 1.5 * math.sin(math.pi * t)))
            extra = ln
        elif kind == "stars":
            lane = rng.randrange(3)
            for i in range(6):
                ents.append(Ent("star", (lane - 1) * LANE_W, z + i * 2.2))
            extra = 12
        elif kind == "boulder":
            ents.append(Ent("boulder", rng.randrange(3) * LANE_W - LANE_W, z + 30, act=55))
            extra = 20
        elif kind == "swiper":
            side = rng.choice([-1, 1])
            ents.append(Ent("swiper", side * 5.4, z + 10))
            extra = 28
        elif kind == "car":
            side = rng.choice([-1, 1])
            ents.append(Ent("car", side * 9.5, z, act=v * rng.uniform(0.9, 1.5), color=rng.choice(
                [(220, 60, 60), (60, 120, 220), (240, 200, 50), (80, 180, 90)])))
            extra = 6
        elif kind == "croc":
            ln = rng.randrange(3)
            ents.append(Ent("croc", (ln - 1) * LANE_W, z))
            ln2 = rng.choice([i for i in range(3) if i != ln])
            ents.append(Ent("croc", (ln2 - 1) * LANE_W, z + 9))
            extra = 9
        elif kind == "troll":
            ln = 6
            gaps.append(Gap(z, z + ln, troll=True))
            ents.append(Ent("troll", -4.9, z - 1.5))
            extra = ln
        z += spacing + extra
    return ents, gaps, end


# ----------------------------------------------------------------------------------
# Procedural sprites
# ----------------------------------------------------------------------------------
SKIN, HAIR, SHIRT, SHORTS, PACK = (240, 190, 140), (62, 36, 20), (240, 90, 150), (245, 150, 40), (130, 70, 190)
OUT = (40, 25, 30)


def make_dora_frame(phase=0.0, pose="run"):
    surf = pygame.Surface((220, 230), pygame.SRCALPHA)
    cx, gy = 110, 218

    def X(v):
        return cx + v * 100

    def Y(v):
        return gy - v * 100

    def rr(col, x0, y0, x1, y1, rad=10):
        r = pygame.Rect(int(X(x0)), int(Y(y1)), int((x1 - x0) * 100), int((y1 - y0) * 100))
        pygame.draw.rect(surf, col, r, border_radius=rad)
        pygame.draw.rect(surf, OUT, r, width=3, border_radius=rad)

    for side in (-1, 1):
        ph = phase + (0 if side < 0 else math.pi)
        if pose == "jump":
            foot = (side * 0.2, 0.32)
        else:
            foot = (side * 0.13, 0.04 + max(0.0, math.cos(ph)) * 0.30)
        hip = (side * 0.12, 0.66)
        pygame.draw.line(surf, OUT, (X(hip[0]), Y(hip[1])), (X(foot[0]), Y(foot[1] + 0.08)), 19)
        pygame.draw.line(surf, SKIN, (X(hip[0]), Y(hip[1])), (X(foot[0]), Y(foot[1] + 0.08)), 13)
        pygame.draw.ellipse(surf, (255, 255, 255), (X(foot[0]) - 17, Y(foot[1]) - 9, 34, 20))
        pygame.draw.ellipse(surf, OUT, (X(foot[0]) - 17, Y(foot[1]) - 9, 34, 20), 3)
        pygame.draw.line(surf, (250, 90, 150), (X(foot[0]) - 13, Y(foot[1]) + 1), (X(foot[0]) + 13, Y(foot[1]) + 1), 3)
    rr(SHORTS, -0.22, 0.58, 0.22, 0.86, 8)
    rr(SHIRT, -0.25, 0.82, 0.25, 1.32, 10)
    for side in (-1, 1):
        ph = phase + (0 if side < 0 else math.pi)
        if pose == "jump":
            hand = (side * 0.5, 1.72)
        else:
            hand = (side * 0.44, 0.88 + math.sin(ph) * 0.16)
        sh = (side * 0.28, 1.24)
        pygame.draw.line(surf, OUT, (X(sh[0]), Y(sh[1])), (X(hand[0]), Y(hand[1])), 17)
        pygame.draw.line(surf, SKIN, (X(sh[0]), Y(sh[1])), (X(hand[0]), Y(hand[1])), 11)
        pygame.draw.circle(surf, SKIN, (int(X(hand[0])), int(Y(hand[1]))), 8)
        pygame.draw.circle(surf, SHIRT, (int(X(sh[0])), int(Y(sh[1]))), 11)
    # Backpack (faces the camera -- it has a face!)
    rr(PACK, -0.29, 0.74, 0.29, 1.30, 14)
    rr(shade(PACK, 0.8), -0.2, 0.78, 0.2, 0.92, 6)
    for ex in (-0.1, 0.1):
        pygame.draw.circle(surf, (255, 255, 255), (int(X(ex)), int(Y(1.12))), 9)
        pygame.draw.circle(surf, (20, 20, 20), (int(X(ex)), int(Y(1.11))), 4)
    pygame.draw.arc(surf, (255, 230, 120), (X(-0.1), Y(1.02), 20, 12), math.pi, 2 * math.pi, 3)
    # Head: bob haircut seen from behind
    pygame.draw.rect(surf, SKIN, (int(X(-0.07)), int(Y(1.4)), 14, 14))
    rr(HAIR, -0.34, 1.16, 0.34, 1.82, 30)
    pygame.draw.arc(surf, shade(HAIR, 1.8), (X(-0.2), Y(1.78), 40, 30), 0.3, 2.6, 4)
    return surf.convert_alpha()


def speak(text):
    """Say text out loud using the operating system's built-in voice (no extra installs)."""
    try:
        if sys.platform.startswith("win"):
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Add-Type -AssemblyName System.Speech; "
                   "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 1; $s.Speak('%s')" % text.replace("'", "''")]
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        elif sys.platform == "darwin":
            subprocess.Popen(["say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for exe in ("spd-say", "espeak-ng", "espeak", "festival"):
                path = shutil.which(exe)
                if path:
                    if exe == "festival":
                        proc = subprocess.Popen([path, "--tts"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        proc.stdin.write(text.encode())
                        proc.stdin.close()
                    else:
                        subprocess.Popen([path, text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    break
    except Exception:
        pass


def make_tone(freq, dur, vol=0.25, sweep=0.0):
    rate = 22050
    n = int(rate * dur)
    buf = array.array("h")
    for i in range(n):
        t = i / rate
        env = 1.0 - i / n
        buf.append(int(32767 * vol * env * math.sin(2 * math.pi * (freq + sweep * t) * t)))
    return pygame.mixer.Sound(buffer=buf.tobytes())


class Game:
    def __init__(self, headless=False):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Dora Dash!")
        self.fullscreen = os.environ.get("DORA_WINDOWED") != "1"
        self.set_display()
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.SysFont("arialblack,comicsansms,arial", 56)
        self.f_mid = pygame.font.SysFont("arialblack,comicsansms,arial", 28)
        self.f_small = pygame.font.SysFont("arial,comicsansms", 20, bold=True)
        self.sfx = {}
        try:
            self.sfx = dict(jump=make_tone(440, 0.18, sweep=900), star=make_tone(1100, 0.12, sweep=1500),
                            hit=make_tone(200, 0.4, 0.35, sweep=-300), win=make_tone(660, 0.6, sweep=500),
                            slide=make_tone(300, 0.15, 0.2, sweep=-400), grr=make_tone(110, 0.35, 0.3, sweep=80))
        except Exception:
            pass
        self.skies = {n: self._make_sky(t) for n, t in THEMES.items()}
        self.frames = [make_dora_frame(i / 8 * 2 * math.pi) for i in range(8)]
        self.frame_jump = make_dora_frame(0, "jump")
        self.state = "menu"
        self.best = {}
        self.menu_z = 0.0
        self.shk = [0.0, 0.0]
        self.cx = self.cy = self.cz = 0.0
        self.focal = 500.0
        self.seen_hints = set()
        self.start_level(0, menu=True)

    def set_display(self):
        # Logical size stays 960x540; SCALED stretches it to the monitor (keeps aspect ratio).
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.fullscreen else 0)
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))

    # ---------------- setup ----------------
    def _make_sky(self, th):
        s = pygame.Surface((W, HORIZON + 20))
        top, bot = th["sky"]
        for y in range(HORIZON + 20):
            pygame.draw.line(s, mix(top, bot, y / (HORIZON + 20)), (0, y), (W, y))
        return s

    def play_sfx(self, name):
        s = self.sfx.get(name)
        if s:
            s.play()

    def start_level(self, idx, menu=False):
        self.level = idx
        self.L = LEVELS[idx]
        self.th = THEMES[self.L["theme"]]
        self.ents, self.gaps, self.finish_z = gen_level(idx, random.randrange(10 ** 6) if not menu else 1)
        self.junk, self.debris, self.parts, self.confetti = [], [], [], []
        self.z, self.x, self.y, self.vy = 0.0, 0.0, 0.0, 0.0
        self.lane = 1
        self.speed = self.L["v0"]
        self.speed_scale = 1.0
        self.slide_t = 0.0
        self.slide_pending = False
        self.jump_buf = 0.0
        self.phase = 0.0
        self.invuln = 0.0
        self.deaths = 0
        self.stars = 0
        self.maps = 0
        self.score = 0
        self.checkpoint = 0.0
        self.dead_t = 0.0
        self.spin = 0.0
        self.death_kind = ""
        self.banner = ("", 0.0)
        self.swing_t = 0.0
        self.swing_start = (0, 0, 0)
        self.result_t = 0.0
        self.elapsed = 0.0
        self.flash_lane = (None, 0.0)
        self.intro = 2.2
        if not menu:
            self.state = "play"

    def say(self, text, t=1.8):
        self.banner = (text, t)

    # ---------------- input ----------------
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            return False
        if e.type != pygame.KEYDOWN:
            return True
        k = e.key
        if k == pygame.K_F11 or (k == pygame.K_RETURN and e.mod & pygame.KMOD_ALT):
            self.fullscreen = not self.fullscreen
            self.set_display()
            return True
        if self.state == "menu":
            if k == pygame.K_ESCAPE:
                return False
            if k in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.start_level(k - pygame.K_1)
            elif k == pygame.K_RETURN:
                self.start_level(0)
            return True
        if k == pygame.K_ESCAPE:
            self.state = "menu"
            self.start_level(self.level, menu=True)
            self.state = "menu"
            return True
        if self.state == "result":
            if k == pygame.K_RETURN:
                self.state = "menu"
                self.start_level(self.level, menu=True)
                self.state = "menu"
            elif k == pygame.K_r:
                self.start_level(self.level)
            return True
        if k == pygame.K_p:
            self.state = "pause" if self.state == "play" else "play" if self.state == "pause" else self.state
            return True
        if self.state != "play":
            return True
        if k in (pygame.K_a, pygame.K_LEFT):
            self.lane = max(0, self.lane - 1)
        elif k in (pygame.K_d, pygame.K_RIGHT):
            self.lane = min(2, self.lane + 1)
        elif k in (pygame.K_w, pygame.K_UP, pygame.K_SPACE):
            self.jump_buf = 0.15
        elif k in (pygame.K_s, pygame.K_DOWN):
            if self.y > 0.01:
                self.vy = -34
                self.slide_pending = True
            elif self.slide_t <= 0:
                self.start_slide()
        return True

    def start_slide(self):
        self.slide_t = 0.75
        self.play_sfx("slide")

    # ---------------- simulation ----------------
    def die(self, kind):
        if self.invuln > 0 or self.state != "play":
            return
        self.state = "dead"
        self.dead_t = 1.25
        self.death_kind = kind
        self.deaths += 1
        self.vy = 12 if kind != "fell" else 4
        self.spin = 0.0
        self.shk = [0.0, 0.0]
        self.shake_t = 0.4
        self.play_sfx("hit")
        self.say(random.choice(["Oh no!", "Swiper, no swiping!", "¡Ay, caramba!", "OOPS!"]), 1.1)

    def respawn(self):
        cp = self.checkpoint
        self.z, self.y, self.vy, self.x = cp, 0.0, 0.0, (self.lane - 1) * LANE_W
        self.lane = 1
        self.x = 0.0
        self.state = "play"
        self.invuln = 2.2
        self.speed_scale = 0.6
        self.slide_t = 0.0
        self.junk.clear()
        for e in self.ents:
            if e.init[1] > cp and e.kind in ("boulder", "car", "swiper", "troll", "croc"):
                e.reset()
        for g in self.gaps:
            if g.troll and g.z0 > cp:
                g.open = False

    def near_barrier(self):
        for e in self.ents:
            if e.kind == "barrier" and abs(e.z - self.z) < e.d / 2 + 0.9:
                return True
        return False

    def update(self, dt):
        if self.state == "menu":
            self.menu_z += 14 * dt
            self.phase += dt * 16
            return
        if self.state in ("pause", "result") and self.state != "result":
            return
        self.update_fx(dt)
        if self.state == "result":
            self.result_t += dt
            self.update_swing_sway(dt)
            return
        if self.state == "dead":
            self.dead_t -= dt
            self.vy -= GRAVITY * dt
            self.y += self.vy * dt
            if self.death_kind != "fell" and self.y < 0:
                self.y, self.vy = 0.0, 0.0
            self.spin += dt * 700
            if self.dead_t <= 0:
                self.respawn()
            return
        if self.state == "swing":
            self.update_swing(dt)
            return
        self.elapsed += dt
        self.intro = max(0.0, self.intro - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.speed_scale = min(1.0, self.speed_scale + dt * 0.4)
        base = lerp(self.L["v0"], self.L["vmax"], clamp(self.z / self.finish_z, 0, 1))
        self.speed = base * self.speed_scale
        self.z += self.speed * dt
        self.phase += dt * (9 + self.speed * 0.55)

        tx = (self.lane - 1) * LANE_W
        self.x += (tx - self.x) * (1 - math.exp(-16 * dt))

        self.jump_buf = max(0.0, self.jump_buf - dt)
        grounded = self.y <= 0.0 and self.vy <= 0
        if self.jump_buf > 0 and grounded:
            self.vy = JUMP_V
            self.y = 0.0001
            self.jump_buf = 0
            self.slide_t = 0
            self.play_sfx("jump")
            grounded = False
        if not grounded:
            self.vy -= GRAVITY * dt
            self.y += self.vy * dt
            if self.y <= 0:
                self.y, self.vy = 0.0, 0.0
                self.burst(self.x, 0.1, self.z, (200, 190, 160), 6)
                if self.slide_pending:
                    self.slide_pending = False
                    self.start_slide()
        if self.slide_t > 0:
            self.slide_t -= dt
            if self.slide_t <= 0 and self.near_barrier():
                self.slide_t = 0.05
        if self.y <= 0.02 and int(self.elapsed * 30) % 3 == 0:
            self.parts.append([self.x + random.uniform(-0.3, 0.3), 0.1, self.z - 0.3, random.uniform(-1, 1), 1.5, 0.35, (210, 200, 170)])

        # checkpoints
        if self.z - self.checkpoint >= CHECKPOINT_EVERY:
            self.checkpoint = int(self.z // CHECKPOINT_EVERY) * CHECKPOINT_EVERY
            self.say("Checkpoint!", 1.0)

        self.update_world(dt)
        self.check_collisions()

        if self.z >= self.finish_z - 12:
            self.begin_swing()

    def update_fx(self, dt):
        if getattr(self, "shake_t", 0) > 0:
            self.shake_t -= dt
            self.shk = [random.uniform(-6, 6), random.uniform(-6, 6)]
        else:
            self.shk = [0.0, 0.0]
        txt, t = self.banner
        self.banner = (txt, max(0.0, t - dt))
        fl, ft = self.flash_lane
        self.flash_lane = (fl, max(0.0, ft - dt))
        for p in self.parts[:]:
            p[0] += p[3] * dt
            p[1] += p[4] * dt
            p[4] -= 9 * dt
            p[5] -= dt
            if p[5] <= 0:
                self.parts.remove(p)
        for d in self.debris[:]:
            d[1] += d[3] * dt
            d[3] -= GRAVITY * dt
            d[4] += 240 * dt
            if d[1] < -5:
                self.debris.remove(d)
        for c in self.confetti[:]:
            c[0] += c[2] * dt
            c[1] += c[3] * dt
            c[3] += 400 * dt
            c[5] -= dt
            if c[5] <= 0 or c[1] > H:
                self.confetti.remove(c)

    def burst(self, x, y, z, col, n):
        for _ in range(n):
            self.parts.append([x, y, z, random.uniform(-2.5, 2.5), random.uniform(2, 6), 0.5, col])

    def update_world(self, dt):
        z = self.z
        for g in self.gaps:
            if g.troll and not g.open and g.z0 - z < 30:
                g.open = True
                self.play_sfx("grr")
                self.say("Troll: \"GRR! You shall not pass!\"", 1.6)
                for i in range(8):
                    self.debris.append([lerp(-ROAD_HALF + 0.4, ROAD_HALF - 0.4, i / 7), 0.0, lerp(g.z0, g.z1, random.random()),
                                        random.uniform(0, 4), random.uniform(0, 90)])
        for e in self.ents:
            dz = e.z - z
            if dz > 130 or dz < -25:
                continue
            k = e.kind
            if k == "boulder":
                if not e.active and dz < e.act:
                    e.active = True
                if e.active:
                    e.z -= 9 * dt
                    e.roll += dt * 360
            elif k == "car":
                if not e.active and dz < e.act:
                    e.active = True
                    e.vx = -math.copysign(7.5 + self.speed / 5, e.x)
                if e.active:
                    e.x += e.vx * dt
            elif k == "croc":
                e.t += dt
                e.open = (e.t % 2.4) < 1.15
            elif k == "swiper":
                if e.state == "idle" and dz < 62 and self.invuln <= 0 or (e.state == "idle" and dz < 62):
                    e.state = "throw"
                    e.timer = 0.6
                    self.say("Swiper: \"Oh, man!\"", 1.2)
                if e.state == "throw":
                    e.age += dt
                    e.timer -= dt
                    if e.timer <= 0 and e.throws > 0:
                        lane = random.randrange(3)
                        self.flash_lane = (lane, 0.7)
                        tx = (lane - 1) * LANE_W
                        j = Ent("junk", e.x, e.z, color=random.choice(JUNK_COLORS))
                        j.tx, j.sx = tx, e.x
                        j.age = 0.0
                        self.junk.append(j)
                        e.throws -= 1
                        e.timer = 0.85
                    if e.throws == 0 and e.timer <= 0:
                        e.state = "done"
        for j in self.junk[:]:
            j.age += dt
            if j.age < 0.5:
                tt = j.age / 0.5
                j.x = lerp(j.sx, j.tx, tt)
                j.y0 = 0.0 + math.sin(math.pi * tt) * 2.5
                j.top = j.y0 + 0.9
            else:
                j.y0, j.top = 0.0, 0.9
                j.x = j.tx
                j.z -= 14 * dt
            j.roll = getattr(j, "roll", 0) + dt * 500
            if j.z < z - 15:
                self.junk.remove(j)

    def check_collisions(self):
        z, ph = self.z, SLIDE_H if self.slide_t > 0 else STAND_H
        # gaps
        if self.invuln <= 0 and self.y <= 0.02:
            for g in self.gaps:
                if g.blocks() and g.z0 + 0.3 < z < g.z1 - 0.3:
                    self.die("fell")
                    return
        for e in self.ents + self.junk:
            if abs(e.z - z) > 4 and e.kind != "car":
                continue
            k = e.kind
            if k in ("star", "map"):
                if not e.dead and abs(e.x - self.x) < 1.0 and abs(e.z - z) < 1.1 and \
                        self.y - 0.3 < e.top and self.y + ph + 0.3 > e.y0:
                    e.dead = True
                    self.play_sfx("star")
                    self.burst(e.x, e.y0 + 0.4, e.z, (255, 220, 60), 8)
                    if k == "star":
                        self.stars += 1
                        self.score += 10
                    else:
                        self.maps += 1
                        self.score += 100
                        self.say("Map piece %d/3!" % self.maps, 1.4)
                continue
            if k not in HAZARDS:
                continue
            if k == "croc" and not e.open:
                continue
            if self.invuln > 0:
                continue
            if abs(e.x - self.x) < e.w / 2 + 0.4 and abs(e.z - z) < e.d / 2 + 0.35 and \
                    self.y < e.top and self.y + ph > e.y0:
                self.die(k)
                return
        # first-time hints
        for e in self.ents:
            dz = e.z - z
            if 0 < dz < 40 and e.kind in ("barrier", "crate", "boulder") and ("h" + e.kind) not in self.seen_hints:
                self.seen_hints.add("h" + e.kind)
                self.say({"barrier": "Slide under it! (S)", "crate": "Switch lanes! (A / D)", "boulder": "Look out, it's rolling!"}[e.kind], 2.0)
        for g in self.gaps:
            if 0 < g.z0 - z < 40 and "hgap" not in self.seen_hints and not g.troll:
                self.seen_hints.add("hgap")
                self.say("Can you say... JUMP?!  (Space)", 2.2)

    # ---------------- Banana Swing ----------------
    def begin_swing(self):
        self.state = "swing"
        self.swing_t = 0.0
        self.swing_start = (self.x, self.y, self.z)
        self.slide_t = 0
        self.play_sfx("win")

    def swing_seat(self, t):
        ang = math.sin(t * 2.2) * 0.45
        L = 3.2
        return (0.0, 6.0 - L * math.cos(ang), self.finish_z + L * math.sin(ang))

    def update_swing(self, dt):
        self.swing_t += dt
        t = clamp(self.swing_t / 0.95, 0, 1)
        sx, sy, sz = self.swing_start
        ex, ey, ez = self.swing_seat(self.swing_t)
        self.x = lerp(sx, ex, t)
        self.z = lerp(sz, ez, t)
        self.y = lerp(sy, ey, t) + math.sin(math.pi * t) * 3.0
        self.spin = t * 720
        self.phase += dt * 10
        if t >= 1.0:
            self.spin = 0
            self.state = "result"
            self.result_t = 0.0
            self.say("I'm Dora the Explorer!", 4.0)
            speak("I'm Dora the Explorer!")
            for _ in range(160):
                self.confetti.append([random.uniform(0, W), random.uniform(-200, 0), random.uniform(-60, 60),
                                      random.uniform(60, 200), random.choice([(255, 90, 150), (255, 210, 50), (90, 200, 255), (130, 230, 120), (190, 120, 255)]),
                                      random.uniform(3, 6)])
            stars_total = sum(1 for e in self.ents if e.kind == "star")
            r = 1 + (self.deaths <= 2) + (stars_total > 0 and self.stars >= 0.7 * stars_total)
            self.rating = int(r)
            self.best[self.level] = max(self.best.get(self.level, 0), self.rating)
            self.stars_total = stars_total

    def update_swing_sway(self, dt):
        self.swing_t += dt
        ex, ey, ez = self.swing_seat(self.swing_t)
        self.x, self.y, self.z = ex, ey, ez
        if random.random() < 0.6:
            self.confetti.append([random.uniform(0, W), -10, random.uniform(-60, 60), random.uniform(60, 200),
                                  random.choice([(255, 90, 150), (255, 210, 50), (90, 200, 255), (130, 230, 120)]), random.uniform(3, 6)])

    # ---------------- projection / drawing helpers ----------------
    def P(self, x, y, z):
        dz = z - self.cz
        if dz < 0.3:
            return None
        s = self.focal / dz
        return (W / 2 + (x - self.cx) * s + self.shk[0], HORIZON + (self.cy - y) * s + self.shk[1], s)

    def fogc(self, col, z):
        return mix(col, self.th["fog"], ((z - self.cz) / DRAW_DIST) ** 1.5)

    def poly(self, pts, col, outline=None, w=2):
        if any(p is None for p in pts):
            return
        xy = [(p[0], p[1]) for p in pts]
        pygame.draw.polygon(self.screen, col, xy)
        if outline:
            pygame.draw.polygon(self.screen, outline, xy, w)

    def set_camera(self):
        self.cx = self.x * 0.65
        self.cy = CAM_H + max(0.0, self.y) * 0.4
        self.cz = self.z - CAM_BACK
        self.focal = 500 + self.speed * 4.5
        if self.state in ("swing", "result"):
            # pull the camera back so the whole swing is in frame
            self.cz = min(self.cz, self.finish_z - 15)
            self.cx *= 0.3
            self.cy = 4.2

    def draw_scene(self, gaps):
        scr, th = self.screen, self.th
        scr.blit(self.skies[self.L["theme"]], (0, 0))
        self.draw_hills()
        hy = int(HORIZON + self.shk[1])
        pygame.draw.rect(scr, th["ground"][0], (0, hy, W, H - hy))
        step = 2.0
        k_far = int((self.cz + DRAW_DIST) // step)
        k_near = int((self.cz + 0.35) // step)
        R = ROAD_HALF
        drawn = set()
        for k in range(k_far, k_near - 1, -1):
            z0, z1 = max(k * step, self.cz + 0.35), (k + 1) * step
            if z1 <= z0:
                continue
            alt = k % 2
            self.poly([self.P(-45, 0, z0), self.P(45, 0, z0), self.P(45, 0, z1), self.P(-45, 0, z1)],
                      self.fogc(th["ground"][alt], z1))
            for g in gaps:
                if id(g) not in drawn and z0 < g.z1 and g.blocks() and g.z1 - self.cz > 0.4 and g.z0 - self.cz < DRAW_DIST:
                    drawn.add(id(g))
                    self.draw_pit(g)
            segs = [(z0, z1)]
            troll_closed = None
            for g in gaps:
                if z0 < g.z1 and z1 > g.z0:
                    if g.blocks():
                        new = []
                        for a, b in segs:
                            if a < g.z0:
                                new.append((a, min(b, g.z0)))
                            if b > g.z1:
                                new.append((max(a, g.z1), b))
                        segs = new
                    else:
                        troll_closed = g
            for a, b in segs:
                if b - a < 0.01:
                    continue
                col = th["road"][alt]
                if troll_closed is not None:
                    col = (150, 100, 55) if int(a) % 2 == 0 else (125, 82, 44)
                self.poly([self.P(-R, 0, a), self.P(R, 0, a), self.P(R, 0, b), self.P(-R, 0, b)], self.fogc(col, b))
                for sx in (-R, R - 0.25):
                    self.poly([self.P(sx, 0, a), self.P(sx + 0.25, 0, a), self.P(sx + 0.25, 0, b), self.P(sx, 0, b)],
                              self.fogc((230, 230, 230) if alt else (200, 60, 60), b))
                if alt == 0 and troll_closed is None:
                    for lx in (-1.0, 1.0):
                        self.poly([self.P(lx - 0.06, 0, a), self.P(lx + 0.06, 0, a), self.P(lx + 0.06, 0, b), self.P(lx - 0.06, 0, b)],
                                  self.fogc(th["dash"], b))

    def draw_pit(self, g):
        R = ROAD_HALF
        za = max(g.z0, self.cz + 0.35)
        pit = self.th["pit"]
        self.poly([self.P(-R, -4, za), self.P(R, -4, za), self.P(R, -4, g.z1), self.P(-R, -4, g.z1)], pit)
        self.poly([self.P(-R, 0, g.z1), self.P(R, 0, g.z1), self.P(R, -4, g.z1), self.P(-R, -4, g.z1)],
                  shade(self.th["road"][0], 0.45))

    def draw_hills(self):
        th = self.th
        off = self.cx * 0.03
        pts = [(0, HORIZON + self.shk[1])]
        for x in range(0, W + 31, 30):
            h = 34 + 22 * math.sin(x * 0.011 + off) + 12 * math.sin(x * 0.037 - off * 2)
            pts.append((x, HORIZON - h + self.shk[1]))
        pts.append((W, HORIZON + self.shk[1]))
        pygame.draw.polygon(self.screen, mix(th["hills"], th["fog"], 0.3), pts)
        if self.L["theme"] == "lake":
            pygame.draw.circle(self.screen, (255, 240, 190), (W // 2 + 140 - int(off * 8), HORIZON - 70), 46)

    def box(self, x, z, w, d, y0, y1, col):
        zn, zf = z - d / 2, z + d / 2
        if zf - self.cz < 0.45:
            return None
        zn = max(zn, self.cz + 0.35)
        x0, x1 = x - w / 2, x + w / 2
        col = self.fogc(col, zn)
        f = [self.P(x0, y1, zn), self.P(x1, y1, zn), self.P(x1, y0, zn), self.P(x0, y0, zn)]
        b = [self.P(x0, y1, zf), self.P(x1, y1, zf), self.P(x1, y0, zf), self.P(x0, y0, zf)]
        if None in f or None in b:
            return None
        ow = 2 if f[0][2] > 14 else 1
        edge = shade(col, 0.4)
        if self.cx < x0:
            self.poly([f[0], b[0], b[3], f[3]], shade(col, 0.7), edge, ow)
        elif self.cx > x1:
            self.poly([f[1], b[1], b[2], f[2]], shade(col, 0.7), edge, ow)
        if y1 < self.cy:
            self.poly([f[0], f[1], b[1], b[0]], shade(col, 1.25), edge, ow)
        self.poly(f, col, edge, ow)
        return (f[0][0], f[0][1], f[2][0], f[2][1], f[0][2])

    # ---------------- entity sprites ----------------
    def draw_ent(self, e):
        k = e.kind
        if k == "crate":
            r = self.box(e.x, e.z, e.w, e.d, 0, 1.2, (190, 130, 60))
            if r:
                pygame.draw.line(self.screen, (110, 70, 30), (r[0], r[1]), (r[2], r[3]), 3)
                pygame.draw.line(self.screen, (110, 70, 30), (r[0], r[3]), (r[2], r[1]), 3)
        elif k == "barrier":
            for px in (-3.0, 3.0):
                self.box(px, e.z, 0.35, 0.5, 0, 3.2, (90, 90, 100))
            r = self.box(0, e.z, 6.2, 0.4, 0.95, 3.0, (250, 200, 30))
            if r:
                l, t, rt, bt, s = r
                n = 7
                for i in range(n):
                    if i % 2:
                        continue
                    a = l + (rt - l) * i / n
                    b = l + (rt - l) * (i + 1) / n
                    pygame.draw.polygon(self.screen, (40, 40, 40), [(a, bt), (b, bt), (b + (b - a) * 0.0 + 14 * s / 80, t), (a + 14 * s / 80, t)])
        elif k == "boulder":
            p = self.P(e.x, 0.8, e.z)
            if p:
                x, y, s = p
                col = self.fogc((130, 130, 140), e.z)
                pygame.draw.circle(self.screen, col, (int(x), int(y)), int(0.85 * s))
                pygame.draw.circle(self.screen, shade(col, 0.4), (int(x), int(y)), int(0.85 * s), 3)
                a = math.radians(e.roll)
                pygame.draw.line(self.screen, shade(col, 0.5), (x, y), (x + math.cos(a) * 0.6 * s, y + math.sin(a) * 0.6 * s), 4)
                pygame.draw.circle(self.screen, shade(col, 0.65), (int(x + math.cos(a + 2) * 0.35 * s), int(y + math.sin(a + 2) * 0.35 * s)), int(0.18 * s))
        elif k == "junk":
            r = self.box(e.x, e.z, 1.0, 1.0, e.y0, e.y0 + 0.9, e.color)
            if r:
                pygame.draw.circle(self.screen, (255, 255, 255), (int((r[0] + r[2]) / 2), int((r[1] + r[3]) / 2)), max(2, int(r[4] * 0.12)))
        elif k == "car":
            self.draw_car(e)
        elif k == "croc":
            self.draw_croc(e)
        elif k in ("star", "map") and not e.dead:
            self.draw_pickup(e)
        elif k == "swiper":
            self.draw_swiper(e)
        elif k == "troll":
            self.draw_troll(e)
        elif k == "flag":
            self.draw_flag(e)

    def draw_car(self, e):
        r = self.box(e.x, e.z, 4.2, 2.2, 0.3, 1.0, e.color)
        self.box(e.x, e.z, 2.4, 1.8, 1.0, 1.6, shade(e.color, 1.1))
        if r:
            l, t, rt, bt, s = r
            for wx in (l + (rt - l) * 0.22, l + (rt - l) * 0.78):
                pygame.draw.circle(self.screen, (25, 25, 25), (int(wx), int(bt)), max(3, int(0.42 * s)))
                pygame.draw.circle(self.screen, (170, 170, 170), (int(wx), int(bt)), max(2, int(0.18 * s)))

    def draw_croc(self, e):
        col = (60, 150, 70)
        if e.open:
            r = self.box(e.x, e.z, 1.7, 2.6, 0, 0.9, col)
            if r:
                l, t, rt, bt, s = r
                pygame.draw.rect(self.screen, (200, 40, 50), (l + 3, t + (bt - t) * 0.3, rt - l - 6, (bt - t) * 0.45))
                n = 5
                for i in range(n):
                    a = l + (rt - l) * i / n
                    pygame.draw.polygon(self.screen, (255, 255, 255), [(a, t + (bt - t) * 0.3), (a + (rt - l) / n, t + (bt - t) * 0.3), (a + (rt - l) / (2 * n), t + (bt - t) * 0.55)])
        else:
            self.box(e.x, e.z, 1.4, 2.2, 0, 0.18, (40, 110, 60))
            for ex in (-0.4, 0.4):
                self.box(e.x + ex, e.z - 0.8, 0.3, 0.3, 0.18, 0.4, (230, 220, 90))

    def draw_pickup(self, e):
        bob = math.sin(self.elapsed * 5 + e.x + e.z) * 0.12
        p = self.P(e.x, e.y0 + 0.45 + bob, e.z)
        if not p:
            return
        x, y, s = p
        if e.kind == "star":
            R = 0.5 * s
            pts = []
            for i in range(10):
                r = R if i % 2 == 0 else R * 0.45
                a = -math.pi / 2 + i * math.pi / 5
                pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
            pygame.draw.polygon(self.screen, self.fogc((255, 215, 40), e.z), pts)
            pygame.draw.polygon(self.screen, (180, 120, 0), pts, 2)
        else:
            w, h = 0.9 * s, 0.7 * s
            pygame.draw.rect(self.screen, (235, 215, 160), (x - w / 2, y - h / 2, w, h), border_radius=4)
            pygame.draw.rect(self.screen, (120, 80, 40), (x - w / 2, y - h / 2, w, h), 3, border_radius=4)
            pygame.draw.line(self.screen, (210, 40, 40), (x - w * 0.25, y - h * 0.25), (x + w * 0.25, y + h * 0.25), 4)
            pygame.draw.line(self.screen, (210, 40, 40), (x - w * 0.25, y + h * 0.25), (x + w * 0.25, y - h * 0.25), 4)

    def draw_swiper(self, e):
        if e.state == "idle":
            return
        p = self.P(e.x, 0, e.z)
        if not p:
            return
        x, y, s = p
        pop = clamp(e.age * 5, 0, 1)
        if e.state == "done":
            pop = 1.0
        x += math.copysign(1, e.x) * (1 - pop) * 2.5 * s
        sc = s
        scr = self.screen
        orange, dark = self.fogc((235, 120, 30), e.z), (40, 25, 15)
        pygame.draw.ellipse(scr, orange, (x - 0.55 * sc, y - 1.6 * sc, 1.1 * sc, 1.7 * sc))
        pygame.draw.ellipse(scr, dark, (x - 0.55 * sc, y - 1.6 * sc, 1.1 * sc, 1.7 * sc), 3)
        tailx = x - math.copysign(1, e.x) * 0.9 * sc
        pygame.draw.ellipse(scr, orange, (tailx - 0.3 * sc, y - 1.5 * sc, 0.6 * sc, 1.3 * sc))
        pygame.draw.circle(scr, (255, 255, 255), (int(tailx), int(y - 1.4 * sc)), int(0.2 * sc))
        hy = y - 2.0 * sc
        pygame.draw.circle(scr, orange, (int(x), int(hy)), int(0.5 * sc))
        pygame.draw.circle(scr, dark, (int(x), int(hy)), int(0.5 * sc), 3)
        for ex in (-0.32, 0.32):
            pygame.draw.polygon(scr, orange, [(x + ex * sc - 0.15 * sc, hy - 0.35 * sc), (x + ex * sc + 0.15 * sc, hy - 0.35 * sc), (x + ex * sc * 1.2, hy - 0.85 * sc)])
        pygame.draw.rect(scr, (50, 70, 200), (x - 0.5 * sc, hy - 0.17 * sc, 1.0 * sc, 0.28 * sc), border_radius=6)
        pygame.draw.ellipse(scr, (255, 255, 255), (x - 0.22 * sc, hy + 0.08 * sc, 0.44 * sc, 0.3 * sc))
        pygame.draw.circle(scr, dark, (int(x), int(hy + 0.13 * sc)), max(2, int(0.07 * sc)))
        up = e.state == "throw" and (e.timer % 0.85) > 0.4
        ax = x + math.copysign(-1, e.x) * 0.7 * sc
        pygame.draw.line(scr, orange, (x, y - 1.35 * sc), (ax, y - (2.0 if up else 0.9) * sc), max(3, int(0.22 * sc)))

    def draw_troll(self, e):
        p = self.P(e.x, 0, e.z)
        if not p:
            return
        x, y, s = p
        scr = self.screen
        body = self.fogc((95, 125, 100), e.z)
        dark = (30, 40, 30)
        pygame.draw.ellipse(scr, body, (x - 0.9 * s, y - 2.0 * s, 1.8 * s, 2.1 * s))
        pygame.draw.ellipse(scr, dark, (x - 0.9 * s, y - 2.0 * s, 1.8 * s, 2.1 * s), 3)
        hy = y - 2.5 * s
        pygame.draw.circle(scr, body, (int(x), int(hy)), int(0.7 * s))
        pygame.draw.circle(scr, dark, (int(x), int(hy)), int(0.7 * s), 3)
        for ex in (-0.28, 0.28):
            pygame.draw.circle(scr, (255, 255, 200), (int(x + ex * s), int(hy - 0.08 * s)), int(0.16 * s))
            pygame.draw.circle(scr, dark, (int(x + ex * s), int(hy - 0.04 * s)), int(0.07 * s))
        pygame.draw.line(scr, dark, (x - 0.5 * s, hy - 0.4 * s), (x - 0.1 * s, hy - 0.2 * s), 5)
        pygame.draw.line(scr, dark, (x + 0.5 * s, hy - 0.4 * s), (x + 0.1 * s, hy - 0.2 * s), 5)
        pygame.draw.circle(scr, shade(body, 0.75), (int(x), int(hy + 0.12 * s)), int(0.18 * s))
        pygame.draw.line(scr, dark, (x - 0.3 * s, hy + 0.42 * s), (x + 0.3 * s, hy + 0.42 * s), 4)
        pygame.draw.line(scr, (120, 80, 40), (x + 1.0 * s, y - 0.2 * s), (x + 1.1 * s, y - 2.8 * s), max(4, int(0.25 * s)))

    def draw_flag(self, e):
        done = self.checkpoint >= e.z
        col = (80, 220, 120) if done else (230, 60, 90)
        for px in (-3.4, 3.4):
            self.box(px, e.z, 0.25, 0.25, 0, 4.0, (210, 210, 220))
        a, b = self.P(-3.4, 4.0, e.z), self.P(3.4, 4.0, e.z)
        if a and b:
            s = a[2]
            pygame.draw.polygon(self.screen, self.fogc(col, e.z), [(a[0], a[1]), (b[0], b[1]), (b[0], b[1] + 0.9 * s), (a[0], a[1] + 0.9 * s)])
            lab = self.f_small.render("CHECKPOINT" if not done else "CHECKED!", True, (255, 255, 255))
            if s > 18:
                lab = pygame.transform.smoothscale(lab, (int(lab.get_width() * s / 60), int(lab.get_height() * s / 60))) if s < 60 else lab
                self.screen.blit(lab, ((a[0] + b[0]) / 2 - lab.get_width() / 2, a[1] + 0.45 * s - lab.get_height() / 2))

    def draw_swing(self):
        fz = self.finish_z
        for px in (-3.6, 3.6):
            self.box(px, fz, 0.5, 0.6, 0, 6.2, (150, 100, 50))
        self.box(0, fz, 7.7, 0.6, 6.0, 6.4, (150, 100, 50))
        ex, ey, ez = self.swing_seat(self.swing_t if self.state in ("swing", "result") else 0.0)
        sp = self.P(ex, ey, ez)
        for rx in (-0.9, 0.9):
            a, b = self.P(rx, 6.0, fz), self.P(ex + rx, ey + 0.4, ez)
            if a and b:
                pygame.draw.line(self.screen, (110, 80, 40), (a[0], a[1]), (b[0], b[1]), 4)
        if sp:
            x, y, s = sp
            pts_o, pts_i = [], []
            for i in range(13):
                a = math.radians(-65 + i * 130 / 12)
                pts_o.append((x + math.sin(a) * 1.5 * s, y + (1 - math.cos(a)) * 0.9 * s))
                pts_i.append((x + math.sin(a) * 1.35 * s, y + (1 - math.cos(a)) * 0.9 * s - 0.28 * s))
            pts = pts_o + pts_i[::-1]
            pygame.draw.polygon(self.screen, (255, 225, 40), pts)
            pygame.draw.polygon(self.screen, (150, 110, 0), pts, 3)
        banner = self.f_mid.render("BANANA SWING!", True, (255, 240, 120))
        top = self.P(0, 6.9, fz)
        if top and top[2] > 6:
            k = clamp(top[2] / 45, 0.2, 2.0)
            bs = pygame.transform.smoothscale(banner, (max(1, int(banner.get_width() * k)), max(1, int(banner.get_height() * k))))
            self.screen.blit(bs, (top[0] - bs.get_width() / 2, top[1] - bs.get_height() / 2))

    def draw_deco(self, side, k):
        rng = random.Random(k * 977 + side * 13 + self.level * 5)
        z = k * 7.0 + rng.uniform(-1.5, 1.5)
        x = side * (4.6 + rng.random() * 7)
        th = self.L["theme"]
        p = self.P(x, 0, z)
        if not p:
            return
        sx, sy, s = p
        scr = self.screen
        if sx < -250 or sx > W + 250:
            return
        if th == "lake":
            if rng.random() < 0.55:
                col = self.fogc((70, 170, 90), z)
                pygame.draw.ellipse(scr, col, (sx - 0.9 * s, sy - 0.2 * s, 1.8 * s, 0.4 * s))
                if rng.random() < 0.4:
                    pygame.draw.circle(scr, self.fogc((255, 130, 190), z), (int(sx), int(sy - 0.25 * s)), max(2, int(0.18 * s)))
            else:
                for i in range(3):
                    pygame.draw.line(scr, self.fogc((90, 140, 60), z), (sx + i * 0.2 * s, sy), (sx + i * 0.2 * s + 0.1 * s, sy - 2.0 * s), max(2, int(0.1 * s)))
            return
        if th == "highway" and k % 3 == 0:
            pygame.draw.line(scr, self.fogc((70, 70, 80), z), (sx, sy), (sx, sy - 5 * s), max(2, int(0.2 * s)))
            pygame.draw.circle(scr, self.fogc((255, 240, 150), z), (int(sx), int(sy - 5.1 * s)), max(2, int(0.35 * s)))
            return
        trunk = self.fogc((90, 60, 40), z)
        leaf = self.fogc((28, 90, 52) if th == "forest" else (40, 140, 55), z)
        pygame.draw.rect(scr, trunk, (sx - 0.25 * s, sy - 2.2 * s, 0.5 * s, 2.2 * s))
        for i, wd in enumerate((2.0, 1.6, 1.1)):
            base = sy - (1.6 + i * 1.1) * s
            pygame.draw.polygon(scr, shade(leaf, 1 + i * 0.12), [(sx - wd * s, base), (sx + wd * s, base), (sx, base - 1.9 * s)])
        if th == "forest" and rng.random() < 0.35:
            mx = sx + side * -1.6 * s
            pygame.draw.rect(scr, (230, 220, 200), (mx - 0.06 * s, sy - 0.4 * s, 0.12 * s, 0.4 * s))
            pygame.draw.ellipse(scr, self.fogc((90, 230, 230), z), (mx - 0.3 * s, sy - 0.65 * s, 0.6 * s, 0.4 * s))

    def draw_dora(self):
        p = self.P(self.x, max(self.y, -3), self.z)
        if not p:
            return
        sx, sy, s = p
        k = s / 100.0
        scr = self.screen
        blink = self.invuln > 0 and int(self.invuln * 14) % 2 == 0 and self.state == "play"
        if blink:
            return
        gp = self.P(self.x, 0, self.z)
        over_gap = any(g.blocks() and g.z0 < self.z < g.z1 for g in self.gaps)
        if gp and not over_gap:
            sh = max(0.35, 1 - self.y * 0.18)
            pygame.draw.ellipse(scr, (0, 0, 0, 90) if False else (20, 20, 20), (gp[0] - 0.45 * s * sh, gp[1] - 0.12 * s * sh, 0.9 * s * sh, 0.24 * s * sh))
        if self.state == "dead":
            img = pygame.transform.rotozoom(self.frame_jump, self.spin, k)
            scr.blit(img, img.get_rect(center=(sx, sy - 0.9 * s)))
            for i in range(3):
                a = self.spin * 0.02 + i * 2.1
                pygame.draw.circle(scr, (255, 220, 60), (int(sx + math.cos(a) * 0.7 * s), int(sy - 1.9 * s + math.sin(a) * 0.2 * s)), max(3, int(0.12 * s)))
            return
        if self.state in ("swing", "result"):
            img = pygame.transform.rotozoom(self.frame_jump, -self.spin if self.state == "swing" else 0, k * 1.1)
            scr.blit(img, img.get_rect(midbottom=(sx, sy + 0.2 * s)) if self.state == "result" else img.get_rect(center=(sx, sy - 0.9 * s)))
            return
        if self.slide_t > 0:
            img = pygame.transform.rotozoom(self.frames[0], 78, k)
            scr.blit(img, img.get_rect(center=(sx, sy - 0.5 * s)))
            return
        frame = self.frame_jump if self.y > 0.15 else self.frames[int(self.phase) % 8]
        img = pygame.transform.smoothscale(frame, (max(1, int(frame.get_width() * k)), max(1, int(frame.get_height() * k))))
        scr.blit(img, img.get_rect(midbottom=(sx, sy + 0.22 * s)))

    def draw_particles(self):
        for x, y, z, vx, vy, life, col in self.parts:
            p = self.P(x, y, z)
            if p:
                pygame.draw.circle(self.screen, col, (int(p[0]), int(p[1])), max(2, int(0.09 * p[2])))
        for x, y, z, vy, rot in self.debris:
            r = self.box(x, z, 1.3, 0.9, y, y + 0.18, (150, 100, 55))

    # ---------------- frame draw ----------------
    def draw(self):
        scr = self.screen
        if self.state == "menu":
            self.draw_menu()
            pygame.display.flip()
            return
        self.set_camera()
        self.draw_scene(self.gaps)
        items = []
        z0 = self.cz
        for side in (-1, 1):
            for k in range(int((z0 + DRAW_DIST) // 7), int(z0 // 7) - 1, -1):
                items.append((k * 7.0, 0, ("deco", side, k)))
        for e in self.ents + self.junk:
            dz = e.z - z0
            if -3 < dz < DRAW_DIST and not (e.kind in ("star", "map") and e.dead):
                items.append((e.z, 1, ("ent", e)))
        items.append((self.finish_z, 1, ("swing",)))
        items.append((self.z, 2, ("dora",)))
        items.sort(key=lambda it: (-it[0], it[1]))
        for _, _, it in items:
            if it[0] == "deco":
                self.draw_deco(it[1], it[2])
            elif it[0] == "ent":
                self.draw_ent(it[1])
            elif it[0] == "swing":
                self.draw_swing()
            else:
                self.draw_dora()
        self.draw_particles()
        self.draw_lane_flash()
        self.draw_speed_lines()
        self.draw_hud()
        for c in self.confetti:
            pygame.draw.rect(scr, c[4], (int(c[0]), int(c[1]), 8, 5))
        if self.state == "result":
            self.draw_result()
        if self.state == "pause":
            self.center_text("PAUSED", self.f_big, H // 2 - 30)
        pygame.display.flip()

    def draw_lane_flash(self):
        lane, t = self.flash_lane
        if lane is None or t <= 0 or int(t * 12) % 2:
            return
        x = (lane - 1) * LANE_W
        z0, z1 = self.z + 8, self.z + 40
        self.poly([self.P(x - 0.9, 0.02, z0), self.P(x + 0.9, 0.02, z0), self.P(x + 0.9, 0.02, z1), self.P(x - 0.9, 0.02, z1)], (255, 70, 70))
        p = self.P(x, 0.2, z0 + 6)
        if p:
            t_ = self.f_mid.render("!", True, (255, 255, 255))
            self.screen.blit(t_, (p[0] - t_.get_width() / 2, p[1] - 80))

    def draw_speed_lines(self):
        if self.speed < 18 or self.state not in ("play", "dead"):
            return
        n = int((self.speed - 16) * 0.9)
        rng = random.Random(int(self.elapsed * 60))
        for _ in range(n):
            a = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(320, 440)
            cx, cy = W / 2, HORIZON + 100
            pygame.draw.line(self.screen, (255, 255, 255), (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.8),
                             (cx + math.cos(a) * (r0 + 90), cy + math.sin(a) * (r0 + 90) * 0.8), 2)

    def text(self, s, font, col, pos, shadow=True, center=False):
        img = font.render(s, True, col)
        x, y = pos
        if center:
            x -= img.get_width() / 2
        if shadow:
            self.screen.blit(font.render(s, True, (20, 20, 30)), (x + 3, y + 3))
        self.screen.blit(img, (x, y))

    def center_text(self, s, font, y, col=(255, 255, 255)):
        self.text(s, font, col, (W / 2, y), center=True)

    def draw_hud(self):
        self.text(self.L["name"], self.f_small, (255, 255, 255), (16, 12))
        self.text("Stars %d   Maps %d/3   Oops %d" % (self.stars, self.maps, self.deaths), self.f_small, (255, 230, 90), (16, 38))
        self.text("%d km/h" % (self.speed * 8 if self.state in ("play", "dead") else 0), self.f_mid, (255, 255, 255), (W - 170, 10))
        bx, by, bw = 300, H - 26, W - 600
        pygame.draw.rect(self.screen, (30, 30, 40), (bx, by, bw, 10), border_radius=5)
        prog = clamp(self.z / self.finish_z, 0, 1)
        pygame.draw.rect(self.screen, (255, 120, 180), (bx, by, bw * prog, 10), border_radius=5)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(bx + bw * prog), by + 5), 9)
        pygame.draw.circle(self.screen, (255, 225, 40), (bx + bw + 14, by + 5), 10)
        txt, t = self.banner
        if t > 0 and txt:
            self.center_text(txt, self.f_mid, 90, (255, 255, 160))
        if self.state == "play" and self.intro > 0:
            self.center_text("¡Vámonos!  Go Go Go!", self.f_big, 200 - (2.2 - self.intro) * 10, (255, 120, 180))

    def draw_result(self):
        ov = pygame.Surface((W, H - 250), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        self.screen.blit(ov, (0, 250))
        self.center_text("LEVEL COMPLETE!", self.f_big, 258, (255, 230, 90))
        self.center_text("\"I'm Dora the Explorer!\"", self.f_mid, 215, (255, 255, 255))
        for i in range(3):
            x = W / 2 + (i - 1) * 80
            on = i < self.rating
            pts = []
            for j in range(10):
                r = 30 if j % 2 == 0 else 13
                a = -math.pi / 2 + j * math.pi / 5
                pts.append((x + math.cos(a) * r, 355 + math.sin(a) * r))
            pygame.draw.polygon(self.screen, (255, 215, 40) if on else (80, 80, 90), pts)
            pygame.draw.polygon(self.screen, (40, 30, 10), pts, 3)
        self.center_text("Stars %d/%d   Map pieces %d/3   Oops %d   Time %.0fs" % (self.stars, self.stars_total, self.maps, self.deaths, self.elapsed),
                         self.f_small, 405)
        if self.result_t > 0.6:
            self.center_text("R  replay        Enter  menu", self.f_mid, 445, (255, 255, 255))

    def draw_menu(self):
        self.level = self.level if self.level in (0, 1, 2) else 0
        self.z = self.menu_z
        self.x, self.y = 0.0, 0.0
        self.speed = 14
        self.slide_t = 0
        self.state_backup = self.state
        self.set_camera()
        self.th = THEMES[self.L["theme"]]
        self.draw_scene([])
        for side in (-1, 1):
            for k in range(int((self.cz + DRAW_DIST) // 7), int(self.cz // 7) - 1, -1):
                self.draw_deco(side, k)
        st = self.state
        self.state = "menu"
        self.draw_dora()
        self.state = st
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((10, 10, 30, 130))
        self.screen.blit(ov, (0, 0))
        self.center_text("DORA DASH!", self.f_big, 30, (255, 120, 180))
        self.center_text("Run! Jump! Slide! Reach the Banana Swing!", self.f_small, 105)
        for i, L in enumerate(LEVELS):
            y = 160 + i * 80
            best = self.best.get(i, 0)
            pygame.draw.rect(self.screen, (30, 30, 60), (W / 2 - 330, y, 660, 66), border_radius=14)
            pygame.draw.rect(self.screen, (255, 160, 200), (W / 2 - 330, y, 660, 66), 3, border_radius=14)
            self.text("%d  %s" % (i + 1, L["name"]), self.f_mid, (255, 255, 255), (W / 2 - 310, y + 6))
            self.text(L["blurb"], self.f_small, (200, 220, 255), (W / 2 - 310, y + 40))
            self.text("*" * best + "-" * (3 - best), self.f_mid, (255, 215, 40), (W / 2 + 230, y + 12))
        self.center_text("Press 1, 2 or 3 to play", self.f_mid, 405, (255, 255, 160))
        self.center_text("A/D lanes   W/Space jump   S slide   P pause   F11 fullscreen   Esc back", self.f_small, 460)
        self.center_text("Fan prototype - Dora the Explorer(c) Nickelodeon", self.f_small, 495, (180, 180, 200))


def main():
    game = Game()
    running = True
    while running:
        dt = min(game.clock.tick(FPS) / 1000.0, 1 / 30)
        for e in pygame.event.get():
            if not game.handle_event(e):
                running = False
        game.update(dt)
        game.draw()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
