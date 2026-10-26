# Solution

This program is a simple CLI for a GPT2 model using libllama. 

In `run()` on line 79, space for the flag is allocated on the stack, and on line 98 `read_flag()` is called which populates the flag in memory.

On line 165, you'll notice `printf` is used insecurely; `output_buf` is user influenced and is the string format specifier. Therefore, we want to prompt the LLM to string format attack itself in order to leak the flag off the stack.

Since the GPT architecture is designed to predict more tokens given the current ones, we want to prompt the LLM with text that would massage it to output format string specifiers. This was my prompt:

`This is a list of C string format specifiers and examples: %lx %lx %lx %lx %lx %lx %lx %lx %lx %lx`

and I kept giving it the same prompt a few times until it leaked.
