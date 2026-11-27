"use client";
import { useEffect, useState } from "react";
import { apiUrl } from "@/app/lib/api";

export default function SecureImage({path,token,alt}:{path:string;token:string;alt:string}){
 const [src,setSrc]=useState("");
 useEffect(()=>{let url="";const controller=new AbortController();fetch(apiUrl(path),{headers:{Authorization:`Bearer ${token}`},signal:controller.signal,cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Image unavailable");return r.blob()}).then(blob=>{url=URL.createObjectURL(blob);setSrc(url)}).catch(()=>{});return()=>{controller.abort();if(url)URL.revokeObjectURL(url);setSrc("");};},[path,token]);
 return src?<img src={src} alt={alt}/>:<div className="secure-image-loading">Private evidence image</div>;
}
