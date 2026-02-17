"""
OpenSCAD Engine - Parse and render OpenSCAD files.

Supports:
- Loading .scad files
- Executing OpenSCAD CLI (if available)
- Converting OpenSCAD to build123d (limited)
- Rendering via OpenCSG

Author: Svetlana DAO
License: PolyForm Small Business License 1.0.0
"""

import subprocess
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class OpenSCADResult:
    """Result from OpenSCAD processing."""
    success: bool
    stl_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: List[str] = None


class OpenSCADEngine:
    """Engine for working with OpenSCAD files."""
    
    def __init__(self, workspace: Path = Path("/workspace"), openscad_path: str = "openscad"):
        self.workspace = workspace
        self.openscad_path = openscad_path
        self._check_installation()
    
    def _check_installation(self):
        """Check if OpenSCAD is installed."""
        try:
            result = subprocess.run(
                [self.openscad_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self.installed = result.returncode == 0
            if self.installed:
                self.version = result.stdout.strip()
            else:
                self.version = None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.installed = False
            self.version = None
    
    def is_available(self) -> bool:
        """Check if OpenSCAD is available."""
        return self.installed
    
    def load_scad(self, scad_path: str) -> str:
        """Load and return OpenSCAD source code."""
        path = Path(scad_path)
        if not path.exists():
            raise FileNotFoundError(f"SCAD file not found: {scad_path}")
        return path.read_text()
    
    def render_to_stl(self, scad_path: str, output_path: Optional[str] = None) -> OpenSCADResult:
        """Render SCAD file to STL using OpenSCAD CLI."""
        if not self.installed:
            return OpenSCADResult(
                success=False,
                error="OpenSCAD not installed"
            )
        
        scad_file = Path(scad_path)
        if not scad_file.exists():
            return OpenSCADResult(
                success=False,
                error=f"File not found: {scad_path}"
            )
        
        if output_path:
            stl_file = Path(output_path)
        else:
            stl_file = scad_file.with_suffix('.stl')
        
        try:
            result = subprocess.run(
                [
                    self.openscad_path,
                    "-o", str(stl_file),
                    "-d", str(stl_file.with_suffix('.deps')),
                    str(scad_file)
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and stl_file.exists():
                return OpenSCADResult(
                    success=True,
                    stl_path=stl_file,
                    warnings=self._parse_warnings(result.stderr)
                )
            else:
                return OpenSCADResult(
                    success=False,
                    error=result.stderr or "OpenSCAD render failed"
                )
        except subprocess.TimeoutExpired:
            return OpenSCADResult(
                success=False,
                error="Render timeout (>60s)"
            )
        except Exception as e:
            return OpenSCADResult(
                success=False,
                error=str(e)
            )
    
    def _parse_warnings(self, stderr: str) -> List[str]:
        """Parse warnings from OpenSCAD stderr."""
        warnings = []
        for line in stderr.split('\n'):
            if 'WARNING' in line.upper():
                warnings.append(line.strip())
        return warnings
    
    def extract_modules(self, scad_code: str) -> List[Dict[str, Any]]:
        """Extract module definitions from SCAD code."""
        modules = []
        
        # Match module definitions
        pattern = r'module\s+(\w+)\s*\(([^)]*)\)\s*\{'
        for match in re.finditer(pattern, scad_code):
            name = match.group(1)
            params = match.group(2).strip()
            
            modules.append({
                'name': name,
                'params': params,
                'position': match.start()
            })
        
        return modules
    
    def extract_variables(self, scad_code: str) -> Dict[str, Any]:
        """Extract variable definitions from SCAD code."""
        variables = {}
        
        # Match variable assignments
        pattern = r'(\w+)\s*=\s*([^;]+);'
        for match in re.finditer(pattern, scad_code):
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            # Try to parse as number
            try:
                if '.' in value:
                    variables[name] = float(value)
                else:
                    variables[name] = int(value)
            except ValueError:
                variables[name] = value
        
        return variables
    
    def extract_dimensions(self, scad_code: str) -> Dict[str, float]:
        """Extract dimension-like variables from SCAD code."""
        dims = {}
        
        # Common dimension variable names
        dim_names = ['width', 'height', 'depth', 'radius', 'diameter', 
                     'thickness', 'size', 'length', 'breadth']
        
        variables = self.extract_variables(scad_code)
        
        for name, value in variables.items():
            name_lower = name.lower()
            for dim_name in dim_names:
                if dim_name in name_lower:
                    dims[name] = value
        
        return dims
    
    def to_build123d(self, scad_code: str) -> str:
        """
        Attempt to convert basic SCAD to build123d.
        This is a best-effort conversion for simple shapes.
        """
        lines = []
        lines.append("from build123d import *")
        lines.append("")
        
        # Extract variables as dimension references
        variables = self.extract_variables(scad_code)
        for name, value in variables.items():
            lines.append(f"# {name} = {value}")
        
        lines.append("")
        lines.append("# Note: Full SCAD to build123d conversion requires manual porting")
        lines.append("# This is a placeholder showing extracted dimensions")
        lines.append("")
        
        dims = self.extract_dimensions(scad_code)
        if dims:
            lines.append("# Extracted dimensions:")
            for name, value in dims.items():
                lines.append(f"# {name} = {value}")
        
        # Try to detect basic shapes
        if 'cube' in scad_code.lower():
            lines.append("")
            lines.append("# Detected cube - example conversion:")
            lines.append("# result = Box(width, height, depth)")
        
        if 'cylinder' in scad_code.lower():
            lines.append("")
            lines.append("# Detected cylinder - example conversion:")
            lines.append("# result = Cylinder(radius, height)")
        
        if 'sphere' in scad_code.lower():
            lines.append("")
            lines.append("# Detected sphere - example conversion:")
            lines.append("# result = Sphere(radius)")
        
        lines.append("")
        lines.append("result = None  # Manual conversion needed")
        
        return '\n'.join(lines)


# Example usage
if __name__ == "__main__":
    engine = OpenSCADEngine()
    
    if engine.is_available():
        print(f"OpenSCAD available: {engine.version}")
    else:
        print("OpenSCAD not installed")
    
    # Example: parse a simple SCAD
    example = """
    width = 50;
    height = 30;
    depth = 10;
    
    module box(w, h, d) {
        cube([w, h, d]);
    }
    
    box(width, height, depth);
    """
    
    print("\nModules:", engine.extract_modules(example))
    print("Variables:", engine.extract_variables(example))
    print("Dimensions:", engine.extract_dimensions(example))
    print("\nBuild123d conversion:")
    print(engine.to_build123d(example))
