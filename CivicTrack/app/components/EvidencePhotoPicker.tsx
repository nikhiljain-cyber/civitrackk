"use client";
import { useState } from "react";
import { ImagePlus, X } from "lucide-react";

export default function EvidencePhotoPicker({onChange}:{onChange:(data:string|null)=>void}){
 const [preview,setPreview]=useState("");
 const choose=(file?:File)=>{if(!file)return;if(file.size>5*1024*1024||!["image/png","image/jpeg","image/webp"].includes(file.type))return;const reader=new FileReader();reader.onload=()=>{const data=String(reader.result);setPreview(data);onChange(data);};reader.readAsDataURL(file);};
 return <label className="evidence-photo-picker">{preview?<><img src={preview} alt="Resolution evidence preview"/><span>Resolution photo selected</span><button type="button" onClick={e=>{e.preventDefault();e.stopPropagation();setPreview("");onChange(null);}}><X size={13}/> Remove</button></>:<><ImagePlus size={15}/><span>Add an optional resolution photo</span><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>choose(e.target.files?.[0])}/></>}</label>;
}
