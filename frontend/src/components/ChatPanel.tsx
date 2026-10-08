"use client";

import { useState } from "react";
import { createJsonEventParser } from "@/lib/sse";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";
import { highlightColor } from "@/lib/highlights";

type NodeId = number | string;
type Candidate = { id: NodeId; label: string; color: string; size: number[]; center?: number[] };
type EvidenceFrame = { object_id: number; frame_id: number };
type Final = { answer: string; target_ids: NodeId[]; targets: { id: NodeId }[]; related: { id: NodeId }[]; session_id: string;
  evidence: { frames: EvidenceFrame[]; tiebreak: boolean }; latency_ms: number };

export default function ChatPanel({ sceneId, viewpoint, onTargets, selectedObjectId }: {
  sceneId: string;
  viewpoint: () => { position: number[]; forward: number[] } | null;
  onTargets: (ids: NodeId[], related?: NodeId[]) => void;
  selectedObjectId: NodeId | null;
}) {
  const [text, setText] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [answer, setAnswer] = useState("");
  const [evidence, setEvidence] = useState<EvidenceFrame[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(choiceId?: NodeId) {
    if (!text.trim() && choiceId === undefined) return;
    setBusy(true);
    setError("");
    setAnswer("");
    setCandidates([]);
    setEvidence([]);
    try {
      const response = await fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/ask`), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, session_id: sessionId,
          selected_object_id: selectedObjectId, choice_id: choiceId, viewpoint: viewpoint() }),
      });
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const feed = createJsonEventParser((name, payload) => {
        const event = payload as Record<string, unknown>;
        if (name === "token") setAnswer(value => value + String(event.text ?? ""));
        if (name === "reset") setAnswer(String(event.text ?? ""));
        if (name === "error") setError(String(event.message ?? "Query failed."));
        if (name === "candidates" && Array.isArray(event.targets))
          onTargets(event.targets as NodeId[]);
        if (name === "clarify") {
          setAnswer(String(event.message ?? "Please clarify."));
          setCandidates((event.candidates as Candidate[]) ?? []);
          if (event.session_id) setSessionId(String(event.session_id));
          if (Array.isArray(event.candidates))
            onTargets((event.candidates as Candidate[]).map(item => item.id));
        }
        if (name === "final") {
          const final = event as Final;
          setAnswer(final.answer);
          setEvidence(final.evidence?.frames ?? []);
          setSessionId(final.session_id);
          onTargets(final.target_ids ?? final.targets.map(item => item.id), (final.related ?? []).map(item => item.id));
        }
      });
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        feed(decoder.decode(value, { stream: true }));
      }
      feed(decoder.decode());
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  return <section className="chat-panel">
    <h2>Ask about this Scene</h2>
    <form onSubmit={event => { event.preventDefault(); submit(); }}>
      <input aria-label="Ask in English" placeholder="chairs, or the chair next to the desk…"
        value={text} onChange={event => setText(event.target.value)} disabled={busy} />
      <Button type="submit" disabled={busy || !text.trim()}>{busy ? "Working…" : "Ask"}</Button>
    </form>
    {error && <p role="alert">{error}</p>}
    {answer && <p className="chat-answer" aria-live="polite">{answer}</p>}
    {candidates.length > 0 && <div className="clarify-options">{candidates.map((item, index) =>
      <Button key={item.id} variant="outline" disabled={busy} onClick={() => submit(item.id)}
        style={{ borderLeft: `4px solid ${highlightColor(index)}` }}
        title={item.center ? `Position: ${item.center.map(value => value.toFixed(2)).join(", ")} m` : undefined}>
        {item.label} #{item.id} · {item.color} · {item.size.map(value => value.toFixed(2)).join(" × ")} m
      </Button>)}</div>}
    {evidence.length > 0 && <div className="evidence-list">{evidence.slice(0, 2).map(item =>
      <figure key={`${item.object_id}-${item.frame_id}`}>
        <img src={apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/frames/${item.frame_id}.jpg`)}
          alt={`Keyframe ${item.frame_id} showing Object ${item.object_id}`} />
        <figcaption>Keyframe {item.frame_id} · Object {item.object_id}</figcaption>
      </figure>)}</div>}
  </section>;
}
