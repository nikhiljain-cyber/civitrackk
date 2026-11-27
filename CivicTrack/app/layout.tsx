import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "./overlays.css";
import "./auth.css";
import "./responsive.css";
import "./forms.css";
import "./extras.css";
import "./officer.css";
import "./responsiveextra.css";
import "./policies.css";
import "./professional.css";
import "./landing.css";
import "./auth-final.css";

export const metadata:Metadata={title:"CivicTrack | Report. Track. Improve.",description:"A transparent civic issue reporting and accountability platform."};
export default function RootLayout({children}:{children:React.ReactNode}){
  return <html lang="en"><body>{children}</body></html>;
}
