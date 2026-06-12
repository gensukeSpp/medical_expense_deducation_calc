import pathlib
import sys

packagedir = pathlib.Path(__file__).resolve().parent.parent.parent
print(packagedir)
sys.path.append(str(packagedir))
