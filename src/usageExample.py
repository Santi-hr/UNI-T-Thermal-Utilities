import matplotlib.pyplot as plt
from src import uniTThermalImage

print("UNI T Thermal Image Extractor Demo")

# -- Load image --
filename = "../examples/samples/IMG_Typical.bmp"
obj_uti = uniTThermalImage.UniTThermalImage()
obj_uti.init_from_image(filename)

# -- Print temperature data --
print("Min temp: %f º%c" % (obj_uti.temp_min, obj_uti.temp_units))
print("Max temp: %f º%c" % (obj_uti.temp_max, obj_uti.temp_units))

# -- Get temperature of a point --
point = (100, 100)
print("Temp in", point, ":", obj_uti.temp_array_np[point], obj_uti.temp_units)

# -- Plot clean image --
plt.imshow(obj_uti.raw_img_rgb_np)
plt.show()

# -- Palette adjustment examples --
fig, axs = plt.subplots(2, 2)
axs[0, 0].imshow(obj_uti.raw_img_rgb_np)
axs[0, 0].set_title('Original image')
axs[0, 0].axis('off')

obj_uti.set_palette(reverse=True)
axs[0, 1].imshow(obj_uti.raw_img_rgb_np)
axs[0, 1].set_title('Reversed palette')
axs[0, 1].axis('off')

obj_uti.set_palette(uniTThermalImage.Palettes.rainbow_hc)
axs[1, 0].imshow(obj_uti.raw_img_rgb_np)
axs[1, 0].set_title('Predefined palette')
axs[1, 0].axis('off')

# Custom palette. Basic Hi/Lo regions highlight
np_custom_palette = uniTThermalImage.Palettes.white_hot
for i in range(0, 15):
    np_custom_palette[i] = [0, 0, 255]
    if i > 0:
        np_custom_palette[-i] = [255, 0, 0]
obj_uti.set_palette(np_custom_palette)
axs[1, 1].imshow(obj_uti.raw_img_rgb_np)
axs[1, 1].set_title('Custom palette')
axs[1, 1].axis('off')
plt.show()
