# test-2
mofobigbongo

## Digital Rain

Run the digital rain effect in your terminal or trigger it from GitHub
Actions:

```bash
./digital_rain.py --duration 10
```

You can also manually run the `Digital Rain Demo` workflow from the
Actions tab to see a short run in the workflow logs.

Use `Ctrl+C` to exit early. If your terminal does not fully support curses,
some characters may not display correctly, but the program will handle these
errors gracefully.

## Flappy Bird Neo

Play the Flappy Bird Neo game. By default it starts in auto-pilot mode. Use
`--manual` to start with manual controls.

```bash
python3 flappy_bird_neo.py [--manual]
```

Controls inside the game:
- `SPACE` to flap (when auto-pilot is off)
- `A` to toggle auto-pilot
- `P` to pause
- `R` to restart after game over
- `ESC` or `Q` to quit
