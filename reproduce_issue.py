
from build123d import *
from src.renderer import Renderer, RenderConfig
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Define the part
box_w, box_d, box_h = 60, 40, 30
wall = 2
lid_h = 5

with BuildPart() as box:
    # Outer shell
    Box(box_w, box_d, box_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # Inner cavity
    with Locations((0, 0, wall)):
        Box(box_w - 2*wall, box_d - 2*wall, box_h - wall,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT)
    # Lid lip
    with Locations((0, 0, box_h - lid_h)):
        Box(box_w - 2*wall - 0.5, box_d - 2*wall - 0.5, lid_h + 0.1,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
            mode=Mode.SUBTRACT)

shape = box.part

# Initialize renderer
renderer = Renderer()

# Try 3D render (which presumably fails or looks bad)
print("Rendering 3D...")
try:
    path_3d = renderer.render_3d(shape, "iso", "test_3d.png")
    print(f"3D render saved to {path_3d}")
except Exception as e:
    print(f"3D render failed: {e}")

# Try 2D render
print("Rendering 2D...")
try:
    path_2d = renderer.render_2d(shape, "front", filename="test_2d.png")
    print(f"2D render saved to {path_2d}")
except Exception as e:
    print(f"2D render failed: {e}")
