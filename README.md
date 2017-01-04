# A panorama viewer plugin for displaying 360° photo sphere images in the 'Eye of Gnome' image viewer

Panoramas are more and more popular no matter whether produced with tripod and 
professional cameras or by mobile apps. Describing XMP-tags have been 
standardized [https://www.adobe.com/products/xmp.html] and web services 
(Google Photos, FB) automatically detect and display panoramas appropriately. 
In Eye of Gnome, a spherical projection would be smarter and more comfortable 
than displaying a panorama photo as a long horizontal strip.

<p align="center">
  <img src="https://cdn.rawgit.com/Aerilius/eog_panorama/master/eog_panorama/eog_panorama.svg?raw=true" alt="eog_panorama icon"/>
</p>

This is a proof of concept and would not have been possible without the help of 
Jérémy Heleine and Damien Sorel's [**Photo Sphere Viewer**](http://photo-sphere-viewer.js.org/) javascript library.
Once GTK scene graph kit is more commonly available and easy to use, a native 
implementation could be realized or even included into Eye of Gnome.

## Requirements

Exiftool can be installed with `sudo apt install libimage-exiftool-perl`

Tested on **Ubuntu 16.10** (it should work on any recent distribution with Eye of Gnome 3, Python3, Gtk+3, WebKit2)

## Installation

1. Copy the folder `eog_panorama` into `~/.local/share/eog/plugins/`

2. Open Eye of Gnome and activate the plugin in **Edit → Preferences → Plugins**

## Usage

While browsing images, panorama photos are automatically detected by their Photo Sphere metadata.

If a panorama photo is not displayed as panorama, ensure that it has the required metadata:

1. Open **Image → Properties → Details**

2. In the "XMP other" section it should have `GPano:UsePanoramaViewer = True` and other GPano metadata.

Usually such metadata is added to photos taken by mobile phones in panorama mode or photos stitched with Hugin.

Note: Due to limitations of using a WebView, large panorama images can cause 
CPU load during loading and take several hundred MB memory.

## License

GPL v3.0

Copyright (C) 2017 - Andreas Eisenbarth
