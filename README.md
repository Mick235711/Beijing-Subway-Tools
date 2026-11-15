# Beijing-Subway-Tools
Tools and data from subway systems around the world (currently only doing Beijing's data).

Mainly focus on electronically recording the timetables of subway lines, to facilitate the creation
of equ-time graphs.

# Running Requirements
Python 3.11+. Install the dependencies for the command-line tools, maps, frontend UI, and MCP server with:

```sh
python -m pip install -r requirements.txt
```

Finding non-repeating paths with the optional Graphillion backend also requires `graphillion`.

(For auxiliary scripts, [see corresponding documentation](docs/tools.md#auxiliary-scripts) to determine their requirements.)

# Add a New City/Subway Line/Train/...
See [specification.md](docs/specification.md) for the specifications (format of JSON5 files within `data/`) you need to
follow, and also [a-new-line-from-scratch.md](docs/a-new-line-from-scratch.md) for the process of creating a new line.

# Usage of Tools
See [tools.md](docs/tools.md) for a description of all usable tools and their parameters.

# Frontend UI

To reduce the difficulty of installing prerequisites, this project packages the frontend UI with `pyinstaller` into an executable application; you may download your platform's version under [nighly releases](https://github.com/Mick235711/Beijing-Subway-Tools/releases/tag/continuous-build).

Alternatively, you can also visit the WeChat mini-program "京轨时刻" to have a friendlier interface (Chinese only).

# Data Sources & License
This work is licensed under [MIT](/LICENSE).

All data present are based on openly available sources obtained from the official Beijing Subway and other official websites.

There may be many mistakes in the data given as I'm human and can and will make mistakes.
