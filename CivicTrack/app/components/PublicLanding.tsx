"use client";

import { ArrowDown, ArrowRight, CheckCircle2, ClipboardList, MapPin, ShieldCheck, Sparkles, Users, Wrench } from "lucide-react";

export default function PublicLanding({ demoMode, onLogin, onRegister }: { demoMode: boolean; onLogin: () => void; onRegister: () => void }) {
  return <div className="landing-shell">
    <a className="landing-skip" href="#landing-main">Skip to content</a>
    <header className="landing-header">
      <a className="landing-brand" href="#top" aria-label="CivicTrack home"><span><ShieldCheck size={19}/></span><span><b>CivicTrack</b><small>CIVIC ACCOUNTABILITY</small></span></a>
      <nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#capabilities">Capabilities</a><a href="#accountability">Accountability</a></nav>
      <div className="landing-actions"><button className="landing-login" onClick={onLogin}>Sign in</button><button className="landing-register" onClick={onRegister}>Get started <ArrowRight size={15}/></button></div>
    </header>

    <main id="landing-main">
      <section className="landing-hero" id="top">
        <div className="landing-copy">
          {demoMode && <p className="landing-demo-badge"><span/><ShieldCheck size={13}/> DEMONSTRATION MODE · SYNTHETIC DATA</p>}
          <p className="landing-kicker">A clearer path from report to repair</p>
          <h1>Report a problem.<br/><span>See what happens next.</span></h1>
          <p className="landing-lead">CivicTrack gives residents and city teams one shared place to report local issues, follow every update, and confirm when work is complete.</p>
          <div className="landing-cta"><button className="landing-primary" onClick={onRegister}>Report an issue <ArrowRight size={16}/></button><button className="landing-secondary" onClick={onLogin}><Users size={16}/> Sign in</button></div>
          <div className="landing-assurance"><CheckCircle2 size={15}/><span>AI offers guidance. People review the report and decide what happens.</span></div>
        </div>

        <div className="landing-map-card" role="img" aria-label="Illustrative map of synthetic civic issue locations">
          <div className="landing-map-top"><div><span className="map-live-dot"/><b>Neighborhood overview</b></div><span>{demoMode ? "SAMPLE MAP" : "MAP PREVIEW"}</span></div>
          <div className="landing-map-art">
            <svg viewBox="0 0 600 360" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
              <defs><pattern id="map-grid" width="72" height="58" patternUnits="userSpaceOnUse"><path d="M0 16H72M22 0V58M55 0V58" fill="none" stroke="#dce4e3" strokeWidth="1"/><path d="M0 44H72" fill="none" stroke="#e4e9e7" strokeWidth="1"/></pattern></defs>
              <rect width="600" height="360" fill="#eef2eb"/><rect width="600" height="360" fill="url(#map-grid)"/>
              <path d="M-10 260C85 210 142 298 230 226S375 155 618 200" fill="none" stroke="#fffdf7" strokeWidth="23"/><path d="M-10 260C85 210 142 298 230 226S375 155 618 200" fill="none" stroke="#e7bc75" strokeWidth="3"/>
              <path d="M155 -20C176 74 210 112 197 195S219 280 245 382M418 -20C387 71 437 117 412 182S418 292 455 380" fill="none" stroke="#fffdf7" strokeWidth="15"/>
              <path d="M38 42L124 38L146 98L84 127L27 101ZM294 28L366 39L352 94L293 104L264 65ZM474 250L560 242L570 316L499 329L462 293Z" fill="#dcebdc" stroke="#c6ddca" strokeWidth="2"/>
              <text x="53" y="75" fill="#728d78" fontSize="12" fontFamily="sans-serif">RIVERSIDE PARK</text><text x="485" y="284" fill="#728d78" fontSize="11" fontFamily="sans-serif">COMMUNITY GARDEN</text><text x="252" y="183" fill="#6d7c80" fontSize="12" fontFamily="sans-serif">CENTRAL AVENUE</text>
            </svg>
            <span className="landing-pin pin-one"><MapPin size={15}/></span><span className="landing-pin pin-two"><MapPin size={15}/></span><span className="landing-pin pin-three"><MapPin size={15}/></span>
            <div className="landing-map-note"><span>ILLUSTRATIVE LOCATION</span><b>Streetlight repair request</b><small>Sample issue · details are generalized</small></div>
          </div>
          <div className="landing-map-legend"><span><i className="legend-road"/>Roads</span><span><i className="legend-park"/>Public spaces</span><span><i className="legend-issue"/>Issue marker</span><small>Locations are approximate</small></div>
        </div>
      </section>

      <section className="landing-proof" aria-label="Platform capabilities"><div><span>9</span><small>civic issue categories</small></div><div><span>3</span><small>connected user roles</small></div><div><span>1</span><small>verified resolution loop</small></div><p>Counts describe platform setup, not real-world service results.</p></section>

      <section className="landing-section workflow-section" id="how-it-works">
        <div className="landing-section-heading"><p className="landing-eyebrow">HOW IT WORKS</p><h2>One report. A visible path to resolution.</h2><p>Each handoff is recorded, so residents and service teams can see the same progress.</p></div>
        <div className="workflow-grid">
          <article><span className="workflow-number">01</span><div className="workflow-icon"><ClipboardList size={20}/></div><h3>Report the issue</h3><p>Describe what happened, add a photo, and choose the place on the map.</p></article>
          <article><span className="workflow-number">02</span><div className="workflow-icon"><Sparkles size={20}/></div><h3>Review AI suggestions</h3><p>Category, priority, and possible duplicates are suggested with reasons for staff review.</p></article>
          <article><span className="workflow-number">03</span><div className="workflow-icon"><Wrench size={20}/></div><h3>Track the response</h3><p>The assigned team records updates, deadlines, and evidence in the report history.</p></article>
          <article><span className="workflow-number">04</span><div className="workflow-icon"><CheckCircle2 size={20}/></div><h3>Confirm the outcome</h3><p>The resident can confirm the repair or reopen the issue if it still needs work.</p></article>
        </div>
      </section>

      <section className="landing-section capabilities-section" id="capabilities">
        <div className="landing-section-heading"><p className="landing-eyebrow">BUILT FOR FOLLOW-THROUGH</p><h2>Useful tools for people on both sides.</h2></div>
        <div className="capability-grid">
          <article><div className="capability-icon"><MapPin size={19}/></div><h3>Location-aware reporting</h3><p>Use GPS or select a map point. Public views reduce location precision and hide personal contact details.</p></article>
          <article><div className="capability-icon"><Sparkles size={19}/></div><h3>Explainable assistance</h3><p>Local models suggest a category, priority, summary, and related reports. Staff can correct every suggestion.</p></article>
          <article><div className="capability-icon"><Users size={19}/></div><h3>Clear role-based workspaces</h3><p>Residents, department officers, and administrators each get the actions and reports they need.</p></article>
        </div>
      </section>

      <section className="landing-accountability" id="accountability"><div><p className="landing-eyebrow">ACCOUNTABILITY BY DESIGN</p><h2>Completion is only the start of verification.</h2><p>Every status update has a timestamp and an actor. Departments can review service trends while residents retain the ability to confirm or reopen a reported issue.</p><ul><li><CheckCircle2 size={15}/> Published experimental scoring formula</li><li><CheckCircle2 size={15}/> Configurable response targets and escalation windows</li><li><CheckCircle2 size={15}/> Citizen feedback feeds service improvement</li></ul><small>The sample index is an academic demonstration, not an official government ranking.</small></div><div className="accountability-visual"><div className="accountability-card-top"><span>REPORT LIFECYCLE</span><span>DEMO FLOW</span></div><div className="lifecycle-step done"><i><CheckCircle2 size={15}/></i><span><b>Report received</b><small>Reference created</small></span><em>RECORDED</em></div><div className="lifecycle-step done"><i><CheckCircle2 size={15}/></i><span><b>Team assigned</b><small>Department and officer set</small></span><em>RECORDED</em></div><div className="lifecycle-step active"><i><ArrowDown size={15}/></i><span><b>Work submitted</b><small>Evidence ready for resident</small></span><em>VERIFY</em></div><div className="lifecycle-step"><i><CheckCircle2 size={15}/></i><span><b>Resident confirms</b><small>Report is resolved or reopened</small></span><em>NEXT</em></div></div></section>

      <section className="landing-bottom-cta"><div><p className="landing-eyebrow">CIVICTRACK WORKSPACE</p><h2>See the workflow from the inside.</h2><p>Create an account to submit a civic report and follow its status updates.</p></div><div><button className="landing-primary" onClick={onRegister}>Create an account <ArrowRight size={16}/></button><button className="landing-text-button" onClick={onLogin}>Sign in</button></div></section>
    </main>

    <footer className="landing-footer"><a className="landing-brand" href="#top"><span><ShieldCheck size={18}/></span><span><b>CivicTrack</b><small>CIVIC ACCOUNTABILITY</small></span></a><p>CivicTrack is an academic software demonstration. Sample reports and metrics are synthetic and are not actual municipal records.</p><span>Report problems. Track progress. Build better cities.</span></footer>
  </div>;
}
