# DASMixer Installation

## Windows

You can download the latest standalone installer from [**GitHub Releases**](https://github.com/protdb/dasmixer/releases/latest).

Under the release changelog in the **Assets** section, find and download `DASMixerX.X.X-setup.exe` as shown below:

![Windows download example](img/win_download.png){data-description="GitHub Releases page — locate the DASMixer installer .exe file in the Assets section."}

Follow the installation wizard steps. Once installed, DASMixer will be available as a standard desktop application and accessible from the Windows Start menu.

DASMixer project files (`.dasmix`) will also be automatically associated with the DASMixer application.

## Install as a Python Package (Linux, macOS, and Windows)

DASMixer can be installed directly from the PyPI repository using `pip`:

```shell
pip install dasmixer
```

Alternatively, if you only need the command-line interface or wish to use the core library on a headless server, you can install the CLI or core packages separately:

```shell
# CLI and core library (no GUI dependencies)
pip install dasmixer-cli

# Core library only (for scripting and embedding)
pip install dasmixer-core
```

> **Optional PRIDE support:** To enable direct dataset imports from the PRIDE archive, install the `pride` extra:
> ```shell
> pip install "dasmixer-core[pride]"
> ```

### Using a Conda Environment

While DASMixer is not distributed through Conda channels directly, you can use Conda (or Mamba) to create an isolated Python environment before installing via `pip`. This is **recommended** on Linux systems or older OS distributions, as DASMixer works best on Python 3.11–3.14:

```shell
conda create -n dasmixer python=3.14 -y
conda activate dasmixer
pip install dasmixer
```

If `pip` encounters issues building native dependencies from source, check the error output for missing system development headers or compilers (such as `gcc` or `python3-dev`) and install them via your system package manager.
