"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { paths } from "@/generated/api";
import { Button } from "@/components/ui/button";
import { apiUrl } from "@/lib/api";

type Scene = { id: string; status: string; error: string | null };
type HealthResponse = paths["/v1/health"]["get"]["responses"][200]["content"]["application/json"];

export default function Home() {
  const [status, setStatus] = useState("Checking API…");
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("S1");
  const [deletePackage, setDeletePackage] = useState(false);
  async function refresh() {
    const sceneResponse = await fetch(apiUrl("/v1/scenes"));
    if (sceneResponse.ok) setScenes(await sceneResponse.json());
  }
  useEffect(() => {
    fetch(apiUrl("/v1/health"))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body: HealthResponse = await response.json();
        setStatus(body.status === "ok" ? "API is online" : "API is unavailable");
      })
      .catch(() => setStatus("API is unavailable"));
    refresh().catch(() => setMessage("Could not load Scenes."));
  }, []);
  useEffect(() => {
    const pending = scenes.filter(scene => scene.status === "imported" || scene.status === "processing");
    const streams = pending.map(scene => {
      const stream = new EventSource(apiUrl(`/v1/scenes/${encodeURIComponent(scene.id)}/events`));
      stream.addEventListener("progress", event => {
        const update = JSON.parse((event as MessageEvent).data);
        setMessage(`${scene.id}: ${update.stage ?? update.status}`);
        refresh().catch(() => {});
        if (["complete", "failed"].includes(update.status)) stream.close();
      });
      return stream;
    });
    return () => streams.forEach(stream => stream.close());
  }, [scenes.map(scene => `${scene.id}:${scene.status}`).join("|")]);
  async function submit(data: FormData, allowReplace = false) {
    setBusy(true);
    setMessage("");
    if (allowReplace) data.set("replace", "true");
    try {
      const response = await fetch(apiUrl("/v1/imports"), { method: "POST", body: data });
      const body = await response.json();
      if (response.status === 409 && confirm("A different Package exists for this scan. Replace its Scene and artifacts?")) {
        await submit(data, true);
        return;
      }
      if (!response.ok) throw new Error(body.detail ?? `HTTP ${response.status}`);
      setMessage(`${body.scene_id}: ${body.status}`);
      await refresh();
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }
  async function reprocess(sceneId: string) {
    const response = await fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/reprocess`), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage }),
    });
    const body = await response.json();
    setMessage(response.ok ? `${sceneId}: processing again` : body.detail);
    await refresh();
  }
  async function remove(sceneId: string) {
    if (!confirm(`Delete Scene ${sceneId}?`)) return;
    const response = await fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}?delete_package=${deletePackage}`), { method: "DELETE" });
    const body = await response.json();
    setMessage(response.ok ? `${sceneId}: deleted` : body.detail);
    await refresh();
  }
  return <main>
    <div className="eyebrow">LOCAL 3D EXPLORER</div>
    <h1>Scenes</h1>
    <p className="muted">Upload an aligned ScanNet Package, then explore its mesh.</p>
    <div className="status"><span className={status === "API is online" ? "dot online" : "dot"} />{status}</div>
    <section className="card">
      <h2>Import a Package</h2>
      <p className="muted">Prepare your Scan outside S3D, then upload its .s3dpkg file. Package v2 is required.</p>
      <label className="upload">Drop or select a .s3dpkg file
        <input type="file" accept=".s3dpkg" disabled={busy} onChange={event => {
          const file = event.target.files?.[0];
          if (file) { const data = new FormData(); data.set("file", file); submit(data); }
        }} />
      </label>
    </section>
    {message && <p role="status" className="message">{message}</p>}
    <section className="card"><h2>Your Scenes</h2>
      <div className="scene-options"><label>Reprocess from <select value={stage} onChange={event => setStage(event.target.value)}>
        {["S1", "S2", "S3", "S4a", "S4b", "S5", "S6"].map(value => <option key={value}>{value}</option>)}
      </select></label><label><input type="checkbox" checked={deletePackage}
        onChange={event => setDeletePackage(event.target.checked)} /> Delete source Package with Scene</label></div>
      {scenes.length === 0 ? <p className="muted">No Scenes imported yet.</p> :
        <div className="scene-list">{scenes.map(scene => <div className="scene-row" key={scene.id}>
          <div><strong>{scene.id}</strong><small>{scene.error || scene.status}</small></div>
          <div className="scene-actions">
            {scene.status === "ready" && <Link href={`/scene?id=${scene.id}`}>Open mesh →</Link>}
            {!["imported", "processing"].includes(scene.status) && <>
              <Button variant="ghost" onClick={() => reprocess(scene.id)}>Reprocess</Button>
              <Button variant="ghost" onClick={() => remove(scene.id)}>Delete</Button>
            </>}
          </div>
        </div>)}</div>}
    </section>
  </main>;
}
