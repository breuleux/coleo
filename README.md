
# Coleo

Coleo is a minimum-effort way to create a command-line interface in Python.

* Declare options where they are used.
* Scale easily to extensive CLIs with dozens of subcommands and options.


## Basic usage

First, define a command line interface as follows:

```python
from coleo import Option, auto_cli, default

@auto_cli
def main():
    # The greeting
    greeting: Option = default("Hello")

    # The name to greet
    name: Option = default("you")

    return f"{greeting}, {name}!"
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

* Any variable annotated with `Option` will become an option.
* You can provide a default value with `default(value)`, although you don't have to, if the argument is required.
* If there is a comment above the variable, it will be used as documentation for the option.


## Option types

By default, all arguments are interpreted as strings, but you can easily give a different type to an argument:

```python
@auto_cli
def main():
    # This argument will be converted to an int
    x: Option & int
    # This argument will be converted to a float
    y: Option & float
    return x + y
```

**Boolean flags**

If the type is bool, the option will take no argument, for example:

```python
@auto_cli
def main():
    flag: Option & bool = default(False)
    return "yes!" if flag else "no!"
```

Use it like this:

```bash
$ python script.py --flag
yes!
$ python script.py
no!
```

You can also *negate* the flag, meaning that you want to provide an option that will store False in the variable instead of True. For example:

```python
@auto_cli
def main():
    # [negate]
    flag: Option & bool = default(True)
    return "yes!" if flag else "no!"
```

By default, the above will create a flag called `--no-<optname>`:

```bash
$ python script.py
yes!
$ python script.py --no-flag
no!
```

You can write `[negate: --xyz -n]` if you want the option to be `--xyz` or `-n`. This overrides the default `--no-flag` option.

Note that using `[negate]` will remove `--flag`, because we assume that it is True by default and there is therefore no need for this option.

If you wish, you can have both options that set the flag to True and others that set the flag to False, using `[false-options]`. You can optionally document these options with `[false-options-doc]` (if not provided, Coleo will use a sensible default):

```python
@auto_cli
def main():
    # Set the flag to True
    # [options: -y]
    # [false-options: -n]
    # [false-options-doc: Set the flag to False]
    flag: Option & bool = default(None)
    return flag
```

```bash
$ python script.py
None
$ python script.py -y
True
$ python script.py -n
False
```


**Files**

Use `coleo.FileType` (or `argparse.FileType`, it's the same thing) to open a file to read from or to write to:

```python
@auto_cli
def main():
    grocery_list: Option & coleo.FileType("r")
    with grocery_list as f:
        for food in f.readlines():
            print(f"Gotta buy some {food}")
```

**Config**

You can manipulate configuration files with `coleo.config` or `coleo.ConfigFile`:

```python
@auto_cli
def main():
    # ConfigFile lets you read or write a configuration file
    book: Option & ConfigFile
    contents = book.read()
    contents["xyz"] = "abc"
    book.write(contents)

    # config will read the file for you or parse the argument as JSON
    magazine: Option & config
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
@auto_cli
def main():
    obj: Option & json.loads
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
@auto_cli
def main():
    obj: Option & eval
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
@auto_cli
def main():
    # This argument can be given as either --greeting or -g
    # [alias: -g]
    greeting: Option = default("Hello")

    # This argument is positional
    # [positional]
    name: Option = default("you")

    # This argument can only be given as -n
    # [options: -n]
    ntimes: Option & int = default(1)

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
* `[remainder]` represents all arguments that are not matched by the argument parser
* `[nargs: n]` declares that the option takes n arguments
  * `[nargs: ?]`: one optional argument
  * `[nargs: *]`: zero or more arguments
  * `[nargs: +]`: one or more arguments
* `[action: <action>]` customizes the action to perform
  * `[action: append]` lets you use an option multiple times, accumulating the results in a list (e.g. `python app.py -a 1 -a 2 -a 3`, would put `[1, 2, 3]` in `a`)
* `[metavar: varname]` changes the variable name right after the option in the help string, e.g. `--opt METAVAR`
* `[group: groupname]` puts the option in a named group. Options in the same group will appear together in the help.
* For **bool** options only:
    * `[negate: ...]` changes the option so that it sets the variable to False instead of True when they are given. Space/comma aliases may be provided for the option, otherwise the flag will be named `--no-<optname>`.
    * `[false-options: ]` provide a list of options that set the flag to False.
    * `[false-options-doc: ]` provide a documentation for the options given using the previous statement.


## Subcommands

You can create an interface with a hierarchy of subcommands by decorating a class with `auto_cli`:

```python
@auto_cli
class main:
    class calc:
        def add():
            x: Option & int
            y: Option & int
            return x + y

        def mul():
            x: Option & int
            y: Option & int
            return x * y

        def pow():
            base: Option & int
            exponent: Option & int
            return base ** exponent

    def greet():
        greeting: Option = default("Hello")
        name: Option = default("you")
        return f"{greeting}, {name}!"
```

The class only holds structure and will never be instantiated, so don't add `self` to the argument lists for these functions.

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
from coleo import Option, auto_cli, config, default, tooled

@tooled
def apikey():
    # The API key to use
    key: Option = default(None)
    if key is None:
        # If no key parameter is given on the command line, try to read it from
        # some standard location.
        key = config("~/.config/myapp/config.json")["key"]
    return key

@auto_cli
class main:
    def search():
        interface = Application(apikey())
        query: Option
        return interface.search(query)

    def install():
        interface = Application(apikey())
        package: Option
        return interface.install(package)
```

If a function is decorated with `@tooled` and is called from one of the main functions (or from another tooled function), Coleo will search for arguments in that function too. Thus any subcommand that calls `apikey()` will gain a `--key` option.

In addition to this, you can "share" arguments by defining the same argument with the same type in multiple functions. Coleo will set all of them to the same value.

For example, in the example above you could easily let the user specify the path to the file that contains the key, simply by replacing

```python
key = config("~/.config/myapp/config.json")["key"]

# ==>

config_path: Option = default("~/.config/myapp/config.json")
key = config(config_path)["key"]
```

And that `config_path` argument could, of course, be declared in any other function that needs to read some configuration value.


## run_cli

```python
from coleo import Option, auto_cli

@auto_cli
def main():
    x: Option
    return x
```

Is equivalent to:

```python
from coleo import Option, run_cli, tooled

@tooled
def main():
    x: Option
    return x

result = run_cli(main)
if result is not None:
    print(result)
```


## Non-CLI usage

It is possible to set arguments without `auto_cli` using `setvars`:

```python
from coleo import Option, setvars, tooled

@tooled
def greet():
    greeting: Option = default("Hello")
    name: Option = default("you")
    return f"{greeting} {name}!"

with setvars(greeting="Hi", name="Bob"):
    assert greet() == "Hi bob!"
```

Note:

* With `setvars`, you *must* decorate the function with `@tooled` (this is something `auto_cli` does on your behalf).
* `setvars` entirely bypasses the option parsing and the type annotations will not be used to wrap these values. In other words, if a variable is annotated `Option & int` and you provide the value "1", it will remain a string.


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

Read the documentation for [Ptera](https://github.com/mila-iqia/ptera) for more information. Note that Ptera is not limited to variables tagged `Option`, it can manipulate *any* variable in a tooled function.
