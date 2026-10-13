import { useGLTF } from "@react-three/drei";
import type { SceneObject, Schemas } from "../../../lib/api/port";
import { useViewer } from "../../../lib/store/viewerStore";
export type SceneLayerProps = {
  sceneId: string;
  assets: Schemas["SceneAssets"];
  objects: SceneObject[];
};
function MeshAsset({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const measuring = useViewer((s) => s.measuring),
    pick = useViewer((s) => s.pick);
  return (
    <primitive
      object={scene}
      onClick={(e: {
        stopPropagation: () => void;
        point: { x: number; y: number; z: number };
      }) => {
        if (measuring) {
          e.stopPropagation();
          pick([e.point.x, e.point.y, e.point.z]);
        }
      }}
    />
  );
}
export function MeshLayer({ assets }: SceneLayerProps) {
  const pick = useViewer((s) => s.pick),
    measuring = useViewer((s) => s.measuring);
  return assets.mesh_url ? (
    <MeshAsset url={assets.mesh_url} />
  ) : (
    <mesh
      onClick={(e) => {
        if (measuring) {
          e.stopPropagation();
          pick([e.point.x, e.point.y, e.point.z]);
        }
      }}
      position={[0, 0, -0.05]}
    >
      <boxGeometry args={[5, 5, 0.1]} />
      <meshStandardMaterial color="#718089" />
    </mesh>
  );
}
export function ObjectBoxesLayer({ objects }: SceneLayerProps) {
  const ids = useViewer((s) => s.highlightedIds),
    select = useViewer((s) => s.select),
    measuring = useViewer((s) => s.measuring);
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
            opacity={ids.includes(o.id) ? 1 : 0.55}
          />
        </mesh>
      ))}
    </>
  );
}
export const sceneLayers: Record<
  string,
  React.ComponentType<SceneLayerProps>
> = { mesh: MeshLayer, boxes: ObjectBoxesLayer };
