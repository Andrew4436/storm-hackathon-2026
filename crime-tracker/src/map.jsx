// Stormhacks 2026
//Thingy for the map

import { MapContainer, TileLayer, Marker, Popup, Circle, Polygon } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import vnp from "./van_neighbourhood_polygon.json";

function Map() {
  const vancouverCenter = [49.2527, -123.1207];
  const westEnd = [49.285, -123.134];
  const neighbourhoodColors = ["#e76f51", "#2a9d8f", "#e9c46a", "#457b9d", "#9b5de5"];

  return (
    <MapContainer 
      className="map"
      center={vancouverCenter}
      zoom={12}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {vnp.neighbourhood_polygons.map((location, index) => (
        <Polygon
          key={location.name}
          positions={location.polygon}
          pathOptions={{
            color: "#ffffff",
            weight: 1,
            fillColor: neighbourhoodColors[index % neighbourhoodColors.length],
            fillOpacity: 0.55,
          }}
        />
      ))}
      // basically like a loop without the loop part
      // the parameter (location) is just the object itself
      // EG. downtown is a location, which has a name and coordinates
      {vnp.neighbourhood_polygons.map((location) => (
        <Marker position={location.center_coords}>
          <Popup>
            <h4>{location.name}</h4>
          </Popup>
        </Marker>
      ))}

      <Marker position={vancouverCenter}>
        <Popup>
          <h3>
          This is the center of the town!
          </h3>
        </Popup>
      </Marker>
      <Marker position={westEnd}>
        <Popup>
        West end
        </Popup>

      </Marker>
      <Circle center={westEnd} radius={200} color="#cf1111" />

    </MapContainer>
  );
}

export default Map;