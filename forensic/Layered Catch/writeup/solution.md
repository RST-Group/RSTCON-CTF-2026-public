# Layered Catch  -  Solution

**Flag:** `rstcon{p0lyglot_png_h1des_a_zip}`

## Recon

`file catch.png` says PNG, but the size is suspicious for a tiny solid image.
Carving confirms a second file riding along:

```
binwalk catch.png
# ... PNG image data ...
# ... Zip archive data, encrypted, flag.txt ...
```

The zip's end-of-central-directory record sits at the tail of the file, so most
zip tools open `catch.png` directly as an archive.

## Get the passphrase

The archive is ZipCrypto encrypted. The password is hidden in the PNG metadata,
in a `tEXt` chunk. Any of these surfaces it:

```
exiftool catch.png            # look at Passphrase / Comment fields
strings catch.png | head      # tEXt chunks are plaintext
python3 -c "from PIL import Image; print(Image.open('catch.png').text)"
```

There is a decoy `Comment` chunk and the real `Passphrase` chunk
(`t1de_p00ls_run_deep`).

## Extract

```
unzip -P t1de_p00ls_run_deep catch.png        # or 7z x -p...
cat flag.txt
```

or in Python:

```python
import zipfile
z = zipfile.ZipFile('catch.png')
print(z.read('flag.txt', pwd=b't1de_p00ls_run_deep').decode())
```

## Common stumbles

- Trying to brute the zip password instead of reading the metadata. The
  passphrase is sitting in plain sight in a tEXt chunk.
- Stopping at "it's just a PNG." Always check for trailing data past `IEND`.
