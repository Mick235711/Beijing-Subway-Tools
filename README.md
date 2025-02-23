# Beijing-Subway-Tools
Tools and data from subway systems around the world (currently only doing Beijing's data).

Mainly focus on electronically recording the timetables of subway lines, to facilitate the creation
of equ-time graphs.

# Running Requirements
Python 3.10+, PyPI packages: `questionary`, `pyjson5`, `pypinyin`, `tabulate` and `tqdm`

(For map-related tasks, also requires `numpy`, `matplotlib` and `scipy`)

(For finding the longest route in the network, requires `networkx` or optionally `graphillion` for finding non-repeating paths)

# Add a New City/Subway Line/Train/...
See [specification.md](docs/specification.md) for the specifications (format of JSON5 files within `data/`) you need to
follow, and also [a-new-line-from-scratch.md](docs/a-new-line-from-scratch.md) for the process of creating a new line.

# Usage of Tools
See [tools.md](docs/tools.md) for a description of all usable tools and their parameters.

# Data Sources & License
This work is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
All data present are based on openly available sources obtained from the official Beijing Subway website.

There may be many mistakes in the data given as I'm human and can and will make mistakes.