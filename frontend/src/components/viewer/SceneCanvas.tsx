"use client";
import { Suspense, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { CameraControls, Html, Line } from "@react-three/drei";
import { Box3, Vector3 } from "three";
import { useFormatter, useTranslations } from "next-intl";
import { sceneLayers, type SceneLayerProps } from "./layers";
import { useViewer } from "../../lib/store/viewerStore";

function Controls({ objects }: Pick<SceneLayerProps, "objects">) {
  const ref = useRef<CameraControls>(null),
    ids = useViewer((s) => s.highlightedIds),
    bounds = useViewer((s) => s.bounds),
    homeRevision = useViewer((s) => s.homeRevision),
    focusRevision = useViewer((s) => s.focusRevision);
  useEffect(() => {
    if (!ref.current) return;
    const box = bounds
      ? new Box3(new Vector3(...bounds.min), new Vector3(...bounds.max))
      : new Box3(new Vector3(-2.5, -2.5, 0), new Vector3(2.5, 2.5, 3));
    const center = box.getCenter(new Vector3()),
      size = box.getSize(new Vector3()),
      distance = Math.max(size.x, size.y, size.z) * 1.35;
    void ref.current.setLookAt(
      center.x + distance * 0.6,
      center.y - distance * 0.8,
      center.z + distance * 0.7,
      center.x,
      center.y,
      center.z,
      false,
    );
    useViewer
      .getState()
      .setCamera(
        [
          center.x + distance * 0.6,
          center.y - distance * 0.8,
          center.z + distance * 0.7,
        ],
        center.toArray(),
      );
  }, [bounds, homeRevision]);
  useEffect(() => {
    if (!ids.length || !ref.current) return;
    const box = new Box3();
    objects
      .filter((o) => ids.includes(o.id))
      .forEach((o) => {
        const c = new Vector3(...o.box.center),
          half = new Vector3(...o.box.size).multiplyScalar(0.5);
        // Enclose rotated boxes rather than clipping their corners on camera flight.
        const yaw = o.box.yaw || 0,
          x =
            Math.abs(Math.cos(yaw)) * half.x + Math.abs(Math.sin(yaw)) * half.y,
          y =
            Math.abs(Math.sin(yaw)) * half.x + Math.abs(Math.cos(yaw)) * half.y;
        const extent = new Vector3(x, y, half.z);
        box.expandByPoint(c.clone().sub(extent));
        box.expandByPoint(c.clone().add(extent));
      });
    if (!box.isEmpty())
      void ref.current.fitToBox(box, true, {
        paddingTop: 0.4,
        paddingBottom: 0.4,
        paddingLeft: 0.4,
        paddingRight: 0.4,
      });
  }, [ids, objects, focusRevision]);
  return (
    <CameraControls
      ref={ref}
      onRest={() => {
        if (ref.current)
          useViewer
            .getState()
            .setCamera(
              ref.current.getPosition(new Vector3()).toArray(),
              ref.current.getTarget(new Vector3()).toArray(),
            );
      }}
      onEnd={() => {
        if (ref.current)
          useViewer
            .getState()
            .setCamera(
              ref.current.getPosition(new Vector3()).toArray(),
              ref.current.getTarget(new Vector3()).toArray(),
            );
      }}
    />
  );
}
function Measurement() {
  const format = useFormatter();
  const points = useViewer((s) => s.points);
  return (
    <>
      {points.map((point, i) => (
        <mesh key={i} position={point}>
          <sphereGeometry args={[0.025, 12, 12]} />
          <meshBasicMaterial color="#CFF5DD" depthTest={false} />
        </mesh>
      ))}
      {points.length === 2 && (
        <>
          <Line
            points={points}
            color="#CFF5DD"
            lineWidth={2}
            dashed
            dashSize={0.06}
            gapSize={0.04}
          />
          <Html
            position={new Vector3(...points[0]).lerp(
              new Vector3(...points[1]),
              0.5,
            )}
            center
          >
            <span className="measurement">
              {format.number(
                new Vector3(...points[0]).distanceTo(new Vector3(...points[1])),
                { maximumFractionDigits: 3 },
              )}{" "}
              m
            </span>
          </Html>
        </>
      )}
    </>
  );
}
export default function SceneCanvas(props: SceneLayerProps) {
  const t = useTranslations();
  return (
    <Canvas
      camera={{
        position: [6, -8, 5],
        up: [0, 0, 1],
        fov: 45,
        near: 0.01,
        far: 500,
      }}
      onPointerMissed={() => {
        if (!useViewer.getState().measuring) useViewer.getState().deselect();
      }}
      onCreated={({ raycaster }) => {
        raycaster.params.Points.threshold = 0.02;
      }}
    >
      <color attach="background" args={["#142326"]} />
      <ambientLight intensity={1.3} />
      <directionalLight position={[3, -3, 8]} intensity={2} />
      <Suspense
        fallback={
          <Html center>
            <span className="measurement" role="status">
              {t("loading")}
            </span>
          </Html>
        }
      >
        {Object.entries(sceneLayers).map(([key, Layer]) => (
          <Layer key={key} {...props} />
        ))}
      </Suspense>
      <Measurement />
      <Controls objects={props.objects} />
    </Canvas>
  );
}
