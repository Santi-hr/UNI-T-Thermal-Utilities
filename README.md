# UNI-T-Thermal-Utilities
![Extraction examples](https://raw.githubusercontent.com/Santi-hr/UNI-T-Thermal-Utilities/main/examples/readme_header.jpg)

UNI-T thermal cameras, like UTi260B, store a clean thermal image embedded at the end of the bmp files that are generated for each capture.
In addition, the selected colorbar, configuration variables, and the temperature of some key points are also stored.

The current small script allows extracting this data and exporting it or as a lib for its use from other scripts.

My end goal is to also provide a GUI tool that can perform some analysis the UNI-T software lacks.
Like setting custom colorbars, or printing temperature profiles.

## Requirements

It only needs the Python package *numpy*.

For running the lib use example also *matplotlib* is required.

## How to use

The module can be used by importing it (See use example for a more in depth usage):

```python
import uniTThermalImage as uti
obj_uti = uti.UniTThermalImage()
obj_uti.init_from_image("examples/IMG_Typical.bmp")
```

Or by calling it as a script:

```bash
python uniTThermalImage.py -i "examples/IMG_Typical.bmp" -bmp -csv
```

```bash
usage: uniTThermalImage.py [-h] -i INPUT [-o OUTPUT] [-bmp] [-csv] [-csv_es]

Extracts thermal data from UNI-T thermal camera images

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input .bmp image
  -o OUTPUT, --output OUTPUT
                        Desired output folder
  -bmp, --exportbmp     Exports a clean thermal image from the input one
  -csv, --exportcsv     Exports the thermal data to a csv file
  -csv_es, --exportcsv_es
                        Exports the thermal data to a csv file, using ;
                        instead of ,
```

This command will create two files from the input image.
A cleaned thermal image without the labels, and a csv file with the embbeded data and the temperature for each point of the image. 


## Tested cameras:

- UTi260B

## Embedded data format

In this section the format used by UNI-T in its newer thermal cameras, firmware v1.1.2, is explained.
When an image is taken two files are generated. One .bmp, that contains all thermal data, and one .jpg with the view from the visible light camera. 

The data in the .bmp file is distributed in the following blocks: 

| Byte length | Description | Notes |
| --- | --- | --- |
| 53 | BMP Header | Standard format |
| BMP Image size | BMP Data | BGR, 3 bytes per color |
| Img Height x Width | Thermal image | Grayscale, 1 byte per pixel |
| 512 | Colorbar | 256 colors, 2 bytes per color (5 bits red, 6 bits green, 5 bits blue) |
| 25 | Embedded data | See next table

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

