import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

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

# -- Obtaining ROI (Region of interest) temperatures --
# Load better example
filename = "../examples/samples/IMG_ROI_Temps.bmp"
obj_uti = uniTThermalImage.UniTThermalImage()
obj_uti.init_from_image(filename)

# Using default ROI, can be set to a custom one by using the roi_shape parameter
roi_temp_min, roi_pos_temp_min, roi_temp_max, roi_pos_temp_max = obj_uti.get_roi_temps()

print("Min ROI temp: %f º%c at ROI pixel:" % (roi_temp_min, obj_uti.temp_units), roi_pos_temp_min)
print("Max ROI temp: %f º%c at ROI pixel:" % (roi_temp_max, obj_uti.temp_units), roi_pos_temp_max)

# Plot ROI
fig, (ax1, ax2) = plt.subplots(1, 2)
img = mpimg.imread(filename)
ax1.imshow(img)
ax1.axis('off')
ax1.set_title('Original')

roi_shape = (81, 198, 71, 168)
img_roi = obj_uti.fix_img_rgb_np[roi_shape[0]:roi_shape[1], roi_shape[2]:roi_shape[3]]
# Draw red cross at high temperature point
img_roi[max(roi_pos_temp_max[0]-5,0):roi_pos_temp_max[0]+6, roi_pos_temp_max[1]] = [255,0,0]
img_roi[roi_pos_temp_max[0], max(roi_pos_temp_max[1]-5,0):roi_pos_temp_max[1]+6] = [255,0,0]
# Draw blue cross at low temperature point
img_roi[max(roi_pos_temp_min[0]-5,0):roi_pos_temp_min[0]+6, roi_pos_temp_min[1]] = [0,0,255]
img_roi[roi_pos_temp_min[0], max(roi_pos_temp_min[1]-5,0):roi_pos_temp_min[1]+6] = [0,0,255]

ax2.imshow(img_roi)
ax2.axis('off')
ax2.set_title('ROI')
plt.show()
