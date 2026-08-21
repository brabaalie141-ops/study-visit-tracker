"""
Study Visit Tracker V8.1
Built from the uploaded working V8 app.

V8.1 preparation:
- preserves the existing working interface and workflow
- adds a safe configuration layer for Supabase
- keeps demo/local operation available until the Supabase schema is verified
"""


import json, re, sqlite3
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import streamlit as st

DB=Path("study_visit_tracker.db")
SOURCE=Path("Project.xlsx")

st.set_page_config(page_title="Study Visit Tracker — Demo",page_icon="📋",layout="wide")

USERS={
 "ra.demo":("Research Assistant","Demo Research Assistant"),
 "ro.demo":("Research Officer","Demo Research Officer"),
 "sra.demo":("Senior Research Assistant","Demo Senior Research Assistant"),
}
VISITS={
 "Adolescent":{1:"Baseline / -12 weeks",2:"Week 0",3:"Week 12",4:"Week 24–35",5:"Week 36–47",6:"Week 48–72"},
 "Treatment Supporter":{1:"Baseline / -12 weeks",2:"Week 0",3:"Week 12",4:"Week 24–35"},
}

def db():
 return sqlite3.connect(DB)

def init():
 c=db()
 c.execute("CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY,role TEXT,display_name TEXT,active INTEGER DEFAULT 1)")
 c.execute("""CREATE TABLE IF NOT EXISTS participants(
 pid TEXT PRIMARY KEY,sheet TEXT,participant_type TEXT,data_json TEXT,
 assigned_to TEXT,updated_by TEXT,updated_at TEXT)""")
 c.execute("""CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,action TEXT,pid TEXT,visit_no INTEGER,
 details TEXT,created_at TEXT)""")
 c.execute("""CREATE TABLE IF NOT EXISTS visit_workflow(
 pid TEXT NOT NULL,visit_no INTEGER NOT NULL,workflow_status TEXT NOT NULL DEFAULT 'Pending',
 submitted_by TEXT,submitted_at TEXT,correction_comment TEXT,
 PRIMARY KEY(pid,visit_no))""")
 c.execute("""CREATE TABLE IF NOT EXISTS visit_reviews(
 id INTEGER PRIMARY KEY AUTOINCREMENT,pid TEXT NOT NULL,visit_no INTEGER NOT NULL,
 reviewer TEXT NOT NULL,decision TEXT NOT NULL,comment TEXT,reviewed_at TEXT NOT NULL,
 UNIQUE(pid,visit_no))""")
 for u,(r,n) in USERS.items():
  c.execute("INSERT OR IGNORE INTO users VALUES(?,?,?,1)",(u,r,n))
 c.commit(); c.close()

def ev(v):
 if pd.isna(v): return None
 if isinstance(v,(pd.Timestamp,datetime)): return v.strftime("%Y-%m-%d")
 if isinstance(v,date): return v.isoformat()
 return v.item() if hasattr(v,"item") else v

def import_workbook():
 c=db()
 if c.execute("SELECT COUNT(*) FROM participants").fetchone()[0]:
  c.close(); return
 for sheet,typ,prefix in [("Adolescent SVD","Adolescent","ad_"),("Treatment Supporter SVD","Treatment Supporter","ts_")]:
  df=pd.read_excel(SOURCE,sheet_name=sheet,header=2)
  df.columns=[str(x).strip() for x in df.columns]
  pid_col=prefix+"PID"
  if pid_col not in df.columns: continue
  for _,row in df.iterrows():
   pid=ev(row.get(pid_col))
   if not pid: continue
   data={str(k):ev(v) for k,v in row.items()}
   c.execute("INSERT OR IGNORE INTO participants VALUES(?,?,?,?,?,?,?)",
             (str(pid),sheet,typ,json.dumps(data,default=str),"","system",
              datetime.now().isoformat(timespec="seconds")))
 c.commit(); c.close()

def allp():
 c=db(); x=pd.read_sql_query("SELECT * FROM participants",c); c.close(); return x

def getp(pid):
 c=db(); r=c.execute("SELECT * FROM participants WHERE pid=?",(pid,)).fetchone(); c.close()
 return dict(zip(["pid","sheet","participant_type","data_json","assigned_to","updated_by","updated_at"],r)) if r else None

def save(pid,data,u):
 c=db()
 c.execute("UPDATE participants SET data_json=?,updated_by=?,updated_at=? WHERE pid=?",
           (json.dumps(data,default=str),u,datetime.now().isoformat(timespec="seconds"),pid))
 c.commit(); c.close()

def audit(u,action,pid=None,visit=None,details=""):
 c=db()
 c.execute("""INSERT INTO audit(username,action,pid,visit_no,details,created_at)
             VALUES(?,?,?,?,?,?)""",
           (u,action,pid,visit,details,datetime.now().isoformat(timespec="seconds")))
 c.commit(); c.close()

def workflow(pid,n,status,u,comment=""):
 c=db()
 c.execute("""INSERT INTO visit_workflow(pid,visit_no,workflow_status,submitted_by,submitted_at,correction_comment)
             VALUES(?,?,?,?,?,?)
             ON CONFLICT(pid,visit_no) DO UPDATE SET workflow_status=excluded.workflow_status,
             submitted_by=excluded.submitted_by,submitted_at=excluded.submitted_at,
             correction_comment=excluded.correction_comment""",
           (pid,n,status,u,datetime.now().isoformat(timespec="seconds"),comment))
 c.commit(); c.close()
 audit(u,"WORKFLOW",pid,n,f"{status}: {comment}")

def workflows():
 c=db(); x=pd.read_sql_query("SELECT * FROM visit_workflow",c); c.close(); return x

def reviews():
 c=db(); x=pd.read_sql_query("SELECT * FROM visit_reviews ORDER BY reviewed_at DESC",c); c.close(); return x

def users():
 c=db(); x=pd.read_sql_query("SELECT username,role,display_name,active FROM users ORDER BY role,display_name",c); c.close(); return x

def pref(t): return "ad_" if t=="Adolescent" else "ts_"

def visit_fields(d,n):
 return [k for k in d if re.search(rf"(?:^|_)V{n}(?:_|$)",k)]

def status(d,p,n):
 s=d.get(f"{p}Status_V{n}")
 if s not in (None,""): return str(s)
 if d.get(f"{p}Actual_V{n}"): return "Completed"
 try:
  if d.get(f"{p}Latest_V{n}") and datetime.fromisoformat(str(d[f"{p}Latest_V{n}"])).date()<date.today():
   return "Overdue"
  if d.get(f"{p}Scheduled_V{n}") and datetime.fromisoformat(str(d[f"{p}Scheduled_V{n}"])).date()>=date.today():
   return "Scheduled"
 except: pass
 return "Pending"

def login():
 if st.session_state.get("user"): return
 st.title("📋 Study Visit Tracker — Demo")
 st.warning("DEMO ENVIRONMENT: contains synthetic participant data for testing only. Do not enter real participant information.")
 st.caption("Research study participant and visit management")
 username=st.text_input("Username",placeholder="Enter your username")
 if st.button("Sign in",type="primary"):
  c=db(); r=c.execute("SELECT username,role,display_name FROM users WHERE username=? AND active=1",(username,)).fetchone(); c.close()
  if r:
   st.session_state.user={"username":r[0],"role":r[1],"name":r[2]}
   st.rerun()
  else: st.error("Username not found.")
 st.info("For testing: ra.demo · ro.demo · sra.demo")
 st.stop()

def dashboard(recs):
 st.title("📊 Study Visit Dashboard")
 wf=workflows()
 completed=scheduled=overdue=0
 rows=[]
 for _,r in recs.iterrows():
  d=json.loads(r.data_json); p=pref(r.participant_type)
  for n,label in VISITS[r.participant_type].items():
   s=status(d,p,n)
   if s=="Completed": completed+=1
   elif s=="Scheduled": scheduled+=1; rows.append([r.pid,r.participant_type,n,label,s,r.assigned_to or "Unassigned"])
   elif s=="Overdue": overdue+=1; rows.append([r.pid,r.participant_type,n,label,s,r.assigned_to or "Unassigned"])
 submitted=int((wf.workflow_status=="Submitted").sum()) if not wf.empty else 0
 approved=int((wf.workflow_status=="Approved").sum()) if not wf.empty else 0
 returned=int((wf.workflow_status=="Returned for correction").sum()) if not wf.empty else 0
 a,b,c,d,e,f=st.columns(6)
 a.metric("Participants",len(recs)); b.metric("Adolescents",int((recs.participant_type=="Adolescent").sum()))
 c.metric("Treatment supporters",int((recs.participant_type=="Treatment Supporter").sum()))
 d.metric("Completed visits",completed); e.metric("Due / overdue",scheduled+overdue); f.metric("Awaiting review",submitted)
 st.caption(f"Approved: {approved} · Returned for correction: {returned}")
 st.subheader("Visits requiring attention")
 if rows: st.dataframe(pd.DataFrame(rows,columns=["PID","Type","Visit","Timepoint","Status","Assigned RA"]),use_container_width=True,hide_index=True)
 else: st.success("No scheduled or overdue visits detected.")
 if not wf.empty:
  st.subheader("Workflow activity")
  st.dataframe(wf.sort_values("submitted_at",ascending=False).head(20),use_container_width=True,hide_index=True)

def work_queue(recs,user):
 st.title("📝 My Work Queue")
 work=recs[recs.assigned_to.fillna("")==user["username"]] if user["role"]=="Research Assistant" else recs
 rows=[]
 for _,r in work.iterrows():
  d=json.loads(r.data_json); p=pref(r.participant_type)
  for n,label in VISITS[r.participant_type].items():
   s=status(d,p,n)
   if s in ("Pending","Scheduled","Overdue"):
    rows.append([r.pid,r.participant_type,n,label,s,r.assigned_to or "Unassigned",
                 d.get(f"{p}Scheduled_V{n}") or "—"])
 a,b,c=st.columns(3); a.metric("Participants",len(work)); b.metric("Visits needing action",len(rows))
 c.metric("Overdue",sum(1 for x in rows if x[4]=="Overdue"))
 if rows: st.dataframe(pd.DataFrame(rows,columns=["PID","Type","Visit","Timepoint","Status","Assigned RA","Scheduled"]),use_container_width=True,hide_index=True)
 else: st.success("No outstanding visits.")

def participants_page(recs):
 st.title("👥 Participants")
 q=st.text_input("Search PID, name, surname, facility or supporter ID")
 rr=recs
 if q: rr=rr[rr.apply(lambda r:q.lower() in json.dumps(json.loads(r.data_json),default=str).lower(),axis=1)]
 st.dataframe(rr[["pid","participant_type","sheet","assigned_to","updated_at"]],use_container_width=True,hide_index=True)
 if not rr.empty:
  pid=st.selectbox("Open participant",rr.pid.tolist())
  r=getp(pid); d=json.loads(r["data_json"]); p=pref(r["participant_type"])
  st.subheader(f"{d.get(p+'FirstName') or ''} {d.get(p+'Surname') or ''} — {pid}")
  rows=[[f"Visit {n}",label,status(d,p,n),d.get(f"{p}Scheduled_V{n}") or "—",
         d.get(f"{p}Expected_V{n}") or "—",d.get(f"{p}Actual_V{n}") or "—"]
        for n,label in VISITS[r["participant_type"]].items()]
  st.dataframe(pd.DataFrame(rows,columns=["Visit","Timepoint","Status","Scheduled","Expected","Actual"]),use_container_width=True,hide_index=True)

def visits_page(recs,user):
 st.title("📅 Visits")
 q=st.text_input("Participant PID",value=st.session_state.get("visit_pid",""))
 rr=recs[recs.pid.astype(str).str.contains(q,case=False,na=False)] if q else recs.head(0)
 if rr.empty: st.info("Enter a PID to open the participant's visits.")
 else:
  pid=st.selectbox("Participant",rr.pid.tolist(),index=0)
  r=getp(pid); d=json.loads(r["data_json"]); p=pref(r["participant_type"])
  st.subheader(f"{d.get(p+'FirstName') or ''} {d.get(p+'Surname') or ''} — {pid}")
  wf=workflows()
  tabs=st.tabs([f"Visit {n}" for n in VISITS[r["participant_type"]]])
  for tab,(n,label) in zip(tabs,VISITS[r["participant_type"]].items()):
   with tab:
    st.header(f"Visit {n} — {label}")
    current=status(d,p,n)
    st.metric("Database status",current)
    row=wf[(wf.pid==pid)&(wf.visit_no==n)] if not wf.empty else pd.DataFrame()
    if not row.empty:
     st.caption(f"Workflow: {row.iloc[0].workflow_status}")
     if row.iloc[0].correction_comment: st.warning(f"Correction requested: {row.iloc[0].correction_comment}")
    fs=visit_fields(d,n); new=dict(d)
    priority=[f"{p}Scheduled_V{n}",f"{p}Expected_V{n}",f"{p}Earliest_V{n}",f"{p}Latest_V{n}",f"{p}Actual_V{n}",f"{p}Status_V{n}"]
    ordered=[x for x in priority if x in fs]+[x for x in fs if x not in priority]
    for i in range(0,len(ordered),2):
     cols=st.columns(2)
     for col,k in zip(cols,ordered[i:i+2]):
      old=d.get(k)
      with col:
       st.markdown(f"**{k.replace('_',' ')}**"); st.caption(f"`{k}`")
       if any(x in k.lower() for x in ["date","scheduled","expected","earliest","latest","actual"]):
        try: dv=datetime.fromisoformat(str(old)).date() if old else None
        except: dv=None
        nv=st.date_input("Edit",value=dv,key=f"{pid}_{n}_{k}")
        new[k]=nv.isoformat() if nv else None
       else:
        nv=st.text_input("Edit",value="" if old is None else str(old),key=f"{pid}_{n}_{k}")
        new[k]=nv if nv!="" else None
    if user["role"]=="Research Assistant":
     if st.button(f"Save & Submit for Review — Visit {n}",key=f"submit_{pid}_{n}",type="primary"):
      save(pid,new,user["username"])
      workflow(pid,n,"Submitted",user["username"],"Submitted for Research Officer review.")
      st.success("Visit saved and submitted for review."); st.rerun()
    else:
     if st.button(f"Save Visit {n}",key=f"save_{pid}_{n}",type="primary"):
      save(pid,new,user["username"]); audit(user["username"],"UPDATE VISIT",pid,n,"Updated visit fields")
      st.success("Visit saved."); st.rerun()

def review_page(recs,user):
 st.title("🔎 Research Officer Review")
 wf=workflows()
 pending=[]
 for _,r in recs.iterrows():
  d=json.loads(r.data_json); p=pref(r.participant_type)
  for n,label in VISITS[r.participant_type].items():
   x=wf[(wf.pid==r.pid)&(wf.visit_no==n)] if not wf.empty else pd.DataFrame()
   if not x.empty and x.iloc[0].workflow_status=="Submitted":
    pending.append([r.pid,r.participant_type,n,label,r.assigned_to or "Unassigned"])
 st.subheader("Visits awaiting review")
 if pending:
  st.dataframe(pd.DataFrame(pending,columns=["PID","Type","Visit","Timepoint","Assigned RA"]),use_container_width=True,hide_index=True)
  pid=st.selectbox("Participant to review",sorted(set(x[0] for x in pending)))
  vn=st.selectbox("Visit",[x[2] for x in pending if x[0]==pid])
  r=getp(pid); d=json.loads(r["data_json"]); p=pref(r["participant_type"])
  st.info("Review the completed fields on the Visits page, then make your decision here.")
  decision=st.selectbox("Decision",["Approved","Returned for correction"])
  comment=st.text_area("Review comment")
  if st.button("Record review decision",type="primary"):
   workflow(pid,vn,decision,user["username"],comment)
   c=db(); c.execute("""INSERT INTO visit_reviews(pid,visit_no,reviewer,decision,comment,reviewed_at)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(pid,visit_no) DO UPDATE SET reviewer=excluded.reviewer,
                       decision=excluded.decision,comment=excluded.comment,reviewed_at=excluded.reviewed_at""",
                     (pid,vn,user["username"],decision,comment,datetime.now().isoformat(timespec="seconds")))
   c.commit(); c.close()
   st.success("Review decision recorded."); st.rerun()
 else:
  st.success("No visits are currently awaiting review.")
 st.subheader("Recent review decisions")
 rv=reviews()
 if not rv.empty: st.dataframe(rv.head(50),use_container_width=True,hide_index=True)

def reports_page(recs):
 st.title("📈 Reports")
 rows=[]
 for _,r in recs.iterrows():
  d=json.loads(r.data_json); p=pref(r.participant_type)
  for n,label in VISITS[r.participant_type].items():
   rows.append([r.pid,r.participant_type,n,label,status(d,p,n),r.assigned_to or "Unassigned",
                d.get(f"{p}Scheduled_V{n}"),d.get(f"{p}Expected_V{n}"),d.get(f"{p}Actual_V{n}")])
 out=pd.DataFrame(rows,columns=["PID","Type","Visit","Timepoint","Status","Assigned RA","Scheduled","Expected","Actual"])
 st.dataframe(out,use_container_width=True,hide_index=True)
 st.download_button("Download visit report",out.to_csv(index=False).encode(),"study_visit_report.csv","text/csv")

def admin_page(recs,user):
 st.title("⚙️ Administration")
 if user["role"]!="Senior Research Assistant":
  st.warning("Senior Research Assistant access only."); return
 us=users()
 st.subheader("Participant assignment")
 pid=st.selectbox("Participant",recs.pid.tolist())
 ra=us[(us.role=="Research Assistant")&(us.active==1)]
 target=st.selectbox("Assign to",ra.username.tolist() or ["ra.demo"])
 if st.button("Assign participant"):
  c=db(); c.execute("UPDATE participants SET assigned_to=? WHERE pid=?",(target,pid)); c.commit(); c.close()
  audit(user["username"],"ASSIGN",pid,None,f"Assigned to {target}"); st.success("Assignment saved."); st.rerun()
 st.subheader("Users")
 st.dataframe(us,use_container_width=True,hide_index=True)
 with st.form("new_user"):
  un=st.text_input("Username"); name=st.text_input("Display name")
  role=st.selectbox("Role",["Research Assistant","Research Officer","Senior Research Assistant"])
  if st.form_submit_button("Add / activate user"):
   if un.strip() and name.strip():
    c=db(); c.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,1)",(un.strip(),role,name.strip())); c.commit(); c.close()
    audit(user["username"],"USER MANAGEMENT",None,None,f"Added/activated {un.strip()}"); st.success("User saved."); st.rerun()
   else: st.error("Username and display name are required.")
 st.subheader("Audit trail")
 c=db(); a=pd.read_sql_query("SELECT * FROM audit ORDER BY id DESC LIMIT 1000",c); c.close()
 st.dataframe(a,use_container_width=True,hide_index=True)

init(); import_workbook(); login()
user=st.session_state.user
recs=allp()

# Role-specific navigation is explicit and always includes Dashboard.
if user["role"]=="Research Assistant":
 pages=["Dashboard","My Work Queue","Participants","Visits","Reports"]
elif user["role"]=="Research Officer":
 pages=["Dashboard","My Work Queue","Participants","Visits","Review","Reports"]
else:
 pages=["Dashboard","My Work Queue","Participants","Visits","Review","Reports","Administration"]

st.sidebar.title("Study Visit Tracker — DEMO")
st.sidebar.warning("DEMO DATA ONLY — no real participant data")
st.sidebar.caption(f"{user['name']} · {user['role']}")
if st.sidebar.button("Sign out"):
 st.session_state.clear(); st.rerun()
page=st.sidebar.radio("Navigation",pages)

if page=="Dashboard": dashboard(recs)
elif page=="My Work Queue": work_queue(recs,user)
elif page=="Participants": participants_page(recs)
elif page=="Visits": visits_page(recs,user)
elif page=="Review": review_page(recs,user)
elif page=="Reports": reports_page(recs)
elif page=="Administration": admin_page(recs,user)
