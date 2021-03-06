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

from collections import namedtuple
from django.utils.translation import ugettext as _
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.conf import settings
from django.views.generic.simple import direct_to_template
from django.template.defaultfilters import slugify

from django.contrib.gis.gdal import SpatialReference, CoordTransform
from django.contrib.gis.geos import Point

import django.contrib.gis.geos as geos
import urllib2
import json as jsonlib
from django.utils.importlib import import_module

table_module, table_class = settings.ROUTEMAP_ROUTE_TABLE.rsplit('.',1)
table_module = import_module(table_module)

class CoordinateError(Exception):
     def __init__(self, value):
         self.value = value
     def __str__(self):
         return repr(self.value)

def get_coordinates(arg):
    coords = arg.split(',')
    if len(coords) != 4:
        # Translators: This message will very rarely be shown, and likely only to people who have manipulated the URL. For more info about bbox: http://wiki.openstreetmap.org/wiki/Bounding_Box
        raise CoordinateError(_("No valid map area specified. Check the bbox parameter in the URL."))

    try:
        coords = tuple([float(x) for x in coords])
    except ValueError:
        # Translators: This message will very rarely be shown, and likely only to people who have manipulated the URL. For more info about bbox: http://wiki.openstreetmap.org/wiki/Bounding_Box
        raise CoordinateError(_("Invalid coordinates given for the map area. Check the bbox parameter in the URL."))

    # restirct coordinates
    # It may actually happen that out-of-bounds coordinates
    # are delivered. Try browsing in New Zealand.
    coords = (max(min(180, coords[0]), -180),
              max(min(90, coords[1]), -90),
              max(min(180, coords[2]), -180),
              max(min(90, coords[3]), -90))

    if (coords[0] >= coords[2]) or (coords[1] >= coords[3]):
        raise CoordinateError(_("Invalid coordinates given for the map area. Check the bbox parameter in the URL."))

    return coords

    

def make_language_dict(request):
    """ Returns a hash with preferred languages and their weights.
        It takes into account the site language and the accept-language header.
    """

    # site language
    ret = { request.LANGUAGE_CODE : 2.0 }
    # aliases for site language
    if request.LANGUAGE_CODE in settings.LANGUAGE_ALIAS:
        for (l,w) in settings.LANGUAGE_ALIAS[request.LANGUAGE_CODE]:
            ret[l] = 1.0 + 0.5*w;

    if 'HTTP_ACCEPT_LANGUAGE' in request.META:
        for lang in request.META['HTTP_ACCEPT_LANGUAGE'].split(','):
            idx = lang.find(';')
            if idx < 0:
                w = 1.0
            else:
                try:
                    w = float(lang[idx+3:])
                except ValueError:
                    w = 0.0
                lang = lang[:idx]
            if w > 0.0 and (len(lang) == 2 or (len(lang) > 2 and lang[2] == '-')):
                lang = lang[:2]
                if lang not in ret or ret[lang] < w:
                    ret[lang] = w
                    if lang in settings.LANGUAGE_ALIAS:
                        for (l,wa) in settings.LANGUAGE_ALIAS[lang]:
                            if l not in ret:
                                ret[l] = w - 0.001*(2.0-wa)

    if 'en' not in ret:
       ret['en'] = 0.0

    return ret

def _make_display_length(length):
    if length < 1:
        return _("%s m") % int(round(length * 100) * 10)
    elif length < 10:
        return _("%s km") % ("%.1f" % length)
    else:
        return _("%s km") % int(round(length))

def info(request, route_id=None):
    langdict = make_language_dict(request)
    langlist = sorted(langdict, key=langdict.get)
    langlist.reverse()

    qs = getattr(table_module, table_class).objects.filter(id=route_id).extra(
                select={'length' : 
                         """ST_length2d_spheroid(ST_Transform(geom,4326),
                             'SPHEROID["WGS 84",6378137,298.257223563,
                             AUTHORITY["EPSG","7030"]]')/1000"""})
    if len(qs) <= 0:
        return direct_to_template(request, 'routes/info_error.html', {'id' : route_id})

    rel = qs[0]
    loctags = rel.tags().get_localized_tagstore(langdict)

    # Translators: The length of a route is presented with two values, this is the
    #              length that has been mapped so far and is actually visible on the map.
    infobox = [(_("Mapped length"), _make_display_length(rel.length))]
    dist = loctags.get_as_length(('distance', 'length'), unit='km')
    if dist:
        # Translators: The length of a route is presented with two values, this is the
        #              length given in the information about the route.
        #              More information about specifying route length in OSM here: 
        #              http://wiki.openstreetmap.org/wiki/Key:distance
        infobox.append((_("Official length"), _make_display_length(dist)))
    if 'operator' in loctags:
        # Translators: This is someone responsible for maintaining the route. Normally 
        #              an organisation. Read more: http://wiki.openstreetmap.org/wiki/Key:operator
        infobox.append((_("Operator"), loctags['operator']))
    rel.localize_name(langlist)

    return direct_to_template(request, 'routes/info.html', 
            {'route': rel,
             'infobox' : infobox,
             'loctags' : loctags,
             'show_elevation_profile' : settings.SHOW_ELEV_PROFILE,
             'superroutes' : rel.superroutes(langlist),
             'subroutes' : rel.subroutes(langlist),
             'symbolpath' : settings.ROUTEMAP_COMPILED_SYMBOL_PATH})

def wikilink(request, route_id=None):
    """ Return a redirect page to the Wikipedia page using the
        language preferences of the user.
    """
    langdict = make_language_dict(request)
    langlist = sorted(langdict, key=langdict.get)
    langlist.reverse()

    try:
        rel = getattr(table_module, table_class).objects.get(id=route_id)
    except:
        raise Http404

    wikientries = rel.tags().get_wikipedia_tags()

    if len(wikientries) == 0:
        raise Http404

    link = None
    outlang = None
    for lang in langlist:
        if lang in wikientries:
            outlang = lang
            link = wikientries[lang]
            break

        for k,v in wikientries.iteritems():
            if not v.startswith('http'):
                try:
                    url = "http://%s.wikipedia.org/w/api.php?action=query&prop=langlinks&titles=%s&llurl=true&&lllang=%s&format=json" % (k,urllib2.quote(v.encode('utf8')),lang)
                    req = urllib2.Request(url, headers={
                        'User-Agent' : 'Python-urllib/2.7 Routemaps (report problems to %s)' % settings.ADMINS[0][1]
                        })
                    data = urllib2.urlopen(req).read()
                    data = jsonlib.loads(data)
                    (pgid, data) = data["query"]["pages"].popitem()
                    if 'langlinks' in data:
                        link = data['langlinks'][0]['url']
                        break
                except:
                    break # oh well, we tried
        if link is not None:
            break


    # given up to find a requested language
    if link is None:
        outlang, link = wikientries.popitem()

    # paranoia, avoid HTML injection
    link.replace('"', '%22')
    link.replace("'", '%27')
    if not link.startswith('http:'):
        link = 'http://%s.wikipedia.org/wiki/%s' % (outlang, link)

    return HttpResponseRedirect(link)


def gpx(request, route_id=None):
    try:
        rel = getattr(table_module, table_class).objects.filter(id=route_id).transform(srid=4326)[0]
    except:
        return direct_to_template(request, 'routes/info_error.html', {'id' : route_id})
    if isinstance(rel.geom, geos.LineString):
        outgeom = (rel.geom, )
    else:
        outgeom = rel.geom
    resp = direct_to_template(request, 'routes/gpx.xml', {'route' : rel, 'geom' : outgeom}, mimetype='application/gpx+xml')
    resp['Content-Disposition'] = 'attachment; filename=%s.gpx' % slugify(rel.name)
    return resp

def json(request, route_id=None):
    try:
        rel = getattr(table_module, table_class).objects.get(id=route_id)
    except:
        return direct_to_template(request, 'routes/info_error.html', {'id' : route_id})
    nrpoints = rel.geom.num_coords
    #print nrpoints
    if nrpoints > 50000:
        rel.geom = rel.geom.simplify(100.0)
    if nrpoints > 10000:
        rel.geom = rel.geom.simplify(20.0)
    elif nrpoints > 1000:
        rel.geom = rel.geom.simplify(10.0)
    elif nrpoints > 300:
        rel.geom = rel.geom.simplify(5.0)
    #print rel.geom.num_coords
    return HttpResponse(rel.geom.json, content_type="text/json")
    
# get distance from user point to relation    
def dist(request, route_id=None):
    try:
        rel = getattr(table_module, table_class).objects.get(id=route_id)
    except:
        return direct_to_template(request, 'routes/info_error.html', {'id' : route_id})
    
    # Coordinate systems
    sphericalCoord = SpatialReference(900913)
    geographicCoord = SpatialReference(4326)
    targetCoord = SpatialReference(32633)

    # Transformations
    sphericalTrans = CoordTransform(sphericalCoord, targetCoord)
    geographicTranc = CoordTransform(geographicCoord, targetCoord)
    
    
    try:
        lat = request.GET.get('lat', '')
        lon = request.GET.get('lon', '')
        userPoint = Point(float(lon), float(lat), srid=4326)
        userPoint.transform(geographicTranc)


        # Check for multilinestring
        if type(rel.geom[0][0]) is tuple:
    
            distStartPoint = float('inf')
            distEndPoint = float('inf')
    
            for linestring in rel.geom:
                # Get start/end point
                startPoint = Point(linestring[0][0], linestring[0][1], srid=900913)
                endPoint = Point(linestring[-1][0], linestring[-1][1], srid=900913)

                # Transform coordinates
                startPoint.transform(sphericalTrans)

                # Distance to start/end point
                tmpDistStartPoint = startPoint.distance(userPoint)
                if tmpDistStartPoint<distStartPoint:
                    distStartPoint = tmpDistStartPoint
        
                tmpDistEndPoint = endPoint.distance(userPoint)
                if tmpDistStartPoint<distEndPoint:
                    distEndPoint = tmpDistEndPoint
        
        else:
            # Get start/end point
            startPoint = Point(rel.geom[0][0], rel.geom[0][1], srid=900913)
            endPoint = Point(rel.geom[-1][0], rel.geom[-1][1], srid=900913)

            # Transform coordinates
            startPoint.transform(sphericalTrans)

            # Distance to start/end point
            distStartPoint = startPoint.distance(userPoint)
            distEndPoint = endPoint.distance(userPoint)
        
        response_data={'route_id': route_id, 'minDistance': round(min(distStartPoint, distEndPoint), 0)}
    except:
        response_data={'route_id': route_id, 'minDistance': 'unknown'}
        
    return HttpResponse(jsonlib.dumps(response_data), content_type="text/json")

def json_box(request):
    try:
        coords = get_coordinates(request.GET.get('bbox', ''))
    except CoordinateError as e:
        return direct_to_template(request, 'routes/error.html', 
                {'msg' : e.value})
    
    ids = []
    for i in request.GET.get('ids', '').split(','):
        try:
            ids.append(int(i))
        except ValueError:
            pass # ignore

    if not ids:
        return HttpResponse('[]', content_type="text/json")

    ids = ids[:settings.ROUTEMAP_MAX_ROUTES_IN_LIST]

    selquery = ("""ST_Intersection(st_transform(ST_SetSRID(
                     'BOX3D(%f %f, %f %f)'::Box3d,4326),%%s) , geom)
               """ % coords) % settings.DATABASES['default']['SRID']
    ydiff = 10*(coords[3]-coords[1])

    if ydiff > 1:
        selquery = "ST_Simplify(%s, %f)"% (selquery, ydiff*ydiff*ydiff/2)
    selquery = "ST_AsGeoJSON(%s)" % selquery

    qs = getattr(table_module, table_class).objects.filter(id__in=ids).extra(
            select={'way' : selquery}).only('id')
    # print qs.query

    return direct_to_template(request, 'routes/route_box.json',
                              { 'rels' : qs },
                              mimetype="text/html")



RouteList = namedtuple('RouteList', 'title shorttitle routes')

def list(request):
    try:
        coords = get_coordinates(request.GET.get('bbox', ''))
    except CoordinateError as e:
        return direct_to_template(request, 'routes/error.html', 
                {'msg' : e.value})


    qs = getattr(table_module, table_class).objects.filter(top=True).extra(where=(("""
            id = ANY(SELECT DISTINCT h.parent
                     FROM hierarchy h,
                          (SELECT DISTINCT unnest(rels) as rel
                           FROM segments
                           WHERE geom && st_transform(ST_SetSRID(
                             'BOX3D(%f %f, %f %f)'::Box3d,4326),%%s)) as r
                     WHERE h.child = r.rel)""" 
            % coords) % settings.DATABASES['default']['SRID'],)).order_by('level')
    #print qs.query
    
    objs = (RouteList(_('continental'), 'int', []),
            RouteList(_('national'), 'nat', []),
            RouteList(_('regional'), 'reg', []),
            RouteList(_('other'), 'other', []),
           )
    osmids = []
    numobj = 0
    langdict = make_language_dict(request)
    langlist = sorted(langdict, key=langdict.get)
    langlist.reverse()

    for rel in qs[:settings.ROUTEMAP_MAX_ROUTES_IN_LIST]:
        listnr = min(3, rel.level / 10)
        rel.localize_name(langlist)
        objs[listnr].routes.append(rel)
        osmids.append(str(rel.id))
        numobj += 1

    if request.flavour == 'mobile':
        ismobile = True
    else:
        ismobile = False
    return direct_to_template(request,
            'routes/list.html', 
             {'objs' : objs,
              'ismobile': ismobile,
              'osmids' : ','.join(osmids),
              'hasmore' : numobj == settings.ROUTEMAP_MAX_ROUTES_IN_LIST,
              'symbolpath' : settings.ROUTEMAP_COMPILED_SYMBOL_PATH,
              'bbox' : request.GET.get('bbox', '')})

