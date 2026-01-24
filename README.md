# CAD Agent

AI-driven CAD modeling system for 3D printing, built on [build123d](https://github.com/gumyr/build123d).

## Features

- **Parametric CAD modeling** via build123d Python API
- **3D rendering** — isometric/perspective views (matplotlib, headless)
- **2D technical drawings** — orthographic projections with hidden lines and dimension annotations (build123d HLR + cairosvg)
- **Multi-view layouts** — standard engineering drawings (front/right/top/iso)
- **Printability analysis** — watertight check, wall thickness, manifold validation
- **Export** — STL, STEP, 3MF
- **Dual interface** — HTTP REST API + MCP (Model Context Protocol) for AI agent integration

## Quick Start

```bash
# Build
docker build -t cad-agent:latest .

# Run HTTP server
docker run -p 8123:8123 -v ./workspace:/workspace -v ./renders:/renders cad-agent:latest serve

# Run self-test
docker run --rm cad-agent:latest test

# Interactive shell
docker run -it --rm cad-agent:latest shell
```

## API

### HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/model/create` | POST | Execute build123d code |
| `/model/modify` | POST | Modify existing model |
| `/model/list` | GET | List all models |
| `/model/{name}/measure` | GET | Get measurements |
| `/render/3d` | POST | 3D perspective render |
| `/render/2d` | POST | 2D technical drawing |
| `/render/multiview` | POST | Multi-view composite |
| `/render/all` | POST | All standard views |
| `/export` | POST | Export STL/STEP/3MF |
| `/analyze/printability` | POST | 3D print analysis |

### MCP Tools

Same functionality exposed via MCP protocol (stdio JSON-RPC) for AI agent integration:

```bash
docker run -i --rm cad-agent:latest mcp
```

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  AI Agent       │────▶│  MCP/HTTP    │────▶│  CAD Engine  │
│  (Claude, etc)  │◀────│  Server      │◀────│  (build123d) │
└─────────────────┘     └──────────────┘     └──────────────┘
                              │                      │
                              ▼                      ▼
                        ┌──────────┐          ┌──────────┐
                        │ Renderer │          │ Exporter │
                        │ 3D + 2D  │          │ STL/STEP │
                        └──────────┘          └──────────┘
```

## Feedback Loop

The key design: AI creates a model → renders it → "sees" the result → iterates.

1. Agent sends build123d code via `create_model`
2. System auto-renders an ISO preview
3. Agent can request additional views (`render_2d`, `render_multiview`)
4. Agent sees dimensions, proportions, issues
5. Agent modifies and re-renders until satisfied

## License

Apache 2.0
