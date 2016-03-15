import os, sys
import tkinter, tkinter.filedialog, tkinter.messagebox

import sgf

WIDTH, HEIGHT = 621, 621
GAP = 31

MOTD = """
  Fohristiwhirl's SGF readwriter. Keys:

  -- LOAD / SAVE: Ctrl-O, Ctrl-S

  -- NAVIGATE: Arrows, Home, End, PageUp, PageDown
  -- SWITCH TO SIBLING: Tab
  -- RETURN TO MAIN LINE: Backspace
  -- DESTROY NODE: Delete

  -- MAKE MOVE: Mouse Button
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
        title = "Empty node"
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

# --------------------------------------------------------------------------------------

class BoardCanvas(tkinter.Canvas):
    def __init__(self, owner, filename, *args, **kwargs):
        tkinter.Canvas.__init__(self, owner, *args, **kwargs)

        self.owner = owner

        self.bind("<Key>", self.call_keypress_handler)
        self.bind("<Button-1>", self.mouseclick_handler)
        self.bind("<Control-o>", self.opener)
        self.bind("<Control-s>", self.saver)

        self.node = sgf.new_tree(19)        # Do this now in case the load fails

        if filename is not None:
            self.open_file(filename)

        self.draw_node(tellowner = False)   # The mainloop in the owner hasn't started yet, dunno if sending event is safe

    def open_file(self, infilename):
        try:
            self.node = sgf.load(infilename)
            print("<--- Loaded: {}\n".format(infilename))
            self.node.dump(include_comments = False)
            print()
            self.node.print_comments()
        except FileNotFoundError:
            print("error while loading: file not found")
        except sgf.BadBoardSize:
            print("error while loading: SZ (board size) was not in range 1:19")
        except sgf.ParserFail:
            print("error while loading: parser failed (invalid SGF?)")

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

    # --------------------------------------------------------------------------------------
    # All the key handlers are in the same form:
    #
    # def handle_key_NAME(self):
    #     <do stuff>
    #
    # where NAME is an uppercase version of the event.keysym, see:
    # http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/key-names.html
    #
    # One can make a new key handler just by creating it, no other work is needed anywhere

    def call_keypress_handler(self, event):
        try:
            function_call = "self.handle_key_{}()".format(event.keysym.upper())
            eval(function_call)
        except AttributeError:
            pass
        self.draw_node()

    # ----- (the above makes the following work) -----

    def handle_key_DOWN(self):
        try:
            self.node = self.node.children[0]
            self.node.print_comments()
        except IndexError:
            pass

    def handle_key_RIGHT(self):
        self.handle_key_DOWN()

    def handle_key_UP(self):
        if self.node.parent:
            self.node = self.node.parent

    def handle_key_LEFT(self):
        self.handle_key_UP()

    def handle_key_NEXT(self):          # PageDown
        for n in range(10):
            try:
                self.node = self.node.children[0]
                self.node.print_comments()
            except IndexError:
                break

    def handle_key_PRIOR(self):         # PageUp
        for n in range(10):
            if self.node.parent:
                self.node = self.node.parent
            else:
                break

    def handle_key_TAB(self):
        if self.node.parent:
            if len(self.node.parent.children) > 1:
                index = self.node.parent.children.index(self.node)
                if index < len(self.node.parent.children) - 1:
                    index += 1
                else:
                    index = 0
                self.node = self.node.parent.children[index]
                self.node.print_comments()

    def handle_key_BACKSPACE(self):         # Return to the main line
        while 1:
            if self.node.is_main_line:
                break
            if self.node.parent is None:
                break
            self.node = self.node.parent

    def handle_key_HOME(self):
        self.node = self.node.get_root_node()

    def handle_key_END(self):
        self.node = self.node.get_end_node()

    def handle_key_DELETE(self):
        if len(self.node.children) > 0:
            ok = tkinter.messagebox.askokcancel("Delete?", "Delete this node and all of its children?")
        else:
            ok = True
        if ok:
            if self.node.parent:
                child = self.node
                self.node = self.node.parent
                self.node.children.remove(child)
                self.node.fix_main_line_status_recursive()
            else:
                self.node = sgf.new_tree(19)

    def handle_key_D(self):
        self.node.debug()

    # Other handlers...

    def opener(self, event):
        infilename = tkinter.filedialog.askopenfilename()
        if infilename:
            self.open_file(infilename)
        self.draw_node()

    def saver(self, event):
        outfilename = tkinter.filedialog.asksaveasfilename(defaultextension=".sgf")
        if outfilename:
            sgf.save_file(outfilename, self.node)
            print("---> Saved: {}\n".format(outfilename))
        self.draw_node()

    def mouseclick_handler(self, event):
        x, y = board_pos_from_screen_pos(event.x, event.y, self.node.board.boardsize)
        result = self.node.try_move(x, y)
        if result:
            self.node = result
        self.draw_node()

# ---------------------------------------------------------------------------------------

if __name__ == "__main__":
    print(MOTD)

    window = tkinter.Tk()
    window.resizable(width = False, height = False)
    window.geometry("{}x{}".format(WIDTH, HEIGHT))
    window.bind("<<boardwasdrawn>>", lambda x: window.wm_title(title_bar_string(board.node)))

    load_graphics()

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = None

    board = BoardCanvas(window, filename, width = WIDTH, height = HEIGHT, bd = 0, highlightthickness = 0)
    board.pack()
    board.focus_set()

    window.wm_title("Fohristiwhirl's SGF readwriter")
    window.mainloop()
