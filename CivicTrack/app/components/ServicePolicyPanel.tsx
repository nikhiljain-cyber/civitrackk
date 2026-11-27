"use client";

import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, Clock3, Save, ShieldCheck } from "lucide-react";
import { api, json } from "@/app/lib/api";

type ServicePolicy = {
  category: string;
  deadline_hours: number;
  escalation_grace_hours: number;
  updated_at: string;
};

export default function ServicePolicyPanel({ token, notify }: { token: string; notify: (message: string) => void }) {
  const [policies, setPolicies] = useState<ServicePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");

  const refresh = async () => {
    setError("");
    try {
      setPolicies(await api<ServicePolicy[]>("/service-policies", token));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load service targets.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [token]);

  const update = (category: string, values: Partial<ServicePolicy>) => {
    setPolicies(current => current.map(policy => policy.category === category ? { ...policy, ...values } : policy));
  };

  const save = async (event: FormEvent<HTMLFormElement>, policy: ServicePolicy) => {
    event.preventDefault();
    setSaving(policy.category);
    setError("");
    try {
      await api(`/service-policies/${encodeURIComponent(policy.category)}`, token, json("PUT", {
        deadline_hours: Number(policy.deadline_hours),
        escalation_grace_hours: Number(policy.escalation_grace_hours),
      }));
      notify(`${policy.category} service target saved`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save service target.");
    } finally {
      setSaving("");
    }
  };

  return <div className="policy-page">
    <section className="panel policy-intro">
      <span className="policy-icon"><Clock3 size={18}/></span>
      <div><h2>Response targets and escalations</h2><p>Set example service targets by issue category. A first alert is raised when a target passes; a second alert follows after the grace period.</p></div>
      <span className="policy-label"><ShieldCheck size={14}/> ADMIN CONTROL</span>
    </section>
    <div className="policy-notice"><AlertTriangle size={15}/><span>These are configurable CivicTrack prototype targets, not official government rules. Changes apply to new reports. Existing report deadlines remain unchanged so their history stays consistent.</span></div>
    {error && <div className="error-inline">{error}</div>}
    {loading ? <div className="panel policy-empty">Loading saved service targets…</div> : <section className="panel policy-list">
      <div className="policy-list-heading"><h3>Category targets</h3><span>Saved in the application database</span></div>
      {policies.map(policy => <form className="policy-row" key={policy.category} onSubmit={event => save(event, policy)}>
        <div className="policy-category"><b>{policy.category}</b><small>Target hours are measured from report submission.</small></div>
        <label>Response target (hours)<input aria-label={`${policy.category} response target in hours`} type="number" min={1} max={8760} required value={policy.deadline_hours} onChange={event => update(policy.category, { deadline_hours: Number(event.target.value) })}/></label>
        <label>Second escalation after (hours)<input aria-label={`${policy.category} escalation grace in hours`} type="number" min={0} max={8760} required value={policy.escalation_grace_hours} onChange={event => update(policy.category, { escalation_grace_hours: Number(event.target.value) })}/></label>
        <button className="button button-outline" disabled={saving === policy.category || !policy.deadline_hours || policy.escalation_grace_hours < 0}><Save size={14}/>{saving === policy.category ? "Saving…" : "Save"}</button>
      </form>)}
      {!policies.length && <div className="policy-empty">No service categories are configured.</div>}
    </section>}
  </div>;
}
