#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Approach:
# - Listen for image load event and check the XMP tag GPano:UsePanoramaViewer
#   https://developers.google.com/streetview/spherical-metadata
#   - GExiv2 (in default Ubuntu install, but not robust enough to inconsistent XMP tags)
#   - ExifTool (not in default install)
# - If it is a panorama, replace 2D image display by 360° display
#   Create a sphere and project the photo according to XMP GPano tags.
#   - OpenGL:              python-gtklext (not maintained and not in repos), 
#                          python-opengl (too low-level), shortcrust
#   - GTK scene graph kit: not yet completed and included in common distributions
#   - JavaScript/WebGL:    PhotoSphereViewer.js
# - Interactivity (drag to rotate around z-axis and tilt; scroll to zoom)



import gi, os, urllib.parse
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Gio, Eog

# EXIF/XMP metadata
from pyexiftool.exiftool import ExifTool

# Webview for WebGL panorama viewer
gi.require_version('WebKit2', '4.0')
from gi.repository import WebKit2

# Encoding image in data uris.
import base64
# Mime type
import magic



class PanoramaPlugin(GObject.Object, Eog.WindowActivatable):
    # Override EogWindowActivatable's window property
    # This is the EogWindow this plugin instance has been activated for
    window = GObject.property(type=Eog.Window)



    def __init__(self):
        GObject.Object.__init__(self)
        self.panorama_viewer_loaded = False
        self.panorama_viewer_active = False
        self.container = None
        self.image_view = None
        self.panorama_view = None
        self.thumb_view = None
        self.selection_change_handler = None



    # Eye-of-Gnome API methods



    def do_activate(self):
        """The plugin has been activated (on app start or through checkbox in preferences), set it up."""
        # For tracking selected image.
        self.thumb_view = self.window.get_thumb_view()
        self.selection_change_handler = self.thumb_view.connect('selection-changed', self.on_selection_changed)
        # Initialization of panorama viewer:
        #    Since it take significant amount of memory, we load it only once we 
        #    encounter a panorama image (see on_selection_changed).
        #self.load_panorama_viewer()



    def do_deactivate(self):
        """The plugin has been deactivated, clean everything up."""
        # Remove all modifications and added widgets from the UI scene graph.
        # (In this implementation same as when hiding the panorama.)
        self.hide_panorama()
        # Unregister event handlers.
        self.thumb_view.disconnect(self.selection_change_handler)
        self.selection_change_handler = None
        # Release resources.
        self.panorama_view = None
        self.panorama_viewer_active = False
        self.panorama_viewer_loaded = False


    def on_selection_changed(self, thumb_view):
        """An image has been selected."""
        # Use the reference of thumb_view passed as parameter, not self.thumb_view (did cause errors).
        current_image = thumb_view.get_first_selected_image() # may be None
        if current_image:
            # Get file path
            uri = current_image.get_uri_for_display()
            filepath = urllib.parse.urlparse(uri).path
            
            # Read panorama metadata
            metadata = self.get_pano_xmp(filepath)
            
            # If it is a panorama, switch to panorama viewer.
            if 'XMP:UsePanoramaViewer' in metadata and metadata['XMP:UsePanoramaViewer'] == True:
                # I tried passing just the image file path, but cross-site-scripting
                # restrictions do not allow local file:// access.
                # Solutions: simple server or data uri.
                image = self.image_to_base64(filepath)
                # Lazy loading: Create panorama_viewer only when a panorama is encountered.
                # TODO: maybe unload it again after a certain amount of non-panorama images.
                if not self.panorama_viewer_loaded:
                    # 1. Load the panorama viewer.
                    self.load_panorama_viewer(lambda: self.panorama_view.load_image(image, metadata, self.show_panorama) )
                else:
                    # 2. Load the image into the panorama viewer.
                    # 3. When finished, make it visible.
                    self.panorama_view.load_image(image, metadata, self.show_panorama)
            else:
                # It is a normal image.
                self.hide_panorama()
                # Release resources in the panorama viewer by loading an empty/none image
                if self.panorama_viewer_loaded:
                    empty_image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIAAAUAAeImBZsAAAAASUVORK5CYII='
                    self.panorama_view.load_image(empty_image, {})



    # Helper methods



    def get_pano_xmp(self, filepath):
        """Read XMP panorama metadata of an image file.

        Args:
            filepath: an image file to read
        Returns:
            a dict containing XMP keys with their values
        """
        # Exiv2 is not robust and does not read any GPano XMP tags at all if there exist duplicate tags.
        #metadata = GExiv2.Metadata(filepath)
        # For tags see: http://www.exiv2.org/tags.html
        # and http://exiv2.org/tags-xmp-GPano.html
        #print(metadata.get_tag_label('Xmp.GPano.UsePanoramaViewer'))
        #print(metadata.get_tag_string('Xmp.GPano.UsePanoramaViewer'))
        #print(metadata.get_tag_raw('Xmp.GPano.UsePanoramaViewer'))
        
        # Using exiftool instead.
        tags = ['XMP:UsePanoramaViewer', 'XMP:ProjectionType', \
                'XMP:FullPanoWidthPixels', 'XMP:FullPanoHeightPixels', \
                'XMP:CroppedAreaImageWidthPixels', 'XMP:CroppedAreaImageHeightPixels', \
                'XMP:CroppedAreaLeftPixels', 'XMP:CroppedAreaTopPixels', \
                'XMP:PoseHeadingDegrees' \
               ]
        with ExifTool() as et:
            metadata = et.get_tags(tags, filepath)
            return metadata



    def load_panorama_viewer(self, on_loaded_cb = None):
        """Initialize the panorama viewer widget.

        Args:
            on_loaded_cb: an optional callback function/lambda that is called 
                          after loading of the panorama widget completes.
        Note:
            Instantiation of the WebView is synchronous, but loading of html is asynchronous.
            For subsequently interacting with the document, pass a callback.
        """
        if not self.panorama_viewer_loaded:
            self.image_view = self.window.get_view()      # EogScrollView
            self.container = self.image_view.get_parent() # its parent, GtkOverlay

            # Create the panorama widget.
            self.panorama_view = PanoramaViewer(on_loaded_cb)
            self.panorama_view.show()
            
            self.panorama_viewer_loaded = True



    def image_to_base64(self, filepath):
        """Read an image file and returm its content as base64 encoded string.

        Args:
            filepath: an image file to read
        Returns:
            a string of the base64 encoded image
        """
        m = magic.open(magic.MAGIC_MIME_TYPE)
        m.load()
        mimetype = m.file(filepath)
        m.close()
        with open(filepath, 'rb') as f:
            return 'data:'+mimetype+';base64,' + base64.b64encode(f.read()).decode('ascii')



    def show_panorama(self):
        """Show the panorama widget and hide the image viewer."""
        if not self.panorama_viewer_active:
            # I tried adding both widgets to the container and just toggling their 
            # visibility or adding them into a Gtk.Stack, but in both cases the 
            # WebView did not receive mouse events. Replacing the widgets works.
            self.container.remove(self.image_view)
            self.container.add(self.panorama_view)
            self.panorama_viewer_active = True



    def hide_panorama(self):
        """Show the image viewer and hide the panorama widget."""
        if self.panorama_viewer_active:
            self.container.remove(self.panorama_view)
            self.container.add(self.image_view)
            self.panorama_viewer_active = False



class PanoramaViewer(WebKit2.WebView):
    
    
    
    #uri_panorama_viewer = 'file://' + os.path.join(self.plugin_info.get_data_dir(), 'eog_panorama.htm')
    uri_panorama_viewer = 'file://' + os.path.join(os.path.dirname(os.path.realpath(__file__)), 'eog_panorama.htm')
    custom_scheme = 'eogp' # This should not clash with the plugin path, otherwise it confuses WebKit.
    
    
    
    def __init__(self, on_loaded_cb = None):
        """Initialize the panorama viewer widget.

        Args:
            on_loaded_cb: an optional callback function/lambda that is called 
                          after loading of the panorama widget completes.
        """
        super(PanoramaViewer, self).__init__()
        # Callback for when loading of the WebView completed.
        self.on_loaded_cb = on_loaded_cb
        # Callback for when loading of an image completed.
        self.pending_on_completed_cb = None
        
        # Settings
        websettings = WebKit2.Settings()
        websettings.set_property('enable-webgl', True)
        websettings.set_property('enable-plugins', False)
        #websettings.set_property('enable-developer-extras', True) # TODO: Enable this when debugging.
        # Trying to work-around file access problems:
        #websettings.set_property('enable-xss-auditor', False)
        #websettings.set_property('allow-file-access-from-file-url', True) # Not implemented :(
        self.set_settings(websettings)
        
        # Fill the parent widget.
        self.set_hexpand(True)
        self.set_vexpand(True)
        
        # Load the panorama viewer page.
        self.load_uri(self.uri_panorama_viewer)
        
        # Disable context menu.
        self.connect('context-menu', lambda *args: True)
        
        # Set up communication from webview document to python:
        context = self.get_context()
        context.register_uri_scheme(self.custom_scheme, self._uri_scheme_cb)
    
    
    
    def load_image(self, img_uri, metadata, on_completed_cb=None):
        """Load an image into the panorama viewer.

        Args:
            img_uri:         a data uri of an image file
            metadata:        a dict containing XMP panorama tags and values.
            on_completed_cb: an optional callback function/lambda that is called 
                             after loading of the image completes.
        """
        self.pending_on_completed_cb = on_completed_cb
        
        tags_to_keys = {'XMP:FullPanoWidthPixels':          'full_width', 
                        'XMP:FullPanoHeightPixels':         'full_height', 
                        'XMP:CroppedAreaImageWidthPixels':  'cropped_width', 
                        'XMP:CroppedAreaImageHeightPixels': 'cropped_height', 
                        'XMP:CroppedAreaLeftPixels':        'cropped_x', 
                        'XMP:CroppedAreaTopPixels':         'cropped_y'
                       }
        pano_data = ', \n'.join(["%s: %d"%(key, metadata[tag]) for tag, key in tags_to_keys.items() if tag in metadata])
        script = "PSV.show_panorama('%s', {%s});"%(img_uri, pano_data)
        self.run_javascript(script)
    
    
    
    def _uri_scheme_cb(self, request):
        """Respond to a custom uri scheme request.

        Args:
            request: a WebKit2.URISchemeRequest
        """
        uri = urllib.parse.urlparse(request.get_uri())
        
        if uri.netloc == 'document_ready':
            # Call the callback.
            if self.on_loaded_cb:
                # Issue: Webkit2.WebView does not return correct JavaScript window.devicePixelRatio on hidpi devices.
                # Set the device pixel ratio from Gtk widget.
                self._set_device_pixel_ratio()
                self.on_loaded_cb()
                self.on_loaded_cb = None
        elif uri.netloc == 'show_panorama_completed':
            # Call the callback.
            if self.pending_on_completed_cb:
                self.pending_on_completed_cb()
                self.pending_on_completed_cb = None
        # Finish the request with dummy data (we do not have a new page to load).
        # Otherwise, subsequent requests and also src='data:image...' will cause an error.
        request.finish(Gio.MemoryInputStream.new_from_data([0]), -1, None)
    
    def _set_device_pixel_ratio(self):
        factor = self.get_scale_factor()
        self.run_javascript("window.devicePixelRatio = %s;"%factor)
        self.run_javascript("PhotoSphereViewer.SYSTEM.pixelRatio = %s;"%factor)
