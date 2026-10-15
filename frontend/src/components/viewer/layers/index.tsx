import { useEffect } from "react";
import { useGLTF } from "@react-three/drei";
import { useLoader, type ThreeEvent } from "@react-three/fiber";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import type { SceneObject, Schemas } from "../../../lib/api/port";
import { useViewer } from "../../../lib/store/viewerStore";
export type SceneLayerProps = {
  sceneId: string;
  assets: Schemas["SceneAssets"];
  objects: SceneObject[];
};
function measurePick(e: ThreeEvent<MouseEvent>) {
  if (!useViewer.getState().measuring) return;
  e.stopPropagation();
  useViewer.getState().pick([e.point.x, e.point.y, e.point.z]);
}
function PointCloudAsset({ url }: { url: string }) {
  const geometry = useLoader(PLYLoader, url),
    measuring = useViewer((s) => s.measuring),
    setBounds = useViewer((s) => s.setBounds);
  useEffect(() => {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    if (box) setBounds({ min: box.min.toArray(), max: box.max.toArray() });
    return () => setBounds(null);
  }, [geometry, setBounds]);
  const colored = geometry.hasAttribute("color");
  return (
    // Only listen while measuring: raycasting millions of points on every click is expensive.
    <points geometry={geometry} onClick={measuring ? measurePick : undefined}>
      <pointsMaterial
        size={0.012}
        sizeAttenuation
        vertexColors={colored}
        color={colored ? "#ffffff" : "#9fb3bb"}
      />
    </points>
  );
}
export function PointCloudLayer({ assets }: SceneLayerProps) {
  const visible = useViewer((s) => s.layers.points);
  return visible && assets.points_url ? (
    <PointCloudAsset url={assets.points_url} />
  ) : null;
}
function MeshAsset({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} onClick={measurePick} />;
}
export function MeshLayer({ assets }: SceneLayerProps) {
  const visible = useViewer((s) => s.layers.mesh);
  if (assets.mesh_url)
    return visible ? <MeshAsset url={assets.mesh_url} /> : null;
  // Without any reconstruction asset, a placeholder floor keeps measuring usable.
  return assets.points_url ? null : (
    <mesh onClick={measurePick} position={[0, 0, -0.05]}>
      <boxGeometry args={[5, 5, 0.1]} />
      <meshStandardMaterial color="#718089" />
    </mesh>
  );
}
export function ObjectBoxesLayer({ objects }: SceneLayerProps) {
  const ids = useViewer((s) => s.highlightedIds),
    select = useViewer((s) => s.select),
    measuring = useViewer((s) => s.measuring),
    visible = useViewer((s) => s.layers.boxes);
  if (!visible) return null;
  return (
    <>
      {objects.map((o) => (
        <mesh
          key={o.id}
          position={o.box.center as [number, number, number]}
          rotation={[0, 0, o.box.yaw || 0]}
          onClick={(e) => {
            if (!measuring) {
              e.stopPropagation();
              select(o.id);
            }
          }}
        >
          <boxGeometry args={o.box.size as [number, number, number]} />
          <meshBasicMaterial
            color={ids.includes(o.id) ? "#f7cb69" : "#75c6b1"}
            wireframe
            transparent
            opacity={ids.includes(o.id) ? 1 : 0.35}
          />
        </mesh>
      ))}
    </>
  );
}
export const sceneLayers: Record<
  string,
  React.ComponentType<SceneLayerProps>
> = { points: PointCloudLayer, mesh: MeshLayer, boxes: ObjectBoxesLayer };
