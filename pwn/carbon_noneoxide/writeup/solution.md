# Reversing
The binary is stripped so we have no symbols, but you'll notice in the strings three important things
1. rstcon{??????} -> this is a placeholder for the flag in the actual deployment. We want to read the data at this address
2. mention of FreeRTOS which is an open sourced RTOS
3. LM3S6965 (Cortex-M3) which is an ARM chip that QEMU support

Pull up the docs for LM3S6965 (https://www.ti.com/lit/ds/symlink/lm3s6965.pdf) and find the memory map. Spoilers: base address is 0x0.

Clone and build FreeRTOS with symbols and use Ghidra's BSIM feature to recover function names in the loaded firmware.

You'll notice that there's an Admin task that gets created. It is gated by a check for the string "charlotte" from UART input. This gets you to a secret menu that lets you pause the sensor task as well as send fake sensor data to the monitoring task in the firmware.

# Bug Finding
The sensor task and the admin task both maintain a circular buffer of sensor readings, *BUT* on the admin version does *Not* have a bounds check on the value used to index the next location to write a sensor reading in the circular buffer. This write can go past the bounds of the buffer if enough readings are done. Right after the end of this buffer is the pointer to the FreeRTOS `QueueHandle_t` queue struct for the monitoring task.

# Exploitation
In the monitoring task, `xQueueReceive` is called on the pointer, we that can overwrite using the overflow in the admin menu. The value pulled out of the queue from the `xQueueReceive` call is immediately printed out to the user over UART. 

Lets call the pointer we can overwrite: `xSensorQueue` (because thats the actual variable name I used in the source). 

1. Construct our own `QueueHandle_t` in the circular buffer of sensor data, where the underlying buffer in the queue actually points to the location of the flag, 
2. Overwrite `xSensorQueue` with the fake queue we just wrote into memory
3. Let the monitor queue read out the buffer (flag) and print it to the user
