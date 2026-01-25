"""
Demo parts for CAD Agent testing.
Each function returns build123d code that creates a printable part.
"""

PARTS = {
    "phone_stand": '''
from build123d import *

# Phone stand - L-bracket with lip
with BuildPart() as stand:
    # Base plate 80x60x5mm
    Box(80, 60, 5, align=(Align.CENTER, Align.MIN, Align.MIN))
    
    # Back support wall 80x5x60mm
    with Locations((0, 57.5, 32.5)):
        Box(80, 5, 60, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    
    # Front lip 80x3x12mm
    with Locations((0, 1.5, 8.5)):
        Box(80, 3, 12, align=(Align.CENTER, Align.CENTER, Align.CENTER))

result = stand.part
''',

    "cable_clip": '''
from build123d import *

# Cable management clip for 3D printing
cable_diameter = 6  # mm
wall_thickness = 2
clip_width = 12

with BuildPart() as clip:
    # Main body - cylinder with opening
    with BuildSketch():
        Circle(cable_diameter/2 + wall_thickness)
        Circle(cable_diameter/2, mode=Mode.SUBTRACT)
        # Opening gap
        with Locations((0, cable_diameter/2 + wall_thickness/2)):
            Rectangle(cable_diameter * 0.6, wall_thickness + 1, mode=Mode.SUBTRACT)
    extrude(amount=clip_width)
    
    # Mounting tab
    with BuildSketch(Plane.XY.offset(0)):
        with Locations((0, -(cable_diameter/2 + wall_thickness + 3))):
            Rectangle(clip_width + 4, 6)
            # Screw hole
            Circle(1.5, mode=Mode.SUBTRACT)
    extrude(amount=clip_width)

result = clip.part
''',

    "box_with_lid": '''
from build123d import *

# Simple parametric box with lid
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

result = box.part
''',

    "knob": '''
from build123d import *

# Knurled knob for M5 bolt
knob_diameter = 25
knob_height = 15
shaft_diameter = 5.2  # M5 clearance

with BuildPart() as knob:
    # Main body
    Cylinder(knob_diameter/2, knob_height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    
    # Top dome
    with Locations((0, 0, knob_height)):
        Sphere(knob_diameter/2 * 0.8)
        # Cut bottom half of sphere
        with Locations((0, 0, -knob_diameter/2 * 0.8)):
            Box(knob_diameter, knob_diameter, knob_diameter * 0.8,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
    
    # Shaft hole
    Cylinder(shaft_diameter/2, knob_height + 5,
             align=(Align.CENTER, Align.CENTER, Align.MIN),
             mode=Mode.SUBTRACT)

result = knob.part
''',

    "bracket_90deg": '''
from build123d import *

# 90-degree mounting bracket
bracket_w = 30
bracket_h = 40
bracket_d = 40
thickness = 4
hole_d = 5

with BuildPart() as bracket:
    # Horizontal plate
    Box(bracket_w, bracket_d, thickness,
        align=(Align.CENTER, Align.MIN, Align.MIN))
    
    # Vertical plate
    with Locations((0, 0, thickness)):
        Box(bracket_w, thickness, bracket_h,
            align=(Align.CENTER, Align.MIN, Align.MIN))
    
    # Gusset/triangle support
    with BuildSketch(Plane.YZ):
        with Locations((thickness + bracket_d/4, thickness + bracket_h/4)):
            pts = [(0, 0), (bracket_d/2 - thickness, 0), (0, bracket_h/2 - thickness)]
            Polygon(*pts)
    extrude(amount=bracket_w, both=True)
    
    # Mounting holes in horizontal plate
    with Locations((0, bracket_d/2, 0)):
        with GridLocations(bracket_w - 10, bracket_d - 15, 2, 2):
            Hole(hole_d/2, thickness)
    
    # Mounting holes in vertical plate
    with Locations((0, thickness/2, thickness + bracket_h/2)):
        with GridLocations(bracket_w - 10, 0, 2, 1):
            Cylinder(hole_d/2, thickness + 1,
                     align=(Align.CENTER, Align.CENTER, Align.CENTER),
                     rotation=(90, 0, 0),
                     mode=Mode.SUBTRACT)

result = bracket.part
''',

    "flange": '''
from build123d import *

# Pipe Flange with bolt circle
outer_d = 80
inner_d = 30
thickness = 10
bolt_circle_d = 60
bolt_count = 6
bolt_hole_d = 6

with BuildPart() as flange:
    # Main disk
    Cylinder(outer_d/2, thickness)
    
    # Center bore
    Cylinder(inner_d/2, thickness, mode=Mode.SUBTRACT)
    
    # Bolt holes
    with Locations((0, 0, 0)):
        with PolarLocations(bolt_circle_d/2, bolt_count):
            Cylinder(bolt_hole_d/2, thickness, mode=Mode.SUBTRACT)
    
    # Chamfer outer edge
    chamfer(flange.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[-1], length=1)

result = flange.part
''',

    "hinge_half": '''
from build123d import *

# Simple hinge half
width = 40
length = 40
thickness = 3
pin_diameter = 4
knuckle_length = 10
knuckle_count = 3

with BuildPart() as hinge:
    # Plate
    Box(width, length, thickness, align=(Align.CENTER, Align.MIN, Align.MIN))
    
    # Knuckles
    with Locations((0, length, thickness/2)):
        with BuildSketch(Plane.YZ):
            with Locations((0, 0)):
                Circle(thickness + pin_diameter/2)
        extrude(amount=width, both=True)
    
    # Cutouts for knuckles
    # This is a simplified "half" that would interlock with itself
    cut_width = width / knuckle_count
    with Locations((-width/2 + cut_width/2, length, thickness/2)):
        with GridLocations(cut_width*2, 0, 2, 1):
            Box(cut_width, (thickness + pin_diameter)*2, (thickness + pin_diameter)*2, mode=Mode.SUBTRACT)

    # Pin hole
    with Locations((0, length, thickness/2)):
         Cylinder(pin_diameter/2, width, rotation=(0, 90, 0), mode=Mode.SUBTRACT)

    # Mounting holes
    with Locations((0, length/2, 0)):
        with GridLocations(width-15, length-15, 2, 2):
            Hole(3.5/2, thickness)

result = hinge.part
'''
}


def get_part_code(name: str) -> str:
    """Get the build123d code for a named part."""
    return PARTS.get(name, PARTS["phone_stand"])


def list_parts() -> list[str]:
    """List available demo parts."""
    return list(PARTS.keys())
