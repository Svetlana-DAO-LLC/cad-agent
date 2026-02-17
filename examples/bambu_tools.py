"""
Bambu Lab Magnetic Tool Holder
=============================
Floating tool holder that attaches to any metal surface
or mounts with 3M tape. Designed for X1/P1 but works anywhere.

Author: Svetlana DAO
License: CC BY-SA 4.0
"""

from build123d import *

# Parameters
WIDTH = 80
HEIGHT = 40
DEPTH = 15
WALL_THICKNESS = 2

# Tool hole diameters (mm)
TOOL_SIZES = [4, 6, 8, 10]


def create_tool_holder() -> Part:
    """Create magnetic tool holder with various hole sizes."""
    
    with BuildPart() as holder:
        # Back plate
        Box(WIDTH, HEIGHT, WALL_THICKNESS, mode=Mode.ADD)
        
        # Side walls
        Box(WALL_THICKNESS, HEIGHT, DEPTH, mode=Mode.ADD)
        Box(WALL_THICKNESS, HEIGHT, DEPTH, loc=Location((WIDTH - WALL_THICKNESS, 0, 0)), mode=Mode.ADD)
        
        # Bottom
        Box(WIDTH, WALL_THICKNESS, DEPTH, loc=Location((0, -HEIGHT/2 + WALL_THICKNESS/2, 0)), mode=Mode.ADD)
        
        # Tool holes (from back)
        spacing = WIDTH / (len(TOOL_SIZES) + 1)
        for i, dia in enumerate(TOOL_SIZES):
            x = -WIDTH/2 + spacing * (i + 1)
            with BuildPart() as hole:
                Cylinder(dia/2, WALL_THICKNESS + 2)
            hole.part = rotate(hole.part, Axis.Y, 90)
            cut(holder.part, hole.part, loc=Location((x, 0, DEPTH/2)))
        
        # Magnet recess (back)
        with BuildPart() as magnet:
            Cylinder(6, 2)
        magnet.part = rotate(magnet.part, Axis.X, 90)
        cut(holder.part, magnet.part, loc=Location((WIDTH/3, HEIGHT/3, 0)))
        cut(holder.part, magnet.part, loc=Location((-WIDTH/3, HEIGHT/3, 0)))
        
        # Rounded edges
        fillet(holder.edges().filter_by(Axis.Z), radius=1)
    
    return holder.part


def create_spool_hook() -> Part:
    """Create a retractable spool hook."""
    
    with BuildPart() as hook:
        # Mount plate
        Box(40, 40, 3, mode=Mode.ADD)
        
        # Hook arm
        with BuildSketch(Plane.YZ) as arm_sketch:
            with Locations((0, 20)):
                Rectangle(4, 50)
        extrude(amount=30, mode=Mode.ADD)
        
        # Hook curve
        with BuildSketch(Plane.XZ) as curve_sketch:
            with Locations((15, 55)):
                Circle(15)
        extrude(amount=4, mode=Mode.ADD)
        
        # Spring recess
        with BuildPart() as spring_hole:
            Cylinder(8, 10)
        spring_hole.part = rotate(spring_hole.part, Axis.X, 90)
        cut(hook.part, spring_hole.part, loc=Location((0, 10, 15)))
    
    return hook.part


# Export
if __name__ == "__main__":
    tool_holder = create_tool_holder()
    export_stl(tool_holder, "/workspace/tool_holder.stl")
    print("Exported: tool_holder.stl")
    
    spool_hook = create_spool_hook()
    export_stl(spool_hook, "/workspace/spool_hook.stl")
    print("Exported: spool_hook.stl")
