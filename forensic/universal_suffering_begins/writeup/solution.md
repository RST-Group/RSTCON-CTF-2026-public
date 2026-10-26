# Solution: Universal Suffering Begins (USB)

`data.pcap` has no Ethernet/IP/TCP — it's a raw USB capture (hence the title). Open it in Wireshark and filter out noise first: `SOF` frames (bus heartbeat, ~1ms interval) and NAK'd polling transactions carry no data, ignore both.

What's left is traffic from three devices sharing the bus: a keyboard, a printer, and a USB mass storage device. Each has a distinct wire signature.

## Keyboard input

For keyboard inputs you'll see: Interrupt IN transfers, fixed endpoint, payload always exactly 8 bytes.

That's the USB HID boot-protocol keyboard report format:

| Byte | Meaning |
|---|---|
| 0 | Modifier bitmask (Ctrl/Shift/Alt/GUI) |
| 1 | Reserved, always `0x00` |
| 2–7 | Up to 6 concurrently pressed keys, as HID usage IDs (scancodes) |

**Parsing:** Pull every 8-byte interrupt IN payload on that endpoint in order. All-zero reports are key-release/idle — drop them. For the rest, map byte 0 to modifiers and bytes 2–7 to scancodes using the HID keyboard usage table (0x04–0xE7), then reconstruct keystrokes in capture order.

## PDF print job

Printers over USB take a raw bulk data stream (no filesystem, no packet framing) — the host just streams the print job's bytes straight to the printer's bulk OUT endpoint.
You'll see bulk transfer payload starts with `%PDF-` in plaintext.

**Parsing:** Filter to bulk transfers on the printer's endpoint/device address, take them in wire order, and concatenate the payloads. The result is the PDF file byte-for-byte

## Mass storage (CBW/CSW)

31-byte payloads starting `USBC`, paired with 13-byte payloads starting `USBS`.

This is USB Bulk-Only Transport (BOT): the Command Block Wrapper (CBW, `USBC`) carries a SCSI command, and the Command Status Wrapper (CSW, `USBS`) closes it out. Both carry a `dCBWTag`/`dCSWTag` field — the same value ties a CBW to its matching CSW.

**Parsing:**
1. **Filter to READ/WRITE.** Decode each CBW's embedded SCSI opcode (offset 15 in the 31-byte wrapper). Most are housekeeping — `TEST UNIT READY` (0x00), `INQUIRY` (0x12), `REQUEST SENSE` (0x03) — skip those. Keep opcode `0x28` (READ(10)) and `0x2A` (WRITE(10)); these carry a real LBA and transfer length in the CDB.
2. **Reassemble the data stage.** Each CBW declares direction (`bmCBWFlags`) and byte count (`dCBWDataTransferLength`). Everything transferred on that device address, in that direction, between the CBW and its matching CSW (same tag) is raw sector data — no other framing. Concatenate in wire order.
3. **Carve.** Concatenate every WRITE command's reassembled bytes (host→device — a file being written to the drive) into one blob and scan for file magic. A PNG header (`89 50 4E 47 0D 0A 1A 0A`) turns up partway through; carve from there to the `IEND` chunk and out comes `chainsaw_guy.png`, byte-for-byte.

## The Flag,
Once you parse all the data over the write, you'll see that there is a PNG transferred over a mass storage device that as the flag in it.
