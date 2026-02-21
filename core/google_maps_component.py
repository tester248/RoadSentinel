"""Streamlit component for Google Maps integration with satellite view."""

import streamlit.components.v1 as components
import os


def render_google_maps(center_lat: float, center_lon: float, markers: list = None, 
                        map_type: str = 'roadmap', zoom: int = 12, 
                        api_key: str = None, height: int = 600) -> None:
    """
    Render Google Maps with markers using the Google Maps JavaScript API.
    
    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        markers: List of marker dictionaries with lat, lon, title, color, etc.
        map_type: 'roadmap', 'satellite', 'hybrid', or 'terrain'
        zoom: Initial zoom level
        api_key: Google Maps API key (required)
        height: Map height in pixels
    """
    if not api_key:
        api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
        if not api_key:
            components.html("<div style='padding:20px;background:#ffebee;border-radius:5px;'>⚠️ Google Maps API key not configured. Please set GOOGLE_MAPS_API_KEY in .env file.</div>", height=100)
            return
    
    markers = markers or []
    
    # Build markers JavaScript
    markers_js = ""
    for i, marker in enumerate(markers):
        lat = marker.get('lat', 0)
        lon = marker.get('lon', 0)
        title = marker.get('title', 'Marker').replace("'", "\\'").replace('"', '\\"')
        info = marker.get('info', '').replace("'", "\\'").replace('"', '\\"').replace('\n', '<br>')
        color = marker.get('color', 'red')
        icon = marker.get('icon', 'circle')
        
        # Map colors to Google Maps marker colors
        color_map = {
            'red': '#FF0000',
            'orange': '#FF8C00',
            'yellow': '#FFD700',
            'green': '#008000',
            'blue': '#0000FF',
            'purple': '#800080',
            'black': '#000000',
            'gray': '#808080'
        }
        marker_color = color_map.get(color, color)
        
        markers_js += f"""
        {{
            const marker{i} = new google.maps.Marker({{
                position: {{ lat: {lat}, lng: {lon} }},
                map: map,
                title: '{title}',
                icon: {{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 8,
                    fillColor: '{marker_color}',
                    fillOpacity: 0.8,
                    strokeColor: 'white',
                    strokeWeight: 2
                }}
            }});
            
            const infowindow{i} = new google.maps.InfoWindow({{
                content: '<div style="max-width:300px;"><b>{title}</b><br>{info}</div>'
            }});
            
            marker{i}.addListener('click', () => {{
                infowindow{i}.open(map, marker{i});
            }});
        }}
        """
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            #map {{
                height: 100%;
                width: 100%;
            }}
            html, body {{
                height: 100%;
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        
        <script>
            function initMap() {{
                const map = new google.maps.Map(document.getElementById("map"), {{
                    center: {{ lat: {center_lat}, lng: {center_lon} }},
                    zoom: {zoom},
                    mapTypeId: '{map_type}',
                    mapTypeControl: true,
                    mapTypeControlOptions: {{
                        style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                        position: google.maps.ControlPosition.TOP_RIGHT,
                        mapTypeIds: ['roadmap', 'satellite', 'hybrid', 'terrain']
                    }},
                    streetViewControl: true,
                    fullscreenControl: true
                }});
                
                {markers_js}
            }}
            
            window.initMap = initMap;
        </script>
        
        <script src="https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap" async defer></script>
    </body>
    </html>
    """
    
    components.html(html_code, height=height)


def render_google_maps_iframe(center_lat: float, center_lon: float, zoom: int = 12, 
                               map_type: str = 'roadmap', api_key: str = None, 
                               height: int = 600) -> None:
    """
    Render Google Maps using embed API (simpler but less interactive).
    
    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        zoom: Zoom level
        map_type: 'roadmap' or 'satellite'
        api_key: Google Maps API key
        height: Map height in pixels
    """
    if not api_key:
        api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
    
    # Note: Embed API doesn't support all features, mainly for static display
    map_type_param = 'satellite' if map_type == 'satellite' else 'roadmap'
    
    iframe_html = f"""
    <iframe
        width="100%"
        height="{height}"
        frameborder="0"
        style="border:0"
        src="https://www.google.com/maps/embed/v1/view?key={api_key}&center={center_lat},{center_lon}&zoom={zoom}&maptype={map_type_param}"
        allowfullscreen>
    </iframe>
    """
    
    components.html(iframe_html, height=height)
