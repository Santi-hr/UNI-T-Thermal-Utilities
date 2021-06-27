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
print("Center temp: %f º%c" % (obj_uti.temp_center, obj_uti.temp_units))

# -- Get temperature of a point --
point = (100, 100)
print("Temp in", point, ":", obj_uti.raw_temp_np[point], obj_uti.temp_units)

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
    np_custom_palette[-i] = [255, 0, 0]
    np_custom_palette[i] = [0, 0, 255]
obj_uti.set_palette(np_custom_palette)
axs[1, 1].imshow(obj_uti.raw_img_rgb_np)
axs[1, 1].set_title('Custom palette')
axs[1, 1].axis('off')
plt.show()

# Undo changes
obj_uti.set_palette(uniTThermalImage.Palettes.iron)

# -- Temperature range adjustment example --
new_temp_min = 30
new_temp_max = 80

# Plot before changing
fig, (ax1, ax2) = plt.subplots(1, 2)
ax1.imshow(obj_uti.raw_img_rgb_np)
ax1.axis('off')
ax1.set_title('Original [%d, %d] ºC' % (obj_uti.temp_min, obj_uti.temp_max))

# Change range
obj_uti.set_temp_range(new_temp_min, new_temp_max)
ax2.imshow(obj_uti.raw_img_rgb_np)
ax2.axis('off')
ax2.set_title('Range [%d, %d] ºC' % (new_temp_min, new_temp_max))
plt.show()

# Undo changes
obj_uti.set_temp_range(obj_uti.temp_min, obj_uti.temp_max)

# -- Temperature fix comparison --
print("Temp center error:", obj_uti.temp_center - obj_uti.raw_temp_np[obj_uti.temp_center_pos_h, obj_uti.temp_center_pos_w], obj_uti.temp_units)
fig, (ax1, ax2, ax3) = plt.subplots(1, 3)
ax1.imshow(obj_uti.raw_temp_np, cmap='gray')
ax1.axis('off')
ax1.set_title('Temp from raw thermal')
ax2.imshow(obj_uti.fix_temp_np, cmap='gray')
ax2.axis('off')
ax2.set_title('Temp with fix')
ax3.imshow(obj_uti.raw_temp_np - obj_uti.fix_temp_np)
ax3.axis('off')
ax3.set_title('Temp diff')
plt.show()
