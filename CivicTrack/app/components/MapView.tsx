"use client";
import { MapContainer,TileLayer,Marker,Popup,CircleMarker,Circle,useMap,useMapEvents } from "react-leaflet";
import L from "leaflet";
import { useEffect } from "react";
import type { Complaint } from "@/app/lib/api";

const palette:Record<string,string>={"Critical":"#dc4c3f","High":"#ed9c43","Normal":"#4383e7","Low":"#56a885"};
const DEFAULT_CENTER:[number,number]=[28.615,77.211];
function markerIcon(color:string){return L.divIcon({className:"ct-marker-wrap",html:`<span class="ct-marker" style="--marker-color:${color}"></span>`,iconSize:[18,18],iconAnchor:[9,9]});}
function FlyTo({center}:{center:[number,number]}){const map=useMap();useEffect(()=>{map.flyTo(center,map.getZoom(),{duration:.7});},[center[0],center[1],map]);return null;}
export default function MapView({complaints,onOpen,compact=false,hotspots=[]}:{complaints:Complaint[];onOpen:(item:Complaint)=>void;compact?:boolean;hotspots?:{id:number;latitude:number;longitude:number;count:number}[]}){
 const center=DEFAULT_CENTER;
 return <MapContainer center={center} zoom={compact?14:14} scrollWheelZoom={!compact} zoomControl={!compact} className={compact?"map-canvas map-compact":"map-canvas"}>
  <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
  {!compact&&hotspots.map(h=><Circle key={`hotspot-${h.id}`} center={[h.latitude,h.longitude]} radius={190+Math.min(280,h.count*30)} pathOptions={{color:"#e39f48",fillColor:"#edae58",fillOpacity:.14,weight:1,dashArray:"4 5"}} />)}
  {complaints.map((c)=><Marker key={c.id} position={[c.latitude,c.longitude]} icon={markerIcon(palette[c.priority_level]||"#4383e7")} eventHandlers={{click:()=>onOpen(c)}}><Popup><div className="map-popup"><span>{c.reference}</span><strong>{c.title}</strong><small>{c.category} · {c.status}</small><button onClick={()=>onOpen(c)}>Open report <span>↗</span></button></div></Popup></Marker>)}
  {!compact&&<CircleMarker center={center} radius={56} pathOptions={{color:"#447fed",fillColor:"#4383e7",fillOpacity:.08,weight:1,dashArray:"6 6"}} />}
  <FlyTo center={center}/>
 </MapContainer>
}

function PickClick({onSelect}:{onSelect:(lat:number,lng:number)=>void}){useMapEvents({click:e=>onSelect(e.latlng.lat,e.latlng.lng)});return null;}
export function LocationPicker({latitude,longitude,onSelect}:{latitude:number;longitude:number;onSelect:(lat:number,lng:number)=>void}){
 const center:[number,number]=[latitude,longitude];
 return <MapContainer center={center} zoom={15} scrollWheelZoom className="location-picker-map"><TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><FlyTo center={center}/><PickClick onSelect={onSelect}/><Marker position={center} icon={markerIcon("#477df3")}/></MapContainer>;
}
