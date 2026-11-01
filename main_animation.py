from manim import *

class SimpleAnimation(Scene):
    def construct(self):
        circle = Circle()           # Create a circle
        circle.set_fill(BLUE, opacity=0.5)  # Set the color and transparency
        self.play(Create(circle))   # Animate the creation of the circle
        self.play(circle.animate.shift(RIGHT * 2))  # Move the circle to the right
        self.play(FadeOut(circle))  # Fade out the circle

# To render, run in terminal:
# manim -pql main_animation.py SimpleAnimation
