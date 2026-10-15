"use client";
import { Suspense, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { CameraControls, Html, Line } from "@react-three/drei";
import { Box3, Vector3 } from "three";
import { sceneLayers, SceneLayerProps } from "./layers";
import { useViewer } from "../../lib/store/viewerStore";
function Controls({ objects }: Pick<SceneLayerProps, "objects">) {
  const ref = useRef<CameraControls>(null),
    ids = useViewer((s) => s.highlightedIds),
    bounds = useViewer((s) => s.bounds);
  useEffect(() => {
    // Frame the whole reconstruction once it has loaded.
    if (!bounds || !ref.current) return;
    const box = new Box3(
        new Vector3(...bounds.min),
        new Vector3(...bounds.max),
      ),
      center = box.getCenter(new Vector3()),
      size = box.getSize(new Vector3()),
      distance = Math.max(size.x, size.y, size.z) * 1.1;
    void ref.current.setLookAt(
      center.x + distance * 0.6,
      center.y - distance * 0.8,
      center.z + distance * 0.7,
      center.x,
      center.y,
      center.z,
      false,
    );
  }, [bounds]);
  useEffect(() => {
    if (!ids.length || !ref.current) return;
    const box = new Box3();
    objects
      .filter((o) => ids.includes(o.id))
      .forEach((o) => {
        const c = new Vector3(...o.box.center),
          half = new Vector3(...o.box.size).multiplyScalar(0.5);
        box.expandByPoint(c.clone().sub(half));
        box.expandByPoint(c.clone().add(half));
      });
    if (!box.isEmpty())
      void ref.current.fitToBox(box, true, {
        paddingTop: 1,
        paddingBottom: 1,
        paddingLeft: 1,
        paddingRight: 1,
      });
  }, [ids, objects]);
  return (
    <CameraControls
      ref={ref}
      onEnd={() => {
        if (ref.current) {
          const p = ref.current.getPosition(new Vector3()),
            target = ref.current.getTarget(new Vector3());
          useViewer.getState().setCamera(p.toArray(), target.toArray());
        }
      }}
    />
  );
}
function Measurement() {
  const points = useViewer((s) => s.points);
  if (points.length !== 2) return null;
  const distance = new Vector3(...points[0]).distanceTo(
    new Vector3(...points[1]),
  );
  const middle = new Vector3(...points[0]).lerp(new Vector3(...points[1]), 0.5);
  return (
    <>
      <Line points={points} color="#f7cb69" lineWidth={3} />
      <Html position={middle}>
        <span className="measurement">{distance.toFixed(3)} m</span>
      </Html>
    </>
  );
}
export default function SceneCanvas(props: SceneLayerProps) {
  return (
    <Canvas
      camera={{
        position: [6, -8, 5],
        up: [0, 0, 1],
        fov: 45,
        near: 0.01,
        far: 500,
      }}
      onCreated={({ raycaster }) => {
        // Picks land within 2 cm of a point instead of three.js' default of one meter.
        raycaster.params.Points.threshold = 0.02;
      }}
    >
      <color attach="background" args={["#17232a"]} />
      <ambientLight intensity={1.3} />
      <directionalLight position={[3, -3, 8]} intensity={2} />
      <Suspense fallback={null}>
        {Object.entries(sceneLayers).map(([key, Layer]) => (
          <Layer key={key} {...props} />
        ))}
      </Suspense>
      <Measurement />
      <Controls objects={props.objects} />
    </Canvas>
  );
}
