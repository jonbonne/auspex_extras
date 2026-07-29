import math
import pygame

GLOW_COLOR=(180, 220, 255)
GLOW_AMP=20
GLOW_FREQ=0.5

class GradientTicker:
    def __init__(self, font, effects=None, warm_color=(255, 100, 0), cool_color=(0, 100, 255), speed=2):
        self.font = font
        self.effects = effects
        self.warm = warm_color
        self.cool = cool_color
        self.speed = speed
        self.offset = 0
        self.glow_intensity = GLOW_AMP

    def lerp_color(self, t):
        """Linearly interpolate between warm and cool by t∈[0,1]."""
        return (
            int(self.warm[0] + (self.cool[0] - self.warm[0]) * t),
            int(self.warm[1] + (self.cool[1] - self.warm[1]) * t),
            int(self.warm[2] + (self.cool[2] - self.warm[2]) * t),
        )

    def render_gradient_text(self, text, text_alpha):
        """Return a surface with the text drawn in a warm→cool gradient."""
        length = len(text)
        # total size of the full string
        width, height = self.font.size(text)
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.set_alpha(text_alpha)
        x = 0
        for i, ch in enumerate(text):
            t = i / (length - 1) if length > 1 else 0
            color = self.lerp_color(t)
            ch_surf = self.font.render(ch, True, color)
            surf.blit(ch_surf, (x, 0))
            x += ch_surf.get_width()
        return surf

    def render_glow_text(self, text, text_alpha):
        """Return a surface with the text drawn in a warm→cool gradient."""
        length = len(text)
        # total size of the full string
        width, height = self.font.size(text)
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.set_alpha(text_alpha)
        x = 0
        for i, ch in enumerate(text):
            ch_surf = self.font.render(ch, True, GLOW_COLOR)
            surf.blit(ch_surf, (x, 0))
            x += ch_surf.get_width()

        return surf

    def update(self, dt):
        # move left by speed * dt
        self.offset = (self.offset + self.speed * dt) % self.total_width
        self.glow_intensity = int(GLOW_AMP * math.sin(2 * math.pi * GLOW_FREQ * dt))

    def draw(self, screen, text, y, text_alpha=200):
        grad_surf = self.render_glow_text(text, text_alpha)
        self.total_width = grad_surf.get_width()
        # tile it if you want wrap-around
        x = -self.offset
        while x < screen.get_width():
            if self.effects:
                self.effects(screen, grad_surf, (x, y), glow_radius=self.glow_intensity)
            else:
                screen.blit(grad_surf, (x, y))
            x += self.total_width
