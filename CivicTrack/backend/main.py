from __future__ import annotations
import base64, binascii, csv, hashlib, io, json, math, mimetypes, os, re, secrets, time
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    Image, PIL_AVAILABLE = None, False
try:
    from sklearn.cluster import DBSCAN
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

ROOT=Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT.parent/".env")
except ImportError:
    pass
UPLOAD_DIR=Path(os.getenv("UPLOAD_DIR",str(ROOT/"uploads"))); UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
DATABASE_URL=os.getenv("DATABASE_URL", f"sqlite:///{ROOT/'civictrack.db'}")
JWT_SECRET=os.getenv("JWT_SECRET", "civictrack-demo-key-change-before-deployment"); JWT_ALGORITHM="HS256"
DEMO_MODE=os.getenv("DEMO_MODE","true").lower()=="true"
engine=create_engine(DATABASE_URL,connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False); bearer=HTTPBearer(auto_error=False)
CATEGORIES=["Road damage","Waste management","Water supply","Drainage & sewage","Street lighting","Public infrastructure","Electricity","Public sanitation","Other"]
STATUSES=["Pending","Under Review","Assigned","In Progress","Awaiting Verification","Resolved","Reopened","Rejected"]
DEADLINES={"Road damage":72,"Waste management":48,"Water supply":24,"Drainage & sewage":36,"Street lighting":72,"Public infrastructure":120,"Electricity":24,"Public sanitation":48,"Other":96}
DEFAULT_INDEX_WEIGHTS={"resolution_rate":30,"resolution_time":20,"overdue_rate":20,"citizen_verification":15,"reopened_rate":5,"citizen_satisfaction":10}
try:
    _configured_weights=json.loads(os.getenv("CIVICTRACK_INDEX_WEIGHTS","{}"))
    INDEX_WEIGHTS={**DEFAULT_INDEX_WEIGHTS,**_configured_weights}
    if set(INDEX_WEIGHTS)!=set(DEFAULT_INDEX_WEIGHTS) or sum(INDEX_WEIGHTS.values())!=100 or any(not isinstance(v,int) or v<0 or v>100 for v in INDEX_WEIGHTS.values()):INDEX_WEIGHTS=DEFAULT_INDEX_WEIGHTS
except (ValueError,TypeError):INDEX_WEIGHTS=DEFAULT_INDEX_WEIGHTS
DEMO_DEPARTMENTS=["Roads & Transport","Sanitation","Water Works","Public Lighting","Electrical Services"]
DEMO_PASSWORD="civictrack123"
def utcnow()->datetime:return datetime.now(timezone.utc).replace(tzinfo=None)
LOGIN_ATTEMPTS:dict[str,deque[float]]=defaultdict(deque)

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(100)); email:Mapped[str]=mapped_column(String(180),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(300)); role:Mapped[str]=mapped_column(String(20),index=True); department_id:Mapped[Optional[int]]=mapped_column(ForeignKey("departments.id"),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Department(Base):
    __tablename__="departments"
    id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120),unique=True); category:Mapped[str]=mapped_column(String(80)); email:Mapped[str]=mapped_column(String(180),default=""); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Complaint(Base):
    __tablename__="complaints"
    id:Mapped[int]=mapped_column(primary_key=True); reference:Mapped[str]=mapped_column(String(32),unique=True,index=True); title:Mapped[str]=mapped_column(String(180)); description:Mapped[str]=mapped_column(Text); category:Mapped[str]=mapped_column(String(80),index=True); subcategory:Mapped[str]=mapped_column(String(120),default="General"); status:Mapped[str]=mapped_column(String(40),default="Pending",index=True); priority_score:Mapped[int]=mapped_column(Integer,default=35,index=True); priority_level:Mapped[str]=mapped_column(String(20),default="Normal"); ai_confidence:Mapped[float]=mapped_column(Float,default=0.0); ai_factors:Mapped[str]=mapped_column(Text,default=""); ai_summary:Mapped[str]=mapped_column(Text,default=""); citizen_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True); department_id:Mapped[Optional[int]]=mapped_column(ForeignKey("departments.id"),nullable=True,index=True); officer_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True,index=True); latitude:Mapped[float]=mapped_column(Float); longitude:Mapped[float]=mapped_column(Float); landmark:Mapped[str]=mapped_column(String(180),default=""); image_url:Mapped[Optional[str]]=mapped_column(String(300),nullable=True); image_hash:Mapped[Optional[str]]=mapped_column(String(32),nullable=True); affected_people:Mapped[int]=mapped_column(Integer,default=1); age_hours:Mapped[int]=mapped_column(Integer,default=0); deadline_at:Mapped[datetime]=mapped_column(DateTime); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,index=True); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)
    ai_suggestion:Mapped[str]=mapped_column(String(80),default="Other")
    ai_review_status:Mapped[str]=mapped_column(String(24),default="Pending")
    ai_reviewed_by_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True)
    ai_review_note:Mapped[str]=mapped_column(String(500),default="")
    ai_reviewed_at:Mapped[Optional[datetime]]=mapped_column(DateTime,nullable=True)
class StatusHistory(Base):
    __tablename__="complaint_status_history"
    id:Mapped[int]=mapped_column(primary_key=True); complaint_id:Mapped[int]=mapped_column(ForeignKey("complaints.id"),index=True); status:Mapped[str]=mapped_column(String(40)); explanation:Mapped[str]=mapped_column(Text); actor_id:Mapped[int]=mapped_column(ForeignKey("users.id")); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Notification(Base):
    __tablename__="notifications"
    id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey("users.id"),index=True); title:Mapped[str]=mapped_column(String(140)); message:Mapped[str]=mapped_column(String(400)); complaint_id:Mapped[Optional[int]]=mapped_column(ForeignKey("complaints.id"),nullable=True); read:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Feedback(Base):
    __tablename__="citizen_feedback"
    id:Mapped[int]=mapped_column(primary_key=True); complaint_id:Mapped[int]=mapped_column(ForeignKey("complaints.id"),index=True); citizen_id:Mapped[int]=mapped_column(ForeignKey("users.id")); rating:Mapped[int]=mapped_column(Integer); comment:Mapped[str]=mapped_column(String(500),default=""); resolved_confirmed:Mapped[bool]=mapped_column(Boolean); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class ResolutionEvidence(Base):
    __tablename__="resolution_evidence"
    id:Mapped[int]=mapped_column(primary_key=True); complaint_id:Mapped[int]=mapped_column(ForeignKey("complaints.id"),index=True); officer_id:Mapped[int]=mapped_column(ForeignKey("users.id")); note:Mapped[str]=mapped_column(String(500)); image_url:Mapped[Optional[str]]=mapped_column(String(300),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class Escalation(Base):
    __tablename__="escalation_events"
    id:Mapped[int]=mapped_column(primary_key=True); complaint_id:Mapped[int]=mapped_column(ForeignKey("complaints.id"),index=True); level:Mapped[int]=mapped_column(Integer,default=1); reason:Mapped[str]=mapped_column(String(300)); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
class ServicePolicy(Base):
    __tablename__="service_policies"
    category:Mapped[str]=mapped_column(String(80),primary_key=True); deadline_hours:Mapped[int]=mapped_column(Integer,default=72); escalation_grace_hours:Mapped[int]=mapped_column(Integer,default=24); updated_by_id:Mapped[Optional[int]]=mapped_column(ForeignKey("users.id"),nullable=True); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)
class DuplicateCandidate(Base):
    __tablename__="duplicate_candidates"
    id:Mapped[int]=mapped_column(primary_key=True); complaint_id:Mapped[int]=mapped_column(ForeignKey("complaints.id"),index=True); candidate_id:Mapped[int]=mapped_column(ForeignKey("complaints.id"),index=True); score:Mapped[float]=mapped_column(Float); reasons:Mapped[str]=mapped_column(String(400))
class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[int]=mapped_column(primary_key=True); actor_id:Mapped[int]=mapped_column(ForeignKey("users.id")); action:Mapped[str]=mapped_column(String(120)); entity_type:Mapped[str]=mapped_column(String(60)); entity_id:Mapped[str]=mapped_column(String(60)); details:Mapped[str]=mapped_column(String(500),default=""); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class RegisterRequest(BaseModel): name:str=Field(min_length=2,max_length=100); email:str=Field(min_length=5,max_length=180); password:str=Field(min_length=8,max_length=120)
class LoginRequest(BaseModel): email:str; password:str
class ComplaintCreate(BaseModel):
    title:str=Field(min_length=5,max_length=180); description:str=Field(min_length=15,max_length=5000); category:Optional[str]=None; subcategory:str="General"; latitude:float=Field(ge=-90,le=90); longitude:float=Field(ge=-180,le=180); landmark:str=Field(default="",max_length=180); affected_people:int=Field(default=1,ge=1,le=100000); age_hours:int=Field(default=0,ge=0,le=8760); image_data:Optional[str]=None
class StatusRequest(BaseModel): status:str; explanation:str=Field(min_length=4,max_length=500); evidence_note:Optional[str]=Field(default=None,max_length=500); evidence_image_data:Optional[str]=None
class AssignmentRequest(BaseModel): department_id:int; officer_id:Optional[int]=None; explanation:str=Field(default="Assigned by administrator",max_length=500)
class AIReviewRequest(BaseModel): category:str; priority_score:int=Field(ge=0,le=100); explanation:str=Field(min_length=4,max_length=500)
class VerifyRequest(BaseModel): confirmed:bool; rating:int=Field(default=5,ge=1,le=5); comment:str=Field(default="",max_length=500)
class DepartmentRequest(BaseModel): name:str=Field(min_length=3,max_length=120); category:str=Field(min_length=3,max_length=80); email:str=""
class OfficerCreateRequest(BaseModel): name:str=Field(min_length=2,max_length=100); email:str=Field(min_length=5,max_length=180); password:str=Field(min_length=8,max_length=120); department_id:int
class ReadRequest(BaseModel): read:bool=True
class ServicePolicyRequest(BaseModel): deadline_hours:int=Field(ge=1,le=8760); escalation_grace_hours:int=Field(ge=0,le=8760)

@asynccontextmanager
async def lifespan(_app):
    Base.metadata.create_all(engine)
    if not DEMO_MODE and JWT_SECRET=="civictrack-demo-key-change-before-deployment":raise RuntimeError("Set a unique JWT_SECRET when DEMO_MODE is disabled")
    with SessionLocal() as db:
        if DEMO_MODE:seed_demo(db)
        else:seed_service_policies(db)
    yield

app=FastAPI(title="CivicTrack API",version="1.0.0",description="Civic issue reporting and accountability API",lifespan=lifespan)
allowed_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS","http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware,allow_origins=allowed_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

def password_hash(password:str)->str:
    salt=secrets.token_hex(16); hashed=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),240_000).hex(); return f"{salt}${hashed}"
def password_ok(password:str,stored:str)->bool:
    try:
        salt,expected=stored.split("$",1); actual=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),240_000).hex(); return secrets.compare_digest(actual,expected)
    except Exception:return False
def token_for(user:User)->str:
    now=datetime.now(timezone.utc); return jwt.encode({"sub":str(user.id),"role":user.role,"iat":now,"exp":now+timedelta(hours=12)},JWT_SECRET,algorithm=JWT_ALGORITHM)
def get_db():
    db=SessionLocal()
    try:yield db
    finally:db.close()
def current_user(credentials:Optional[HTTPAuthorizationCredentials]=Depends(bearer),db:Session=Depends(get_db))->User:
    if not credentials:raise HTTPException(401,"Sign in to continue")
    try:
        payload=jwt.decode(credentials.credentials,JWT_SECRET,algorithms=[JWT_ALGORITHM]); user=db.get(User,int(payload["sub"]))
    except (JWTError,KeyError,ValueError):user=None
    if not user:raise HTTPException(401,"Your session is invalid or has expired")
    return user
def require_role(*roles:str):
    def check(user:User=Depends(current_user))->User:
        if user.role not in roles:raise HTTPException(403,"This action is not available for your role")
        return user
    return check
def user_payload(u:User)->dict[str,Any]:return {"id":u.id,"name":u.name,"email":u.email,"role":u.role,"department_id":u.department_id}
def area_for(c:str)->str:return {"Road damage":"Roads & Transport","Waste management":"Sanitation","Water supply":"Water Works","Drainage & sewage":"Water Works","Street lighting":"Public Lighting","Public infrastructure":"Roads & Transport","Electricity":"Electrical Services","Public sanitation":"Sanitation"}.get(c,"City Services")
def policy_for(db:Session,category:str)->ServicePolicy|None:return db.get(ServicePolicy,category)

def priority_for(text:str,people:int,age_hours:int,has_image:bool)->tuple[int,str,list[str]]:
    lower=text.lower(); score=20; factors=[]
    if any(w in lower for w in ["injur","accident","exposed wire","electric shock","school zone","hospital","fire","collapse","danger"]):score+=34;factors.append("Safety language detected (+34)")
    if any(w in lower for w in ["severe","major","blocked","overflow","flood","deep pothole","urgent","contaminat"]):score+=18;factors.append("High severity terms (+18)")
    if people>=100:score+=16;factors.append("Large reported impact (+16)")
    elif people>=20:score+=10;factors.append("Community impact reported (+10)")
    elif people>=5:score+=5;factors.append("Several people affected (+5)")
    if age_hours>=168:score+=8;factors.append("Issue ongoing for a week (+8)")
    elif age_hours>=48:score+=5;factors.append("Issue ongoing for more than two days (+5)")
    if has_image:score+=4;factors.append("Supporting photo provided (+4)")
    score=min(score,100); level="Critical" if score>=75 else "High" if score>=55 else "Normal" if score>=30 else "Low"
    return score,level,factors or ["Baseline civic service priority (+20)"]

TRAINING={"Road damage":["pothole broken road asphalt crater damaged pavement road surface","street is cracked and unsafe for cars and bicycles","road sinkhole needs repair"],"Waste management":["garbage trash waste overflowing bin collection missed","dumped rubbish bags litter not picked up","sanitation truck did not collect waste"],"Water supply":["water pipe leaking burst pipe water supply low pressure","no water from tap water outage","drinking water contaminated"],"Drainage & sewage":["drain blocked sewage overflow flooding street","storm drain clogged wastewater is spilling","manhole backed up after rain"],"Street lighting":["street light lamp is out dark road pole","broken traffic signal lighting at night","streetlight flickering"],"Public infrastructure":["broken sidewalk footpath damaged bench public structure","park equipment broken railing damaged","unsafe public stairs"],"Electricity":["exposed electrical wire power outage electric pole sparks","transformer damaged power cables","electricity hazard"],"Public sanitation":["public toilet restroom washroom dirty sanitation","public washroom needs cleaning","toilet facilities are unusable"],"Other":["noise issue public nuisance civic service","other civic issue not listed","general municipal problem"]}
_vectorizer=_classifier=None
if SKLEARN_AVAILABLE:
    try:
        examples=[(s,c) for c,docs in TRAINING.items() for s in docs]; _vectorizer=TfidfVectorizer(ngram_range=(1,2),stop_words="english",sublinear_tf=True); X=_vectorizer.fit_transform([x[0] for x in examples]); _classifier=LogisticRegression(max_iter=500,random_state=7).fit(X,[x[1] for x in examples])
    except Exception:_vectorizer=_classifier=None
def classify(text:str,selected:Optional[str]=None)->tuple[str,float,list[str]]:
    if _classifier is not None:
        probs=_classifier.predict_proba(_vectorizer.transform([text]))[0]; ix=int(probs.argmax()); category=_classifier.classes_[ix]; confidence=float(probs[ix]); reasons=[f"Text patterns most closely match {category.lower()} reports"]
        terms=[w for w in re.findall(r"[a-z]{4,}",text.lower()) if any(w in s for s in TRAINING[category])][:4]
        if terms:reasons.append("Matched terms: "+", ".join(terms))
    else:
        lower=text.lower(); keywords={"Road damage":["pothole","road","asphalt","crater","pavement"],"Waste management":["garbage","trash","waste","litter","rubbish"],"Water supply":["water","pipe","leak","tap"],"Drainage & sewage":["drain","sewage","flood","overflow"],"Street lighting":["light","lamp","streetlight","dark"],"Electricity":["electric","wire","power","transformer"],"Public sanitation":["toilet","restroom","washroom"],"Public infrastructure":["sidewalk","footpath","bench","park"]}; scores={c:sum(lower.count(w) for w in ws) for c,ws in keywords.items()}; category=max(scores,key=scores.get) if max(scores.values(),default=0) else "Other"; confidence=min(.9,.38+scores[category]*.11); reasons=["Matched issue vocabulary in the description"] if scores.get(category,0) else ["No strong issue keywords found; defaulted to Other"]
    if selected in CATEGORIES and selected!=category:reasons.append(f"Reporter selected {selected}; shown as a human override");return selected,confidence,reasons
    return category,confidence,reasons

def photo_save(data_url:Optional[str])->tuple[Optional[str],Optional[str]]:
    if not data_url:return None,None
    if len(data_url)>7_000_000:raise HTTPException(413,"Images must be under 5 MB")
    match=re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)",data_url)
    if not match:raise HTTPException(400,"Upload a PNG, JPEG, or WebP image")
    try:raw=base64.b64decode(match.group(2),validate=True)
    except (binascii.Error,ValueError):raise HTTPException(400,"Image data is invalid")
    if len(raw)>5*1024*1024:raise HTTPException(413,"Images must be under 5 MB")
    suffix="jpg" if match.group(1)=="jpeg" else match.group(1); digest=hashlib.sha256(raw).hexdigest()[:24]; path=UPLOAD_DIR/f"{digest}.{suffix}"
    phash=None
    if PIL_AVAILABLE:
        try:
            source=Image.open(io.BytesIO(raw))
            if source.width*source.height>25_000_000:raise HTTPException(413,"Image dimensions are too large")
            expected_format={"png":"PNG","jpeg":"JPEG","webp":"WEBP"}[match.group(1)]
            if source.format!=expected_format:raise HTTPException(400,"Image contents do not match the selected file type")
            image=source.convert("L").resize((8,8)); pixels=list(image.getdata()); avg=sum(pixels)/len(pixels); bits=sum((1<<i) for i,p in enumerate(pixels) if p>=avg); phash=f"{bits:016x}"
        except HTTPException:raise
        except Exception:raise HTTPException(400,"Image file could not be read")
    if not path.exists():path.write_bytes(raw)
    return f"/uploads/{path.name}",phash
def geo_km(a_lat:float,a_lon:float,b_lat:float,b_lon:float)->float:
    r=6371;p1,p2=math.radians(a_lat),math.radians(b_lat);dl,do=math.radians(b_lat-a_lat),math.radians(b_lon-a_lon);v=math.sin(dl/2)**2+math.cos(p1)*math.cos(p2)*math.sin(do/2)**2;return 2*r*math.asin(min(1,math.sqrt(v)))
def duplicate_score(new:Complaint,old:Complaint)->tuple[float,list[str]]:
    a=set(re.findall(r"[a-z0-9]{3,}",(new.title+" "+new.description).lower()));b=set(re.findall(r"[a-z0-9]{3,}",(old.title+" "+old.description).lower()));text_score=len(a&b)/max(1,len(a|b));distance=geo_km(new.latitude,new.longitude,old.latitude,old.longitude);hours=abs((new.created_at-old.created_at).total_seconds())/3600;score=text_score*.45;reasons=[]
    if text_score>.12:reasons.append("Similar description")
    if new.category==old.category:score+=.25;reasons.append("Same category")
    if distance<=.7:score+=.22;reasons.append(f"Nearby ({distance:.1f} km)")
    elif distance<=2:score+=.12;reasons.append(f"Within {distance:.1f} km")
    if hours<=168:score+=.08;reasons.append("Reported within the same week")
    if new.image_hash and old.image_hash and len(new.image_hash)==len(old.image_hash):
        diff=sum((int(x,16)^int(y,16)).bit_count() for x,y in zip(new.image_hash,old.image_hash));similarity=1-diff/64
        if similarity>.72:score+=.15;reasons.append(f"Photo appearance similar ({similarity:.0%})")
    return min(score,1),reasons

def serialize_complaint(c:Complaint,db:Session,with_history:bool=False)->dict[str,Any]:
    department=db.get(Department,c.department_id) if c.department_id else None; officer=db.get(User,c.officer_id) if c.officer_id else None; citizen=db.get(User,c.citizen_id)
    result={"id":c.id,"reference":c.reference,"title":c.title,"description":c.description,"category":c.category,"subcategory":c.subcategory,"status":c.status,"priority_score":c.priority_score,"priority_level":c.priority_level,"ai_confidence":round(c.ai_confidence,2),"ai_factors":c.ai_factors.split("\n") if c.ai_factors else [],"ai_summary":c.ai_summary,"department":department.name if department else None,"department_id":c.department_id,"officer":officer.name if officer else None,"officer_id":c.officer_id,"latitude":round(c.latitude,3),"longitude":round(c.longitude,3),"landmark":c.landmark,"image_url":c.image_url,"affected_people":c.affected_people,"created_at":c.created_at.isoformat()+"Z","updated_at":c.updated_at.isoformat()+"Z","deadline_at":c.deadline_at.isoformat()+"Z","citizen_name":citizen.name if citizen else "Resident","overdue":c.status not in ["Resolved","Rejected"] and utcnow()>c.deadline_at}
    reviewer=db.get(User,c.ai_reviewed_by_id) if c.ai_reviewed_by_id else None
    result.update({"ai_suggestion":c.ai_suggestion,"ai_review_status":c.ai_review_status,"ai_reviewed_by":reviewer.name if reviewer else None,"ai_review_note":c.ai_review_note})
    if with_history:
        history=db.scalars(select(StatusHistory).where(StatusHistory.complaint_id==c.id).order_by(StatusHistory.created_at)).all()
        result["history"]=[{"status":h.status,"explanation":h.explanation,"actor":(db.get(User,h.actor_id).name if db.get(User,h.actor_id) else "System"),"created_at":h.created_at.isoformat()+"Z"} for h in history]
        evidence=db.scalars(select(ResolutionEvidence).where(ResolutionEvidence.complaint_id==c.id).order_by(ResolutionEvidence.created_at.desc())).all()
        result["evidence"]=[{"note":e.note,"image_url":e.image_url,"created_at":e.created_at.isoformat()+"Z"} for e in evidence]
        candidates=db.scalars(select(DuplicateCandidate).where(DuplicateCandidate.complaint_id==c.id).order_by(DuplicateCandidate.score.desc())).all()
        result["duplicates"]=[{"score":round(d.score,2),"reasons":d.reasons.split("; "),"complaint":serialize_complaint(db.get(Complaint,d.candidate_id),db)} for d in candidates if db.get(Complaint,d.candidate_id)]
        feedback=db.scalars(select(Feedback).where(Feedback.complaint_id==c.id).order_by(Feedback.created_at.desc())).all()
        result["feedback"]=[{"rating":f.rating,"comment":f.comment,"resolved_confirmed":f.resolved_confirmed,"created_at":f.created_at.isoformat()+"Z"} for f in feedback]
        escalations=db.scalars(select(Escalation).where(Escalation.complaint_id==c.id).order_by(Escalation.level)).all()
        result["escalations"]=[{"level":e.level,"reason":e.reason,"created_at":e.created_at.isoformat()+"Z"} for e in escalations]
    return result

def visible_query(db:Session,user:User):
    query=select(Complaint)
    if user.role=="citizen":query=query.where(Complaint.citizen_id==user.id)
    elif user.role=="officer":query=query.where(Complaint.officer_id==user.id)
    return query
def notify(db:Session,user_id:int,title:str,message:str,complaint_id:Optional[int]=None):db.add(Notification(user_id=user_id,title=title,message=message,complaint_id=complaint_id))
def audit(db:Session,user:User,action:str,entity:str,entity_id:Any,details:str=""):db.add(AuditLog(actor_id=user.id,action=action,entity_type=entity,entity_id=str(entity_id),details=details[:500]))

SAMPLES=[
 ("Deep pothole outside the school gate","A deep pothole has opened beside the primary school entrance. Two cyclists have fallen this week and cars swerve into the bus lane.","Road damage","Assigned",28.6134,77.2091,"Central School crossing",42),
 ("Overflowing bins on Market Lane","The community bins have been overflowing since Monday. Food waste is attracting stray animals near the evening market.","Waste management","In Progress",28.6162,77.2130,"Market Lane",17),
 ("Water leaking from street pipe","Clean water has been running down the footpath for two days. The leak appears near the corner and pressure is low in nearby homes.","Water supply","Assigned",28.6100,77.2172,"Cedar Street corner",32),
 ("Streetlight out on park path","Three lamps are out along the park path. It is very dark for people walking home after sunset.","Street lighting","Under Review",28.6171,77.2050,"Riverside Park north path",11),
 ("Drain backing up after rain","The storm drain is blocked and sewage water has begun to pool at the crossing. The smell is strong and pedestrians cannot pass safely.","Drainage & sewage","Awaiting Verification",28.6085,77.2103,"Old Post Office crossing",58),
 ("Cracked footpath ramp","The curb ramp has broken concrete and is difficult for wheelchair users and strollers to cross.","Public infrastructure","Pending",28.6200,77.2154,"Library Avenue",9),
 ("Missed waste collection","Garbage bags have not been collected for four days on the residential side street.","Waste management","Resolved",28.6140,77.2070,"Lotus Apartments",24),
 ("Exposed wire near bus stop","A cable is hanging low with exposed wiring close to the bus stop. This may be dangerous for people waiting there.","Electricity","Pending",28.6054,77.2135,"Bus stop 12",6),
 ("Tap water pressure issue","Water pressure has been unusually low across the block since yesterday morning.","Water supply","In Progress",28.6118,77.2140,"Pine Residency",38),
 ("Broken lamp on Cedar Street","The streetlight is flickering and then goes dark most nights.","Street lighting","Resolved",28.6182,77.2098,"Cedar Street",13),
 ("Blocked drain at school road","A blocked storm drain is flooding the roadway after rain. The water is deep enough to hide potholes.","Drainage & sewage","Pending",28.6150,77.2088,"School Road",53),
 ("Damaged park bench","A broken metal edge is exposed on the park bench and could cut someone. Please repair or remove it.","Public infrastructure","Under Review",28.6220,77.2071,"Riverside Park",4),
]
def seed_demo(db:Session,clear:bool=False):
    if clear:
        for model in [AuditLog,ServicePolicy,DuplicateCandidate,Escalation,ResolutionEvidence,Feedback,Notification,StatusHistory,Complaint,User,Department]:db.query(model).delete()
        db.commit()
    seed_service_policies(db,reset=clear)
    if db.scalar(select(User.id).limit(1)):return
    cats=["Road damage","Waste management","Water supply","Street lighting","Electricity"]
    depts=[Department(name=name,category=cat,email=f"{name.lower().replace(' & ','-').replace(' ','-')}@civictrack.demo") for name,cat in zip(DEMO_DEPARTMENTS,cats)]
    db.add_all(depts);db.flush()
    users=[User(name="Aarav Mehta",email="citizen@civictrack.demo",password_hash=password_hash(DEMO_PASSWORD),role="citizen"),User(name="Mira Kapoor",email="admin@civictrack.demo",password_hash=password_hash(DEMO_PASSWORD),role="admin")]
    names=["Rohan Verma","Priya Nair","Kabir Shah","Anaya Iyer","Dev Patel"]
    users.extend(User(name=names[i],email=f"officer{i+1}@civictrack.demo",password_hash=password_hash(DEMO_PASSWORD),role="officer",department_id=depts[i].id) for i in range(len(depts)))
    db.add_all(users);db.flush();citizen,admin,*officers=users;now=utcnow();items=[]
    age_days=[1,2,4,5,7,8,11,13,15,17,20,24]
    for i,(title,desc,cat,state,lat,lon,landmark,people) in enumerate(SAMPLES):
        created=now-timedelta(days=age_days[i]);score,level,factors=priority_for(desc,people,i*6,False);dept=next((d for d in depts if d.name==area_for(cat)),None);officer=next((o for o in officers if o.department_id==dept.id),None) if dept else None
        item=Complaint(reference=f"CT-{now.strftime('%y%m')}-{i+1:04d}",title=title,description=desc,category=cat,subcategory="Street-level issue",status=state,priority_score=score,priority_level=level,ai_confidence=.86,ai_factors="\n".join(factors),ai_summary=desc[:140]+("…" if len(desc)>140 else ""),citizen_id=citizen.id,department_id=dept.id if state in ["Assigned","In Progress","Awaiting Verification","Resolved"] else None,officer_id=officer.id if state in ["Assigned","In Progress","Awaiting Verification","Resolved"] else None,latitude=lat,longitude=lon,landmark=landmark,affected_people=people,age_hours=i*6,deadline_at=created+timedelta(hours=DEADLINES.get(cat,96)),created_at=created,updated_at=created+timedelta(hours=2))
        item.ai_suggestion=cat;db.add(item);items.append((item,state,created))
    db.flush()
    for item,state,created in items:
        db.add(StatusHistory(complaint_id=item.id,status="Pending",explanation="Report received",actor_id=citizen.id,created_at=created))
        if state!="Pending":db.add(StatusHistory(complaint_id=item.id,status=state,explanation="Demonstration workflow update",actor_id=admin.id,created_at=created+timedelta(hours=2)))
    db.add(DuplicateCandidate(complaint_id=items[0][0].id,candidate_id=items[10][0].id,score=.64,reasons="Same category; Nearby (0.3 km); Similar description"))
    db.add(ResolutionEvidence(complaint_id=items[4][0].id,officer_id=officers[2].id,note="Drain cleared and flow checked. Please verify the crossing is clear.",created_at=now-timedelta(hours=6)))
    notify(db,citizen.id,"Resolution ready to verify",f"{items[4][0].reference} is awaiting your confirmation.",items[4][0].id);notify(db,admin.id,"Welcome to CivicTrack demo","Sample records are labelled demonstration data.")
    db.commit()

def seed_service_policies(db:Session,reset:bool=False):
    if reset:db.query(ServicePolicy).delete()
    existing={p.category for p in db.scalars(select(ServicePolicy)).all()}
    for category,hours in DEADLINES.items():
        if reset or category not in existing:db.add(ServicePolicy(category=category,deadline_hours=hours,escalation_grace_hours=24))
    db.commit()
@app.get("/health")
def health():return {"status":"ok","demo_mode":DEMO_MODE,"database":"connected","ai":{"text_model":"scikit-learn logistic regression" if _classifier else "keyword fallback","image_hash":"average hash" if PIL_AVAILABLE else "unavailable"}}
@app.get("/uploads/{filename}")
def get_upload(filename:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if Path(filename).name!=filename or filename.startswith("."):raise HTTPException(404,"Image not found")
    path=UPLOAD_DIR/filename
    image_path=f"/uploads/{filename}";item=db.scalar(select(Complaint).where(Complaint.image_url==image_path))
    if not item:
        evidence=db.scalar(select(ResolutionEvidence).where(ResolutionEvidence.image_url==image_path))
        if evidence:item=db.get(Complaint,evidence.complaint_id)
    if not path.is_file() or not item:raise HTTPException(404,"Image not found")
    allowed=user.role=="admin" or (user.role=="citizen" and item.citizen_id==user.id) or (user.role=="officer" and item.officer_id==user.id)
    if not allowed:raise HTTPException(403,"You cannot access this image")
    return FileResponse(path,media_type=mimetypes.guess_type(filename)[0] or "application/octet-stream",headers={"Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})
@app.post("/auth/register")
def register(body:RegisterRequest,db:Session=Depends(get_db)):
    email=body.email.strip().lower()
    if "@" not in email:raise HTTPException(422,"Enter a valid email address")
    if db.scalar(select(User.id).where(User.email==email)):raise HTTPException(409,"An account with this email already exists")
    user=User(name=body.name.strip(),email=email,password_hash=password_hash(body.password),role="citizen");db.add(user);db.commit();db.refresh(user)
    return {"access_token":token_for(user),"token_type":"bearer","user":user_payload(user)}
@app.post("/auth/login")
def login(body:LoginRequest,db:Session=Depends(get_db)):
    email=body.email.strip().lower();now=time.monotonic();attempts=LOGIN_ATTEMPTS[email]
    while attempts and now-attempts[0]>60:attempts.popleft()
    if len(attempts)>=8:raise HTTPException(429,"Too many sign-in attempts. Wait a minute and try again.")
    attempts.append(now);user=db.scalar(select(User).where(User.email==email))
    if not user or not password_ok(body.password,user.password_hash):raise HTTPException(401,"Email or password did not match")
    return {"access_token":token_for(user),"token_type":"bearer","user":user_payload(user)}
@app.get("/auth/me")
def me(user:User=Depends(current_user)):return {"user":user_payload(user),"demo_mode":DEMO_MODE}
@app.get("/departments")
def departments(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [{"id":d.id,"name":d.name,"category":d.category,"email":d.email} for d in db.scalars(select(Department).order_by(Department.name)).all()]
@app.get("/service-policies")
def service_policies(db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    seed_service_policies(db)
    return [{"category":p.category,"deadline_hours":p.deadline_hours,"escalation_grace_hours":p.escalation_grace_hours,"updated_at":p.updated_at.isoformat()+"Z"} for p in db.scalars(select(ServicePolicy).order_by(ServicePolicy.category)).all()]
@app.put("/service-policies/{category}")
def update_service_policy(category:str,body:ServicePolicyRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    if category not in CATEGORIES:raise HTTPException(404,"Issue category not found")
    item=policy_for(db,category)
    if not item:item=ServicePolicy(category=category);db.add(item)
    item.deadline_hours=body.deadline_hours;item.escalation_grace_hours=body.escalation_grace_hours;item.updated_by_id=user.id;item.updated_at=utcnow()
    audit(db,user,"service_policy.updated","service_policy",category,f"Target {body.deadline_hours}h; next escalation after {body.escalation_grace_hours}h")
    db.commit();return {"category":item.category,"deadline_hours":item.deadline_hours,"escalation_grace_hours":item.escalation_grace_hours,"updated_at":item.updated_at.isoformat()+"Z"}
@app.post("/departments")
def create_department(body:DepartmentRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    item=Department(name=body.name.strip(),category=body.category,email=body.email);db.add(item)
    try:db.commit()
    except Exception:db.rollback();raise HTTPException(409,"A department with this name already exists")
    audit(db,user,"department.created","department",item.id,item.name);db.commit();return {"id":item.id,"name":item.name,"category":item.category,"email":item.email}
@app.put("/departments/{department_id}")
def update_department(department_id:int,body:DepartmentRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    item=db.get(Department,department_id)
    if not item:raise HTTPException(404,"Department not found")
    item.name,item.category,item.email=body.name.strip(),body.category,body.email;audit(db,user,"department.updated","department",item.id,item.name);db.commit();return {"id":item.id,"name":item.name,"category":item.category,"email":item.email}
@app.get("/officers")
def officers(department_id:Optional[int]=None,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    query=select(User).where(User.role=="officer")
    if department_id:query=query.where(User.department_id==department_id)
    out=[]
    for u in db.scalars(query).all():
        dept=db.get(Department,u.department_id) if u.department_id else None;active=len(db.scalars(select(Complaint.id).where(Complaint.officer_id==u.id,Complaint.status.notin_(["Resolved","Rejected"]))).all());out.append({**user_payload(u),"department":dept.name if dept else None,"active_assignments":active})
    return out
@app.post("/officers",status_code=201)
def create_officer(body:OfficerCreateRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    email=body.email.strip().lower();department=db.get(Department,body.department_id)
    if not department:raise HTTPException(404,"Department not found")
    if "@" not in email:raise HTTPException(422,"Enter a valid email address")
    if db.scalar(select(User.id).where(User.email==email)):raise HTTPException(409,"An account with this email already exists")
    officer=User(name=body.name.strip(),email=email,password_hash=password_hash(body.password),role="officer",department_id=department.id);db.add(officer);db.flush();audit(db,user,"officer.created","user",officer.id,f"{officer.email}; {department.name}");db.commit();db.refresh(officer)
    return {**user_payload(officer),"department":department.name,"active_assignments":0}

@app.get("/complaints")
def complaints(status_filter:Optional[str]=Query(default=None,alias="status"),category:Optional[str]=None,search:Optional[str]=None,limit:int=Query(100,ge=1,le=250),db:Session=Depends(get_db),user:User=Depends(current_user)):
    query=visible_query(db,user)
    if status_filter:query=query.where(Complaint.status==status_filter)
    if category:query=query.where(Complaint.category==category)
    if search:
        pattern=f"%{search.strip()}%";query=query.where(Complaint.title.ilike(pattern)|Complaint.reference.ilike(pattern)|Complaint.description.ilike(pattern))
    return [serialize_complaint(c,db) for c in db.scalars(query.order_by(Complaint.created_at.desc()).limit(limit)).all()]
@app.post("/complaints",status_code=201)
def create_complaint(body:ComplaintCreate,db:Session=Depends(get_db),user:User=Depends(require_role("citizen"))):
    recent=db.scalars(select(Complaint.id).where(Complaint.citizen_id==user.id,Complaint.created_at>=utcnow()-timedelta(hours=1)).limit(21)).all()
    if len(recent)>=20:raise HTTPException(429,"You have reached the hourly report limit. Please try again later.")
    image_url,image_hash=photo_save(body.image_data);suggested,confidence,explain=classify(f"{body.title}. {body.description}");category=body.category if body.category in CATEGORIES else suggested
    if category!=suggested:explain.append(f"Reporter selected {category}; shown as a human override")
    score,level,factors=priority_for(f"{body.title}. {body.description}",body.affected_people,body.age_hours,bool(image_url));now=utcnow();short=secrets.token_hex(5).upper();summary=body.description.strip();summary=summary[:177].rsplit(" ",1)[0]+"…" if len(summary)>180 else summary
    service_policy=policy_for(db,category);deadline_hours=service_policy.deadline_hours if service_policy else DEADLINES.get(category,96)
    item=Complaint(reference=f"CT-{now.strftime('%y%m')}-{short}",title=body.title.strip(),description=body.description.strip(),category=category,subcategory=body.subcategory,status="Pending",priority_score=score,priority_level=level,ai_confidence=confidence,ai_factors="\n".join(factors),ai_summary=summary,citizen_id=user.id,latitude=body.latitude,longitude=body.longitude,landmark=body.landmark,affected_people=body.affected_people,age_hours=body.age_hours,image_url=image_url,image_hash=image_hash,deadline_at=now+timedelta(hours=deadline_hours),created_at=now,updated_at=now)
    item.ai_suggestion=suggested;db.add(item);db.flush();db.add(StatusHistory(complaint_id=item.id,status="Pending",explanation="Report received. AI suggestions are advisory and may be reviewed by staff.",actor_id=user.id))
    candidates=db.scalars(select(Complaint).where(Complaint.id!=item.id,Complaint.created_at>=now-timedelta(days=30)).order_by(Complaint.created_at.desc()).limit(80)).all()
    for old in candidates:
        score_dup,reasons=duplicate_score(item,old)
        if score_dup>=.38:db.add(DuplicateCandidate(complaint_id=item.id,candidate_id=old.id,score=score_dup,reasons="; ".join(reasons)))
    for admin in db.scalars(select(User).where(User.role=="admin")).all():notify(db,admin.id,"New citizen report",f"{item.reference} is ready for review.",item.id)
    audit(db,user,"complaint.created","complaint",item.id,item.reference);db.commit();db.refresh(item);result=serialize_complaint(item,db,True);result["ai_explanation"]=explain;result["ai_disclaimer"]="Local advisory model; review category and priority before acting.";return result
@app.get("/complaints/{complaint_id}")
def complaint_detail(complaint_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(Complaint,complaint_id)
    if not item:raise HTTPException(404,"Complaint not found")
    if user.role=="citizen" and item.citizen_id!=user.id:raise HTTPException(403,"This complaint belongs to another citizen")
    if user.role=="officer" and item.officer_id!=user.id:raise HTTPException(403,"This complaint is not assigned to you")
    return serialize_complaint(item,db,True)
@app.patch("/complaints/{complaint_id}/ai-review")
def review_ai(complaint_id:int,body:AIReviewRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    item=db.get(Complaint,complaint_id)
    if not item:raise HTTPException(404,"Complaint not found")
    if body.category not in CATEGORIES:raise HTTPException(422,"Choose a supported issue category")
    score_changed=body.priority_score!=item.priority_score
    item.category=body.category;item.priority_score=body.priority_score;item.priority_level="Critical" if body.priority_score>=75 else "High" if body.priority_score>=55 else "Normal" if body.priority_score>=30 else "Low";item.ai_review_status="Approved" if body.category==item.ai_suggestion and not score_changed else "Adjusted";item.ai_reviewed_by_id=user.id;item.ai_review_note=body.explanation;item.ai_reviewed_at=utcnow();item.updated_at=utcnow()
    audit(db,user,"ai.recommendation_reviewed","complaint",item.id,f"{item.ai_review_status}: {body.category}; priority {body.priority_score}; {body.explanation}");db.commit();return serialize_complaint(item,db,True)
@app.post("/complaints/{complaint_id}/assign")
def assign_complaint(complaint_id:int,body:AssignmentRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    item=db.get(Complaint,complaint_id);dept=db.get(Department,body.department_id)
    if not item or not dept:raise HTTPException(404,"Complaint or department not found")
    if item.status in ["Resolved","Rejected"]:raise HTTPException(409,"Closed reports cannot be reassigned")
    officer=db.get(User,body.officer_id) if body.officer_id else None
    if officer and (officer.role!="officer" or officer.department_id!=dept.id):raise HTTPException(422,"Choose an officer from the selected department")
    item.department_id=dept.id;item.officer_id=officer.id if officer else None;item.status="Assigned";item.updated_at=utcnow();db.add(StatusHistory(complaint_id=item.id,status="Assigned",explanation=body.explanation,actor_id=user.id))
    if officer:notify(db,officer.id,"Complaint assigned",f"{item.reference} has been assigned to your queue.",item.id)
    notify(db,item.citizen_id,"Complaint assigned",f"{item.reference} has been routed to {dept.name}.",item.id);audit(db,user,"complaint.assigned","complaint",item.id,f"{dept.name}; {officer.name if officer else 'No officer selected'}");db.commit();return serialize_complaint(item,db,True)
@app.patch("/complaints/{complaint_id}/status")
def change_status(complaint_id:int,body:StatusRequest,db:Session=Depends(get_db),user:User=Depends(require_role("admin","officer"))):
    item=db.get(Complaint,complaint_id)
    if not item:raise HTTPException(404,"Complaint not found")
    if user.role=="officer" and item.officer_id!=user.id:raise HTTPException(403,"This complaint is not assigned to you")
    if body.status not in STATUSES:raise HTTPException(422,"Unknown complaint status")
    allowed={"Pending":["Under Review","Assigned","Rejected"],"Under Review":["Assigned","Rejected","Pending"],"Assigned":["In Progress","Under Review","Rejected"],"In Progress":["Awaiting Verification","Under Review"],"Awaiting Verification":["In Progress"],"Reopened":["Assigned","In Progress","Rejected"]}
    if body.status=="Resolved":raise HTTPException(422,"A citizen must confirm resolution before the status becomes Resolved")
    if body.status not in allowed.get(item.status,[]):raise HTTPException(409,f"Cannot move a {item.status} complaint to {body.status}")
    if body.status=="Awaiting Verification" and not body.evidence_note:raise HTTPException(422,"Add a resolution note before requesting citizen verification")
    item.status=body.status;item.updated_at=utcnow();db.add(StatusHistory(complaint_id=item.id,status=body.status,explanation=body.explanation,actor_id=user.id))
    if body.status=="Awaiting Verification":
        evidence_url,_=photo_save(body.evidence_image_data)
        db.add(ResolutionEvidence(complaint_id=item.id,officer_id=user.id,note=body.evidence_note,image_url=evidence_url));notify(db,item.citizen_id,"Please verify the resolution",f"Review the work reported for {item.reference}.",item.id)
    else:notify(db,item.citizen_id,"Complaint update",f"{item.reference} moved to {body.status}.",item.id)
    audit(db,user,"complaint.status_changed","complaint",item.id,body.status);db.commit();return serialize_complaint(item,db,True)
@app.post("/complaints/{complaint_id}/verify")
def verify(complaint_id:int,body:VerifyRequest,db:Session=Depends(get_db),user:User=Depends(require_role("citizen"))):
    item=db.get(Complaint,complaint_id)
    if not item or item.citizen_id!=user.id:raise HTTPException(404,"Complaint not found")
    if item.status!="Awaiting Verification":raise HTTPException(409,"This complaint is not waiting for verification")
    new_status="Resolved" if body.confirmed else "Reopened";item.status=new_status;item.updated_at=utcnow();explanation="Citizen confirmed the issue is resolved." if body.confirmed else "Citizen reported the issue remains; follow-up is required."
    db.add(StatusHistory(complaint_id=item.id,status=new_status,explanation=explanation,actor_id=user.id));db.add(Feedback(complaint_id=item.id,citizen_id=user.id,rating=body.rating,comment=body.comment,resolved_confirmed=body.confirmed))
    if item.officer_id:notify(db,item.officer_id,"Citizen verification received",f"{item.reference} was marked {new_status.lower()} by the citizen.",item.id)
    for admin in db.scalars(select(User).where(User.role=="admin")).all():notify(db,admin.id,"Citizen verification received",f"{item.reference} was marked {new_status.lower()} by the citizen.",item.id)
    audit(db,user,"complaint.verified","complaint",item.id,new_status);db.commit();return serialize_complaint(item,db,True)

def process_escalations(db:Session):
    now=utcnow();rows=db.scalars(select(Complaint).where(Complaint.status.notin_(["Resolved","Rejected"]),Complaint.deadline_at<now)).all()
    for item in rows:
        latest=db.scalar(select(Escalation).where(Escalation.complaint_id==item.id).order_by(Escalation.level.desc()))
        policy=policy_for(db,item.category);grace_hours=policy.escalation_grace_hours if policy else 24
        if latest and (latest.level>=2 or now<item.deadline_at+timedelta(hours=grace_hours)):continue
        level=2 if latest else 1
        reason="Second escalation: configured follow-up window passed" if level==2 else "First escalation: configured response target passed"
        db.add(Escalation(complaint_id=item.id,level=level,reason=reason))
        title="Complaint escalated" if level==1 else "Complaint escalated again"
        for admin in db.scalars(select(User).where(User.role=="admin")).all():notify(db,admin.id,title,f"{item.reference} is overdue and needs level {level} review.",item.id)
        if level==2 and item.officer_id:notify(db,item.officer_id,"Overdue report follow-up",f"{item.reference} has passed its configured escalation window.",item.id)
    db.commit()
def accountability(db:Session)->list[dict[str,Any]]:
    result=[]
    for dept in db.scalars(select(Department).order_by(Department.name)).all():
        rows=db.scalars(select(Complaint).where(Complaint.department_id==dept.id)).all()
        if not rows:result.append({"department":dept.name,"score":None,"resolved_rate":0,"avg_days":0,"overdue_rate":0,"verified_rate":0,"reopened_rate":0,"citizen_rating":None,"cases":0});continue
        done=[c for c in rows if c.status=="Resolved"];feedback=db.scalars(select(Feedback).where(Feedback.complaint_id.in_([c.id for c in rows]))).all();resolved_rate=len(done)/len(rows)*100
        avg_days=sum(max(0,(c.updated_at-c.created_at).total_seconds()/86400) for c in done)/len(done) if done else 0
        overdue_rate=sum(c.status not in ["Resolved","Rejected"] and utcnow()>c.deadline_at for c in rows)/len(rows)*100
        verified_rate=sum(f.resolved_confirmed for f in feedback)/max(1,len(done))*100;reopened_rate=sum(c.status=="Reopened" for c in rows)/len(rows)*100;rating=sum(f.rating for f in feedback)/len(feedback) if feedback else None
        score=round(resolved_rate*INDEX_WEIGHTS["resolution_rate"]/100+(max(0,100-avg_days*3) if done else 50)*INDEX_WEIGHTS["resolution_time"]/100+(100-overdue_rate)*INDEX_WEIGHTS["overdue_rate"]/100+min(100,verified_rate)*INDEX_WEIGHTS["citizen_verification"]/100+(100-reopened_rate)*INDEX_WEIGHTS["reopened_rate"]/100+(rating*20 if rating else 50)*INDEX_WEIGHTS["citizen_satisfaction"]/100)
        result.append({"department":dept.name,"score":score,"resolved_rate":round(resolved_rate),"avg_days":round(avg_days,1),"overdue_rate":round(overdue_rate),"verified_rate":round(min(100,verified_rate)),"reopened_rate":round(reopened_rate),"citizen_rating":round(rating,1) if rating else None,"cases":len(rows)})
    return result

@app.get("/dashboard/summary")
def dashboard_summary(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(visible_query(db,user).order_by(Complaint.created_at.desc())).all();now=utcnow()
    return {"total":len(rows),"pending":sum(c.status in ["Pending","Under Review","Assigned"] for c in rows),"in_progress":sum(c.status in ["In Progress","Awaiting Verification","Reopened"] for c in rows),"resolved":sum(c.status=="Resolved" for c in rows),"overdue":sum(c.status not in ["Resolved","Rejected"] and c.deadline_at<now for c in rows),"recent":[serialize_complaint(c,db) for c in rows[:5]],"demo_mode":DEMO_MODE}
@app.get("/map/issues")
def map_issues(category:Optional[str]=None,status_filter:Optional[str]=Query(default=None,alias="status"),db:Session=Depends(get_db),user:User=Depends(current_user)):
    query=select(Complaint)
    if category:query=query.where(Complaint.category==category)
    if status_filter:query=query.where(Complaint.status==status_filter)
    return [{"id":c.id,"reference":c.reference,"title":c.title,"category":c.category,"status":c.status,"priority_level":c.priority_level,"latitude":round(c.latitude,3),"longitude":round(c.longitude,3),"created_at":c.created_at.isoformat()+"Z"} for c in db.scalars(query.order_by(Complaint.created_at.desc()).limit(500)).all()]
@app.get("/map/issues/{complaint_id}")
def public_map_detail(complaint_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(Complaint,complaint_id)
    if not item:raise HTTPException(404,"Complaint not found")
    history=db.scalars(select(StatusHistory).where(StatusHistory.complaint_id==item.id).order_by(StatusHistory.created_at)).all()
    return {"id":item.id,"reference":item.reference,"title":item.title,"description":item.description,"category":item.category,"status":item.status,"priority_level":item.priority_level,"latitude":round(item.latitude,3),"longitude":round(item.longitude,3),"landmark":item.landmark,"created_at":item.created_at.isoformat()+"Z","history":[{"status":h.status,"explanation":h.explanation,"created_at":h.created_at.isoformat()+"Z"} for h in history]}
@app.get("/notifications")
def notifications(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc()).limit(50)).all()
    return [{"id":n.id,"title":n.title,"message":n.message,"complaint_id":n.complaint_id,"read":n.read,"created_at":n.created_at.isoformat()+"Z"} for n in rows]
@app.patch("/notifications/{notification_id}")
def read_notification(notification_id:int,body:ReadRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(Notification,notification_id)
    if not item or item.user_id!=user.id:raise HTTPException(404,"Notification not found")
    item.read=body.read;db.commit();return {"id":item.id,"read":item.read}

@app.get("/analytics")
def analytics(db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    process_escalations(db);rows=db.scalars(select(Complaint)).all();now=utcnow();counts=Counter(c.status for c in rows);categories=Counter(c.category for c in rows);monthly=defaultdict(lambda:{"reported":0,"resolved":0})
    for c in rows:
        key=c.created_at.strftime("%b");monthly[key]["reported"]+=1
        if c.status=="Resolved":monthly[key]["resolved"]+=1
    names=[(now-timedelta(days=30*i)).strftime("%b") for i in range(5,-1,-1)];trend=[{"month":name,**monthly[name]} for name in names];overdue=[c for c in rows if c.status not in ["Resolved","Rejected"] and c.deadline_at<now];resolved=[c for c in rows if c.status=="Resolved"];feedback=db.scalars(select(Feedback)).all()
    return {"total":len(rows),"pending":sum(counts[s] for s in ["Pending","Under Review","Assigned"]),"in_progress":sum(counts[s] for s in ["In Progress","Awaiting Verification","Reopened"]),"resolved":counts["Resolved"],"overdue":len(overdue),"avg_resolution_days":round(sum((c.updated_at-c.created_at).total_seconds()/86400 for c in resolved)/len(resolved),1) if resolved else 0,"verification_rate":round(sum(f.resolved_confirmed for f in feedback)/max(1,len(resolved))*100),"categories":[{"name":k,"value":v} for k,v in categories.most_common()],"trend":trend,"departments":accountability(db),"priority":[{"name":p,"value":sum(c.priority_level==p for c in rows)} for p in ["Critical","High","Normal","Low"]],"demo_mode":DEMO_MODE,"weights":INDEX_WEIGHTS}
@app.get("/hotspots")
def hotspots(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(select(Complaint)).all()
    if not rows:return {"clusters":[],"experimental":True,"record_count":0}
    groups:dict[int,list[Complaint]]=defaultdict(list)
    if SKLEARN_AVAILABLE and len(rows)>=4:
        coords=[[math.radians(c.latitude),math.radians(c.longitude)] for c in rows];labels=DBSCAN(eps=.8/6371,min_samples=2,metric="haversine").fit_predict(coords)
        for label,item in zip(labels,rows):
            if label>=0:groups[int(label)].append(item)
    else:
        remaining=set(range(len(rows)));label=0
        while remaining:
            i=min(remaining);cluster={j for j in remaining if geo_km(rows[i].latitude,rows[i].longitude,rows[j].latitude,rows[j].longitude)<.8}
            if len(cluster)>=2:groups[label]=[rows[j] for j in cluster];label+=1
            remaining-=cluster or {i}
    clusters=[]
    for members in groups.values():
        cats=Counter(c.category for c in members);clusters.append({"id":len(clusters)+1,"count":len(members),"latitude":sum(c.latitude for c in members)/len(members),"longitude":sum(c.longitude for c in members)/len(members),"lead_category":cats.most_common(1)[0][0],"categories":dict(cats)})
    return {"clusters":clusters,"experimental":len(rows)<20,"record_count":len(rows),"algorithm":"DBSCAN / Haversine, 0.8 km neighborhood" if SKLEARN_AVAILABLE else "Distance grouping fallback, 0.8 km"}
@app.get("/reports.csv")
def report_csv(db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    rows=db.scalars(select(Complaint).order_by(Complaint.created_at.desc())).all();output=io.StringIO();writer=csv.writer(output);writer.writerow(["CivicTrack demonstration report" if DEMO_MODE else "CivicTrack report",f"Generated {utcnow().isoformat()} UTC"]);writer.writerow(["Reference","Title","Category","Status","Priority","Department","Created at","Deadline","Area"])
    for c in rows:
        dept=db.get(Department,c.department_id) if c.department_id else None;writer.writerow([c.reference,c.title,c.category,c.status,c.priority_level,dept.name if dept else "Unassigned",c.created_at.isoformat()+"Z",c.deadline_at.isoformat()+"Z",c.landmark])
    output.seek(0);return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=civictrack-report.csv"})
@app.get("/reports.json")
def report_data(db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    rows=db.scalars(select(Complaint).order_by(Complaint.created_at.desc())).all()
    return [{"id":c.id,"reference":c.reference,"title":c.title,"category":c.category,"status":c.status,"priority_level":c.priority_level,"department":db.get(Department,c.department_id).name if c.department_id and db.get(Department,c.department_id) else "Unassigned","created_at":c.created_at.isoformat()+"Z","deadline_at":c.deadline_at.isoformat()+"Z","landmark":c.landmark} for c in rows]
@app.get("/audit")
def audit_logs(limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    rows=db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all();result=[]
    for r in rows:
        actor=db.get(User,r.actor_id);result.append({"id":r.id,"actor":actor.name if actor else "Unknown","action":r.action,"entity_type":r.entity_type,"entity_id":r.entity_id,"details":r.details,"created_at":r.created_at.isoformat()+"Z"})
    return result
@app.post("/admin/reset")
def reset_demo(db:Session=Depends(get_db),user:User=Depends(require_role("admin"))):
    if not DEMO_MODE:raise HTTPException(403,"Demo reset is disabled")
    seed_demo(db,clear=True)
    for path in UPLOAD_DIR.iterdir():
        if path.is_file():path.unlink()
    fresh=db.scalar(select(User).where(User.email=="admin@civictrack.demo"))
    if fresh:audit(db,fresh,"demo.reset","system","all","Restored sample demonstration dataset");db.commit()
    return {"ok":True,"message":"Demonstration dataset restored","access_token":token_for(fresh) if fresh else None}
