"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";

const SceneCanvas = dynamic(() => import("@/components/SceneCanvas"), { ssr: false });

export default function ScenePage() {
  const [sceneId, setSceneId] = useState("");
  useEffect(() => setSceneId(new URLSearchParams(window.location.search).get("id") || ""), []);
  return <main className="scene-page">
    <Link href="/">← Scenes</Link>
    <h1>{sceneId || "Scene"}</h1>
    {sceneId ? <SceneCanvas sceneId={sceneId} /> : <p>Choose a Scene from the home page.</p>}
  </main>;
}
