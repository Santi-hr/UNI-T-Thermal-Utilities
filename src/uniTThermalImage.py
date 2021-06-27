import numpy as np
import argparse
from pathlib import Path
from datetime import datetime


class UniTThermalImage:
    """Class to handle UNI-T thermal camera images. Tested with UTi260B"""

    def __init__(self, *, use_fix=True):
        """Class constructor

        :param use_fix: Temperature fix can be disabled to increase performance greatly if not going to be used
        """
        # User configurable data
        self.bmp_suffix = "_thermal_rgb.bmp"
        self.csv_suffix = ".csv"
        self.output_folder = Path("")

        # Class variables
        self.flag_initialized = False
        self.filename = ""  # Name of the file
        self.file_bytes = []  # Bytes of the loaded .bmp

        self.bmp_header = {}  # Bmp header of the loaded image

        self.palette_rgb_np = None  # Numpy array [Pallete Len, 3] with the rgb values of the palette

        self.raw_img_np = None      # Numpy array [W,L] with the raw thermal image
        self.raw_img_rgb_np = None  # Numpy array [W,L,3] with the rgb thermal image (palette applied to previous)
        self.raw_temp_np = None     # Numpy array [W,L] with the temperature of each pixel using linear interpolation

        self.fix_img_np = None      # Numpy array [W,L] with a fixed thermal image
        self.fix_img_rgb_np = None  # Numpy array [W,L,3] with the rgb thermal image (palette applied to previous)
        self.fix_temp_np = None     # Numpy array [W,L] with the temperature of each pixel using 3 point interpolation
        # The fix uses a linear interpolation that passes through the center temperature to reduce temperature error
        # See docs/temperature_issue.md to know more about why the need for a fix
        self.use_fix = use_fix      # Fix can be disabled to increase performance greatly if not going to be used

        self.temp_units = 'N'       # Temperature units, Celsius (C) or Fahrenheit (F)
        self.temp_max = 0           # Maximum temperature of the picture
        self.temp_min = 0           # Minimum temperature of the picture
        self.temp_center = 0        # Center temperature of the picture
        self.emissivity = 0         # Configured emissivity
        self.temp_min_pos_w = 0     # Pixel pos in width axis of the minimum temperature
        self.temp_min_pos_h = 0     # Pixel pos in height axis of the minimum temperature
        self.temp_max_pos_w = 0     # Pixel pos in width axis of the maximum temperature
        self.temp_max_pos_h = 0     # Pixel pos in height axis of the maximum temperature
        self.temp_center_pos_w = 0  # Pixel pos in width axis of the center temperature
        self.temp_center_pos_h = 0  # Pixel pos in height axis of the center temperature

        self.img_datetime = None    # Datetime object with the date and time of image capture

        self.temp_max_ow = 0        # Maximum temperature of the picture (Overwritten by changing temp range)
        self.temp_min_ow = 0        # Minimum temperature of the picture (Overwritten by changing temp range)

        self.__palette_updated = False  # True if palette was changed

    def init_from_image(self, filepath):
        """Initializes this object by extracting data from a UNI-T .bmp file

        :param filepath: Path to the file
        """
        path_in = Path(filepath)
        self.filename = path_in.name[:-len(path_in.suffix)]

        # Input file checks
        if not path_in.exists():
            raise FileNotFoundError("File %s not found" % path_in)
        if path_in.suffix.lower() != ".bmp":
            raise ValueError("File is not .bmp")
        # TODO: Check internal file format

        # Read file and save file modification date
        with open(path_in, "rb") as file:
            self.file_bytes = file.read()
        self.__get_file_time_os(path_in)

        # Read BMP header
        self.__get_bmp_header()
        # Get grayscale image after .bmp
        byte_offset = self.__extract_grayscale_img()

        # Get palette after grayscale image
        byte_offset = self.__extract_palette(byte_offset)

        # Get embedded temperature after palette
        byte_offset = self.__extract_temp_data(byte_offset)

        # Get embedded timestamp after embedded data
        self.__extract_file_time(byte_offset)

        # Set internal variables using the loaded data
        self.__set_raw_temp_matrix()
        if self.use_fix:
            self.__set_fix_temp_matrix()
            self.__set_fix_grayscale_image()
        self.__set_rgb_image()

        self.flag_initialized = True

    def set_palette(self, palette_in_np=None, reverse=False):
        """Changes the palette and updates the rbg image

        :param palette_in_np: RGB Palette as (256 ,3) numpy array
        :param reverse: Bool flag. If true the current palette is reversed
        """
        if palette_in_np is not None:
            if palette_in_np.shape != (256, 3):
                raise ValueError("Invalid shape of palette. Expected (256,3), actual: " + str(palette_in_np.shape))
            self.palette_rgb_np = palette_in_np
        if reverse:
            self.palette_rgb_np = np.flip(self.palette_rgb_np, 0)
        self.__set_rgb_image()
        self.__palette_updated = True

    def set_temp_range(self, t_min, t_max):
        """Changes the temperature range and updates the gray and rgb images
        (This changes do not export to avoid loosing data)

        :param t_min: Lower end of the new temperature range
        :param t_max: Higher end of the new temperature range
        """
        # Store the new range limits to allow accessing them if needed by the user
        self.temp_min_ow = t_min
        self.temp_max_ow = t_max

        # Min < Max not checked. Can be used to invert the scale, but changing the palette is prefered
        # Linear interpolation of temperature [t_min, t_max] > [0, 255], temperatures outside this range are clipped
        # Grayscale numpy array is forced to be uint8 for the rgb conversion, decimal info is lost
        self.raw_img_np = np.clip(255 * (self.raw_temp_np - t_min) / (t_max - t_min), 0, 255)
        self.raw_img_np = self.raw_img_np.astype(dtype=np.uint8)
        if self.use_fix:
            self.fix_img_np = np.clip(255 * (self.fix_temp_np - t_min) / (t_max - t_min), 0, 255)
            self.fix_img_np = self.fix_img_np.astype(dtype=np.uint8)

        self.__set_rgb_image()

    def export_csv(self, only_img=False, delimiter=',', decimal_sep='.', export_fix=True):
        """Exports data to a csv file

        :param only_img: True to skip header data and only save temperature data.
        :param delimiter: Data row delimiter
        :param decimal_sep: Decimal separator
        :param export_fix: Exports data using fix, if possible
        """
        export_temp_np = self.raw_temp_np
        if self.use_fix and export_fix:
            export_temp_np = self.fix_temp_np

        output_path = self.output_folder / (self.filename + self.csv_suffix)

        with open(output_path, "w") as file:
            if not only_img:
                # Embedded data values
                header_data = ["Units", "Temp min", "Temp max", "Temp center", "Emissivity",
                               "Temp min X", "Temp min Y", "Temp max X", "Temp max Y", "Datetime"]
                data_data = [self.temp_units, self.temp_min, self.temp_max, self.temp_center, self.emissivity,
                             self.temp_min_pos_w, self.temp_min_pos_h, self.temp_max_pos_w, self.temp_max_pos_h,
                             self.img_datetime.strftime("%Y-%m-%d %H:%M:%S")]

                file.write(self.__csv_str_line_formatter(header_data, delimiter, decimal_sep))
                file.write(self.__csv_str_line_formatter(data_data, delimiter, decimal_sep))

                # Thermal image header
                header_data_img = ["Pixel temperatures", "Down Y (Height)", "Right X (Width)"]
                file.write(self.__csv_str_line_formatter(header_data_img, delimiter, decimal_sep))
            # Thermal image as temperature values
            for idx_h in range(len(export_temp_np)):
                temp_list = []
                for idx_w in range(len(export_temp_np[idx_h])):
                    temp_list.append(export_temp_np[idx_h, idx_w])
                file.write(self.__csv_str_line_formatter(temp_list, delimiter, decimal_sep))

    def export_bmp(self, export_fix=True):
        """Exports a version of the input image without its overlay. It keeps the embedded data

        :param export_fix: Exports data using fix, if possible
        """
        export_img_rgb_np = self.raw_img_rgb_np
        if self.use_fix and export_fix:
            export_img_rgb_np = self.fix_img_rgb_np

        # Fixme: Check if rows needs padding for other resolutions. Now set for the UTi260B which does not require them
        output_bytes = list(self.file_bytes)
        bytes_offset = self.bmp_header['data_start_byte']
        bytes_per_px = round(self.bmp_header['bits_per_px']/8)
        for idx_h in range(self.bmp_header['img_height_px']-1, -1, -1): # In bmp files the rows are stored from the last
            for idx_w in range(self.bmp_header['img_width_px']):
                # 24 bit bmp files are BGR
                output_bytes[bytes_offset] = export_img_rgb_np[idx_h, idx_w, 2]
                output_bytes[bytes_offset + 1] = export_img_rgb_np[idx_h, idx_w, 1]
                output_bytes[bytes_offset + 2] = export_img_rgb_np[idx_h, idx_w, 0]
                bytes_offset += bytes_per_px

        # Update palette if it was changed
        if self.__palette_updated:
            self.__serialize_palette(output_bytes)

        # Add extra data at the end of file.
        # Only done before exporting to avoid converting from bytes to list multiple times
        self.__serialize_additional_data(output_bytes)

        # Write to file
        output_path = self.output_folder / (self.filename + self.bmp_suffix)
        with open(output_path, "wb") as file:
            file.write(bytes(output_bytes))

    def set_output_folder(self, folder_in):
        """Modifies output folder. Raises exception if it does not exist.

        :param folder_in: Desired output path
        """
        folder_path = Path(folder_in)
        if not folder_path.exists():
            raise OSError("Output folder %s does not exist" % folder_path)
        if not folder_path.is_dir():
            raise OSError("Output folder %s is not a valid directory" % folder_path)
        self.output_folder = folder_path

    @staticmethod
    def __csv_str_line_formatter(list_in, delimiter, decimal_sep):
        """Helper to format the strings to be written on the csv

        :param delimiter: Data row delimiter
        :param decimal_sep: Decimal separator
        :return: Formatted string
        """
        converted_list = [str(element) for element in list_in]
        return (delimiter.join(converted_list).replace(".", decimal_sep)) + '\n'

    def __read_int32(self, ini):
        """Gets a 32 signed bit variable stored as Little-Endian in the file bytes

        :param ini: First byte of the variable to extract
        :return: int32
        """
        int_return = self.file_bytes[ini] | (self.file_bytes[ini + 1] << 8) | (self.file_bytes[ini + 2] << 16) | (
                self.file_bytes[ini + 3] << 24)
        # Two's complement if the number is negative
        if int_return & 0x80000000:
            int_return = ~(int_return ^ 0xFFFFFFFF)
        return int_return

    def __read_int16(self, ini):
        """Gets a 16 signed bit variable stored as Little-Endian in the file bytes

        :param ini: First byte of the variable to extract
        :return: int16
        """
        int_return = self.file_bytes[ini] | (self.file_bytes[ini + 1] << 8)
        # Two's complement if the number is negative
        if int_return & 0x8000:
            int_return = ~(int_return ^ 0xFFFF)
        return int_return

    def __get_file_time_os(self, path_in):
        """Gets the modification time of the file. For a raw bmp this is also the image capture time.

        :param path_in: Libpath object to the file being loaded
        """
        self.img_datetime = datetime.fromtimestamp(path_in.stat().st_mtime)

    def __get_bmp_header(self):
        """Gets data from an standard bmp header into a class dictionary"""
        self.bmp_header['file_size'] = self.__read_int32(2)
        self.bmp_header['reserved_1'] = self.__read_int16(6)
        self.bmp_header['reserved_2'] = self.__read_int16(8)
        self.bmp_header['data_start_byte'] = self.__read_int32(10)
        self.bmp_header['bmp_header_size'] = self.__read_int32(14)
        self.bmp_header['img_width_px'] = self.__read_int32(18)
        self.bmp_header['img_height_px'] = self.__read_int32(22)
        self.bmp_header['plane_num'] = self.__read_int16(26)
        self.bmp_header['bits_per_px'] = self.__read_int16(28)
        self.bmp_header['compression'] = self.__read_int32(30)
        self.bmp_header['img_size'] = self.__read_int32(34)
        self.bmp_header['horizontal_res'] = self.__read_int32(38)
        self.bmp_header['vertical_res'] = self.__read_int32(42)
        self.bmp_header['color_table_size'] = self.__read_int32(46)
        self.bmp_header['important_colors'] = self.__read_int32(50)

    def __extract_grayscale_img(self):
        """Extracts the raw thermal image embedded after the .bmp data to a numpy array.
        The image depth is 1 byte per pixel. Used range [0, 254]

        :return: Last byte read. To use as offset for next extracts"""
        raw_image_size = self.bmp_header['img_width_px'] * self.bmp_header['img_height_px']
        byte_image_end = self.bmp_header['file_size'] + raw_image_size
        # Load the thermal image slice into a numpy array using frombuffer, as we read bytes. Then reshape to resolution
        self.raw_img_np = np.frombuffer(self.file_bytes[self.bmp_header['file_size']:byte_image_end], dtype=np.uint8)
        self.raw_img_np = self.raw_img_np.reshape((self.bmp_header['img_height_px'], self.bmp_header['img_width_px']))

        return byte_image_end

    def __extract_palette(self, byte_index_input):
        """Extracts the palette embedded in the .bmp data, after grayscale img, to a numpy array

        :param byte_index_input: Starting byte of the data segment
        :return: Last byte read. To use as offset for next extracts"""
        palette_size = 512
        bytes_per_color = 2
        self.palette_rgb_np = np.zeros((round(palette_size / bytes_per_color), 3), np.uint8)
        counter_palette = 0
        for i in range(byte_index_input, byte_index_input + palette_size, bytes_per_color):
            # Deserialize int16
            color_raw = self.__read_int16(i)
            # 5 bits red, 6 bits green, 5 bits blue
            color_r_raw = (color_raw & 0xF800) >> 11
            color_g_raw = (color_raw & 0x7E0) >> 5
            color_b_raw = (color_raw & 0x1F)
            # Convert 5/6 bits into 8 bit colors
            color_r = round(color_r_raw * 0xFF / 0x1F)
            color_g = round(color_g_raw * 0xFF / 0x3F)
            color_b = round(color_b_raw * 0xFF / 0x1F)

            self.palette_rgb_np[counter_palette] = (color_r, color_g, color_b)
            counter_palette += 1
        byte_offset = byte_index_input + palette_size
        return byte_offset

    def __extract_temp_data(self, byte_index_input):
        """Extracts the embedded temperature information in the .bmp data, after palette, to variables

        :param byte_index_input: Starting byte of the data segment
        :return: Last byte read. To use as offset for next extracts"""
        if self.file_bytes[byte_index_input] == 0:
            self.temp_units = 'C'
        else:
            self.temp_units = 'F'

        self.temp_max = self.__read_int16(byte_index_input + 1) / 10.0
        self.temp_min = self.__read_int16(byte_index_input + 3) / 10.0
        # Byte 5, unknown. Always 255
        # Byte 6, unknown. Always 0
        self.temp_center = self.__read_int16(byte_index_input + 7) / 10.0
        self.emissivity = self.file_bytes[byte_index_input + 9] / 100.0
        # Byte 10, unknown. Always 6
        # Byte 11, 12 & 13, unknown. Always 0
        self.temp_min_pos_w = self.__read_int16(byte_index_input + 14)
        self.temp_min_pos_h = self.__read_int16(byte_index_input + 16)
        self.temp_max_pos_w = self.__read_int16(byte_index_input + 18)
        self.temp_max_pos_h = self.__read_int16(byte_index_input + 20)
        self.temp_center_pos_w = self.__read_int16(byte_index_input + 22)
        self.temp_center_pos_h = self.__read_int16(byte_index_input + 24)

        byte_offset = byte_index_input + 26
        return byte_offset

    def __extract_file_time(self, byte_index_input):
        """Extracts the capture timestamp from the .bmp data (If existent)

        :param byte_index_input: Starting byte of the data segment
        """
        # Only existent if the bmp is generated from this script
        # If there is no more data in the file it means that it is raw from the thermal camera
        if byte_index_input != len(self.file_bytes):
            self.img_datetime = datetime.fromtimestamp(self.__read_int32(byte_index_input))

    def __serialize_palette(self, output_bytes):
        raw_image_size = self.bmp_header['img_width_px'] * self.bmp_header['img_height_px']
        bytes_offset = self.bmp_header['file_size'] + raw_image_size
        for color in self.palette_rgb_np:
            color_r = round(color[0] * 0x1F / 0xFF)  # Back to 5 bits
            color_g = round(color[1] * 0x3F / 0xFF)  # Back to 6 bits
            color_b = round(color[2] * 0x1F / 0xFF)  # Back to 5 bits
            color_raw = (color_r << 11 | color_g << 5 | color_b)  # Combine into 16 bit

            output_bytes[bytes_offset] = color_raw & 0x00FF
            output_bytes[bytes_offset+1] = (color_raw & 0xFF00) >> 8
            bytes_offset += 2

    def __serialize_additional_data(self, output_bytes):
        """Adds additional data to the end of the output bytes

        :param output_bytes: Reference to the list with the file bytes converted into list
        """
        self.__serialize_file_time(output_bytes)

    def __serialize_file_time(self, output_bytes):
        """Appends the timestamp of the capture at the end of the file bytes

        :param output_bytes: Reference to the list with the file bytes converted into list
        """
        timestamp = int(round(datetime.timestamp(self.img_datetime)))
        output_bytes.append(timestamp & 0xFF)
        output_bytes.append((timestamp >> 8) & 0xFF)
        output_bytes.append((timestamp >> 16) & 0xFF)
        output_bytes.append((timestamp >> 24) & 0xFF)

    def __set_rgb_image(self):
        """Applies palette to grayscale thermal image to generate a clean rgb version of the BMP image"""
        # As the raw images are integers between 0 and 255 we can use direct numpy indexing
        self.raw_img_rgb_np = self.palette_rgb_np[self.raw_img_np]
        if self.fix_img_np is not None:
            self.fix_img_rgb_np = self.palette_rgb_np[self.fix_img_np]

    def __set_raw_temp_matrix(self):
        """Calculates the temperature of each pixel in the raw thermal image. Linear interpolation between max and min temperatures """
        self.raw_temp_np = self.temp_min + (self.temp_max - self.temp_min) * (self.raw_img_np / 254.0)

    def __set_fix_temp_matrix(self):
        """Calculates the temperature of each pixel in the raw thermal image. Linear interpolation using center temperature"""
        # Uses a 3 point linear interpolation. Tmin to Tcenter and Tcenter to Tmax. Using this method some error is
        # reduced as more accurate data is used for the temperature extraction
        self.fix_temp_np = np.zeros(self.raw_img_np.shape)
        center_gray = self.raw_img_np[self.temp_center_pos_h, self.temp_center_pos_w]

        mask_high = (self.raw_img_np >= center_gray) & (self.raw_img_np != 254)
        self.fix_temp_np[mask_high] = \
            self.temp_center + (self.temp_max - self.temp_center) * ((self.raw_img_np[mask_high] - center_gray) / (254.0 - center_gray))
        mask_low = (self.raw_img_np < center_gray) & (self.raw_img_np != 0)
        self.fix_temp_np[mask_low] = \
            self.temp_min + (self.temp_center - self.temp_min) * (self.raw_img_np[mask_low] / center_gray)

        # Set min and max temperatures.
        # This fixes when center temperature has a brightness value equal to 254 or 0.
        self.fix_temp_np[self.raw_img_np == 0] = self.temp_min
        self.fix_temp_np[self.raw_img_np == 254] = self.temp_max

    def __set_fix_grayscale_image(self):
        """Calculates the grayscale thermal image with a linear scale using the fixed temperatures"""
        self.fix_img_np = np.round((self.fix_temp_np - self.temp_min)/(self.temp_max - self.temp_min) * 254, 0).astype(np.uint8)
        # Faster using truncation, but would give less precise results
        # self.fix_img_np = ((self.fix_temp_np - self.temp_min)/(self.temp_max - self.temp_min) * 254).astype(np.uint8)


class Palettes:
    """Class with standard palettes as numpy rgb arrays"""
    iron = np.array([[0,20,25],[0,16,33],[0,12,33],[0,8,41],[0,8,49],[0,8,58],[0,8,58],[0,8,58],[0,4,66],[0,4,74],[0,4,82],[0,0,82],[0,0,82],[8,0,90],[8,0,90],[8,0,99],[16,0,99],[16,0,99],[25,0,107],[25,0,107],[25,0,115],[33,0,123],[33,0,123],[41,0,123],[41,0,132],[41,0,132],[49,0,132],[49,0,140],[58,0,140],[58,0,140],[58,0,140],[66,0,148],[66,0,148],[66,0,148],[74,0,148],[74,0,148],[74,0,156],[82,0,156],[82,0,156],[82,0,156],[90,0,156],[90,0,156],[90,0,156],[99,0,156],[99,0,165],[107,0,165],[107,0,165],[107,0,165],[107,0,165],[115,0,165],[115,0,165],[115,0,173],[115,0,173],[123,0,173],[123,0,173],[123,0,173],[132,0,165],[132,0,173],[132,0,173],[140,0,173],[140,0,165],[140,0,165],[140,0,165],[140,0,173],[148,0,165],[148,0,165],[148,4,165],[156,4,165],[156,4,165],[165,4,165],[165,4,165],[165,4,165],[165,4,165],[165,8,165],[165,8,156],[173,12,156],[173,12,156],[173,12,156],[173,16,156],[181,16,156],[181,16,156],[181,16,156],[181,16,148],[181,16,148],[189,20,148],[189,20,140],[189,24,140],[189,24,140],[189,24,140],[197,28,140],[197,28,140],[197,28,132],[197,28,132],[206,32,132],[206,32,132],[206,32,132],[206,32,132],[206,32,123],[206,36,123],[206,40,123],[214,40,115],[214,40,115],[214,40,115],[214,45,115],[222,45,107],[222,45,107],[222,49,107],[222,49,107],[222,49,99],[222,53,99],[222,53,99],[222,57,99],[222,57,90],[230,61,90],[230,61,90],[230,61,90],[230,65,82],[230,65,82],[230,65,82],[230,69,74],[230,69,74],[239,73,74],[239,73,74],[239,77,66],[239,77,66],[239,81,66],[239,81,66],[239,81,58],[247,85,58],[247,85,58],[247,89,58],[247,89,58],[247,89,49],[247,93,49],[247,93,49],[247,97,41],[247,97,41],[247,101,41],[247,101,41],[255,101,33],[255,105,33],[255,105,33],[255,109,33],[255,109,33],[255,113,33],[255,113,25],[255,117,25],[255,117,25],[255,117,16],[255,121,16],[255,121,16],[255,125,16],[255,125,16],[255,130,16],[255,130,16],[255,130,8],[255,134,8],[255,138,8],[255,138,0],[255,138,0],[255,142,0],[255,142,0],[255,142,0],[255,146,0],[255,146,0],[255,146,0],[255,150,0],[255,150,0],[255,154,0],[255,154,0],[255,158,0],[255,158,0],[255,158,0],[255,162,0],[255,166,0],[255,166,0],[255,166,0],[255,170,0],[255,170,0],[255,170,0],[255,174,0],[255,174,0],[255,178,0],[255,178,0],[255,182,0],[255,182,0],[255,186,0],[255,186,0],[255,186,0],[255,190,0],[255,190,0],[255,190,0],[255,194,0],[255,194,0],[255,194,0],[255,198,0],[255,198,0],[255,202,0],[255,202,0],[255,202,0],[255,206,0],[255,206,8],[255,206,8],[255,210,8],[255,210,16],[255,210,16],[255,215,16],[255,215,16],[255,215,25],[255,219,25],[255,219,25],[255,223,33],[255,223,33],[255,223,33],[255,227,41],[255,227,41],[255,227,41],[255,227,49],[255,231,49],[255,231,58],[255,231,58],[255,235,66],[255,235,66],[255,235,66],[255,239,74],[255,239,74],[255,239,82],[255,239,82],[255,239,90],[255,243,90],[255,243,99],[255,243,99],[255,243,107],[255,247,115],[255,247,123],[255,247,123],[255,247,132],[255,247,140],[255,251,140],[255,251,148],[255,251,156],[255,251,165],[255,255,165],[255,255,173],[255,255,181],[247,255,189],[247,255,197],[247,255,206],[247,255,206],[247,255,214],[247,255,222],[247,255,230],[247,255,239],[247,255,247],[247,255,247],[247,255,247]])
    rainbow = np.array([[0,8,33],[0,4,41],[0,4,58],[0,4,66],[0,0,66],[0,4,66],[0,4,66],[0,4,66],[0,4,66],[0,4,74],[0,8,82],[0,12,82],[0,12,82],[0,16,82],[0,20,90],[0,20,90],[0,32,99],[0,36,99],[0,36,107],[0,36,107],[0,40,107],[0,45,115],[0,49,115],[0,53,123],[0,57,123],[0,57,132],[0,61,132],[0,61,132],[0,61,132],[0,61,132],[0,61,140],[0,65,148],[0,65,148],[0,69,148],[0,69,156],[0,69,156],[0,73,156],[0,73,165],[0,73,165],[0,77,173],[0,77,173],[0,77,173],[0,81,181],[0,81,181],[0,81,181],[0,81,181],[0,81,181],[0,81,181],[0,81,189],[0,81,189],[0,81,189],[0,81,197],[0,85,197],[0,89,206],[0,89,206],[0,89,206],[0,93,214],[0,89,214],[0,93,214],[0,97,214],[0,97,214],[0,101,214],[0,101,214],[0,105,222],[0,105,214],[0,105,222],[0,109,222],[0,113,222],[8,117,222],[0,117,222],[0,117,214],[0,121,214],[0,121,214],[0,125,206],[0,125,197],[0,125,197],[0,130,189],[0,130,181],[8,134,181],[8,138,173],[8,138,165],[8,138,165],[16,142,156],[16,142,148],[16,146,140],[25,150,132],[25,150,123],[25,154,115],[33,154,107],[41,162,107],[49,166,107],[49,166,90],[58,170,82],[66,170,74],[74,170,66],[74,170,58],[90,178,58],[99,182,49],[99,178,41],[107,182,33],[115,182,33],[123,186,33],[123,194,25],[132,194,25],[140,194,25],[148,194,25],[156,198,25],[165,198,25],[165,194,16],[165,194,16],[173,198,25],[173,198,25],[181,202,16],[189,210,25],[189,210,16],[197,210,16],[197,210,16],[206,210,16],[206,210,16],[214,215,16],[214,210,25],[222,210,25],[222,210,25],[230,210,25],[230,210,25],[230,215,25],[230,210,25],[239,210,25],[239,210,25],[239,210,25],[239,210,25],[239,210,25],[239,206,25],[239,202,25],[239,202,25],[247,202,25],[247,198,25],[247,198,25],[247,198,25],[255,194,25],[255,194,33],[255,190,33],[255,190,41],[255,186,33],[255,182,41],[255,182,41],[255,182,41],[255,182,41],[255,178,41],[255,178,41],[255,178,41],[255,178,41],[255,174,41],[255,166,41],[255,162,41],[255,154,41],[255,150,41],[255,150,41],[255,146,41],[255,142,41],[255,142,49],[255,138,49],[247,125,41],[247,121,41],[255,117,41],[255,113,41],[255,109,49],[255,97,49],[255,93,49],[255,85,49],[247,77,49],[255,73,49],[247,69,49],[247,65,49],[247,61,49],[247,53,49],[247,49,58],[247,45,58],[247,40,58],[247,36,58],[239,32,66],[239,32,66],[239,32,66],[239,32,74],[247,28,74],[247,28,74],[247,32,74],[239,36,74],[239,36,82],[239,36,74],[239,36,82],[239,40,82],[239,45,82],[239,49,90],[239,53,90],[239,57,90],[239,57,90],[239,65,99],[247,69,99],[247,73,99],[247,81,107],[255,89,115],[255,93,115],[255,97,115],[255,101,115],[255,105,115],[247,105,115],[247,109,115],[247,109,115],[247,117,123],[247,121,123],[247,125,132],[247,130,132],[247,134,132],[247,138,140],[255,142,140],[247,138,140],[247,142,140],[255,146,140],[255,150,148],[255,154,148],[255,158,148],[255,162,156],[255,166,156],[255,170,156],[255,170,156],[247,170,156],[247,170,156],[247,174,165],[247,178,165],[247,182,165],[247,182,165],[247,186,173],[247,190,173],[255,194,181],[255,202,181],[255,202,189],[255,202,189],[255,202,189],[247,206,189],[255,210,197],[255,215,197],[255,219,197],[255,219,197],[255,219,206],[255,223,206],[255,223,214],[255,223,214],[255,223,214],[255,223,214],[255,227,214],[255,227,214],[247,227,214],[247,227,222],[247,227,222],[247,235,230]])
    white_hot = np.array([[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,4,0],[0,4,0],[0,4,0],[0,4,0],[8,8,8],[8,8,8],[8,8,8],[8,8,8],[8,12,8],[8,12,8],[8,12,8],[8,12,8],[16,16,16],[16,16,16],[16,16,16],[16,16,16],[16,20,16],[16,20,16],[16,20,16],[16,20,16],[16,24,16],[25,24,25],[25,24,25],[25,24,25],[25,28,25],[25,28,25],[25,28,25],[25,28,25],[25,32,25],[33,32,33],[33,32,33],[33,32,33],[33,36,33],[33,36,33],[33,36,33],[33,36,33],[33,40,33],[33,40,33],[41,40,41],[41,40,41],[41,45,41],[41,45,41],[41,45,41],[41,45,41],[41,49,41],[41,49,41],[49,49,49],[49,49,49],[49,53,49],[49,53,49],[49,53,49],[49,53,49],[49,57,49],[49,57,49],[49,57,49],[58,57,58],[58,61,58],[58,61,58],[58,61,58],[58,61,58],[58,65,58],[58,65,58],[58,65,58],[66,65,66],[66,69,66],[66,69,66],[66,69,66],[66,69,66],[66,73,66],[66,73,66],[66,73,66],[66,73,66],[74,77,74],[74,77,74],[74,77,74],[74,77,74],[74,81,74],[74,81,74],[74,81,74],[74,81,74],[82,85,82],[82,85,82],[82,85,82],[82,85,82],[82,85,82],[82,89,82],[82,89,82],[82,89,82],[82,89,82],[90,93,90],[90,93,90],[90,93,90],[90,93,90],[90,97,90],[90,97,90],[90,97,90],[90,97,90],[99,101,99],[99,101,99],[99,101,99],[99,101,99],[99,105,99],[99,105,99],[99,105,99],[99,105,99],[107,109,107],[107,109,107],[107,109,107],[107,109,107],[107,113,107],[107,113,107],[107,113,107],[107,113,107],[115,117,115],[115,117,115],[115,117,115],[115,117,115],[115,121,115],[115,121,115],[115,121,115],[115,121,115],[123,125,123],[123,125,123],[123,125,123],[123,125,123],[123,130,123],[123,130,123],[123,130,123],[123,130,123],[132,134,132],[132,134,132],[132,134,132],[132,134,132],[132,138,132],[132,138,132],[132,138,132],[132,138,132],[140,142,140],[140,142,140],[140,142,140],[140,142,140],[140,146,140],[140,146,140],[140,146,140],[140,146,140],[148,150,148],[148,150,148],[148,150,148],[148,150,148],[148,154,148],[148,154,148],[148,154,148],[148,154,148],[156,158,156],[156,158,156],[156,158,156],[156,158,156],[156,162,156],[156,162,156],[156,162,156],[156,162,156],[165,166,165],[165,166,165],[165,166,165],[165,166,165],[165,170,165],[165,170,165],[165,170,165],[165,170,165],[165,170,165],[173,174,173],[173,174,173],[173,174,173],[173,174,173],[173,178,173],[173,178,173],[173,178,173],[173,178,173],[181,182,181],[181,182,181],[181,182,181],[181,182,181],[181,186,181],[181,186,181],[181,186,181],[181,186,181],[189,190,189],[189,190,189],[189,190,189],[189,190,189],[189,194,189],[189,194,189],[189,194,189],[189,194,189],[197,198,197],[197,198,197],[197,198,197],[197,198,197],[197,202,197],[197,202,197],[197,202,197],[197,202,197],[206,206,206],[206,206,206],[206,206,206],[206,206,206],[206,210,206],[206,210,206],[206,210,206],[206,210,206],[214,215,214],[214,215,214],[214,215,214],[214,215,214],[214,219,214],[214,219,214],[214,219,214],[214,219,214],[222,223,222],[222,223,222],[222,223,222],[222,223,222],[222,227,222],[222,227,222],[222,227,222],[222,227,222],[230,231,230],[230,231,230],[230,231,230],[230,231,230],[230,235,230],[230,235,230],[230,235,230],[230,235,230],[239,239,239],[239,239,239],[239,239,239],[239,239,239],[239,243,239],[239,243,239],[239,243,239],[239,243,239],[247,247,247],[247,247,247],[247,247,247],[247,247,247],[247,251,247],[247,251,247],[247,251,247],[247,251,247]])
    red_hot = np.array([[66,61,58],[66,61,58],[66,61,58],[66,61,58],[66,65,66],[66,65,66],[66,65,66],[66,69,66],[74,69,66],[74,69,66],[74,73,74],[74,73,74],[74,73,74],[82,77,74],[82,77,82],[82,77,82],[82,81,82],[82,81,82],[90,85,82],[90,85,90],[90,89,90],[90,89,90],[90,89,90],[99,93,99],[99,93,99],[99,97,99],[99,97,107],[107,101,107],[107,101,107],[107,105,107],[107,105,115],[107,109,115],[115,109,115],[115,113,123],[115,113,123],[123,117,123],[123,117,123],[123,121,132],[123,121,132],[132,125,132],[132,125,140],[132,130,140],[132,134,140],[140,134,148],[140,138,148],[140,138,148],[140,142,156],[148,142,156],[148,146,156],[148,146,156],[156,150,165],[156,150,165],[156,154,165],[156,158,173],[165,158,173],[165,162,173],[165,162,173],[165,162,181],[165,166,181],[173,166,181],[173,170,181],[173,170,189],[173,170,189],[173,174,189],[181,174,189],[181,178,197],[181,178,197],[181,182,197],[181,182,197],[189,182,197],[189,186,206],[189,186,206],[189,190,206],[189,190,206],[197,190,206],[197,194,214],[197,194,214],[197,198,214],[197,198,214],[206,198,214],[206,202,222],[206,202,222],[206,206,222],[206,206,222],[214,206,222],[214,210,230],[214,210,230],[214,210,230],[214,215,230],[214,215,230],[222,215,230],[222,219,239],[222,219,239],[222,223,239],[222,223,239],[222,223,239],[230,227,239],[230,227,239],[230,227,247],[230,231,247],[230,231,247],[230,231,247],[239,231,247],[239,235,247],[239,235,247],[239,235,247],[239,239,255],[239,239,255],[239,239,255],[247,239,255],[247,243,255],[247,243,255],[247,243,255],[247,247,255],[247,247,255],[247,247,255],[247,247,255],[255,247,255],[255,251,255],[255,251,255],[255,251,255],[255,251,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,255],[255,255,247],[255,255,247],[255,255,247],[255,255,247],[255,255,247],[255,255,239],[255,255,239],[255,255,239],[255,255,230],[255,255,230],[255,255,230],[255,255,222],[255,255,222],[255,255,214],[255,255,214],[255,255,214],[255,255,206],[255,255,206],[255,255,197],[255,255,197],[255,255,189],[255,255,189],[255,255,181],[255,255,181],[255,255,173],[255,255,173],[255,255,165],[255,255,165],[255,255,156],[255,255,156],[255,255,148],[255,255,140],[255,255,140],[255,255,132],[255,255,123],[255,255,123],[255,255,115],[255,255,107],[255,255,107],[255,255,99],[247,255,90],[247,255,90],[247,255,82],[247,255,74],[247,255,74],[247,255,66],[247,255,58],[247,255,58],[247,255,49],[247,255,49],[239,255,41],[239,255,41],[239,255,33],[239,255,33],[239,251,33],[239,251,25],[239,247,25],[239,247,25],[239,243,25],[239,243,16],[239,239,16],[239,239,16],[239,235,16],[239,231,16],[239,231,8],[239,227,8],[239,223,8],[239,219,8],[239,215,8],[239,215,8],[239,210,8],[239,206,0],[239,202,0],[239,198,0],[239,194,0],[239,190,0],[239,186,0],[239,182,0],[239,178,0],[247,174,0],[247,170,0],[247,166,0],[247,162,0],[247,158,0],[247,154,0],[247,150,0],[247,142,0],[247,138,0],[247,134,0],[247,130,0],[247,125,0],[247,121,0],[247,117,0],[247,109,0],[247,105,0],[247,101,0],[247,93,0],[247,89,0],[247,85,0],[247,81,0],[247,73,0],[247,69,0],[247,65,0],[247,61,0],[247,57,0],[247,49,0],[247,45,0],[255,40,0],[255,36,0],[255,32,0],[255,28,0],[255,24,0],[255,24,0],[255,20,0],[255,16,0],[255,12,0],[255,8,0],[255,8,0],[255,4,0],[255,4,0],[255,0,0]])
    lava = np.array([[0,0,0],[0,0,0],[0,4,8],[0,8,16],[0,8,25],[0,12,33],[8,16,41],[8,20,49],[8,24,58],[8,28,66],[16,28,74],[16,32,82],[16,36,90],[16,36,99],[16,40,107],[16,45,115],[25,49,123],[25,53,123],[25,53,132],[25,57,140],[25,61,148],[25,65,156],[33,69,156],[33,69,156],[25,69,165],[25,69,165],[25,73,165],[25,73,156],[25,77,156],[25,77,156],[25,77,156],[25,77,156],[25,81,156],[25,81,156],[25,81,156],[25,85,156],[16,85,156],[16,85,156],[16,89,156],[16,89,156],[16,89,156],[16,89,156],[16,93,156],[16,93,156],[16,97,156],[16,97,156],[8,97,156],[8,97,156],[8,101,156],[8,101,156],[8,105,148],[8,105,148],[8,105,156],[8,105,156],[8,109,148],[8,109,148],[8,113,148],[0,113,148],[0,113,148],[0,113,148],[0,117,148],[0,117,148],[0,117,148],[0,117,148],[0,121,148],[0,121,148],[0,125,148],[0,125,148],[0,125,148],[0,125,148],[0,130,148],[0,130,148],[0,130,140],[0,130,140],[0,130,140],[0,134,140],[0,134,140],[0,134,140],[0,134,140],[0,134,140],[0,138,140],[0,138,140],[0,138,140],[0,138,140],[0,138,140],[0,138,140],[0,138,132],[0,134,132],[8,130,132],[16,125,132],[25,121,132],[33,117,132],[33,113,132],[41,109,132],[49,105,132],[49,101,132],[58,97,132],[58,93,123],[66,85,123],[74,81,123],[82,77,123],[82,73,123],[90,69,123],[99,65,123],[99,61,123],[107,57,123],[115,53,123],[115,49,123],[123,45,115],[123,45,115],[123,45,115],[123,45,115],[132,45,115],[132,45,107],[132,45,107],[132,45,107],[140,40,99],[140,40,99],[140,40,99],[148,40,99],[148,40,99],[148,36,99],[148,36,90],[156,36,90],[156,36,90],[156,36,82],[156,36,82],[156,36,82],[165,32,82],[165,32,82],[165,32,74],[173,32,74],[173,32,74],[173,32,66],[173,28,66],[181,28,66],[181,28,66],[181,28,66],[181,28,58],[181,28,58],[189,28,58],[189,24,49],[189,24,49],[197,24,49],[197,24,49],[197,24,49],[197,20,41],[197,20,41],[206,20,41],[206,20,33],[206,20,33],[214,20,33],[214,24,33],[214,24,33],[214,28,33],[214,28,33],[222,32,33],[222,32,33],[222,32,33],[230,36,33],[230,36,33],[230,36,33],[239,40,33],[239,40,33],[239,40,33],[239,45,33],[247,45,33],[247,49,33],[247,49,33],[255,53,33],[255,53,33],[255,57,33],[255,57,33],[255,57,33],[255,61,33],[255,61,25],[255,65,25],[255,65,25],[255,69,25],[255,69,16],[255,73,16],[255,73,16],[255,77,16],[255,81,16],[255,81,16],[255,85,8],[255,85,8],[255,89,8],[255,93,8],[255,93,8],[255,97,8],[255,97,0],[255,97,0],[255,101,0],[255,105,0],[255,105,0],[255,109,0],[255,109,0],[255,113,0],[255,117,0],[255,117,0],[255,125,0],[255,125,0],[255,134,0],[255,134,0],[255,142,0],[255,142,0],[255,146,0],[255,150,0],[255,154,0],[255,158,0],[255,158,0],[255,162,0],[255,166,0],[255,166,0],[255,170,0],[255,174,0],[255,174,0],[255,178,0],[255,182,0],[255,186,0],[255,186,0],[255,190,0],[255,194,0],[255,194,0],[255,198,0],[255,198,0],[255,202,0],[255,202,0],[255,206,0],[255,210,0],[255,210,0],[255,210,0],[255,215,0],[255,215,0],[255,219,8],[255,223,25],[255,223,33],[255,223,49],[255,227,66],[255,227,74],[255,231,82],[255,231,99],[255,235,115],[255,235,123],[255,239,132],[255,239,148],[255,243,156],[255,243,173],[255,247,181],[255,247,197],[255,247,206],[255,251,222],[255,255,230],[255,255,247],[255,255,255]])
    rainbow_hc = np.array([[0,0,0],[0,0,0],[0,0,0],[8,0,8],[8,0,8],[8,0,16],[16,0,16],[25,0,25],[33,0,25],[33,0,33],[41,0,33],[41,0,41],[49,0,49],[49,0,49],[58,0,58],[66,0,66],[74,0,74],[74,0,74],[82,0,82],[90,0,82],[90,0,90],[99,0,90],[107,0,99],[107,0,107],[107,0,107],[115,0,115],[123,0,123],[132,0,132],[140,0,140],[140,0,140],[148,0,148],[156,0,156],[165,0,156],[165,0,165],[173,0,173],[173,0,173],[181,0,181],[181,0,181],[189,0,189],[197,0,197],[206,0,206],[206,0,206],[214,0,214],[214,0,214],[222,0,222],[222,0,222],[230,0,230],[230,0,230],[222,0,230],[222,0,230],[222,0,230],[214,0,230],[214,0,230],[206,0,222],[206,0,222],[197,0,222],[197,0,222],[189,0,222],[181,0,214],[181,0,214],[181,0,214],[173,0,214],[173,0,214],[165,0,206],[156,0,206],[156,0,206],[148,0,206],[148,0,206],[140,0,206],[140,0,197],[140,0,197],[132,0,197],[123,0,197],[123,0,197],[115,0,189],[107,0,189],[99,0,189],[99,0,189],[90,0,189],[90,0,181],[82,0,181],[74,0,181],[66,0,173],[58,0,173],[58,0,173],[49,0,173],[41,0,165],[33,0,165],[25,0,165],[8,0,156],[0,0,156],[0,4,156],[0,8,156],[0,24,165],[0,32,165],[0,49,173],[0,65,181],[0,77,181],[0,93,189],[0,97,189],[0,109,189],[0,121,189],[0,138,197],[0,154,206],[0,162,206],[0,178,214],[0,186,214],[0,198,222],[0,202,222],[0,215,222],[0,227,230],[0,223,222],[0,219,214],[0,206,197],[0,202,189],[0,198,181],[0,194,173],[0,190,173],[0,186,165],[0,178,156],[0,170,140],[0,166,132],[0,162,132],[0,158,123],[0,154,115],[0,154,107],[0,146,99],[0,142,90],[0,130,74],[0,130,74],[0,125,74],[0,121,66],[0,117,58],[0,113,49],[0,105,41],[0,101,33],[0,101,33],[0,97,25],[0,93,16],[0,89,16],[0,81,0],[0,77,0],[8,85,0],[16,89,0],[25,101,0],[33,101,0],[33,101,0],[41,105,0],[49,113,0],[58,117,0],[58,121,0],[66,125,0],[82,130,0],[90,138,0],[99,146,0],[107,146,0],[107,150,0],[123,158,0],[123,162,0],[132,170,0],[140,174,0],[156,186,0],[165,186,0],[173,190,0],[181,194,0],[189,206,0],[197,210,0],[206,215,0],[214,223,0],[222,227,0],[230,227,0],[230,223,0],[222,210,0],[214,198,0],[206,182,0],[206,174,0],[197,158,0],[189,150,0],[189,150,0],[189,138,0],[181,125,0],[181,117,0],[173,105,0],[165,97,0],[165,89,0],[156,77,0],[148,65,0],[156,65,0],[148,49,0],[140,36,0],[132,24,0],[123,16,0],[123,4,0],[123,0,0],[123,0,0],[132,0,0],[132,4,0],[140,4,0],[140,8,8],[148,12,8],[148,12,8],[156,16,16],[156,16,16],[165,20,16],[165,20,16],[173,20,25],[173,24,25],[181,28,25],[181,28,25],[189,32,33],[189,32,33],[197,32,33],[197,36,33],[197,36,41],[206,36,41],[206,40,41],[214,45,41],[214,45,41],[222,49,49],[222,53,49],[222,61,58],[222,65,66],[222,73,74],[222,81,82],[222,89,90],[230,101,99],[230,101,107],[230,109,107],[230,113,115],[230,121,123],[230,130,132],[239,138,140],[239,142,148],[239,146,148],[239,154,156],[239,158,156],[239,166,165],[239,174,173],[239,178,181],[247,186,189],[247,186,189],[247,194,189],[247,194,197],[247,202,197],[247,206,206],[247,210,206],[247,215,214],[247,219,222],[247,219,222],[247,227,230],[255,231,230],[255,235,239],[255,235,239],[255,243,247],[255,243,247],[255,247,247]])
    # black_hot = white_hot reversed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extracts thermal data from UNI-T thermal camera images")
    parser.add_argument("-i", "--input", type=str, help="Input .bmp image", required=True)
    parser.add_argument("-o", "--output", type=str, default="", help="Desired output folder", required=False)
    parser.add_argument("-bmp", "--exportbmp", action="store_true", required=False,
                        help="Exports a clean thermal image from the input one")
    parser.add_argument("-csv", "--exportcsv", required=False, choices=['en', 'es', 'img'],
                        help="Exports the thermal data to a csv file. Options: en - default csv, es - semicolon delimited "
                             "csv, img - only image data to a tab-delimited csv. Allows import in ThermImageJ")
    parser.add_argument("-p", "--palette", action="append", required=False,
                        help="Sets palette. Multiple. Options: iron, rainbow, white_hot, red_hot, lava, rainbow_hc, reverse")
    parser.add_argument("-th", "--temphigh", type=float, required=False,
                        help="Sets the maximum on the temperature range")
    parser.add_argument("-tl", "--templow", type=float, required=False,
                        help="Sets the minimum on the temperature range")
    parser.add_argument("-nf", "--nofix", action="store_false", required=False,
                        help="Processes data without temperature fix. Check temperature_issue.md for more info")

    args = parser.parse_args()

    # - Extract thermal data -
    obj_uti = UniTThermalImage(use_fix=args.nofix)
    obj_uti.init_from_image(args.input)
    if obj_uti.flag_initialized:
        # - Set palette -
        if args.palette:
            for key in args.palette:
                if key == "reverse":
                    obj_uti.set_palette(reverse=True)
                else:
                    palette_np = {'iron': Palettes.iron, 'rainbow': Palettes.rainbow, 'white_hot': Palettes.white_hot, 
                                  'red_hot': Palettes.red_hot, 'lava': Palettes.lava, 'rainbow_hc': Palettes.rainbow_hc}.get(key, None)                 
                    if palette_np is not None:
                        obj_uti.set_palette(palette_in_np=palette_np)
                    else:
                        raise ValueError("Palette not found")

        # - Set range -
        if args.temphigh or args.templow:
            # Get current range and overwrite only if specified in args
            t_min = obj_uti.temp_min
            t_max = obj_uti.temp_max
            if args.temphigh:
                t_max = args.temphigh
            if args.templow:
                t_min = args.templow
            obj_uti.set_temp_range(t_min, t_max)

        # - Export -
        if args.output:
            obj_uti.set_output_folder(args.output)

        if args.exportbmp:
            obj_uti.export_bmp()

        if args.exportcsv:
            if args.exportcsv == 'es':
                obj_uti.export_csv(delimiter=';', decimal_sep=',')
            elif args.exportcsv == 'img':
                obj_uti.export_csv(only_img=True, delimiter='\t')
            else:
                obj_uti.export_csv()

    else:
        raise RuntimeError("Error extracting data from image")
