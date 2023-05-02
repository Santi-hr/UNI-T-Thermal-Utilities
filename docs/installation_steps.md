## Step-by-step procedure to run the script on a terminal

The following steps ensure python and the required packages are installed:
1. Open a terminal
2. Check if Python is installed by entering `python3 --version` into the terminal:
    1. If the command is recognized and the version is 3.7 or above continue
    2. If the command was not recognized go to  [the Python download website](https://www.python.org/downloads/) and get the installer for your SO.
3. Install requiered packages
    1. Check if the Package Installer for Python (PIP) is installed by entering `python3 -m pip --version` into the terminal.
    2. If not installed run the command `python3 -m ensurepip` and try again
    3. Install numpy using the command `pip3 install numpy` or `python3 -m pip install numpy`
4. Download the whole repository or only [main script, uniTThermalImage.py,](https://github.com/Santi-hr/UNI-T-Thermal-Utilities/blob/main/src/uniTThermalImage.py) into a folder
5. Open a terminal into the folder where the uniTThermalImage.py is located and run the script using the command `python3 uniTThermalImage.py`
   1. Data is passed to the script by using arguments, for example `-i` followed by the path to an image or folder to set its input.
   2. Run in the terminal `python3 uniTThermalImage.py -h` to get a list of possible arguments
   3. Example, if you downloaded the whole repository and are running the script from the src folder, using the following command will save a new clean thermal image where the palette is changed to rainbow: `python3 uniTThermalImage.py -i "../examples/samples/IMG_Typical.bmp" -bmp -p rainbow`

If no argument for output folder is specified it will be the working path.