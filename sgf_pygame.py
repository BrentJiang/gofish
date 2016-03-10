import os, pygame, sys
from pygame.locals import *
import sgf

if len(sys.argv) != 2:
	os.exit(1)


WIDTH, HEIGHT = 601, 601

# Initialise...

pygame.mixer.pre_init(frequency=22050, size=-16, channels=16, buffer=512)		# Reduces audio lag
pygame.init()
pygame.mixer.init()

fpsClock = pygame.time.Clock()

# Load resources...

directory = os.path.dirname(os.path.realpath(sys.argv[0]))
os.chdir(directory)	# Set working dir to be same as infile.

spriteGoban = pygame.image.load("gfx/goban.jpg")
spriteBlack = pygame.image.load("gfx/black.png")
spriteWhite = pygame.image.load("gfx/white.png")
spriteCross = pygame.image.load("gfx/cross.png")

# Initialise the window...

virtue = pygame.display.set_mode((WIDTH, HEIGHT))

# Input device states...

keyboard = dict()

# Utility functions...

def cleanexit():
	pygame.quit()
	sys.exit()

def blit(target, source, x, y):
	topleftx = x - source.get_width() / 2
	toplefty = y - source.get_height() / 2
	target.blit(source, (topleftx, toplefty))

def blit_without_adjust(target, source, x, y):
	target.blit(source, (x, y))

# Game...

node = sgf.load(sys.argv[1])
node.print_comments()

while 1:

	# Update keyboard states...

	for event in pygame.event.get():
		if event.type == QUIT:
			cleanexit()
		if event.type == KEYDOWN:
			keyboard[event.key] = 1
		if event.type == KEYUP:
			keyboard[event.key] = 0

	# Handle input if a key is down. Set the key to be up to avoid repetitions...

	if keyboard.get(K_DOWN, 0):
		keyboard[K_DOWN] = 0
		try:
			node = node.children[0]
			node.print_comments()
		except:
			pass

	if keyboard.get(K_UP, 0):
		keyboard[K_UP] = 0
		if node.parent:
			node = node.parent

	if keyboard.get(K_RIGHT, 0):
		keyboard[K_RIGHT] = 0
		for n in range(10):
			try:
				node = node.children[0]
				node.print_comments()
			except:
				pass

	if keyboard.get(K_LEFT, 0):
		keyboard[K_LEFT] = 0
		for n in range(10):
			if node.parent:
				node = node.parent

	if keyboard.get(K_TAB, 0):
		keyboard[K_TAB] = 0
		if node.parent:
			if len(node.parent.children) > 1:
				index = node.parent.children.index(node)
				if index < len(node.parent.children) - 1:
					index += 1
				else:
					index = 0
				node = node.parent.children[index]
				node.print_comments()

	# Set the title...

	if node.parent and len(node.parent.children) > 1:
		index = node.parent.children.index(node)
		pygame.display.set_caption("{} of {} variations available (press Tab)".format(index + 1, len(node.parent.children)))
	else:
		move_string = "Move {}".format(node.moves_made)
		pygame.display.set_caption("{}. Navigate with Arrow Keys".format(move_string))

	# Draw the board...

	blit_without_adjust(virtue, spriteGoban, 0, 0)
	for x in range(20):
		for y in range(20):
			if node.board.state[x][y] == sgf.BLACK:
				blit(virtue, spriteBlack, 30 * x, 30 * y)
			elif node.board.state[x][y] == sgf.WHITE:
				blit(virtue, spriteWhite, 30 * x, 30 * y)
	move = node.what_was_the_move()
	if move is not None:
		mark_x = move[0]
		mark_y = move[1]
		blit(virtue, spriteCross, 30 * mark_x, 30 * mark_y)

	# Update and wait...

	pygame.display.update()
	fpsClock.tick(30)
