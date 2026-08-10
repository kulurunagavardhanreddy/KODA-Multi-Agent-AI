# image_tools.py

from langchain_core.tools import tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
import requests
import urllib.parse
import html
from ddgs import DDGS
import math

GEOCODE_CACHE = {}

@tool
def local_places_tool(query: str, location: str = "") -> str:
    """Searches for detailed information about a local place (hospital, hotel, restaurant, landmark, etc.).
    Use this when the user asks for details, ratings, images, hours, map link, or navigation to a specific place or type of place nearby.
    Pass the specific name of the place as 'query' and the city/area as 'location'.
    """
    search_query = f"{query} {location}".strip()
    try:
        wrapper = DuckDuckGoSearchAPIWrapper()
        text_query = f"{search_query} address hours rating reviews"
        results = wrapper.results(text_query, max_results=3)
        
        print(f"🏪 [Local Places] DuckDuckGo found results for '{text_query}':")
        for r in results:
            print(f"   -> {r.get('link')}")
        
        image_url = ""
        try:
            with DDGS() as ddgs:
                img_results = list(ddgs.images(f"{search_query} building exterior", max_results=1))
                if img_results:
                    image_url = img_results[0].get("image", "")
        except Exception as img_e:
            print(f"⚠️ [Image Search] Failed: {img_e}")
        
        encoded_query = urllib.parse.quote(search_query)
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={encoded_query}&travelmode=driving&dir_action=navigate"
        
        preview_img = image_url if image_url else "https://images.unsplash.com/photo-1478860409682-ce295931e5f1?auto=format&fit=crop&q=80&w=400&h=180"
        safe_title = html.escape(query)
        html_card = f"""\t\t\t<div class="koda-map-card" onclick="window.open('{maps_link}', '_blank')">
                <div class="map-preview">
                    <img src="{preview_img}" alt="Location Preview">
                    <div class="status-badge">Location Found</div>
                </div>
                <div class="card-content">
                    <div class="location-info">
                        <div class="dot-indicator"></div>
                        <div class="text-block">
                            <h3>{safe_title}</h3>
                            <p>Click to navigate via Google Maps</p>
                        </div>
                    </div>
                    <div class="nav-button">View Location <span class="arrow">→</span></div>
                </div>
            </div>
        """

        response = f"TARGET PLACE: {query}\n"
        response += "\nWEB SEARCH RESULTS (Extract address, rating, and hours from here):\n"
        response += "\n".join([res.get('snippet', '') for res in results])
        
        response += f"\n\nCRITICAL INSTRUCTION: First, write a friendly conversational response summarizing the place details. Then, you MUST embed this EXACT HTML block below your text to display the interactive premium card. DO NOT modify the HTML and Do NOT wrap the HTML in code backticks (```).\n\nHTML CARD:\n{html_card}\n\nBelow the card, also provide this Direct Link: {maps_link}"
        return response
    except Exception as e:
        return f"Failed to fetch place details: {e}"

@tool
def route_distance_tool(origin: str, destination: str) -> str:
    """Calculates the exact driving distance and estimated travel time between an origin and a destination.
    Always use this tool for 'distance', 'how far', 'route', 'directions', 'map link', or 'navigation' queries. 
    Pass the user's raw GPS coordinates (e.g. '17.4588,78.3635') as the origin if asking from their current location.
    """
    try:
        headers = {'User-Agent': 'NexaFetchBot/1.0'}
        
        def get_coords(location: str):
            loc_clean = location.replace(" ", "")
            if "," in loc_clean:
                parts = loc_clean.split(",")
                if len(parts) == 2:
                    try:
                        return float(parts[0]), float(parts[1])
                    except ValueError:
                        pass
            
            loc_lower = location.lower().strip()
            if loc_lower in GEOCODE_CACHE:
                return GEOCODE_CACHE[loc_lower]

            safe_loc = urllib.parse.quote(location)
            url = f"https://nominatim.openstreetmap.org/search?q={safe_loc}&format=json&limit=1"
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200 and resp.json():
                data = resp.json()[0]
                coords = (float(data['lat']), float(data['lon']))
                GEOCODE_CACHE[loc_lower] = coords
                return coords
                
            if "," in location or " " in location:
                fallback_loc = location.split(",")[0].split(" ")[0].strip()
                safe_loc2 = urllib.parse.quote(fallback_loc)
                url2 = f"https://nominatim.openstreetmap.org/search?q={safe_loc2}&format=json&limit=1"
                resp2 = requests.get(url2, headers=headers, timeout=5)
                if resp2.status_code == 200 and resp2.json():
                    data = resp2.json()[0]
                    coords = (float(data['lat']), float(data['lon']))
                    GEOCODE_CACHE[loc_lower] = coords
                    return coords
                
            try:
                from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
                import re
                wrapper = DuckDuckGoSearchAPIWrapper()
                search_res = wrapper.results(f"{location} exact latitude longitude coordinates", max_results=2)
                for r in search_res:
                    snip = r.get('snippet', '')
                    matches = re.findall(r'(-?\d{1,2}\.\d{3,})[^\d-]+(-?\d{1,3}\.\d{3,})', snip)
                    if matches:
                        coords = (float(matches[0][0]), float(matches[0][1]))
                        GEOCODE_CACHE[loc_lower] = coords
                        return coords
            except: pass
            return None, None

        orig_lat, orig_lon = get_coords(origin)
        dest_lat, dest_lon = get_coords(destination)

        if orig_lat is None: return f"Could not find coordinates for origin: {origin}. Please inform the user that the location could not be mapped."
        if dest_lat is None: return f"Could not find coordinates for destination: {destination}. Please inform the user that the location could not be mapped."

        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={dest_lat},{dest_lon}&travelmode=driving&dir_action=navigate"
        static_map_url = f"https://static-maps.yandex.ru/1.x/?lang=en_US&l=map&size=400,180&pt={orig_lon},{orig_lat},pm2rdl~{dest_lon},{dest_lat},pm2blm"
        safe_dest = html.escape(destination)
        
        dist_str = "Route mapped via Google Maps"
        osrm_success = False
        
        try:
            osrm_url = f"http://router.project-osrm.org/route/v1/driving/{orig_lon},{orig_lat};{dest_lon},{dest_lat}?overview=false"
            resp = requests.get(osrm_url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok":
                    route = data["routes"][0]
                    dist_km = route["distance"] / 1000.0
                    duration_min = route["duration"] / 60.0
                    hours = int(duration_min // 60)
                    mins = int(duration_min % 60)
                    dist_str = f"ETA: <strong>{hours} hr {mins} min</strong> &bull; Dist: <strong>{dist_km:.1f} km</strong>"
                    osrm_success = True
        except Exception as osrm_e:
            print(f"⚠️ [OSRM Route Error] {osrm_e}")

        if not osrm_success:
            def haversine(lat1, lon1, lat2, lon2):
                R = 6371.0
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                return R * c
            
            est_dist_km = haversine(orig_lat, orig_lon, dest_lat, dest_lon) * 1.3
            est_duration_min = (est_dist_km / 50.0) * 60
            hours = int(est_duration_min // 60)
            mins = int(est_duration_min % 60)
            dist_str = f"ETA: ~<strong>{hours} hr {mins} min</strong> &bull; Dist: ~<strong>{est_dist_km:.1f} km</strong>"

        html_card = f"""
  <div class="koda-map-card" onclick="window.open('{maps_link}', '_blank')">
    <div class="map-preview">
      <img src="{static_map_url}" alt="Route Preview">
      <div class="status-badge">Fastest Route</div>
    </div>
    <div class="card-content">
      <div class="location-info">
        <div class="dot-indicator"></div>
        <div class="text-block">
          <h3>{safe_dest}</h3>
          <p>{dist_str}</p>
        </div>
      </div>
      <div class="nav-button">Start Navigation <span class="arrow">→</span></div>
    </div>
  </div>
"""
        plain_dist = dist_str.replace('<strong>', '').replace('</strong>', '').replace('&bull;', '•')
        
        return f"""SUCCESS! Route generated.
        
ROUTE FACTS:
- Destination: {destination}
- {plain_dist}
- Direct Maps Link: {maps_link}

CRITICAL INSTRUCTIONS FOR YOUR RESPONSE:
1. FIRST, write a friendly conversational response explaining the distance and ETA to the user.
2. SECOND, you MUST embed the EXACT HTML block below at the very bottom of your text to display the interactive premium route card. 
3. DO NOT modify the HTML. Do NOT add markdown formatting (like **) inside the HTML. Do NOT wrap the HTML in code backticks (```).

{html_card}"""
        
    except Exception as e:
        return f"Error calculating distance: {e}"
