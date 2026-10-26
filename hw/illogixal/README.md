# illogixal

**Category:** Hardware  
**Author:** phlebas

## Description

Connect to WiFi network "OT Test Bed" with password `Visiting9/Staple/Sprung`

Rules of Engagement for Physical Hardware. 
Violation of these will result in me being sad and probable disqual from this chal.
- No Nmap. Manual testing of port connectivity only
- No spamming (do your research before throwing packets)
- No directory bruteforcing, including for the http server
- No screen peeking (one solver approach the PLC at a time)
- You don't need to touch anything

ICS Village swag will (stock permitting) be rewarded upon a solve

Outcome:
  Manipulate the physical hardware in order to reveal the flag

Scope of Assessment:
  Network evaluation of CompactLogix L23E Device at 192.168.100.10
Out of Scope: Any device apart from 192.168.100.10

## Flag

```
^rstcon\{Not_Thinking_Logixally\}$
```
