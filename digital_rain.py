import random
import curses
import time

# Digital rain effect inspired by The Matrix

def digital_rain(stdscr, speed=0.05):
    curses.curs_set(0)
    stdscr.nodelay(True)
    height, width = stdscr.getmaxyx()
    columns = [0] * width

    try:
        while True:
            stdscr.clear()
            for i in range(width):
                if columns[i] == 0 and random.random() < 0.02:
                    columns[i] = random.randint(1, height)
                if columns[i] > 0:
                    for j in range(columns[i]):
                        char = chr(random.randint(33, 126))
                        stdscr.addch((height - j) % height, i, char, curses.A_BOLD)
                    columns[i] -= 1
            stdscr.refresh()
            time.sleep(speed)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    curses.wrapper(digital_rain)
