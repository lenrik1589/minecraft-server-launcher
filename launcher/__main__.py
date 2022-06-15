import os
import pathlib

from launcher import main

if __name__ == '__main__':
	pathlib.Path("minecraft server launcher").mkdir(parents=True, exist_ok=True)
	os.chdir("minecraft server launcher")
	main()
