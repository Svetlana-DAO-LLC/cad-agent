"""
Bambu Lab P1S Compatible Parts
Designed for printing without supports on P1S/P2S

Part: Universal Phone/Tablet Stand with Hidden Storage
Author: Svetlana DAO
License: CC BY-SA 4.0
"""

from build123d import *

# Parameters - adjust these to customize
PHONE_WIDTH = 75  # mm (max phone width)
PHONE_DEPTH = 15  # mm (max phone depth)
ANGLE = 45  # degrees (stand angle)
HEIGHT = 80  # mm
THICKNESS = 2  # mm (wall thickness)
STORAGE_DEPTH = 20  # mm (hidden compartment)

def create_phone_stand(
    phone_width: float = 75,
    phone_depth: float = 15,
    angle: float = 45,
    height: float = 80,
    thickness: float = 2,
    storage_depth: float = 20
) -> Part:
    """Create a parametric phone stand with hidden storage compartment."""
    
    # Calculate dimensions
    base_size = phone_width + 10
    
    with BuildPart() as stand:
        # Main base plate
        Box(base_size, storage_depth + 20, thickness, mode=Mode.ADD)
        
        # Back support (angled)
        with BuildSketch(Plane.XY) as back_sketch:
            Rectangle(phone_width + 5, height)
        extrude(amount=thickness, mode=Mode.ADD)
        
        # Rotate back to angle
        rotate_part = stand.part
        stand.part = rotate(stand.part, Axis.X, angle)
        
        # Phone cradle arms
        for x_offset in [-phone_width/2 - 2, phone_width/2 + 2]:
            with BuildPart() as arm:
                Box(thickness, 15, height * 0.3)
                fillet(arm.edges().filter_by(Axis.Z), radius=2)
            loc = Location(
                (x_offset, storage_depth/2, height * 0.15),
                (angle, 0, 0)
            )
            add(stand.part, loc)
        
        # Cable management hole in back
        with BuildPart() as cable_hole:
            Cylinder(6, thickness * 2)
        cable_hole.part = rotate(cable_hole.part, Axis.X, angle)
        cut(stand.part, cable_hole.part)
        
        # Hidden storage compartment (cut from base)
        with BuildPart() as compartment:
            Box(
                base_size - thickness * 2,
                storage_depth - thickness,
                15
            )
            # Add divider
            Box(thickness, storage_depth, 15, mode=Mode.ADD)
        
        # Position compartment
        compartment.part = locate(Location((
            0,
            storage_depth/2 + 5,
            thickness + 7.5
        )))
        cut(stand.part, compartment.part)
        
        # Rubber feet bumps (4 corners)
        for x in [-base_size/3, base_size/3]:
            for y in [-storage_depth/3, storage_depth/3]:
                with BuildPart() as foot:
                    Cylinder(4, 1)
                locate(stand.part, Location((x, y, -0.5)))
        
    return stand.part


def create_spool_holder() -> Part:
    """Create a Bambu Lab compatible filament spool holder."""
    
    SPOOL_DIA = 200  #mm (max spool diameter)
    SPOOL_WIDTH = 65  #mm
    ROD_DIA = 8
    
    with BuildPart() as holder:
        # Main rod
        Cylinder(ROD_DIA/2, SPOOL_WIDTH + 20, mode=Mode.ADD)
        
        # Spool rests (T-shaped)
        for side in [-1, 1]:
            with BuildSketch() as rest_sketch:
                with Locations((0, side * (SPOOL_WIDTH/2 + 5))):
                    Rectangle(30, 6)
            extrude(amount=ROD_DIA + 4, mode=Mode.ADD)
        
        # Mounting base (for enclosure wall)
        Box(40, 10, 4, mode=Mode.ADD)
        
        # Bearings (simplified)
        Cylinder(10, 4, mode=Mode.ADD)
        
    return holder.part


def create_nozzle_brush_mount() -> Part:
    """Create a mount for the BambuLab nozzle brush cleaning mod."""
    
    with BuildPart() as mount:
        # Base plate (mounts to frame)
        Box(30, 20, 3, mode=Mode.ADD)
        
        # Brush holder tube
        with BuildSketch(Plane.YZ) as tube_sketch:
            Circle(8)
        extrude(amount=25, mode=Mode.ADD)
        
        # Brush entry funnel
        with BuildSketch(Plane.YZ) as funnel_sketch:
            with Locations((0, 0, 25)):
                Circle(12)
        extrude(amount=5, mode=Mode.ADD)
        
        # Frame clip
        with BuildSketch(Plane.XY) as clip_sketch:
            with Locations((0, 10)):
                Rectangle(10, 15)
        extrude(amount=3, mode=Mode.ADD)
        
    return mount.part


# Generate and export
if __name__ == "__main__":
    # Phone stand
    stand = create_phone_stand()
    export_stl(stand, "/workspace/phone_stand.stl")
    export_step(stand, "/workspace/phone_stand.step")
    print("Exported phone_stand.stl")
    
    # Spool holder
    spool = create_spool_holder()
    export_stl(spool, "/workspace/spool_holder.stl")
    print("Exported spool_holder.stl")
    
    # Nozzle brush mount
    brush = create_nozzle_brush_mount()
    export_stl(brush, "/workspace/nozzle_brush_mount.stl")
    print("Exported nozzle_brush_mount.stl")
