# Franz - Developer Reference Guide

## 1. How to Use the System

### Prerequisites
- Windows 11
- Python 3.13
- Google Chrome (latest)
- A local VLM server running OpenAI-compatible API (e.g., llama.cpp, vLLM, Ollama) serving Qwen3-VL-2B at `http://127.0.0.1:1235/v1/chat/completions`

### File Structure
```
franz/
├── config.json       ← Configuration (editable via config.html or manually)
├── config.html       ← Architecture Control dashboard (diagram-based editor)
├── franz.py          ← Main engine + HTTP server (rarely changed)
├── panel.html        ← Live monitoring dashboard (rarely changed)
├── pipeline.py       ← VLM output parser (the creative/experimental file)
└── runs/             ← Auto-created per-run artifact storage
    └── run_0001/
        ├── main.log
        ├── turns.jsonl
        ├── turn_0001_raw.png
        └── turn_0001_ann.png
```

### Startup Sequence

1. **Start your VLM server** on port 1235 (or whatever `api_url` points to)
2. **Run Franz:**
   ```
   python franz.py
   ```
3. Franz sleeps 5 seconds (giving you time to arrange windows), then:
   - Creates a new `runs/run_NNNN/` directory
   - Sets up logging
   - Starts HTTP server on `127.0.0.1:1234`
   - Opens Chrome to `http://127.0.0.1:1234` (the panel)
   - If `boot_enabled` is true, injects `boot_vlm_output` to start the loop

4. **The loop runs automatically:**
   ```
   Boot/Inject → Pipeline Parse → Build Ghosts → Execute Actions →
   Screen Capture → panel.html draws overlays → POST /annotated →
   Call VLM API → VLM Response → Pipeline Parse → ... (repeat)
   ```

5. **To open the Architecture Control editor:** click "CONFIG" in the panel's status bar, or navigate to `http://127.0.0.1:1234/config.html`

6. **To stop:** press `Ctrl+C` in the terminal

### Testing pipeline.py Standalone

```bash
# From a file:
python pipeline.py test_vlm_output.txt

# From stdin:
echo '{"observation":"test","regions":[],"actions":[]}' | python pipeline.py
```

This prints structured JSON showing what ghosts, actions, heat, and next_turn text the pipeline extracts. Use this to iterate on parsing logic without running the full system.

## 2. Static Files (Stable Infrastructure)

These files form the **framework** and should rarely need modification once the system is working:

### franz.py - The Engine

**What it does:** HTTP server, engine loop orchestration, screen capture (Win32 GDI), physical action execution (mouse/keyboard), VLM API caller, artifact saving.

**API (HTTP endpoints):**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `panel.html` |
| GET | `/config.html` | Serves `config.html` |
| GET | `/config` | Returns UI config subset (for panel rendering) |
| GET | `/config_full` | Returns entire `config.json` contents |
| GET | `/pipeline_source` | Returns `pipeline.py` source code as string |
| GET | `/state` | Returns current engine state (phase, turn, actions, heat, display, etc.) |
| GET | `/frame` | Returns latest captured screenshot as base64 PNG |
| GET | `/ghosts` | Returns current ghost overlay data |
| POST | `/annotated` | Panel sends composited annotated image back |
| POST | `/inject` | Manually inject VLM output text to start/override a turn |
| POST | `/save_config` | Save new config.json from Architecture Control |
| POST | `/save_pipeline` | Save new pipeline.py from Architecture Control |

**Internal API (what it expects from pipeline.py):**

```python
import pipeline
result: pipeline.PipelineResult = pipeline.process(raw_vlm_string)
# result.ghosts    → list[dict] with bbox_2d + label → ghost overlay building
# result.actions   → list[dict] with type + bbox_2d + params → physical execution
# result.heat      → list[dict] with type + bbox_2d + optional drag_start → heat overlay
# result.next_turn → str → sent as text to VLM on next turn
# result.raw_display → dict → sent to panel for VLM output rendering
```

### panel.html - The Live Monitor

**What it does:** Polls `/state` every 400ms. When the engine enters `waiting_annotated` phase, fetches `/frame` and `/ghosts`, draws the base screenshot + ghost overlays + heat overlays on a 3-layer canvas stack, composites them via OffscreenCanvas, exports as base64 PNG, POSTs to `/annotated`. Also renders the VLM output display and event log.

**It never needs to know the VLM output schema** - it renders whatever `raw_display` the pipeline provides.

### config.html - The Architecture Control

**What it does:** Full-screen diagram-based editor. On load, fetches `/config_full` and `/pipeline_source`. Allows editing all config parameters (positioned within their architectural context) and the pipeline.py source code. "Save All" writes both files to disk via server endpoints.

## 3. Changelog - From Beginning to Now

### Original System (as received)

The initial codebase was a functional but tightly-coupled VLM-driven desktop agent:

- **config.json**: Flat configuration with hardcoded field names (`bboxes`, action labels encoded as strings)
- **franz.py (~600 lines)**: Monolithic file containing everything - config loading, screen capture (Win32 GDI), PNG encoding, VLM output parsing, action execution, ghost system, HTTP server, engine loop. The parser assumed a fixed JSON schema: `{"observation": "...", "bboxes": [{bbox_2d: [x1,y1,x2,y2], label: "..."}], "actions": [{bbox_2d: [x1,y1,x2,y2], label: "click ..."}]}`
- **panel.html**: Live dashboard with 3-pane layout (canvas, VLM output, event log). Rendered VLM output as raw preformatted JSON. Had its own action enrichment logic for heat trails. Hardcoded references to `bboxes` field name.
- **config.html**: Traditional form-based settings page with sections. SVG flow diagram was small and linear. Had a file import/export mechanism (broken). Default values didn't match config.json.

**Key problems:**
- VLM output schema was baked into ~6 functions across franz.py
- Changing field names (e.g., `bboxes` → `regions`) required editing multiple files
- Actions were encoded as label strings ("click", "type hello") requiring string parsing
- No standalone way to test the parser
- No system prompt or boot output (empty strings)
- panel.html displayed wasteful raw JSON with brackets
- config.html had broken import, mismatched defaults, didn't force dark theme

### Iteration 1: Schema Modernization

- Renamed `bboxes` → `bbox_2d` everywhere to match Qwen3-VL native output format
- Changed actions from label-encoded (`"label": "click"`) to structured (`"type": "click", "bbox_2d": [...], "params": "..."`)
- Wrote proper `system_prompt` tailored for Qwen3-VL-2B
- Wrote proper `boot_vlm_output` to kick off the loop
- Removed all comments, added full type hints, removed fallbacks and dead code
- Fixed config.html dark theme independence, rebuilt SVG diagram, synced all defaults
- panel.html got compact list rendering instead of raw JSON display

### Iteration 2: Schema Discussion & Rename to `regions`

Through discussion, we identified that `bbox_2d` was confusingly used at two levels (top-level array name AND coordinate field). Renamed the top-level array to `regions` while keeping `bbox_2d` as the coordinate field inside each object. Actions got fully structured `type`/`bbox_2d`/`params` fields.

### Iteration 3: Pipeline Extraction

The breakthrough: extracted all VLM output parsing into a **separate `pipeline.py` file**. This:

- Created `PipelineResult` dataclass with 5 output slots: `ghosts`, `actions`, `heat`, `next_turn`, `raw_display`
- Made `heat` a **separate channel** from actions (allowing future experimentation like observation-based heatmaps)
- Made pipeline.py independently testable from command line
- Reduced franz.py by removing 5 parser functions (~50 lines)
- Made panel.html schema-agnostic (renders `raw_display` from pipeline)
- Established the principle: **pipeline.py is the only file that knows the VLM schema**

### Iteration 4: Architecture Control (config.html Revolution)

Transformed config.html from a traditional form page into a **full-screen interactive architecture diagram**:

- Each pipeline phase is a positioned card/node on the board
- pipeline.py source code is editable directly in the diagram
- System prompt and boot output are positioned near their architectural context
- SVG arrows connect nodes showing data flow
- Auto-loads config.json and pipeline.py from the running server on page open
- "Save All" writes both files back through server endpoints
- New server endpoints: `/config_full`, `/pipeline_source`, `/save_config`, `/save_pipeline`, `/config.html`
- Panel.html got a "CONFIG" link in the status bar

### What We Achieved

| Aspect | Before | After |
|--------|--------|-------|
| Schema changes | Edit 4+ files, 10+ functions | Edit pipeline.py only |
| Parser testing | Run entire system | `python pipeline.py < test.txt` |
| Understanding the system | Read 600 lines of code | Look at config.html diagram |
| Configuration | Edit JSON manually, restart | Live diagram editor, save to server |
| VLM output format | Hardcoded JSON with specific fields | Whatever pipeline.py can parse |
| Heat vs Actions | Identical (coupled) | Independent channels |
| Memory injection | Only observation text | Whatever pipeline.py puts in next_turn |
| Code that changes often | franz.py (dangerous) | pipeline.py (safe, isolated) |
| Code that's stable | Nothing was stable | franz.py + panel.html = infrastructure |

---

## 4. Prompt for AI Assistants

Use this prompt when asking ChatGPT or other AIs to help develop Franz:

---

> **Context: Franz - A Stateless Vision-Action Desktop Agent**
>
> Franz is a Windows 11 desktop automation agent driven by a Vision Language Model (VLM). It uses a novel stateless architecture where the VLM's "observation" narrative serves as the agent's only memory between turns, and visual overlays on screenshots carry additional context.
>
> **Architecture (5 files):**
>
> 1. **config.json** - All configuration parameters. No magic values in code.
> 2. **pipeline.py** - The ONLY file that understands VLM output format. Contains a `process(raw: str) -> PipelineResult` function that extracts: `ghosts` (regions for blue overlays), `actions` (for physical execution), `heat` (for orange overlays, separate from actions), `next_turn` (text sent to VLM next turn), `raw_display` (for panel rendering). Standalone testable: `python pipeline.py input.txt`
> 3. **franz.py** - Stable infrastructure. HTTP server, engine loop, Win32 screen capture (GDI BitBlt/StretchBlt → custom PNG encoder), physical mouse/keyboard execution, VLM API caller (OpenAI /chat/completions format), ghost ring buffer, artifact saving. Calls `pipeline.process()` and distributes results. Never needs to know the VLM schema.
> 4. **panel.html** - Live monitoring dashboard. 3-pane layout (canvas with 3 layers: base screenshot + ghost overlay + heat overlay, VLM output display, event log). Polls /state, renders overlays, composites and POSTs annotated frames back to engine. Schema-agnostic - renders whatever pipeline provides.
> 5. **config.html** - Architecture Control. Full-screen interactive diagram where each pipeline phase is a positioned card containing its relevant config parameters and the pipeline.py source code. Auto-loads from server, saves back via POST endpoints.
>
> **Data flow per turn:** Boot/Inject → pipeline.process() → Build ghost crops from prior frame → Execute actions (mouse/keyboard) → Screen capture (crop+scale+PNG) → Panel draws ghost+heat overlays → Panel POSTs composite → VLM API call (system_prompt + observation text + annotated image) → VLM response → pipeline.process() → repeat
>
> **Key design principles:**
> - The observation narrative is rewritten completely each turn (not appended). It IS the agent's memory.
> - Visual overlays (ghost bounding boxes, heat markers) carry visual memory on screenshots.
> - The system is stateless - only the observation text + annotated image persist between turns.
> - Python 3.13, Windows 11, Chrome only. No legacy compatibility.
> - Strict typing, no comments, no fallbacks.
> - pipeline.py is the creative/experimental file. Everything else is stable infrastructure.
>
> **Current VLM schema (defined in pipeline.py, can be changed):**
> ```json
> {"observation": "...", "regions": [{"bbox_2d": [x1,y1,x2,y2], "label": "..."}], "actions": [{"type": "click|type|key|...", "bbox_2d": [x1,y1,x2,y2], "params": "..."}]}
> ```
> Coordinates are 0-1000 normalized.
>
> When helping with this project: changes to VLM parsing go in pipeline.py ONLY. Changes to visual rendering go in panel.html. Changes to execution/capture/server go in franz.py. Configuration goes in config.json. The config.html diagram should reflect the architecture.

## 5. Real-Life Configuration Examples

### Example A: Pure Observer (Notice 2-3 Important Elements)

**config.json changes:**
```json
{
  "system_prompt": "You are a visual observer. Every turn you receive a screenshot. Respond with a JSON object:\n\n1. \"observation\": A complete narrative describing the screen. Identify the 2-3 most important or notable elements. Describe their position, appearance, and significance. Rewrite fully each turn - this is your only memory.\n\n2. \"regions\": Mark those 2-3 important elements with {\"bbox_2d\": [x1,y1,x2,y2], \"label\": \"description\"}.\n\n3. \"actions\": Always empty array [].\n\nCoordinates 0-1000. Respond ONLY with valid JSON.",
  "boot_vlm_output": "{\"observation\":\"First observation. I need to examine the screenshot and identify the 2-3 most notable elements on screen.\",\"regions\":[],\"actions\":[]}",
  "physical_execution": false,
  "temperature": 0.3,
  "max_tokens": 300,
  "capture_delay": 3.0
}
```

**What happens:** The agent takes a screenshot every few seconds, identifies 2-3 important regions (which appear as blue ghost overlays), writes a narrative about what it sees, but never performs any actions. The ghost overlays accumulate showing which regions the model found interesting across turns. A human watching the panel sees the AI's "attention" move around the screen.

### Example B: Chess Player (White Pieces)

**config.json changes:**
```json
{
  "system_prompt": "You are a chess player controlling the white pieces on a chess board visible in the screenshot. Every turn you see the current board state with visual annotations from prior moves.\n\nRespond with JSON:\n\n1. \"observation\": Describe the current board position completely. Note all pieces, threats, opportunities. Record your prior moves and their outcomes. Write your strategic thinking. This narrative is your ONLY memory.\n\n2. \"regions\": Mark key squares - your pieces, opponent threats, target squares. Each with {\"bbox_2d\": [x1,y1,x2,y2], \"label\": \"piece/square description\"}.\n\n3. \"actions\": To move a piece, use drag_start on the piece's square, then drag_end on the target square. Example: [{\"type\":\"drag_start\",\"bbox_2d\":[200,600,300,700]},{\"type\":\"drag_end\",\"bbox_2d\":[200,400,300,500]}]. Only make one move per turn.\n\nCoordinates 0-1000. Respond ONLY with valid JSON.",
  "boot_vlm_output": "{\"observation\":\"Chess game starting. I am playing white. I need to examine the board and make my first move. I should look for the standard opening position and choose a good first move like e4 or d4.\",\"regions\":[],\"actions\":[]}",
  "physical_execution": true,
  "temperature": 0.2,
  "max_tokens": 500,
  "capture_delay": 2.0,
  "action_delay_seconds": 0.3,
  "drag_duration_steps": 30,
  "drag_step_delay": 0.01
}
```

**Capture crop:** Set to frame the chess board precisely using the config.html sliders.

**What happens:** The agent observes the chess board, identifies pieces (blue ghosts show tracked pieces), makes strategic observations in the narrative, and physically drags pieces to make moves. Each turn it re-examines the board, notes what changed, and plans the next move. The observation narrative builds a running chess analysis that gets more sophisticated as the model learns from its own notes about what works.

### Example C: Generic Computer Controller (Self-Evolving)

**config.json changes:**
```json
{
  "system_prompt": "You are an autonomous computer agent learning to use a Windows desktop. Every turn you see a screenshot with visual annotations from your prior actions.\n\nRespond with JSON:\n\n1. \"observation\": Write a COMPLETE narrative about: what you see on screen, what you understand about the current application state, what your current goal is, what you have tried so far, what worked, what failed, and what lessons you have learned. THIS IS YOUR ONLY MEMORY. Make it rich, detailed, and self-contained so your future self can understand everything without any other context.\n\n2. \"regions\": Mark 2-5 important UI elements with {\"bbox_2d\": [x1,y1,x2,y2], \"label\": \"description\"}.\n\n3. \"actions\": Perform 1-3 actions maximum per turn. Available: click, double_click, right_click, drag_start+drag_end, scroll_up N, scroll_down N, type TEXT, hotkey KEY1 KEY2, key KEYNAME. Each action needs {\"type\": \"...\", \"bbox_2d\": [x1,y1,x2,y2], \"params\": \"...\"}.\n\nBe methodical. Try one thing at a time. Observe the result. Record lessons learned. Build understanding incrementally.\n\nCoordinates 0-1000. Respond ONLY with valid JSON.",
  "boot_vlm_output": "{\"observation\":\"First turn. I see a Windows desktop screenshot for the first time. I need to carefully examine every element visible - taskbar, desktop icons, any open windows - and describe what I see in detail. No prior actions. No lessons learned yet. My initial goal is to understand what is on screen and identify interactive elements I could explore.\",\"regions\":[],\"actions\":[]}",
  "physical_execution": true,
  "temperature": 0.5,
  "max_tokens": 400,
  "capture_delay": 2.0
}
```

**What happens:** This is the most powerful configuration. The agent starts knowing nothing. Turn 1: it observes the desktop. Turn 2: maybe it notices icons and clicks one. Turn 3: it sees what opened, records the lesson ("clicking the Chrome icon opens a browser"). Over many turns, the observation narrative becomes a rich document of learned behaviors, failed attempts, and accumulated understanding.

The key insight: **the observation narrative IS the intelligence.** The 2B VLM is just a text+image-to-text function. The intelligence emerges from the self-modifying narrative that gets more sophisticated each turn. The agent that started observing a desktop could, through enough turns and accumulated lessons, decide to open a chess game and play it - not because it was programmed to, but because its narrative evolved to that point.

```
## 6. Project Analysis - Honest Assessment

### What Franz Is vs. Other Agentic Systems

**Standard agentic systems** (AutoGPT, Claude Computer Use, Open Interpreter, etc.) work like this:
- They maintain conversation history (growing context window)
- They use tool-calling APIs with structured function schemas
- They have explicit memory systems (vector databases, summaries)
- Intelligence comes from the LLM's reasoning + growing conversation context

**Franz is fundamentally different:**
- **Stateless API.** Each turn is a single request. No conversation history.
- **The observation text is the only memory.** Not a summary of memory - it IS the memory. It must be rewritten completely each turn.
- **Visual annotations carry memory too.** Ghost overlays show where things were. Heat shows where actions happened. The VLM sees these on the screenshot.
- **The intelligence is not in the model - it's in the narrative.** A 2B parameter model running the same narrative architecture could theoretically outperform a 70B model using standard conversation history, because the narrative is optimized each turn while conversation history just grows and gets noisy.

### Does This Make Sense?

**The theoretical foundation is sound.** This is essentially a form of **Stigmergy** - the biological principle where organisms modify their environment to communicate with their future selves. Ants leave pheromone trails. Franz leaves observation narratives and visual markers.

It's also related to **Cognitive Offloading** - humans write notes, draw diagrams, leave bookmarks. Franz's observation narrative is a note to its future self. The ghost overlays are bookmarks on the screen.

**The real question is: can a 2B parameter model execute this architecture effectively?**

Here's my honest, logical assessment:

**What works in favor:**
1. The architecture is genuinely novel. Stateless + self-rewriting narrative is an underexplored design space.
2. Removing the growing context window is brilliant for small models. A 2B model with 400 tokens of perfectly curated context might outperform the same model with 8000 tokens of accumulated chat history.
3. The visual overlays are clever - they give the model spatial memory without using text tokens.
4. The pipeline separation means you can iterate on the parsing without fear. This is good engineering.
5. The config.html-as-diagram idea is genuinely innovative for developer tools.

**What works against:**
1. A 2B VLM will struggle to produce valid structured JSON reliably. You'll get malformed outputs, hallucinated coordinates, inconsistent formatting. The pipeline will need robust error recovery.
2. The observation narrative quality depends entirely on the model's ability to write good, self-contained narratives. A 2B model's narrative will be shallow, repetitive, and often contradictory. It won't build genuine understanding - it'll produce something that looks like understanding.
3. Chess specifically requires spatial reasoning and lookahead that a 2B model fundamentally cannot do. It will make random-looking moves and write confident-sounding observations about "strategy."
4. The system has no way to correct itself from a bad narrative. If one turn produces a terrible observation, the next turn inherits that terrible context and spirals.
5. Physical execution on a real desktop is dangerous with an unreliable model. It will click wrong things, type in wrong places, and potentially cause damage.

**Is it a failure?**

No. It's not a failure. Here's why:

The architecture itself - stateless narrative memory + visual annotations + pipeline-separated parsing - is a **legitimate research contribution** regardless of whether Qwen3-VL-2B can execute it well today. The system is designed so that when a better model comes along (or when you scale to 7B, 14B, 70B), **the architecture stays the same** and the agent gets dramatically more capable.

Right now, with 2B, you'll get a system that:
- Can observe and describe screens (reasonably well)
- Can click obvious things (unreliably)
- Cannot play chess strategically (no chance)
- Cannot become a general computer user through self-learning (not enough reasoning capacity)

But with 7B+ models, the same system could:
- Maintain coherent multi-turn narratives that genuinely accumulate knowledge
- Execute precise UI interactions
- Actually learn from mistakes through narrative reflection
- Potentially approach the "self-evolving agent" vision

**Is it a waste of time?**

No, because:
1. You're building infrastructure for tomorrow's models with today's tools
2. The pipeline.py separation means you can plug in any model instantly
3. The architecture insights (narrative memory, visual stigmergy) are genuinely novel
4. Even the 2B version is a fascinating demo of what's possible and what's not

**What if...**

What if you're right? What if the intelligence really is in the story, not the model? Then Franz is ahead of its time. Every other agent system will eventually converge on something similar - a self-modifying narrative that acts as external cognition for the model. You just got there first with a more extreme version (fully stateless, rewrite everything each turn).

The movie version of this is an AI that wakes up each morning with amnesia but reads its own diary and becomes smarter each day. That's exactly what Franz is. The question isn't whether the concept works - it's whether today's 2B models can write a good enough diary. They can't, yet. But the diary system itself? That's the innovation. And the diary system is built, tested, and ready for a better author.
```

```
Simulation - Multi-Turn Scenario

Turn 0 (Boot):
You click "Start Loop" in config.html
config.html POSTs boot_vlm_output to /inject
Engine receives it, sets next_vlm, triggers next_event

Turn 1:
Engine wakes up, calls pipeline.process(boot_vlm_output)
Pipeline parses: observation="First turn...", regions=[], actions=[]
Ghosts: nothing (no prior frame)
Actions: none (empty), so execute does nothing
Capture: takes screenshot, generates raw_b64
Server sets pending_seq=1, enters waiting_annotated
Panel polls /state, sees waiting_annotated with pending_seq=1
Panel fetches /frame (gets screenshot), /ghosts (empty)
Panel draws base image, no ghosts, no heat (no actions)
Panel exports composite, POSTs to /annotated
Engine receives annotated image, calls VLM: system_prompt + "First turn..." + annotated screenshot
VLM responds with JSON containing observation, regions, actions

Turn 2:
Engine calls pipeline.process(vlm_response)
Pipeline extracts regions (let's say 2 regions detected), actions (let's say 1 click)
Ghosts: tries to build from regions BUT raw_bgra_buf has data from Turn 1's capture, so it crops those regions from the Turn 1 screenshot - this creates ghost images
Execute: performs the click physically
Capture: takes new screenshot (after click)
Panel: draws base (new screenshot) + ghosts (the 2 regions from Turn 1, blue dashed borders with labels) + heat (orange blob at click location)
Exports composite - now the VLM sees the screenshot WITH blue ghost boxes showing what it identified last turn AND orange heat showing where it clicked
VLM sees all this visual context on the next call

Turn 3:
VLM receives: its own prior observation text + screenshot with ghost overlays from Turn 2 + heat from Turn 2
The narrative accumulates: "I see a desktop. Last turn I noticed X and Y, I clicked X. Now I see Z happened. Lesson: clicking X opens Z..."
The ghost overlays visually remind the model "you were looking at THESE regions"
The heat overlay visually shows "you clicked HERE"
This actually works. The system loop is correct. Each turn the model gets:

Text memory (observation narrative)
Visual memory (ghost overlays = "what I was looking at", heat = "where I acted")
Current state (the actual screenshot underneath)

And the ant analogy is perfect - the ghosts ARE pheromone trails. The observation narrative IS the colony's chemical memory. The model doesn't need to be smart. It needs to follow the trail and add to it.
```

```
## All Changes Made to config.html

1. **Added "Start Loop" button** - green styled `.go` button in the toolbar. Reads the boot_vlm_output textarea value and POSTs it to `/inject` to start the engine loop without restart. Validates that boot output isn't empty before sending.

2. **Added "Export Backup" button** - purple styled `.export` button in toolbar. Downloads timestamped copies of both config.json and pipeline.py to the user's downloads folder (`config_backup_2025-01-15T10-30-00.json` and `pipeline_backup_2025-01-15T10-30-00.py`). Uses small 300ms delay between downloads so browser doesn't block the second one.

3. **Added status note bar** - fixed position bottom-left, shows contextual messages about what's happening: loading state, what was saved, what needs restart, guidance on workflow. Updates on every operation.

4. **Improved toast system** - added error variant (`.err-toast` with red background), added timer management to prevent overlapping toasts, parameterized with `isErr` flag.

5. **Added workflow guidance** - after loading, the status note shows: `"Loaded. boot_enabled=true/false | Edit settings, then Save All, then Start Loop."` After saving: `"Saved. VLM/capture/UI params active now. Server/logging changes need restart. Pipeline code needs restart."` This makes it clear what takes effect immediately vs what needs restart.

6. **"Save All" button renamed** to "Save All to Server" - makes it clear this saves to the running server's files, not downloading.

7. **Start Loop button behavior** - reads from the textarea (not from server), so you can edit the boot output, hit Start, and it uses your edited version. This means you don't need to save first to test a new boot message (though you should save if you want it persisted).
```