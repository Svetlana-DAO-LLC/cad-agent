
import sys
import os
sys.path.append(os.getcwd())

from build123d import *
from src.renderer import Renderer

def test_renderer():
    print("Creating shape...")
    # Create a shape with some features
    with BuildPart() as p:
        Box(100, 50, 20)
        with Locations((0, 0, 10)):
             Cylinder(15, 10)
        with Locations((30, 0, 0)):
             Hole(5)
             
    shape = p.part
    
    print("Initializing renderer...")
    renderer = Renderer()
    
    print("Rendering 2D Front View...")
    path = renderer.render_2d(shape, view="front", filename="test_front.png")
    print(f"Rendered to {path}")
    
    print("Rendering 2D Top View...")
    path = renderer.render_2d(shape, view="top", filename="test_top.png")
    print(f"Rendered to {path}")
    
    print("Rendering Multiview...")
    path = renderer.render_multiview(shape, filename="test_multi.png")
    print(f"Rendered to {path}")

if __name__ == "__main__":
    test_renderer()
