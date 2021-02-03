import numpy as np
import argparse
from pathlib import Path
from datetime import datetime


class UniTThermalImage:
    """Class to handle UNI-T thermal camera images. Tested with UTi260B"""

    def __init__(self):
        # User configurable data
        self.bmp_suffix = "_thermal_rgb.bmp"
        self.csv_suffix = ".csv"
        self.output_folder = Path("")

        # Class variables
        self.flag_initialized = False
        self.filename = ""  # Name of the file
        self.file_bytes = []  # Bytes of the loaded .bmp

        self.bmp_header = {}  # Bmp header of the loaded image

        self.raw_img_np = None      # Numpy array [W,L] with the raw thermal image
        self.raw_img_rgb_np = None  # Numpy array [W,L,3] with the rgb thermal image (colorbar applied to raw)
        self.colorbar_rgb_np = None # Numpy array [CbL,3] with the rgb values of the colorbar
        self.temp_array_np = None   # Numpy array [W,L] with the thermal values for each pixel

        self.temp_units = 'N'       # Temperature units, Celsius (C) or Fahrenheit (F)
        self.temp_max = 0           # Maximum temperature on the frame
        self.temp_min = 0           # Minimum temperature on the frame
        self.temp_center = 0        # Center temperature on the frame
        self.emissivity = 0         # Configured emissivity
        self.temp_min_pos_w = 0     # Pixel pos in width axis of the minimum temperature
        self.temp_min_pos_h = 0     # Pixel pos in height axis of the minimum temperature
        self.temp_max_pos_w = 0     # Pixel pos in width axis of the maximum temperature
        self.temp_max_pos_h = 0     # Pixel pos in height axis of the maximum temperature
        self.temp_center_pos_w = 0  # Pixel pos in width axis of the center temperature
        self.temp_center_pos_h = 0  # Pixel pos in height axis of the center temperature

        self.img_datetime = None  # Datetime object with the date and time of image capture

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

        # Get colorbar after grayscale image
        byte_offset = self.__extract_colorbar(byte_offset)

        # Get embedded temperature after colorbar
        byte_offset = self.__extract_temp_data(byte_offset)

        # Get embedded timestamp after embedded data
        self.__extract_file_time(byte_offset)

        # Set internal variables using the loaded data
        self.__set_rgb_image()
        self.__set_temp_matrix()

        self.flag_initialized = True

    def export_csv(self, only_img=False, delimiter=',', decimal_sep='.'):
        """Exports data to a csv file

        :param only_img: True to skip header data and only save temperature data.
        :param delimiter: Data row delimiter
        :param decimal_sep: Decimal separator
        """
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
            for idx_h in range(len(self.temp_array_np)):
                temp_list = []
                for idx_w in range(len(self.temp_array_np[idx_h])):
                    temp_list.append(self.temp_array_np[idx_h, idx_w])
                file.write(self.__csv_str_line_formatter(temp_list, delimiter, decimal_sep))

    def export_bmp(self):
        """Exports a version of the input image without its overlay. It keeps the embedded data"""
        # Fixme: Check if rows needs padding for other resolutions. Now set for the UTi260B which does not require them
        output_bytes = list(self.file_bytes)
        bytes_offset = self.bmp_header['data_start_byte']
        bytes_per_px = round(self.bmp_header['bits_per_px']/8)
        for idx_h in range(self.bmp_header['img_height_px']-1, 0, -1):  # In bmp files the rows are stored from the last
            for idx_w in range(self.bmp_header['img_width_px']):
                # 24 bit bmp files are BGR
                output_bytes[bytes_offset] = self.raw_img_rgb_np[idx_h, idx_w, 2]
                output_bytes[bytes_offset + 1] = self.raw_img_rgb_np[idx_h, idx_w, 1]
                output_bytes[bytes_offset + 2] = self.raw_img_rgb_np[idx_h, idx_w, 0]
                bytes_offset += bytes_per_px

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
            raise OSError("Output folder %s is not a valid directoy" % folder_path)
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
        The image depth is 1 byte per pixel [0, 254]

        :return: Last byte read. To use as offset for next extracts"""
        raw_image_size = self.bmp_header['img_width_px'] * self.bmp_header['img_height_px']
        byte_image_end = self.bmp_header['file_size'] + raw_image_size
        # Load the thermal image slice into a numpy array using frombuffer, as we read bytes. Then reshape to resolution
        self.raw_img_np = np.frombuffer(self.file_bytes[self.bmp_header['file_size']:byte_image_end], dtype=np.uint8)
        self.raw_img_np = self.raw_img_np.reshape((self.bmp_header['img_height_px'], self.bmp_header['img_width_px']))

        return byte_image_end

    def __extract_colorbar(self, byte_index_input):
        """Extracts the colorbar embedded in the .bmp data, after grayscale img, to a numpy array

        :param byte_index_input: Starting byte of the data segment
        :return: Last byte read. To use as offset for next extracts"""
        colorbar_size = 512
        bytes_per_color = 2
        self.colorbar_rgb_np = np.zeros((round(colorbar_size / bytes_per_color), 3), np.uint8)
        counter_colorbar = 0
        for i in range(byte_index_input, byte_index_input + colorbar_size, bytes_per_color):
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

            self.colorbar_rgb_np[counter_colorbar] = (color_r, color_g, color_b)
            counter_colorbar += 1
        byte_offset = byte_index_input + colorbar_size
        return byte_offset

    def __extract_temp_data(self, byte_index_input):
        """Extracts the embedded temperature information in the .bmp data, after colorbar, to variables

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
        """Extracts the capture timestamp from the .bmp data (If existant)

        :param byte_index_input: Starting byte of the data segment
        """
        # Only existent if the bmp is generated from this script
        # If there is no more data in the file it means that it is raw from the thermal camera
        if byte_index_input != len(self.file_bytes):
            self.img_datetime = datetime.fromtimestamp(self.__read_int32(byte_index_input))

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
        """Applies colorbar to raw thermal image to generate a clean rgb version of the BMP image"""
        # As the raw images are integers between 0 and 255 we can use direct numpy indexing
        self.raw_img_rgb_np = self.colorbar_rgb_np[self.raw_img_np]

    def __set_temp_matrix(self):
        """Calculates the temperature of each pixel in the raw thermal image"""
        self.temp_array_np = self.temp_min + (self.temp_max - self.temp_min) * (self.raw_img_np / 254.0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extracts thermal data from UNI-T thermal camera images")
    parser.add_argument("-i", "--input", type=str, help="Input .bmp image", required=True)
    parser.add_argument("-o", "--output", type=str, default="", help="Desired output folder", required=False)
    parser.add_argument("-bmp", "--exportbmp", action="store_true",
                        help="Exports a clean thermal image from the input one", required=False)
    parser.add_argument("-csv", "--exportcsv", action="store_true",
                        help="Exports the thermal data to a csv file", required=False)
    parser.add_argument("-csv_es", "--exportcsv_es", action="store_true",
                        help="Exports the thermal data to a csv file, using ; instead of ,", required=False)
    parser.add_argument("-csv_img", "--exportcsv_img", action="store_true",
                        help="Exports the thermal image data to a tab-delimited csv file. Allows import in ThermImageJ", required=False)

    args = parser.parse_args()

    # Extract thermal data
    obj_img = UniTThermalImage()
    obj_img.init_from_image(args.input)
    if obj_img.flag_initialized:
        if args.output:
            obj_img.set_output_folder(args.output)

        if args.exportbmp:
            obj_img.export_bmp()

        if args.exportcsv:
            obj_img.export_csv()
        if args.exportcsv_es:
            obj_img.export_csv(delimiter=';', decimal_sep=',')
        if args.exportcsv_img:
            obj_img.export_csv(only_img=True, delimiter='\t')


    else:
        raise RuntimeError("Error extracting data from image")
