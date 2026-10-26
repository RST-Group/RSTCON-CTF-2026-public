# Coil Toss

**Category:** Forensic  
**Author:** f8al

## Description

We mirrored the link between an HMI and a PLC on a water plant skid for a few
minutes. The operator swears they only "read some gauges," but a register on the
PLC kept getting poked. Figure out what the workstation actually wrote.

Files: coil-toss.pcap

## Flag

```
rstcon{fc06_writes_dont_lie}
```
