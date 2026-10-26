## Fixing the Dimensions
If you examin the metadata of the png with `exiftool` you'll notice the image dimensions are 0 by 0, which is clearly wrong. The dimensions of the image can be calculated using the existing header information and examinging the IDAT chunk sizes

Decompress each IDAT chunk with zlib. The data of each is a sequence of scanlines where each row starts with a filter byte that must be 0–4. Since every row is exactly `width × bytes_per_pixel + 1` bytes long, the filter bytes appear at regular intervals. So the stride we need to calculate can be checked by trying all possible values for the stride which is related to the actual width of the image.

`bytes_per_pixel` can be calculated using the number of channels and bit depth which can be pulled/derived from the IHDR chunk.

## CRCs

Now, I personally haven't tried every image viewer, but `feh` complains about CRCs being incorrect. I guess it's possible for a PNG view to ignore CRC errors and just roll with it, but the next step is the fix all the CRC values for each IDAT chunk which are zero'ed out.

PNGs use the standard CRC32 calculation that you can grab from a number of libraries.