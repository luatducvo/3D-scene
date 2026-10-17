"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { CameraControls, Html, Line } from "@react-three/drei";
import { Box3, Vector3 } from "three";
import { useFormatter, useTranslations } from "next-intl";
import { sceneLayers, type SceneLayerProps } from "./layers";
import { attachCamera } from "./camera";
import { focusBounds, homePose, visibleBounds } from "./view";
import { useViewer } from "../../lib/store/viewerStore";

function Controls({ objects }: Pick<SceneLayerProps, "objects">) {
  const ref = useRef<CameraControls>(null),
    objectsRef = useRef(objects),
    bounds = useViewer((s) => visibleBounds(s.layers, s.loadedBounds));
  objectsRef.current = objects;
  /** Remember where the camera is, for questions that depend on the viewpoint. */
  const remember = () => {
    if (ref.current)
      useViewer
        .getState()
        .setCamera(
          ref.current.getPosition(new Vector3()).toArray(),
          ref.current.getTarget(new Vector3()).toArray(),
        );
  };
  const home = () => {
    const { layers, loadedBounds } = useViewer.getState();
    const { position, target } = homePose(visibleBounds(layers, loadedBounds));
    void ref.current?.setLookAt(...position, ...target, false);
    useViewer.getState().setCamera(position, target);
  };
  const focus = (ids: string[]) => {
    const box = focusBounds(objectsRef.current, ids);
    if (box && ref.current)
      void ref.current.fitToBox(
        new Box3(new Vector3(...box.min), new Vector3(...box.max)),
        true,
        {
          paddingTop: 0.4,
          paddingBottom: 0.4,
          paddingLeft: 0.4,
          paddingRight: 0.4,
        },
      );
  };
  useEffect(() => {
    const detach = attachCamera({ goHome: home, focus });
    // A focus given before the canvas existed still applies.
    const pending = useViewer.getState().highlightedIds;
    if (pending.length) focus(pending);
    return detach;
  }, []);
  // The room's frame changed (a layer loaded or the view mode switched): show all of it.
  useEffect(home, [bounds]);
  return <CameraControls ref={ref} onRest={remember} onEnd={remember} />;
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
/**
 * Suspense fallback inside the canvas: reports loading instead of drawing it. drei's `Html` must
 * not be a fallback, because unmounting it while the canvas commits throws in React 19.
 */
function LoadingSignal({ onChange }: { onChange: (loading: boolean) => void }) {
  useEffect(() => {
    onChange(true);
    return () => onChange(false);
  }, [onChange]);
  return null;
}
export default function SceneCanvas(props: SceneLayerProps) {
  const t = useTranslations();
  const [loading, setLoading] = useState(false);
  return (
    <>
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
        <Suspense fallback={<LoadingSignal onChange={setLoading} />}>
          {Object.entries(sceneLayers).map(([key, Layer]) => (
            <Layer key={key} {...props} />
          ))}
        </Suspense>
        <Measurement />
        <Controls objects={props.objects} />
      </Canvas>
      {loading && (
        <div className="viewer-state viewer-loading">
          <span className="measurement" role="status">
            {t("loading")}
          </span>
        </div>
      )}
    </>
  );
}
