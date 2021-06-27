# UNI-T-Thermal-Utilities
![Extraction examples](https://raw.githubusercontent.com/Santi-hr/UNI-T-Thermal-Utilities/main/examples/readme_header.jpg)

UNI-T thermal cameras, like UTi260B, store a clean thermal image embedded at the end of its bmp files.
In addition, the selected palette, configuration variables, and the temperature of some key points are also stored.

The current small script allows extracting this data and exporting it, or as a python lib for its use from other scripts.
Also, it provides functions to: 
* Change the palette, between the ones from the camera or to a custom one.
* Set the temperature range, to highlight details or compare between images.

Beware, the extracted thermal data can have large errors when there is a large temperature range. This happens because the data stored does not come directly from the sensor, but from what appears on screen. Check [here](docs/temperature_issue.md) for more information.
For precise measurements use the "point temperature" option directly on the camera. 

My end goal is to also provide a GUI tool that can perform some analysis the UNI-T software lacks.
Like setting custom palettes, or printing temperature profiles.

## Requirements

It only needs the Python package *numpy*.

For running the [usage example](src/usageExample.py) script *matplotlib* is required.

## How to use

The module can be used as a library (See [usage example](src/usageExample.py) for a more in depth example):

```python
import uniTThermalImage
obj_uti = uniTThermalImage.UniTThermalImage()
obj_uti.init_from_image("examples/IMG_Typical.bmp")
```

Or by calling it as a script:
```bash
python uniTThermalImage.py -i "examples/IMG_Typical.bmp" -bmp -csv en
```

This command will create two files from the input image.
A cleaned thermal image without the labels, and a csv file with the embedded data and the temperature for each point of the image.


```bash
usage: uniTThermalImage.py [-h] -i INPUT [-o OUTPUT] [-bmp] [-csv {en,es,img}]
                           [-p PALETTE] [-nf]

Extracts thermal data from UNI-T thermal camera images

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input .bmp image
  -o OUTPUT, --output OUTPUT
                        Desired output folder
  -bmp, --exportbmp     Exports a clean thermal image from the input one
  -csv {en,es,img}, --exportcsv {en,es,img}
                        Exports the thermal data to a csv file. Options: en -
                        default csv, es - semicolon delimited csv, img - only
                        image data to a tab-delimited csv. Allows import in
                        ThermImageJ
  -p PALETTE, --palette PALETTE
                        Sets palette. Multiple. Options: iron, rainbow,
                        white_hot, red_hot, lava, rainbow_hc, reverse
  -th TEMPHIGH, --temphigh TEMPHIGH
                        Sets the maximum on the temperature range
  -tl TEMPLOW, --templow TEMPLOW
                        Sets the minimum on the temperature range
  -nf, --nofix          Processes data without temperature fix. Check
                        temperature_issue.md for more info
```
Regarding the palettes, to get *black_hot* use two palette arguments. See next example: 
```bash
python uniTThermalImage.py -i "examples/IMG_Typical.bmp" -bmp -p white_hot -p reverse
```

## Tested cameras:

- UTi260B
- UTi220A Pro

## Embedded data format

In this section the format used by UNI-T in its newer thermal cameras, firmware v1.1.2, is explained.
When an image is taken two files are generated. One .bmp, that contains all thermal data, and one .jpg with the view from the visible light camera. 

The data in the .bmp file is distributed in the following blocks: 

| Byte length | Description | Notes |
| --- | --- | --- |
| 53 | BMP Header | Standard format |
| BMP Image size | BMP Data | BGR, 3 bytes per pixel |
| Img Height x Width | Thermal image | Grayscale, 1 byte per pixel ([0, 254] = [Min. temp., Max. temp.])* |
| 512 | Palette | 256 colors, 2 bytes per color (5 bits red, 6 bits green, 5 bits blue) |
| 25 | Embedded data | See next table

*Using this approximation temperatures are not exact when the temperature range is large.
This behaviour is also seen in the UNI-T software. [More info.](docs/temperature_issue.md)

The embedded data is as shown in the next table. All is stored in little endian:

| Bytes | Description | Type | Notes |
| --- | --- | --- | --- |
| 0 | Temperature unit | uint8 | Enum: 0:ºC, 1:ºF |
| 1 - 2 | Maximum temp. | int16 | Scaled by 10 |
| 3 - 4 | Minimum temp. | int16 | Scaled by 10 |
| 5 - 6 | Unknown | int16 | Always 255/0 |
| 7 - 8 | Center temp. | int16 | Scaled by 10 |
| 9 | Emissivity | uint8 | Scaled by 100 |
| 10 - 13 | Unknown | uint16 | Always 6/0/0/0 |
| 14 - 15 | Max. temp. pos X | uint16 | |
| 16 - 17 | Max. temp. pos Y | uint16 | |
| 18 - 19 | Min. temp. pos X | uint16 | |
| 20 - 21 | Min. temp. pos Y | uint16 | |
| 22 - 23 | Center temp. pos X | uint16 | |
| 24 - 25 | Center temp. pos Y | uint16 | |

Note: Images exported with this script include after this data an aditional uint32 with the timestamp of the image to avoid losing this information.