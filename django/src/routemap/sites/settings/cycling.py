#!/usr/bin/python
# This file is part of the Waymarked Trails Map Project
# Copyright (C) 2011-2012 Sarah Hoffmann
#
# This is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

# common settings for all route maps
from siteconfig import *


# Django settings for cycling project.
_ = lambda s : s

# Project settings
ROUTEMAP_PAGEINFO = {
    # Translators: This is the category of routes for the active map view, will be preceded by site name, such as "Waymarked Trails: ".
    "maptopic" : _("Cycling"),
    "mapdescription" : _("Waymarked Trails shows cycling routes from the local to international level, with maps and information from OpenStreetMap."),
    "cssfile" : "cycling_theme.css",
    "bgimage" : "banner_bike.jpg",
    "iconimg" : "map_cycling.ico"
}

ROUTEMAP_ROUTE_TABLE = 'routemap.sites.models.CyclingRoutes'
ROUTEMAP_SCHEMA = 'cycling'
ROUTEMAP_COMPILED_SYMBOL_PATH = 'cyclingsyms'

ROUTEMAP_TILE_URL = ROUTEMAP_TILE_BASEURL + '/cycling'

ROUTEMAP_HELPPAGES = {
   'source' : PROJECTDIR + 'django/locale/%s/helppages.yaml',
   "structure" : (("about", "cycling", "osm"),
                  ("rendering", "cyclingroutes", "classification",
                   "labels", "hierarchy",
                     (("hierarchies", "text"),
                      ("hikinglocal", "ukcycle"),
                      ("elevationprofiles", "general"),
                  )),
                  ("technical", "general", "translation"),
                  ("legal", "copyright", "usage", "disclaimer"),
                  ("acknowledgements", "text"),
                  ("contact", "text")
                 )
}
