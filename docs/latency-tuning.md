# Per-node latency tuning — operator runbook

Every CUEMS playback pipeline (audio, video, DMX) has a small amount
of buffering between the cue trigger and the moment the speaker,
pixel, or fixture actually responds. MTC timecode is compensated in
each player so that the end result lands at wire-MTC; the compensation
value per pipeline is tunable per node.

This runbook covers what to set, how to set it, how to measure, and
what to expect.

## The three knobs

All three live in `/etc/cuems/settings.xml` (operator-hand-placed, or
generated later by `hardware-discovery`). Each sits inside its player
block as a child of `<node>`:

```xml
<videoplayer>
    ...
    <output_latency_ms>auto</output_latency_ms>
</videoplayer>
<audioplayer>
    ...
    <output_latency_ms>auto</output_latency_ms>
</audioplayer>
<dmxplayer>
    ...
    <output_latency_ms>35</output_latency_ms>
</dmxplayer>
```

Each element accepts **integer 0–500** (milliseconds, explicit
override) or **`auto`** (defer to the binary's built-in default).
Absent element = same as `auto` for video/audio, 35 ms default for
DMX.

### audioplayer

- `auto` (recommended on most rigs): JACK self-measures the output
  latency at startup and the value is used as the compensation. JACK
  knows its own latency better than an operator can guess.
- integer: override the JACK-queried value. Use this only if
  measurement shows JACK's number is wrong.

### videoplayer (videocomposer)

- `auto` (recommended): binary uses its hard-coded 33 ms default,
  appropriate for direct-scanout (DRM/KMS) on most displays.
- integer: override for measurement-driven tuning.

Typical starting points:

| Display path | Starting point |
|---|---|
| Direct-scanout (DRM/KMS) | 16–33 ms |
| Compositor-mediated (Wayland/X11) | 40–66 ms |

### dmxplayer

- `35` (default): midpoint of ENTTEC (~31 ms typical) and ArtNet
  (~44 ms typical), the two DMX output paths CUEMS supports.
- integer: override based on your specific adapter and rig.

DMX **does not accept `auto`** — the schema rejects it. There is no
self-measurement path for DMX (no photodiode rig built in), and the
`auto` keyword would imply magic the binary doesn't have. Either set
an integer or leave the element absent (35 ms built-in default).

Per-adapter starting points:

| Adapter | Starting point | Notes |
|---|---|---|
| ENTTEC USB Pro / DMXKing | ~30 ms | Firmware-driven USB-DMX widget. Low jitter. |
| OpenDMX (FTDI bit-banged) | ~35 ms | Driver-level DMX framing; more jitter under system load. |
| ArtNet (dedicated 1GbE) | ~44 ms | OLA ArtNet plugin + UDP + node DMX-refresh phase + wire + fixture. |
| ArtNet (shared / wireless LAN) | 60–80 ms | Higher and jitterier under congestion. Measure. |

## How to apply a change

1. Edit `/etc/cuems/settings.xml` with `sudo vi` (or your editor of
   choice). The file is typically owned by `stagelab` but lives in a
   root-owned directory.
2. Validate the change against the schema before restarting anything:

   ```bash
   python3 -c "
   import xmlschema
   xsd = xmlschema.XMLSchema11('/etc/cuems/settings.xsd')
   xsd.validate('/etc/cuems/settings.xml')
   print('OK')
   "
   ```

3. Restart the services. The engines spawn audio/dmx players fresh,
   and videocomposer re-reads its extracted env file on every start:

   ```bash
   sudo systemctl restart cuems-videocomposer cuems-node-engine cuems-controller-engine
   ```

## How to verify the change took effect

Each pipeline exposes the compensation in a different place.

**videocomposer** — the Strategy-A extractor writes a shell-style env
file that the unit consumes via `$OUTPUT_LATENCY_FLAG`:

```bash
cat /run/cuems/videocomposer.env
# OUTPUT_LATENCY_FLAG=--output-latency-ms 33   (integer case)
# OUTPUT_LATENCY_FLAG=                          ("auto" / absent)

ps auxww | grep -v grep | grep cuems-videocomposer
# /usr/bin/cuems-videocomposer [--verbose] [--output-latency-ms N]
```

**dmxplayer** — the engine appends `--output-latency-ms` to the spawn
command when settings.xml has an integer:

```bash
ps auxww | grep -v grep | grep cuems-dmxplayer
# /usr/bin/cuems-dmxplayer [--output-latency-ms N] --port ... --uuid ...
```

**audioplayer** — spawned on-demand (per cue), also via the engine.
When settings.xml has an integer, the engine appends the flag and the
binary uses it in place of the JACK query:

```bash
ps auxww | grep -v grep | grep cuems-audioplayer
# /usr/bin/cuems-audioplayer -w -1 [--output-latency-ms N]
```

The binary also logs the effective value on startup:

```bash
sudo journalctl -u cuems-node-engine | grep -i "output latency"
```

## Other videocomposer flags (operator env file)

Unrelated to latency but same shape: videocomposer accepts any extra
CLI flag through a separate env file:

```bash
# /etc/cuems/videocomposer-flags.env
OPERATOR_FLAGS=--verbose
```

The ExecStart composes both: `$OPERATOR_FLAGS $OUTPUT_LATENCY_FLAG`.
See `/etc/cuems/videocomposer-flags.env.example` for the template.

## Measurement procedure

A single value that works on every rig does not exist — measure per
node for anything better than "starting point".

### Equipment

- Phone with a 120 fps slow-motion camera (most modern phones).
- A click track with audible beats (metronome, or a repeating
  `TickCue`).
- Optional: a frame-counter overlay video for the video pipeline
  (a numbered timecode burn-in).

### Video

1. Load a cue containing a frame-counter or high-contrast flash
   synchronized to a click-track audio layer on the same MTC.
2. Point the phone at both the display and the audio source
   (a speaker works) in the same frame.
3. Shoot 120 fps.
4. Step through frames and count the offset between the audible click
   and the visible frame change. Positive (video late) = raise the
   current `output_latency_ms`; negative (video early) = lower.

### Audio

`auto` is usually within a millisecond or two of correct on rigs
where JACK is configured properly. Only override if an A/B
comparison with a known-correct reference (e.g. a tightly
timecode-locked second audio source) shows audible drift.

### DMX

1. Stream a cue with a DMX fixture flashing on every beat, locked to
   the same MTC as a click-track audio layer.
2. Phone at 120 fps pointed at the fixture and a speaker in one
   frame.
3. Step through frames. If the fixture comes up before the click,
   `output_latency_ms` is too high; after, too low.

Expect per-node variation on ArtNet especially — LAN conditions
matter.

## Expected runtime behaviour

After Phase-5 is deployed and settings.xml is tuned:

- **Audio** lands at wire-MTC (compensation removes JACK output
  latency).
- **Video** lands at wire-MTC (compensation removes display pipeline
  latency).
- **DMX** fires ~compensation_ms ahead of wire-MTC so the fixture
  latches at wire-MTC. Accuracy depends on the DMX path:
  ENTTEC rigs may be a few ms early, ArtNet rigs a few ms late —
  typically sub-perceptual on most shows.

If DMX appears visibly late vs audio/video (typical for ArtNet on a
shared LAN), raise the value. If it appears early (typical for
optimized ENTTEC rigs with fast LEDs), lower it.

## Related files

- `/etc/cuems/settings.xml` — authoritative operator config, per
  node.
- `/etc/cuems/settings.xsd` — the schema; defines the accepted value
  ranges and the `auto` keyword semantics per player type.
- `cuems-utils/templates/settings.xml` — reference template with
  REPLACE placeholders.
- `/etc/cuems/videocomposer-flags.env` — operator-tunable extra
  videocomposer flags (see `.example` for guidance).
- `/run/cuems/videocomposer.env` — machine-generated, ephemeral;
  rewritten on every `cuems-videocomposer.service` start from
  settings.xml by `/usr/lib/cuems/bin/cuems-extract-video-latency`.
