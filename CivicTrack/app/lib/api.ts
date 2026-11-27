export type User = { id:number; name:string; email:string; role:"citizen"|"admin"|"officer"; department_id:number|null };
export type Complaint = { id:number; reference:string; title:string; description:string; category:string; subcategory:string; status:string; priority_score:number; priority_level:string; ai_confidence:number; ai_factors:string[]; ai_summary:string; ai_suggestion:string; ai_review_status:string; ai_reviewed_by:string|null; ai_review_note:string; department:string|null; department_id:number|null; officer:string|null; officer_id:number|null; latitude:number; longitude:number; landmark:string; image_url:string|null; affected_people:number; created_at:string; updated_at:string; deadline_at:string; citizen_name:string; overdue:boolean; history?:{status:string;explanation:string;actor:string;created_at:string}[]; escalations?:{level:number;reason:string;created_at:string}[]; evidence?:{note:string;image_url:string|null;created_at:string}[]; duplicates?:{score:number;reasons:string[];complaint:Complaint}[]; feedback?:{rating:number;comment:string;resolved_confirmed:boolean}[]; ai_explanation?:string[]; ai_disclaimer?:string };
export type Department={id:number;name:string;category:string;email:string};
export type Officer={id:number;name:string;email:string;role:string;department_id:number;department:string;active_assignments:number};
export type Analytics={total:number;pending:number;in_progress:number;resolved:number;overdue:number;avg_resolution_days:number;verification_rate:number;categories:{name:string;value:number}[];trend:{month:string;reported:number;resolved:number}[];departments:{department:string;score:number|null;resolved_rate:number;avg_days:number;overdue_rate:number;verified_rate:number;reopened_rate:number;citizen_rating:number|null;cases:number}[];priority:{name:string;value:number}[];demo_mode:boolean;weights:Record<string,number>};

const API_BASE=(process.env.NEXT_PUBLIC_API_BASE_URL||"").replace(/\/$/,"");
export const apiUrl=(path:string)=>API_BASE?`${API_BASE}${path}`:`/api${path}`;

export async function api<T>(path:string, token?:string|null, options:RequestInit={}):Promise<T>{
  const headers=new Headers(options.headers);
  if(token)headers.set("Authorization",`Bearer ${token}`);
  if(options.body && !(options.body instanceof FormData))headers.set("Content-Type","application/json");
  const response=await fetch(apiUrl(path),{...options,headers,cache:"no-store"});
  if(!response.ok){let message=`Request failed (${response.status})`;try{const body=await response.json();message=body.detail||message;}catch{}throw new Error(message);}
  return response.json() as Promise<T>;
}
export const json=(method:string,body:unknown):RequestInit=>({method,body:JSON.stringify(body)});
