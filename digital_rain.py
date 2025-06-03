#!/usr/bin/env python3
"""Digital rain terminal animation."""

import argparse
import random
import curses
import time

# Digital rain effect inspired by The Matrix

def digital_rain(stdscr, speed: float = 0.05, duration: float | None = None) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    height, width = stdscr.getmaxyx()
    columns = [0] * width
    start_time = time.time()
    try:
        while duration is None or time.time() - start_time < duration:
            stdscr.clear()
            for i in range(width):
                if columns[i] == 0 and random.random() < 0.02:
                    columns[i] = random.randint(1, height)
                if columns[i] > 0:
                    for j in range(columns[i]):
                        char = chr(random.randint(33, 126))
                        try:
                            stdscr.addch((height - j) % height, i, char, curses.A_BOLD)
                        except curses.error:
                            # Ignore drawing errors (e.g., bottom-right corner)
                            pass
                    columns[i] -= 1
            stdscr.refresh()
            time.sleep(speed)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Digital rain")
    parser.add_argument("--duration", type=float, default=None,
                        help="Duration to run in seconds")
    parser.add_argument("--speed", type=float, default=0.05,
                        help="Delay between frames")
    args = parser.parse_args()
    curses.wrapper(digital_rain, args.speed, args.duration)
