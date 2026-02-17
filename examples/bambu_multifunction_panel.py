"""
Bambu Lab X1/P1 Multi-Function Side Panel
==========================================
A replacement side panel with:
- Exhaust filter compartment (activated carbon)
- RGB LED ambient lighting (WS2812B)
- OLED status display cutout (0.96" SSD1306)
- Magnetic tool attachment area

Author: Svetlana DAO
License: CC BY-SA 4.0
Target: Bambu Lab X1, P1S, P1P

Dimensions: ~220mm x 280mm (matches stock panel)
"""

from build123d import *
import math

# ============ PARAMETERS ============
PANEL_WIDTH = 220
PANEL_HEIGHT = 280
PANEL_THICKNESS = 3

FILTER_WIDTH = 180
FILTER_HEIGHT = 60
FILTER_DEPTH = 12

OLED_WIDTH = 26
OLED_HEIGHT = 12

LED_CHANNEL_WIDTH = 8
LED_CHANNEL_DEPTH = 5
LED_CHANNEL_LENGTH = 200

MOUNT_HOLE_DIA = 3.5
MOUNT_HOLE_LOCATIONS = [
    (-90, -120), (90, -120),
    (-90, 120), (90, 120),
]

MAGNET_DIA = 6
MAGNET_LOCATIONS = [
    (-70, -80), (70, -80),
]


def create_side_panel() -> Part:
    """Create the multi-function side panel."""
    
    with BuildPart() as panel:
        # Main panel body
        Box(PANEL_WIDTH, PANEL_HEIGHT, PANEL_THICKNESS, mode=Mode.ADD)
        
        # === FILTER COMPARTMENT (back side) ===
        with BuildSketch(Plane.XY) as filter_sketch:
            # Filter compartment outline
            with Locations((0, -80)):
                Rectangle(FILTER_WIDTH, FILTER_HEIGHT, align=Align.CENTER)
        extrude(amount=FILTER_DEPTH, mode=Mode.ADD)
        
        # === FILTER GRILLE (perforations) ===
        with BuildSketch(Plane.XY) as grille_sketch:
            with Locations((0, -80)):
                # Grid of small circles for airflow
                rows = 4
                cols = 12
                spacing_x = FILTER_WIDTH / (cols + 1)
                spacing_y = FILTER_HEIGHT / (rows + 1)
                
                for row in range(rows):
                    for col in range(cols):
                        x = -FILTER_WIDTH/2 + spacing_x * (col + 1)
                        y = -FILTER_HEIGHT/2 + spacing_y * (row + 1)
                        with Locations((x, y)):
                            Circle(1.5)
        extrude(amount=2, mode=Mode.CUT)
        
        # === OLED CUTOUT (front side) ===
        with BuildSketch(Plane.XY) as oled_sketch:
            with Locations((0, 60)):
                Rectangle(OLED_WIDTH + 2, OLED_HEIGHT + 2, align=Align.CENTER)
        extrude(amount=PANEL_THICKNESS + 1, mode=Mode.CUT)
        
        # === LED CHANNEL (front side) ===
        with BuildSketch(Plane.XY) as led_sketch:
            with Locations((0, 100)):
                Rectangle(LED_CHANNEL_LENGTH, LED_CHANNEL_WIDTH, align=Align.CENTER)
        extrude(amount=LED_CHANNEL_DEPTH, mode=Mode.ADD)
        
        # === MOUNTING HOLES ===
        for x, y in MOUNT_HOLE_LOCATIONS:
            with BuildPart() as hole:
                Cylinder(MOUNT_HOLE_DIA/2, PANEL_THICKNESS + 2)
            hole.part = rotate(hole.part, Axis.X, 90)
            cut(panel.part, hole.part, loc=Location((x, y, 0)))
        
        # === MAGNET RECESSES ===
        for x, y in MAGNET_LOCATIONS:
            with BuildPart() as magnet_hole:
                Cylinder(MAGNET_DIA/2, 3)
            magnet_hole.part = rotate(magnet_hole.part, Axis.X, 90)
            cut(panel.part, magnet_hole.part, loc=Location((x, y, PANEL_THICKNESS/2)))
        
        # === VENTS (decorative) ===
        with BuildSketch(Plane.XY) as vent_sketch:
            for i in range(3):
                with Locations((0, -130 + i * 10)):
                    Rectangle(60, 3)
        extrude(amount=PANEL_THICKNESS, mode=Mode.CUT)
        
        # === FILLET EDGES ===
        fillet(panel.edges().filter_by(Axis.Z), radius=1)
    
    return panel.part


def create_filter_frame() -> Part:
    """Create the carbon filter frame (replaceable)."""
    
    with BuildPart() as frame:
        # Outer frame
        Box(FILTER_WIDTH + 6, FILTER_HEIGHT + 6, 2, mode=Mode.ADD)
        
        # Inner cutout for filter material
        with BuildSketch(Plane.XY) as inner:
            Rectangle(FILTER_WIDTH, FILTER_HEIGHT, align=Align.CENTER)
        extrude(amount=2, mode=Mode.CUT)
        
        # Mesh grid for support
        with BuildSketch(Plane.XZ) as mesh_sketch:
            for i in range(10):
                with Locations((0, -FILTER_HEIGHT/2 + i * (FILTER_HEIGHT/9))):
                    Rectangle(FILTER_WIDTH - 4, 1)
        extrude(amount=1, mode=Mode.ADD)
    
    return frame.part


def create_led_mount() -> Part:
    """Create LED strip mounting bracket."""
    
    with BuildPart() as mount:
        # Base
        Box(LED_CHANNEL_LENGTH + 4, LED_CHANNEL_WIDTH + 4, 2, mode=Mode.ADD)
        
        # Clip arms
        for side in [-1, 1]:
            with BuildSketch(Plane.YZ) as arm_sketch:
                with Locations((side * (LED_CHANNEL_WIDTH/2 + 2), 0)):
                    Rectangle(3, 8)
            extrude(amount=LED_CHANNEL_LENGTH, mode=Mode.ADD)
    
    return mount.part


# ============ GENERATE AND EXPORT ============
if __name__ == "__main__":
    # Main panel
    panel = create_side_panel()
    export_stl(panel, "/workspace/bambu_side_panel.stl")
    export_step(panel, "/workspace/bambu_side_panel.step")
    print("Exported: bambu_side_panel.stl")
    
    # Filter frame
    frame = create_filter_frame()
    export_stl(frame, "/workspace/bambu_filter_frame.stl")
    print("Exported: bambu_filter_frame.stl")
    
    # LED mount
    led = create_led_mount()
    export_stl(led, "/workspace/bambu_led_mount.stl")
    print("Exported: bambu_led_mount.stl")
    
    print("\n=== BOM ===")
    print("1x Main panel (PETG, 3mm)")
    print("1x Filter frame (PETG, 2mm)")
    print("1x LED mount (PETG, 2mm)")
    print("\nAdd from electronics:")
    print("1x 0.96\" OLED display (SSD1306)")
    print("1x ESP32-C3 or XIAO-ESP32")
    print("1x WS2812B LED strip (60 LED/m, 200mm)")
    print("1x Activated carbon filter sheet")
    print("4x M3x8mm screws")
    print("2x 6mm disc magnets")
