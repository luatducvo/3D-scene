"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import { BufferAttribute, BufferGeometry, DataTexture, GLSL3, NearestFilter, PerspectiveCamera,
  RGBAFormat, Vector3 } from "three";
import { decodeMesh, SceneMesh } from "@/lib/mesh";
import { Button } from "@/components/ui/button";
import ChatPanel from "@/components/ChatPanel";
import { apiUrl } from "@/lib/api";
import { HIGHLIGHT_COLORS } from "@/lib/highlights";

type Structure = { id: string; kind: string; normal: [number, number, number]; offset: number;
  min?: [number, number, number]; max?: [number, number, number] };
type ObjectItem = { id: number; label: string; confidence: number; color: string;
  rgb: [number, number, number]; vertices: number; keyframes: number[];
  center: [number, number, number]; size: [number, number, number] };
type Relation = { predicate: string; subject: string; anchor: string; score: number };

const vertexShader = `
attribute vec3 color;
attribute float instanceId;
attribute float structureFlag;
varying vec3 vColor;
flat varying float vInstanceId;
varying float vStructureFlag;
void main() {
  vColor = color;
  vInstanceId = instanceId;
  vStructureFlag = structureFlag;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;
const fragmentShader = `
uniform sampler2D stateTexture;
uniform float stateWidth;
uniform bool hasSelection;
uniform bool hasStructureSelection;
varying vec3 vColor;
flat varying float vInstanceId;
varying float vStructureFlag;
out vec4 outColor;
void main() {
  vec3 base = vColor;
  vec4 state = vInstanceId >= 0.0 ? texture(stateTexture,
    vec2((floor(vInstanceId + 0.5) + 0.5) / stateWidth, 0.5)) : vec4(0.0);
  if (hasStructureSelection && vStructureFlag > 0.5) state = vec4(vColor, 1.0);
  if (hasSelection) {
    base = state.a > 0.5 ? mix(base, state.rgb, 0.72) : base * 0.24;
  }
  outColor = vec4(base, hasSelection && state.a < 0.5 ? 0.12 : 1.0);
}`;

export default function SceneCanvas({ sceneId }: { sceneId: string }) {
  const [mesh, setMesh] = useState<SceneMesh | null>(null);
  const [error, setError] = useState("");
  const [clicked, setClicked] = useState<number | null>(null);
  const [structures, setStructures] = useState<Structure[]>([]);
  const [showStructures, setShowStructures] = useState(false);
  const [objects, setObjects] = useState<ObjectItem[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [filter, setFilter] = useState("");
  const [highlightTargets, setHighlightTargets] = useState<number[]>([]);
  const [selectedStructureIds, setSelectedStructureIds] = useState<string[]>([]);
  const cameraRef = useRef<PerspectiveCamera | null>(null);
  const selectionTexture = useMemo(() => {
    const width = Math.max(1, ...objects.map(item => item.id + 1));
    const data = new Uint8Array(width * 4);
    const selectedIds = highlightTargets.length ? highlightTargets : clicked !== null && clicked >= 0 ? [clicked] : [];
    selectedIds.forEach((id, index) => { if (id >= 0 && id < width) data.set([...HIGHLIGHT_COLORS[index % HIGHLIGHT_COLORS.length], 255], id * 4); });
    const texture = new DataTexture(data, width, 1, RGBAFormat);
    texture.magFilter = texture.minFilter = NearestFilter;
    texture.needsUpdate = true;
    return { texture, width, active: selectedIds.length > 0 };
  }, [objects, clicked, highlightTargets]);
  useEffect(() => () => selectionTexture.texture.dispose(), [selectionTexture]);
  useEffect(() => {
    fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/mesh`))
      .then(async response => {
        if (!response.ok) throw new Error(`Mesh unavailable: HTTP ${response.status}`);
        setMesh(decodeMesh(await response.arrayBuffer()));
      })
      .catch(error => setError(String(error)));
    fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/structures`))
      .then(response => response.ok ? response.json() : [])
      .then(setStructures)
      .catch(() => {});
    fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/objects`))
      .then(response => response.ok ? response.json() : [])
      .then(setObjects).catch(() => {});
    fetch(apiUrl(`/v1/scenes/${encodeURIComponent(sceneId)}/graph`))
      .then(response => response.ok ? response.json() : { relations: [] })
      .then(graph => setRelations(graph.relations)).catch(() => {});
  }, [sceneId]);
  const { geometry, center, radius } = useMemo(() => {
    if (!mesh) return { geometry: null, center: new Vector3(), radius: 5 };
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(mesh.positions, 3));
    const colors = mesh.colors.slice();
    const structureFlags = new Float32Array(mesh.positions.length / 3);
    if (showStructures) {
      for (let i = 0; i < mesh.positions.length / 3; i++) {
        const x = mesh.positions[i * 3];
        const y = mesh.positions[i * 3 + 1];
        const z = mesh.positions[i * 3 + 2];
        const structure = structures.find(item =>
          (selectedStructureIds.length === 0 || selectedStructureIds.includes(item.id)) &&
          Math.abs(item.normal[0] * x + item.normal[1] * y + item.normal[2] * z - item.offset) < .07 &&
          (item.kind === "floor" || (item.min && item.max &&
            z >= item.min[2] && z <= item.max[2])));
        if (structure) {
          const rgb = structure.kind === "floor" ? [245, 181, 79] : [83, 190, 224];
          colors.set(rgb, i * 3);
          if (selectedStructureIds.length) structureFlags[i] = 1;
        }
      }
    }
    geometry.setAttribute("color", new BufferAttribute(colors, 3, true));
    geometry.setAttribute("instanceId", new BufferAttribute(Float32Array.from(mesh.instanceIds), 1));
    geometry.setAttribute("structureFlag", new BufferAttribute(structureFlags, 1));
    geometry.setIndex(new BufferAttribute(mesh.indices, 1));
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();
    const bounds = geometry.boundingBox!;
    const center = bounds.getCenter(new Vector3());
    const radius = Math.max(bounds.getSize(new Vector3()).length(), 1);
    return { geometry, center, radius };
  }, [mesh, structures, showStructures, selectedStructureIds]);
  useEffect(() => () => geometry?.dispose(), [geometry]);
  function onClick(event: ThreeEvent<MouseEvent>) {
    if (!mesh || event.faceIndex == null) return;
    const index = mesh.indices[event.faceIndex * 3 + 2];
    setHighlightTargets([]);
    setSelectedStructureIds([]);
    setClicked(mesh.instanceIds[index]);
  }
  const selected = objects.find(item => item.id === clicked);
  useEffect(() => {
    const camera = cameraRef.current;
    if (!camera || !selected) return;
    const target = new Vector3(...selected.center);
    const direction = camera.position.clone().sub(center).normalize();
    const distance = Math.max(new Vector3(...selected.size).length() * 2.5, 1.2);
    camera.position.copy(target).addScaledVector(direction, distance);
    camera.lookAt(target);
  }, [selected, center]);
  const selectedRelations = relations.filter(item => item.subject === String(clicked)).slice(0, 30);
  return <div className="viewer-layout"><div className="viewer">
    {error && <p role="alert">{error}</p>}
    {!mesh && !error && <p>Loading mesh…</p>}
    {mesh && geometry && <>
      <Button variant="outline" className="structure-toggle" onClick={() => {
        setSelectedStructureIds([]); setShowStructures(value => !value);
      }}>
        {showStructures ? "Hide" : "Show"} Structures
      </Button>
      <Canvas camera={{ position: [center.x + radius, center.y - radius, center.z + radius / 2],
                        fov: 55, near: 0.01, far: radius * 50 }}
        onCreated={({ camera }) => {
          camera.up.set(0, 0, 1);
          cameraRef.current = camera as PerspectiveCamera;
        }}>
        <color attach="background" args={["#111b2d"]} />
        <ambientLight intensity={1.8} />
        <directionalLight position={[5, 4, 8]} intensity={1.2} />
        <mesh geometry={geometry} onClick={onClick}>
          <shaderMaterial vertexShader={vertexShader} fragmentShader={fragmentShader} glslVersion={GLSL3}
            transparent depthWrite={!selectionTexture.active && selectedStructureIds.length === 0}
            uniforms={{ stateTexture: { value: selectionTexture.texture },
              stateWidth: { value: selectionTexture.width },
              hasSelection: { value: selectionTexture.active || selectedStructureIds.length > 0 },
              hasStructureSelection: { value: selectedStructureIds.length > 0 } }} side={2} />
        </mesh>
        {selected && <mesh position={selected.center}>
          <boxGeometry args={selected.size} />
          <meshBasicMaterial wireframe color="#ffca28" />
        </mesh>}
        <OrbitControls target={selected ? selected.center : center} makeDefault />
      </Canvas>
      <div className="viewer-hint">Drag to orbit · scroll to zoom
        {clicked !== null && <span> · Instance {clicked < 0 ? "unassigned" : clicked}</span>}
      </div>
    </>}
  </div><aside className="object-panel">
    <h2>Objects <small>{objects.length}</small></h2>
    <label>Filter by label<input value={filter} onChange={event => setFilter(event.target.value)}
      placeholder="chair, table…" /></label>
    <div className="object-list">{objects.filter(item =>
      item.label.toLowerCase().includes(filter.toLowerCase())).map(item =>
      <button className={clicked === item.id ? "object-item selected" : "object-item"}
        key={item.id} onClick={() => { setHighlightTargets([]); setSelectedStructureIds([]); setClicked(item.id); }}>
        <span className="swatch" style={{ backgroundColor: `rgb(${item.rgb.join(",")})` }} />
        <span><strong>{item.label}</strong><small>#{item.id} · {Math.round(item.confidence * 100)}% · {item.color}</small></span>
      </button>)}</div>
    {selected && <div className="object-details"><h3>{selected.label} #{selected.id}</h3>
      <p>{Math.round(selected.confidence * 100)}% confidence · {selected.vertices.toLocaleString()} vertices</p>
      <p>Color: {selected.color}</p>
      <h4>Relations</h4>
      {selectedRelations.length === 0 ? <p>None found.</p> : selectedRelations.map((relation, index) =>
        <button className="relation-item" key={`${relation.predicate}-${relation.anchor}-${index}`}
          onClick={() => {
            const id = Number(relation.anchor);
            setHighlightTargets([]);
            if (Number.isInteger(id)) { setSelectedStructureIds([]); setClicked(id); }
            else { setClicked(null); setSelectedStructureIds(relation.anchor === "room" ? [] : relation.anchor.split(",")); setShowStructures(relation.anchor !== "room"); }
          }}>
          {relation.predicate.toLowerCase().replaceAll("_", " ")} → {objects.find(item =>
            String(item.id) === relation.anchor)?.label ?? relation.anchor}
        </button>)}
    </div>}
  </aside><ChatPanel sceneId={sceneId} selectedObjectId={clicked ?? (selectedStructureIds.length === 1 ? selectedStructureIds[0] : null)} onTargets={ids => {
    const objectIds = ids.filter((id): id is number => typeof id === "number");
    const structureIds = ids.filter((id): id is string => typeof id === "string" && id !== "room");
    setHighlightTargets(objectIds);
    setClicked(objectIds.length === 1 ? objectIds[0] : null);
    setSelectedStructureIds(structureIds);
    if (structureIds.length) setShowStructures(true);
  }} viewpoint={() => {
    const camera = cameraRef.current;
    if (!camera) return null;
    const forward = camera.getWorldDirection(new Vector3());
    return { position: camera.position.toArray(), forward: forward.toArray() };
  }} /></div>;
}
