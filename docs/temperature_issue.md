# Temperature extraction issue

Beware, thermal data extracted from the embedded data is not accurate. This issue is present on the UNI-T UTi260B v1.1.2 firmware.

It seems that the raw thermal image is stored already processed to increase its contrast, probably using a histogram equalization before the upscale to 320x240.
As a result the temperature scale becomes non-linear and impossible to characterize.
Therefore, the conversion to real temperatures cannot be properly done, especially if using the expected linear interpolation. 

The following image, a), shows a small handheld blowtorch.
The flame is the hottest point in the picture, reaching 150ºC (Image took with the High Sensitivity setting). 
It can be seen that the flame and hand have almost the same white shade.
However, the temperature of the hand, point 2, is 31ºC, and it should be much much lower on the scale.
So, when converting back the pixel brightness using a linear interpolation between 18.5ºC and 150ºC the result is 142.2ºC, which is clearly wrong.

Image b) shows how the image would look with a proper linear scale. Is easy to understand why UNI-T engineers decided to enhance contrast.
But this is how the data should be stored for posterior analysis, at least in the embedded part.

![Center temperature vs brightness](img/temp_issue_example.png)

This issue can be also verified by plotting the center temperature, which is accurate, vs its corresponding pixel brightness (0 to 254).
If the scale were to be linear, the resulting point will lay on the line between the min and max temperatures.
I plotted this for all the pictures I have right now (340). The temperatures were normalized (Tn = (T - Tmin)/(Tmax - Tmin)).
Clearly, the points do not lay as expected, with more error typically in the middle, as is further from the limits.

![Center temperature vs brightness](img/center_temp_vs_brigthness.png)

The higher the temperature range the larger the errors become.
Also, it seems that usually when the range is large the extracted temperatures are higher than it should be.

![Center error vs temperature range](img/error_vs_temp_range.png)

Right now, at postprocessing using this script or UNI-T software, only high, low and center temperatures can be trusted.
The manual set 3 point measurements are also accurate, but are not stored within the embedded data, so right now cannot be used without image processing.

In order to reduce some temperature error the script now offers a fix version of the img and temperature array that uses a 3 point linear regression, adding the center temperature to the mix.
The effect on the error depends on where the center temperature sits on the temperature scale. If it is close to the minimum or maximum temperatures it won't have much effect.
Anyways, it offers some degree of correction. 

![Fix example](img/temp_fix_example.png)

In conclusion, when working with images took from these UNI-T cameras keep in mind that the resulting temperatures could not be exact.
For precise measurements use the built-in camera features.
