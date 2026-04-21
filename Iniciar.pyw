import runpy
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
runpy.run_path("ExtractorPro/app.py", run_name="__main__")
