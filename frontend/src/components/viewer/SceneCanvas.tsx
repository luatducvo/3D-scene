import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { CameraControls, Html, Line } from "@react-three/drei";
import { Box3, Vector3 } from "three";
import { useFormatter, useTranslations } from "use-intl";
import { sceneLayers, type SceneLayerProps } from "./layers";
import { attachCamera } from "./camera";
import { pickAt } from "./picking";
import { focusBounds, homePose, labelAnchor, visibleBounds } from "./view";
import { cursor, useViewer } from "../../lib/store/viewerStore";

/** A press that moves less than this many pixels is a click, not an orbit or pan. */
const CLICK_SLOP_PX = 4;
/**
 * Hover and click on Objects through GPU picking. Pointer moves only record the position; the next
 * focus picks once, so picking runs at most once per focus and never while dragging or measuring.
 */
function Picker({
  objects,
  membership,
}: Pick<SceneLayerProps, "objects" | "membership">) {
  const gl = useThree((s) => s.gl),
    camera = useThree((s) => s.camera);
  const pending = useRef<{ x: number; y: number; cx: number; cy: number }>(
    null,
  );
  /** The Object last picked under the pointer, so the cursor can follow interaction changes. */
  const under = useRef<string | null>(null);
  const known = useRef(new Set<string>());
  known.current = new Set(objects.map((o) => o.id));
  /** The known Object id drawn at canvas pixel (x, y), or null. */
  const objectAt = (x: number, y: number) => {
    if (!membership) return null;
    const index = pickAt(gl, camera, x, y);
    const id = index === null ? undefined : membership.ids[index];
    return id && known.current.has(id) ? id : null;
  };
  const objectAtRef = useRef(objectAt);
  objectAtRef.current = objectAt;
  useEffect(() => {
    const canvas = gl.domElement;
    let press: { x: number; y: number } | null = null;
    const local = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    const leave = () => {
      pending.current = null;
      under.current = null;
      useViewer.getState().hover(null);
      canvas.style.cursor = "";
    };
    const move = (e: PointerEvent) => {
      if (e.buttons || useViewer.getState().measuring) return leave();
      pending.current = { ...local(e), cx: e.clientX, cy: e.clientY };
    };
    const down = (e: PointerEvent) => {
      press = e.button === 0 ? local(e) : null;
    };
    const up = (e: PointerEvent) => {
      const start = press;
      press = null;
      if (!start || e.button !== 0 || useViewer.getState().measuring) return;
      const { x, y } = local(e);
      if (Math.hypot(x - start.x, y - start.y) > CLICK_SLOP_PX) return;
      useViewer.getState().click(objectAtRef.current(x, y));
    };
    // A click, Esc or a Search changes what a click reaches without the pointer moving.
    const unsubscribe = useViewer.subscribe((state) => {
      canvas.style.cursor = cursor(state, under.current);
    });
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerleave", leave);
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointerup", up);
    return () => {
      unsubscribe();
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointerup", up);
      leave();
    };
  }, [gl]);
  useFrame(() => {
    const at = pending.current;
    if (!at) return;
    pending.current = null;
    const id = objectAt(at.x, at.y);
    under.current = id;
    useViewer.getState().hover(id ? { id, x: at.cx, y: at.cy } : null);
    gl.domElement.style.cursor = cursor(useViewer.getState(), id);
  });
  return null;
}
/** The hovered Object's label next to the cursor. */
function HoverLabel({ objects }: Pick<SceneLayerProps, "objects">) {
  const hovered = useViewer((s) => s.hovered);
  const object = hovered && objects.find((o) => o.id === hovered.id);
  if (!hovered || !object) return null;
  return (
    <div
      className="hover-label"
      role="tooltip"
      style={{ left: hovered.x + 14, top: hovered.y + 14 }}
    >
      {object.label}
    </div>
  );
}
/** The selected Object's label on top of its box, moving with the camera. */
function SelectionLabel({ objects }: Pick<SceneLayerProps, "objects">) {
  const selectedId = useViewer((s) => s.selectedId);
  const object = selectedId && objects.find((o) => o.id === selectedId);
  if (!object) return null;
  return (
    <Html position={labelAnchor(object.box)} center zIndexRange={[4, 0]}>
      <span className="selection-label">{object.label}</span>
    </Html>
  );
}

function Controls({ objects }: Pick<SceneLayerProps, "objects">) {
  const ref = useRef<CameraControls>(null),
    objectsRef = useRef(objects),
    bounds = useViewer((s) => visibleBounds(s.layers, s.loadedBounds));
  objectsRef.current = objects;
  const home = () => {
    const { layers, loadedBounds } = useViewer.getState();
    const { position, target } = homePose(visibleBounds(layers, loadedBounds));
    void ref.current?.setLookAt(...position, ...target, false);
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
  // The room's focus changed (a layer loaded or the view mode switched): show all of it.
  useEffect(home, [bounds]);
  return <CameraControls ref={ref} />;
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
        onCreated={({ raycaster }) => {
          raycaster.params.Points.threshold = 0.02;
        }}
      >
        <color attach="background" args={["#f0ead8"]} />
        <ambientLight intensity={1.3} />
        <directionalLight position={[3, -3, 8]} intensity={2} />
        <Suspense fallback={<LoadingSignal onChange={setLoading} />}>
          {Object.entries(sceneLayers).map(([key, Layer]) => (
            <Layer key={key} {...props} />
          ))}
        </Suspense>
        <Measurement />
        <SelectionLabel objects={props.objects} />
        <Controls objects={props.objects} />
        <Picker objects={props.objects} membership={props.membership} />
      </Canvas>
      <HoverLabel objects={props.objects} />
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
