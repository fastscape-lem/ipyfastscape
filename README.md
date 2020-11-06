[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/fastscape-lem/fastscape-demo/master?urlpath=lab/tree/ipyfastscape)
[![Tests](https://github.com/fastscape-lem/ipyfastscape/workflows/test/badge.svg)](https://github.com/fastscape-lem/ipyfastscape/actions)

# Ipyfastscape

Interactive widgets for topographic data analysis and modelling in Jupyter notebooks.

While ipyfastscape is tightly integrated with [fastscape](https://github.com/fastscape-lem/fastscape),
it also integrates very well with any data in the form of an [xarray](https://github.com/pydata/xarray)
dataset or any model created with [xarray-simlab](https://github.com/benbovy/xarray-simlab).

The widgets available here are built on top of libraries of the jupyter's widget
ecosystem such as [ipywidgets](https://github.com/jupyter-widgets/ipywidgets)
and [ipygany](https://github.com/QuantStack/ipygany). You can reuse those
high-level UI components as-is within notebooks (embedded mini-apps) or for
building interactive dashboards that you can then publish as standalone web
applications (using [voilà](https://github.com/voila-dashboards/voila)).

## Features

- `TopoViz3d`: Paraview-like 3D terrain visualization, with time player and dimension explorer

![TopoViz3d demo](https://user-images.githubusercontent.com/4160723/95083363-b4e02800-071c-11eb-939d-463ebb8342a2.gif)

- `AppLinker`: Easily link different application instances for, e.g., side-by-side comparison

<img src="https://user-images.githubusercontent.com/4160723/95762839-8af3ac00-0cae-11eb-8080-0472e7e6b9d6.gif" width="640" title="AppLinker demo">

## Installation

You can install ipyfastscape either with conda:

``` sh
$ conda install ipyfastscape -c conda-forge
```

or using pip:

``` sh
$ python -m pip install ipyfastscape
```

If you use jupyterlab (2.x), you also need to install some extensions:

``` sh
$ jupyter labextension install @jupyter-widgets/jupyterlab-manager ipygany
```

If you installed ipyfastscape using pip and you are using jupyter's "classic"
notebook, you need to enable those extensions:

``` sh
$ jupyter nbextension enable --py --sys-prefix ipygany
```
