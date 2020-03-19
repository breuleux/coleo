
# Coleo

Coleo is a minimum-effort way to create a command-line interface in Python.

* Declare options where they are used.
* Scale easily to extensive CLIs with dozens of subcommands and options.


## Basic usage

First, define a command line interface as follows:

```python
from coleo import Argument, auto_cli, default

def main():
    # The greeting
    greeting: Argument = default("Hello")

    # The name to greet
    name: Argument = default("you")

    return f"{greeting}, {name}!"

if __name__ == "__main__":
    auto_cli(main)
```

Then you may run it like this on the command line:

```bash
$ python hello.py
Hello, you!
$ python hello.py --name Luke
Hello, Luke!
$ python hello.py --name Luke --greeting "Happy birthday"
Happy birthday, Luke!
$ python hello.py -h
usage: hello.py [-h] [--greeting VALUE] [--name VALUE]

optional arguments:
  -h, --help        show this help message and exit
  --greeting VALUE  The greeting
  --name VALUE      The name to greet
```

* Any variable annotated with `Argument` will become an option.
* You can provide a default value with `default(value)`, although you don't have to, if the argument is required.
* If there is a comment above the variable, it will be used as documentation for the option.


## Argument types

By default, all arguments are interpreted as strings, but you can easily give a different type to an argument:

```python
def main():
    # This argument will be converted to an int
    x: Argument & int
    # This argument will be converted to a float
    y: Argument & float
    return x + y
```

**Boolean flags**

If the type is bool, the option will take no argument, and the `--no-<optname>` option is added to negate the value. For example:

```python
def main():
    flag: Argument & bool
    return "yes!" if flag else "no!"
```

Use it like this:

```bash
$ python script.py --flag
yes!
$ python script.py --no-flag
no!
```

**Files**

Use `coleo.FileType` (or `argparse.FileType`, it's the same thing) to open a file to read from or to write to:

```python
def main():
    grocery_list: Argument & coleo.FileType("r")
    with grocery_list as f:
        for food in f.readlines():
            print(f"Gotta buy some {food}")
```

**Config**

You can manipulate configuration files with `coleo.config` or `coleo.ConfigFile`:

```python
def main():
    # ConfigFile lets you read or write a configuration file
    book: Argument & ConfigFile
    contents = book.read()
    contents["xyz"] = "abc"
    book.write(contents)

    # config will read the file for you or parse the argument as JSON
    magazine: Argument & config
    print(magazine)
```

Use it simply like this:

```bash
$ python librarian.py --book alice.json --magazine vogue.json
$ python librarian.py --book history.yaml --magazine gamez.toml
$ python librarian.py --book physics.json --magazine '{"a": 1, "b": 2}'
# etc
```

Supported extensions are `json`, `yaml` and `toml` (the latter two require installing the `pyyaml` or `toml` packages).


**Other**

Any function can be used as a "type" for an argument. So for example, if you want to be able to provide lists and dictionaries on the command line you can simply use `json.loads` (although `coleo.config` is usually better, because it can also read files, in various formats):

```python
def main():
    obj: Argument & json.loads
    return type(obj).__name__
```

```bash
$ python json.py --obj 1
int
$ python json.py --obj '"hello"'
str
$ python json.py --obj '{"a": 1, "b": 2}'
dict
```

If you're feeling super feisty and care nothing about safety, you can even use `eval`:

```python
def main():
    obj: Argument & eval
    return type(obj).__name__
```

```bash
$ python eval.py --obj "1 + 2"
int
$ python eval.py --obj "lambda x: x + 1"
function
```


## Customization

Using comments of the form `# [<instruction>: <args ...>]` you can customize the option parser:

```python
def main():
    # This argument can be given as either --greeting or -g
    # [alias: -g]
    greeting: Argument = default("Hello")

    # This argument is positional
    # [positional]
    name: Argument = default("you")

    # This argument can only be given as -n
    # [options: -n]
    ntimes: Argument & int = default(1)

    for i in range(ntimes):
        print(f"{greeting}, {name}!")
```

The above would be used like this:

```bash
$ python hello.py Alice -g Greetings -n 2
Greetings, Alice!
Greetings, Alice!
```

The following customizations are available:

* `[alias: ...]` defines one or several options that are aliases for the main one. Options are separated by spaces, commas or semicolons.
* `[options: ...]` defines one or several options for this argument, which *override* the default one. Options are separated by spaces, commas or semicolons.
* `[positional]` defines one positional argument.
  * `[positional: n]`: n positional arguments (a list is returned).
  * `[positional: ?]`: one optional positional argument
  * `[positional: *]`: zero or more positional arguments
  * `[positional: +]`: one or more positional arguments

It is currently not possible to define multiple arguments as positional, although you can simulate it by using e.g. `[positional: 2]` on a single argument to get a pair, and then you can get the elements of the list.


## Subcommands

You can create an interface with a hierarchy of subcommands by passing a dictionary to `auto_cli`:

```python
def add():
    x: Argument & int
    y: Argument & int
    return x + y

def mul():
    x: Argument & int
    y: Argument & int
    return x * y

def pow():
    base: Argument & int
    exponent: Argument & int
    return base ** exponent

def greet():
    greeting: Argument = default("Hello")
    name: Argument = default("you")
    return f"{greeting}, {name}!"

if __name__ == "__main__":
    auto_cli({
        "calc": {
            "__doc__": "Calculate something!",
            "add": add,
            "mul": mul,
            "pow": pow,
        },
        "greet": greet,
    })
```

Then you may use it like this:

```bash
$ python multi.py greet --name Alice --greeting Hi
Hi, Alice!
$ python multi.py calc add --x=3 --y=8
11
```


## Sharing arguments

It is possible to share behavior and arguments between subcommands, or to split complex functionality into multiple pieces. For example, maybe multiple subcommands in your application require an API key, which can either be given on the command line or can be read from a file. This is how you would share this behavior across all subcommands:

```python
from coleo import Argument, auto_cli, default, tooled

@tooled
def apikey():
    # The API key to use
    key: Argument = default(None)
    if key is None:
        # If no key parameter is given on the command line, try to read it from
        # some standard location.
        key = config("~/.config/myapp/config.json")["key"]
    return key

def search():
    interface = Application(apikey())
    query: Argument
    return interface.search(query)

def install():
    interface = Application(apikey())
    package: Argument
    return interface.install(package)

if __name__ == "__main__":
    auto_cli({"search": search, "install": install})
```

If a function is decorated with `@tooled` and is called from one of the main functions (or from another tooled function), Coleo will search for arguments in that function too. Thus any subcommand that calls `apikey()` will gain a `--key` option.

In addition to this, you can "share" arguments by defining the same argument with the same type in multiple functions. Coleo will set all of them to the same value.

For example, in the example above you could easily let the user specify the path to the file that contains the key, simply by replacing

```python
key = config("~/.config/myapp/config.json")["key"]

# ==>

config_path: Argument = default("~/.config/myapp/config.json")
key = config(config_path)["key"]
```

And that `config_path` argument could, of course, be declared in any other function that needs to read some configuration value.


## Non-CLI usage

It is possible to set arguments without `auto_cli` with `setvars`:

```python
from coleo import Argument, setvars, tooled

@tooled
def greet():
    greeting: Argument = default("Hello")
    name: Argument = default("you")
    return f"{greeting} {name}!"

with setvars(greeting="Hi", name="Bob"):
    assert greet() == "Hi bob!"
```

Note:

* With `setvars`, you *must* decorate the function with `@tooled` (this is something `auto_cli` does on your behalf).
* `setvars` entirely bypasses the option parsing and the type annotations will not be used to wrap these values. In other words, if a variable is annotated `Argument & int` and you provide the value "1", it will remain a string.


### Using with Ptera

Coleo is based on [Ptera](https://github.com/mila-iqia/ptera) and all of Ptera's functionality is de facto available on functions marked as `@tooled`. For example, using the example above:

```python
# Set the variables in the greet function -- it's a bit like making an object
hibob = greet.new(greeting="Hi", name="Bob")
assert hibob() == "Hi Bob!"

# Same as above but this would also change greeting/name in any other function
# that is called by greet, and so on recursively (a bit like dynamic scoping)
hibob = greet.tweaking({"greeting": "Hi", "name": "Bob"})
assert hibob() == "Hi Bob!"

# More complex behavior
from ptera import overlay
with overlay.tweaking({
    "greet(greeting='Bonjour') > name": "Toto"
}):
    assert greet() == "Hello you!"
    assert greet.new(greeting="Hi")() == "Hi you!"
    assert greet.new(greeting="Bonjour")() == "Bonjour toto!"
```

Read the documentation for [Ptera](https://github.com/mila-iqia/ptera) for more information. Note that Ptera is not limited to variables tagged `Argument`, it can manipulate *any* variable in a tooled function.
