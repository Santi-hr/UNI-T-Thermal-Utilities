import matplotlib.pyplot as plt
from src import uniTThermalImage

print("UNI T Thermal Image Extractor Demo")

# Load image
filename = "../examples/samples/IMG_Typical.bmp"
obj_uti = uniTThermalImage.UniTThermalImage()
obj_uti.init_from_image(filename)

# Print temperature data
print("Min temp: %f º%c" % (obj_uti.temp_min, obj_uti.temp_units))
print("Max temp: %f º%c" % (obj_uti.temp_max, obj_uti.temp_units))

# Get temperature of a point
point = (100, 100)
print("Temp in", point, ":", obj_uti.temp_array_np[point], obj_uti.temp_units)

# Plot clean image
plt.imshow(obj_uti.raw_img_rgb_np)
plt.show()
