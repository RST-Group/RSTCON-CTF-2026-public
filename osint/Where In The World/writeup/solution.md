# Where In The World  -  Solution

## Step 1: read the metadata

The JPEG carries EXIF GPS tags. Any of these pull them:

```
exiftool vacation.jpg
# GPS Latitude  : 41 deg 15' 56.00" N
# GPS Longitude : 95 deg 55' 20.00" W
# User Comment  : caught the sunset with one foot in each state
```

Or in Python:

```python
import piexif
e = piexif.load('vacation.jpg')
g = e['GPS']
def dd(dms, ref):
    v = dms[0][0]/dms[0][1] + dms[1][0]/dms[1][1]/60 + dms[2][0]/dms[2][1]/3600
    return -v if ref in (b'S', b'W') else v
lat = dd(g[piexif.GPSIFD.GPSLatitude], g[piexif.GPSIFD.GPSLatitudeRef])
lon = dd(g[piexif.GPSIFD.GPSLongitude], g[piexif.GPSIFD.GPSLongitudeRef])
print(lat, lon)   # 41.26556 -95.92222
```

## Step 2: plot and identify

Drop `41.26556, -95.92222` into any map. It lands on the Missouri River between
Omaha, Nebraska and Council Bluffs, Iowa, on the Bob Kerrey Pedestrian Bridge.
