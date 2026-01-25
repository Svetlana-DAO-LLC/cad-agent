# CAD Agent

**Give your AI agent eyes for CAD.**

## The Problem

AI agents doing CAD work are essentially blind. They can generate code, but they can't see the result. The typical workaround — taking screenshots and feeding them back — is painfully slow, manual, and breaks the agent's flow.

Without visual feedback, the agent guesses. It can't see that the hole is in the wrong place, the fillet is too large, or the part won't fit. Every iteration requires human intervention to capture and relay what the model looks like.

## The Solution

CAD Agent is a self-contained rendering server that lets AI agents **see what they're building**. The agent sends modeling commands, the container does all the work, and returns images the agent can actually interpret.

```
Agent: "Create a box with a hole"
       ↓
┌─────────────────────────────────────────────┐
│           CAD Agent Container               │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │build123d│→ │   VTK   │→ │  PNG    │     │
│  │ modeling│  │ render  │  │ output  │     │
│  └─────────┘  └─────────┘  └─────────┘     │
└─────────────────────────────────────────────┘
       ↓
Agent: *sees the render* "The hole is off-center, let me fix that..."
```

The feedback loop is immediate. The agent creates, sees, evaluates, and iterates — without human screenshot relay.

## Architecture

**All CAD logic runs inside the container.** The external AI agent only:
1. Sends commands (HTTP/MCP)
2. Receives results (JSON + PNG)
3. Decides what to do next

```
┌─────────────────┐         ┌─────────────────────────────┐
│  AI Agent       │  HTTP   │  cad-agent container        │
│                 │ ──────► │                             │
│  • Sends code   │         │  • build123d modeling       │
│  • Views renders│ ◄────── │  • VTK 3D rendering         │
│  • Iterates     │  JSON   │  • 2D technical drawings    │
│                 │  + PNG  │  • STL/STEP/3MF export      │
│  NO CAD logic   │         │  • Printability analysis    │
│  lives here     │         │                             │
└─────────────────┘         └─────────────────────────────┘
```

The agent should **never** do STL manipulation, rendering, or modeling outside the container. That defeats the purpose and leads to fragile, inconsistent results.

## Quick Start

```bash
# Build the container
docker build -t cad-agent:latest .

# Run the server
docker run -p 8123:8123 -v ./workspace:/workspace cad-agent:latest serve

# Verify it's running
curl http://localhost:8123/health
```

## API

### Create a Model

```bash
curl -X POST http://localhost:8123/model/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "bracket",
    "code": "from build123d import *\nresult = Box(60, 40, 10) - Cylinder(5, 10).locate(Pos(20, 0, 0))"
  }'
```

### Render It

```bash
# 3D isometric view
curl -X POST http://localhost:8123/render/3d \
  -d '{"model_name": "bracket", "view": "isometric"}' -o bracket_3d.png

# Multi-view technical drawing
curl -X POST http://localhost:8123/render/multiview \
  -d '{"model_name": "bracket"}' -o bracket_views.png

# 2D orthographic with dimensions
curl -X POST http://localhost:8123/render/2d \
  -d '{"model_name": "bracket", "view": "front"}' -o bracket_2d.png
```

### Export for Printing

```bash
curl -X POST http://localhost:8123/export \
  -d '{"model_name": "bracket", "format": "stl"}' -o bracket.stl
```

### All Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/model/create` | POST | Execute build123d code |
| `/model/modify` | POST | Modify existing model |
| `/model/list` | GET | List all models in session |
| `/model/{name}/measure` | GET | Get bounding box & dimensions |
| `/render/3d` | POST | 3D shaded render (VTK) |
| `/render/2d` | POST | 2D technical drawing (build123d) |
| `/render/multiview` | POST | 4-view composite |
| `/export` | POST | Export STL/STEP/3MF |
| `/analyze/printability` | POST | Manifold/watertight check |

## MCP Integration

For AI agents using Model Context Protocol:

```bash
docker run -i --rm cad-agent:latest mcp
```

Same functionality via stdio JSON-RPC.

## Protecting Your Designs

CAD Agent includes safeguards to prevent your AI agent from accidentally publishing your design files:

- **`.gitignore`** excludes all CAD outputs (STL, STEP, 3MF, OBJ, etc.)
- **Pre-commit hook** rejects commits containing design files
- **Output directories** (`renders/`, `workspace/`, `exports/`) are excluded by default

Your designs stay local. Only the tool source gets versioned. To enable the hook after cloning:

```bash
git config core.hooksPath .githooks
```

## The Workflow

1. **Agent writes build123d code** — describes the geometry
2. **Container builds the model** — creates 3D solid
3. **Container renders** — returns PNG the agent can see
4. **Agent evaluates** — checks proportions, features, fit
5. **Agent iterates** — modifies code, requests new render
6. **Export** — generate STL/STEP when satisfied

The agent stays in the loop. No manual screenshot passing. No blind iteration.

## License

Polyform Noncommercial 1.0.0 — See https://polyformproject.org/licenses/noncommercial/1.0.0

Free for personal, educational, and open-source use. Contact author for commercial licensing.
