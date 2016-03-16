import os, queue, subprocess, sys, threading
import tkinter, tkinter.filedialog, tkinter.messagebox

import sgf
from sgf import BLACK, WHITE, EMPTY

WIDTH, HEIGHT = 621, 621
GAP = 31

MOTD = """
  Fohristiwhirl's GTP relay.
"""

# --------------------------------------------------------------------------------------
# Various utility functions...

def load_graphics():
    directory = os.path.dirname(os.path.realpath(sys.argv[0]))
    os.chdir(directory)    # Set working dir to be same as infile.

    # PhotoImages have a tendency to get garbage-collected even when they're needed.
    # Avoid this by making them globals, so there's always a reference to them.

    global spriteTexture; spriteTexture = tkinter.PhotoImage(file = "gfx/texture.gif")
    global spriteBlack; spriteBlack = tkinter.PhotoImage(file = "gfx/black.gif")
    global spriteWhite; spriteWhite = tkinter.PhotoImage(file = "gfx/white.gif")
    global spriteHoshi; spriteHoshi = tkinter.PhotoImage(file = "gfx/hoshi.gif")
    global spriteMove; spriteMove = tkinter.PhotoImage(file = "gfx/move.gif")
    global spriteVar; spriteVar = tkinter.PhotoImage(file = "gfx/var.gif")
    global spriteTriangle; spriteTriangle = tkinter.PhotoImage(file = "gfx/triangle.gif")
    global spriteCircle; spriteCircle = tkinter.PhotoImage(file = "gfx/circle.gif")
    global spriteSquare; spriteSquare = tkinter.PhotoImage(file = "gfx/square.gif")
    global spriteMark; spriteMark = tkinter.PhotoImage(file = "gfx/mark.gif")

    global markup_dict; markup_dict = {"TR": spriteTriangle, "CR": spriteCircle, "SQ": spriteSquare, "MA": spriteMark}

# --------------------------------------------------------------------------------------
# Currently everything that returns a value is outside the class...

def screen_pos_from_board_pos(x, y, boardsize):
    gridsize = GAP * (boardsize - 1) + 1
    margin = (WIDTH - gridsize) // 2
    ret_x = (x - 1) * GAP + margin
    ret_y = (y - 1) * GAP + margin
    return ret_x, ret_y

def board_pos_from_screen_pos(x, y, boardsize):        # Inverse of the above
    gridsize = GAP * (boardsize - 1) + 1
    margin = (WIDTH - gridsize) // 2
    ret_x = round((x - margin) / GAP + 1)
    ret_y = round((y - margin) / GAP + 1)
    return ret_x, ret_y

def title_bar_string(node):
    wwtm = node.what_was_the_move()
    mwp = node.move_was_pass()

    if wwtm is None and not mwp:
        if node.parent:
            title = "Empty node"
        else:
            title = "Root node"
    else:
        title = "Move {}".format(node.moves_made)
    if node.parent:
        if len(node.parent.children) > 1:
            index = node.parent.children.index(node)
            title += " [{} of {} variations]".format(index + 1, len(node.parent.children))
    if mwp:
        title += " (pass)"
    elif wwtm:
        x, y = wwtm
        title += " ({})".format(sgf.english_string_from_point(x, y, node.board.boardsize))
    return title

def send_command(process, command, verbose = True):

    if len(command) == 0 or command[-1] != "\n":
        command += "\n"

    if verbose:
        print(command, end="")

    process.stdin.write(bytearray(command, encoding="ascii"))
    process.stdin.flush()

def get_reply(process, verbose = True):

    response = ""

    while 1:
        newlinebytes = process.stdout.readline()
        newline = str(newlinebytes, encoding="ascii")
        newline = newline.replace("\r\n", "\n")             # is there a better way to deal with this Windows nonsense?

        response += newline

        if len(response) >= 2:
            if response[-2:] == "\n\n":
                response = response.strip()
                if verbose:
                    print(response)
                return response

def send_and_get(process, command, output_queue, verbose = True):

    send_command(process, command, verbose)
    response = get_reply(process)

    if output_queue:
        output_queue.put(response)

    return response

def send_and_get_threaded(process, command, output_queue, verbose = True):

    newthread = threading.Thread(target = send_and_get,
                                 kwargs = {
                                            "process": process,
                                            "command": command,
                                            "output_queue": output_queue,
                                            "verbose": verbose
                                           })
    newthread.start()

# --------------------------------------------------------------------------------------

class GTP_GUI(tkinter.Canvas):

    def __init__(self, owner, proc_args, *args, **kwargs):
        tkinter.Canvas.__init__(self, owner, *args, **kwargs)
        self.owner = owner
        self.bind("<Button-1>", self.mouseclick_handler)
        self.process = subprocess.Popen(args = proc_args, stdin = subprocess.PIPE, stdout = subprocess.PIPE)    #, stderr = subprocess.DEVNULL)

        self.reset()
        self.draw_node(tellowner = False)   # The mainloop in the owner hasn't started yet, dunno if sending event is safe

        self.engine_output = queue.Queue()

        self.engine_msg_poller()


    def reset(self):
        for cmd in ["boardsize 19", "clear_board", "komi 0"]:
            send_command(self.process, cmd)
            get_reply(self.process)

        self.node = sgf.new_tree(19)
        self.next_colour = BLACK
        self.human_colour = BLACK
        self.engine_colour = WHITE


    def mouseclick_handler(self, event):

        if self.next_colour == self.human_colour:

            x, y = board_pos_from_screen_pos(event.x, event.y, self.node.board.boardsize)
            result = self.node.try_move(x, y)

            if result:
                self.next_colour = self.engine_colour
                
                self.node = result

                colour_lookup = {BLACK: "black", WHITE: "white"}

                command = "play {} {}".format(colour_lookup[self.human_colour], sgf.english_string_from_point(x, y, self.node.board.boardsize))
                send_and_get(self.process, command, output_queue = None)

                command = "genmove {}".format(colour_lookup[self.engine_colour])
                send_and_get_threaded(self.process, command, output_queue = self.engine_output)

        self.draw_node()


    def engine_msg_poller(self):
        self.after(100, self.engine_msg_poller)     # Add a callback here in 100 ms
        self.engine_move_handler()


    def engine_move_handler(self):
        try:
            message = self.engine_output.get(block = False)
        except queue.Empty:
            return
        if message[0] != "=":
            return
        message = message[1:].strip()
        if len(message) in [2,3]:
            point = sgf.point_from_english_string(message, self.node.board.boardsize)
            if point is None:
                return
            else:
                x, y = point
            if self.next_colour != self.engine_colour:
                print("ERROR: got move at unexpected time")
                return
            result = self.node.try_move(x, y)
            if result is None:
                print("ERROR: got illegal move {}".format(message))
                return
            self.node = result
            self.draw_node()
            self.next_colour = self.human_colour


    def draw_node(self, tellowner = True):
        self.delete(tkinter.ALL)              # DESTROY all!
        boardsize = self.node.board.boardsize

        # Tell the owner that we drew...

        if tellowner:
            self.owner.event_generate("<<boardwasdrawn>>", when="tail")

        # Draw the texture...

        self.create_image(0, 0, anchor = tkinter.NW, image = spriteTexture)

        # Draw the hoshi points...

        for x in range(3, boardsize - 1):
            for y in range(boardsize - 1):
                if sgf.is_star_point(x, y, boardsize):
                    screen_x, screen_y = screen_pos_from_board_pos(x, y, boardsize)
                    self.create_image(screen_x, screen_y, image = spriteHoshi)

        # Draw the lines...

        for n in range(1, boardsize + 1):
            start_a, start_b = screen_pos_from_board_pos(n, 1, boardsize)
            end_a, end_b = screen_pos_from_board_pos(n, boardsize, boardsize)

            end_b += 1

            self.create_line(start_a, start_b, end_a, end_b)
            self.create_line(start_b, start_a, end_b, end_a)

        # Draw the stones...

        for x in range(1, self.node.board.boardsize + 1):
            for y in range(1, self.node.board.boardsize + 1):
                screen_x, screen_y = screen_pos_from_board_pos(x, y, self.node.board.boardsize)
                if self.node.board.state[x][y] == sgf.BLACK:
                    self.create_image(screen_x, screen_y, image = spriteBlack)
                elif self.node.board.state[x][y] == sgf.WHITE:
                    self.create_image(screen_x, screen_y, image = spriteWhite)

        # Draw a mark at the current move, if there is one...

        move = self.node.what_was_the_move()
        if move is not None:
            screen_x, screen_y = screen_pos_from_board_pos(move[0], move[1], self.node.board.boardsize)
            self.create_image(screen_x, screen_y, image = spriteMove)

        # Draw a mark at variations, if there are any...

        for sib_move in self.node.sibling_moves():
            screen_x, screen_y = screen_pos_from_board_pos(sib_move[0], sib_move[1], self.node.board.boardsize)
            self.create_image(screen_x, screen_y, image = spriteVar)

        # Draw the commonly used marks...

        for mark in markup_dict:
            if mark in self.node.properties:
                points = set()
                for value in self.node.properties[mark]:
                    points |= sgf.points_from_points_string(value, self.node.board.boardsize)
                for point in points:
                    screen_x, screen_y = screen_pos_from_board_pos(point[0], point[1], self.node.board.boardsize)
                    self.create_image(screen_x, screen_y, image = markup_dict[mark])

# ---------------------------------------------------------------------------------------

if __name__ == "__main__":
    print(MOTD)

    window = tkinter.Tk()
    window.resizable(width = False, height = False)
    window.geometry("{}x{}".format(WIDTH, HEIGHT))
    window.bind("<<boardwasdrawn>>", lambda x: window.wm_title(title_bar_string(board.node)))

    load_graphics()

    if len(sys.argv) < 2:
        print("Need an argument: the engine to run (it may also require more arguments)")
        sys.exit(1)

    board = GTP_GUI(window, sys.argv[1:], width = WIDTH, height = HEIGHT, bd = 0, highlightthickness = 0)
    board.pack()
    board.focus_set()

    window.wm_title("Fohristiwhirl's GTP relay")
    window.mainloop()
