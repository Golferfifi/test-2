#!/usr/bin/env python3
"""
Flappy Bird Neo — 2×-Scale Deluxe with PD-Controller Auto-Pilot
Improved version with optional manual mode selection.
"""

import argparse
import io
import math
import pickle
import random
import struct
import sys
import wave
from pathlib import Path
from typing import List, Tuple

import pygame

# ─── CONFIG ───
SCALE       = 2
SCREEN_W    = 288 * SCALE
SCREEN_H    = 512 * SCALE
FPS         = 60

GRAVITY     = 0.25 * SCALE
FLAP_VEL    = -4.5 * SCALE
PIPE_GAP    = 100 * SCALE
PIPE_DELAY  = 1400  # ms
BASE_SPEED  = 2.0 * SCALE
RAMP_SEC    = 15    # seconds to ramp speed

COOLDOWN_MS = 100   # ms between flaps
AUTO_PLAY   = True

# PD Controller gains
PD_KP      = 0.13
PD_KD      = 0.32
PD_MARGIN  = 4 * SCALE

# High-score file
try:
    HS_PATH = Path(__file__).with_name("flappy_hs.dat")
except NameError:
    HS_PATH = Path.cwd() / "flappy_hs.dat"

# ─── Helpers ───

def load_high_score() -> int:
    if HS_PATH.exists():
        try:
            with open(HS_PATH, 'rb') as f:
                return int(pickle.load(f))
        except Exception:
            return 0
    return 0


def save_high_score(score: int) -> None:
    try:
        with open(HS_PATH, 'wb') as f:
            pickle.dump(int(score), f)
    except Exception:
        pass


def draw_gradient(surface: pygame.Surface,
                  top: Tuple[int, int, int],
                  bot: Tuple[int, int, int]) -> None:
    h = surface.get_height()
    w = surface.get_width()
    for y in range(h):
        t = y / h
        color = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (w, y))


def make_tone(frequency: int, duration: float,
              volume: float = 0.3) -> pygame.mixer.Sound:
    sample_rate = 44100
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = []
        for i in range(int(sample_rate * duration)):
            sample = int(
                32767 * math.sin(2 * math.pi * frequency * i / sample_rate)
            )
            frames.append(struct.pack('<h', sample))
        wav_file.writeframes(b''.join(frames))
    buf.seek(0)
    snd = pygame.mixer.Sound(file=buf)
    snd.set_volume(volume)
    return snd

def create_bird_frames() -> Tuple[pygame.Surface, pygame.Surface]:
    w = 34 * SCALE
    h = 24 * SCALE

    def mk(up: bool) -> pygame.Surface:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (255, 255, 0), surf.get_rect())
        wing = 10 * SCALE
        pts = [
            (w // 4, h // 2),
            (w // 2, h // 2 - wing if up else h // 2 + wing),
            (w // 2, h // 2),
        ]
        pygame.draw.polygon(surf, (255, 200, 0), pts)
        pygame.draw.circle(surf, (0, 0, 0),
                           (w - int(8 * SCALE), int(8 * SCALE)),
                           int(3 * SCALE))
        return surf

    return mk(True), mk(False)


def create_pipe_image() -> pygame.Surface:
    w = 52 * SCALE
    h = 320 * SCALE
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        g = int(180 - 80 * (y / h))
        pygame.draw.line(surf, (0, g, 0), (0, y), (w, y))
    pygame.draw.rect(surf, (0, 120, 0), surf.get_rect(),
                     int(4 * SCALE), border_radius=int(12 * SCALE))
    return surf


def create_base_image() -> pygame.Surface:
    bh = 100 * SCALE
    surf = pygame.Surface((SCREEN_W * 2, bh))
    surf.fill((40, 40, 40))
    for x in range(0, surf.get_width(), int(20 * SCALE)):
        pygame.draw.line(surf, (255, 160, 0), (x, 0), (x, bh), int(2 * SCALE))
    return surf

# ─── Assets ───
BIRD_UP, BIRD_DN = create_bird_frames()
PIPE_IMG = create_pipe_image()
BASE_IMG = create_base_image()

# ─── Entities ───
class Bird:
    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.v = 0.0
        self.rect = BIRD_UP.get_rect(center=(x, y))
        self.last_flap = 0
        self.anim_frame = 0

    def flap(self) -> None:
        self.v = FLAP_VEL
        Game.SND_FLAP.play()
        self.last_flap = pygame.time.get_ticks()

    def can_flap(self) -> bool:
        return pygame.time.get_ticks() - self.last_flap >= COOLDOWN_MS

    def update(self) -> None:
        self.v += GRAVITY
        self.y += self.v
        self.rect.center = (self.x, self.y)
        self.anim_frame = (self.anim_frame + 1) % 30

    def draw(self, surface: pygame.Surface) -> None:
        frame = BIRD_UP if self.anim_frame < 15 else BIRD_DN
        angle = max(min(-self.v * 5, 30), -30)
        img = pygame.transform.rotate(frame, angle)
        sh = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        sh.fill((0, 0, 0, 80))
        sh = pygame.transform.rotate(sh, angle)
        combo = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        combo.blit(sh, (3, 3))
        combo.blit(img, (0, 0))
        surface.blit(combo, combo.get_rect(center=self.rect.center))


class Pipe:
    def __init__(self, x: float, y: float, top: bool) -> None:
        self.top = top
        self.x = x
        self.img = pygame.transform.flip(PIPE_IMG, False, True) if top else PIPE_IMG
        self.rect = (
            self.img.get_rect(midbottom=(x, y)) if top
            else self.img.get_rect(midtop=(x, y))
        )
        self.scored = False

    def update(self, speed: float) -> None:
        self.x -= speed
        self.rect.x = self.x

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.img, self.rect)

    def off(self) -> bool:
        return self.x + self.img.get_width() < 0


class Cloud:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.x = random.randint(0, SCREEN_W)
        self.y = random.randint(20, SCREEN_H // 2)
        self.spd = random.uniform(0.3, 1.0) * SCALE
        self.size = random.randint(int(20 * SCALE), int(50 * SCALE))

    def update(self) -> None:
        self.x -= self.spd
        if self.x < -self.size * 2:
            self.reset()

    def draw(self, surface: pygame.Surface) -> None:
        c = pygame.Surface((self.size * 2, self.size), pygame.SRCALPHA)
        pygame.draw.ellipse(c, (255, 255, 255, 180), c.get_rect())
        surface.blit(c, (self.x, self.y))


class Particle:
    def __init__(self, pos: Tuple[int, int]) -> None:
        self.x, self.y = pos
        self.vx = random.uniform(-3, 3) * SCALE
        self.vy = random.uniform(-3, 3) * SCALE
        self.life = random.randint(30, 60)
        self.r = random.randint(int(2 * SCALE), int(4 * SCALE))
        self.col = (
            random.randint(200, 255),
            random.randint(50, 100),
            random.randint(50, 100),
        )

    def update(self) -> None:
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surface: pygame.Surface) -> None:
        if self.life > 0:
            pygame.draw.circle(surface, self.col,
                               (int(self.x), int(self.y)), self.r)

# ─── Game Class ───
class Game:
    def __init__(self) -> None:
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Flappy Bird Neo")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", int(28 * SCALE))

        Game.SND_FLAP = make_tone(600, 0.08)
        Game.SND_HIT = make_tone(180, 0.25)
        Game.SND_SCORE = make_tone(420, 0.12)

        self.reset()

    def reset(self) -> None:
        self.bird = Bird(50 * SCALE, SCREEN_H // 2)
        self.pipes = []  # type: List[Pipe]
        self.clouds = [Cloud() for _ in range(6)]
        self.particles = []  # type: List[Particle]
        self.score = 0.0
        self.high_score = load_high_score()
        self.auto = AUTO_PLAY
        self.pipe_timer = pygame.time.get_ticks()
        self.base_scroll = 0.0
        self.start_time = pygame.time.get_ticks()
        self.paused = False
        self.over = False
        self.debug = False
        self.band = None
        self.target = None
        self.last_error = 0.0

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                        pygame.quit(); sys.exit()
                    if ev.key == pygame.K_p:
                        self.paused = not self.paused
                    if ev.key == pygame.K_d:
                        self.debug = not self.debug
                    if ev.key == pygame.K_a:
                        self.auto = not self.auto
                    if ev.key == pygame.K_r and self.over:
                        self.reset()
                    if ev.key == pygame.K_SPACE and not self.auto \
                       and not self.paused and not self.over:
                        self.bird.flap()

            if not self.paused and not self.over:
                self.update_game()

            self.draw_game()
            pygame.display.flip()
    def update_game(self) -> None:
        elapsed = (pygame.time.get_ticks() - self.start_time) / 1000.0
        speed = BASE_SPEED + elapsed / RAMP_SEC

        self.bird.update()

        self.band = None
        self.target = None
        if self.auto and self.bird.can_flap():
            tops = [p for p in self.pipes
                    if p.top and p.x + p.img.get_width() > self.bird.rect.centerx]
            if tops:
                top_p = min(tops, key=lambda p: p.x)
                bot_p = next(p for p in self.pipes if not p.top and p.x == top_p.x)

                gap_top = top_p.rect.bottom
                gap_bot = bot_p.rect.top
                center = (gap_top + gap_bot) / 2

                half_h = self.bird.rect.height / 2
                self.band = (int(gap_top + half_h), int(gap_bot - half_h))
                self.target = (int(top_p.x), int(center))

                err = self.bird.y - center
                deriv = err - self.last_error
                ctl = PD_KP * err + PD_KD * deriv

                if ctl > PD_MARGIN:
                    self.bird.flap()
                self.last_error = err
            else:
                mid = SCREEN_H / 2
                if self.bird.y > mid + PD_MARGIN:
                    self.bird.flap()

        now = pygame.time.get_ticks()
        if now - self.pipe_timer > PIPE_DELAY:
            self.pipe_timer = now
            y = random.randint(int(150 * SCALE), SCREEN_H - int(150 * SCALE))
            self.pipes.extend([
                Pipe(SCREEN_W, y - PIPE_GAP / 2, True),
                Pipe(SCREEN_W, y + PIPE_GAP / 2, False),
            ])

        for p in self.pipes:
            p.update(speed)
            if not p.scored and p.x + p.img.get_width() < self.bird.x:
                p.scored = True
                self.score += 0.5
                if self.score.is_integer():
                    Game.SND_SCORE.play()
        self.pipes = [p for p in self.pipes if not p.off()]

        self.base_scroll = (self.base_scroll + speed) % BASE_IMG.get_width()

        hit = (
            self.bird.y >= SCREEN_H - BASE_IMG.get_height() or
            self.bird.y < 0 or
            any(self.bird.rect.colliderect(p.rect) for p in self.pipes)
        )
        if hit:
            Game.SND_HIT.play()
            for _ in range(80):
                self.particles.append(Particle(self.bird.rect.center))
            self.over = True
            if int(self.score) > self.high_score:
                self.high_score = int(self.score)
                save_high_score(self.high_score)

        for pa in self.particles:
            pa.update()
        self.particles = [pa for pa in self.particles if pa.life > 0]

    def draw_game(self) -> None:
        bg = pygame.Surface((SCREEN_W, SCREEN_H))
        draw_gradient(bg, (20, 20, 60), (10, 10, 30))
        for cl in self.clouds:
            cl.update(); cl.draw(bg)
        self.screen.blit(bg, (0, 0))

        for p in self.pipes:
            p.draw(self.screen)
        self.bird.draw(self.screen)
        for pa in self.particles:
            pa.draw(self.screen)

        base_y = SCREEN_H - BASE_IMG.get_height()
        self.screen.blit(BASE_IMG, (-self.base_scroll, base_y))
        self.screen.blit(BASE_IMG,
                         (BASE_IMG.get_width() - self.base_scroll, base_y))

        if self.auto and self.band:
            top, bot = self.band
            band_surf = pygame.Surface((SCREEN_W, bot - top), pygame.SRCALPHA)
            band_surf.fill((0, 255, 0, 30))
            self.screen.blit(band_surf, (0, top))
            pygame.draw.line(self.screen, (255, 0, 0),
                             (0, top), (SCREEN_W, top), int(2 * SCALE))
            pygame.draw.line(self.screen, (255, 0, 0),
                             (0, bot), (SCREEN_W, bot), int(2 * SCALE))
            if self.target:
                bx, by = self.bird.rect.center
                tx, ty = self.target
                dash = int(8 * SCALE)
                dist = math.hypot(tx - bx, ty - by)
                steps = int(dist // (dash * 2)) + 1
                for i in range(steps):
                    t1 = i / steps; t2 = min((i + 0.5) / steps, 1)
                    x1 = bx + (tx - bx) * t1; y1 = by + (ty - by) * t1
                    x2 = bx + (tx - bx) * t2; y2 = by + (ty - by) * t2
                    pygame.draw.line(self.screen, (0, 255, 0),
                                     (x1, y1), (x2, y2), int(2 * SCALE))

        score_surf = self.font.render(str(int(self.score)), True, (255, 255, 255))
        self.screen.blit(score_surf,
                         score_surf.get_rect(center=(SCREEN_W // 2, 40 * SCALE)))
        best_surf = self.font.render(f"BEST {self.high_score}", True, (200, 200, 200))
        self.screen.blit(best_surf,
                         best_surf.get_rect(center=(SCREEN_W // 2, 70 * SCALE)))

        hint_font = pygame.font.SysFont(None, int(18 * SCALE))
        hint_surf = hint_font.render(
            "SPACE-flap  P-pause  A-auto  D-debug  R-restart  ESC-quit",
            True, (255, 255, 255)
        )
        self.screen.blit(hint_surf, (5 * SCALE, SCREEN_H - 30 * SCALE))

        if self.paused:
            p = self.font.render("PAUSED", True, (255, 215, 0))
            self.screen.blit(p, p.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
        if self.over:
            o = self.font.render("GAME OVER — R to restart", True, (255, 50, 50))
            self.screen.blit(o, o.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))
        if self.debug:
            fps = int(self.clock.get_fps())
            d = self.font.render(f"{fps} FPS", True, (0, 255, 255))
            self.screen.blit(d, (5 * SCALE, SCREEN_H - 60 * SCALE))



def main() -> None:
    parser = argparse.ArgumentParser(description="Play Flappy Bird Neo")
    parser.add_argument('--manual', action='store_true',
                        help='start with auto-pilot disabled')
    args = parser.parse_args()

    global AUTO_PLAY
    if args.manual:
        AUTO_PLAY = False

    Game().run()


if __name__ == "__main__":
    main()
