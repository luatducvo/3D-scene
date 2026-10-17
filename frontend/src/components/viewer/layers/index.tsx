import { useEffect, useMemo, useRef } from "react";
import { useGLTF } from "@react-three/drei";
import { useLoader, type ThreeEvent } from "@react-three/fiber";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  Box3,
  BufferAttribute,
  Color,
  type BufferGeometry,
  type Material,
  type Mesh,
  type Points,
  type PointsMaterial,
} from "three";
import {
  objectIndices,
  owners,
  pickColors,
  Painter,
  type Members,
} from "../highlight";
import { addPickTwin, meshTwin, pointsTwin } from "../picking";
import type { ViewMode } from "../view";
import type { Membership } from "../../../lib/api/membership";
import type { SceneObject, Schemas } from "../../../lib/api/types";
import { useViewer } from "../../../lib/store/viewerStore";
export type SceneLayerProps = {
  sceneId: string;
  assets: Schemas["SceneAssets"];
  objects: SceneObject[];
  /** Which points and mesh vertices belong to each Object; null while absent or loading. */
  membership: Membership | null;
};
const POINT_COLOR = "#9fb3bb";
function measurePick(e: ThreeEvent<MouseEvent>) {
  if (!useViewer.getState().measuring) return;
  e.stopPropagation();
  useViewer.getState().pick([e.point.x, e.point.y, e.point.z]);
}

/** A colour array the viewer repaints, the real colours it restores, and the attributes to upload. */
type Paintable = {
  colors: Float32Array;
  base: Float32Array;
  attributes: BufferAttribute[];
};
// Loaders cache geometry per URL, so each geometry is made paintable once and keeps its real colours.
const paintables = new WeakMap<object, Paintable>();
function realColors(geometry: BufferGeometry, fallback: Color) {
  const count = geometry.getAttribute("position").count,
    color = geometry.getAttribute("color");
  const base = new Float32Array(count * 3);
  for (let i = 0; i < count; i++)
    if (color && color.itemSize >= 3) {
      base[3 * i] = color.getX(i);
      base[3 * i + 1] = color.getY(i);
      base[3 * i + 2] = color.getZ(i);
    } else fallback.toArray(base, 3 * i);
  return base;
}
function paintablePoints(geometry: BufferGeometry): Paintable {
  const known = paintables.get(geometry);
  if (known) return known;
  const base = realColors(geometry, new Color(POINT_COLOR)),
    current = geometry.getAttribute("color");
  // PLYLoader's float RGB is repainted in place; anything else is replaced by one.
  let attribute: BufferAttribute;
  if (
    current instanceof BufferAttribute &&
    current.array instanceof Float32Array &&
    current.itemSize === 3
  )
    attribute = current;
  else {
    attribute = new BufferAttribute(new Float32Array(base), 3);
    geometry.setAttribute("color", attribute);
  }
  const paintable = {
    colors: attribute.array as Float32Array,
    base,
    attributes: [attribute],
  };
  paintables.set(geometry, paintable);
  return paintable;
}

type MeshPart = { mesh: Mesh; offset: number; count: number };
/**
 * The glTF's meshes in membership vertex order: by glTF mesh, then primitive, each primitive's
 * POSITION entries in turn (api.md "Object membership"). Clones of one primitive count once.
 */
function meshParts(gltf: GLTF): MeshPart[] {
  const found = new Map<string, { mesh: Mesh; key: number[] }>();
  let order = 0;
  gltf.scene.traverse((object) => {
    if (!(object as Mesh).isMesh) return;
    const mesh = object as Mesh;
    const reference = gltf.parser.associations.get(mesh) as
      { meshes?: number; primitives?: number } | undefined;
    const key =
      reference?.meshes === undefined
        ? [Number.MAX_SAFE_INTEGER, order]
        : [reference.meshes, reference.primitives ?? 0];
    order += 1;
    if (!found.has(String(key))) found.set(String(key), { mesh, key });
  });
  let offset = 0;
  return [...found.values()]
    .sort((a, b) => a.key[0] - b.key[0] || a.key[1] - b.key[1])
    .map(({ mesh }) => {
      const count = mesh.geometry.getAttribute("position").count;
      offset += count;
      return { mesh, offset: offset - count, count };
    });
}
/** One colour array over every part; each part's colour attribute views its slice of it. */
function paintableMesh(parts: MeshPart[], total: number): Paintable {
  const known = paintables.get(parts[0].mesh);
  if (known) return known;
  const colors = new Float32Array(total * 3),
    base = new Float32Array(total * 3),
    white = new Color(1, 1, 1);
  const attributes = parts.map(({ mesh, offset, count }) => {
    base.set(realColors(mesh.geometry, white), offset * 3);
    const attribute = new BufferAttribute(
      colors.subarray(offset * 3, (offset + count) * 3),
      3,
    );
    mesh.geometry.setAttribute("color", attribute);
    for (const material of [mesh.material].flat() as Material[]) {
      material.vertexColors = true;
      material.needsUpdate = true;
    }
    return attribute;
  });
  colors.set(base);
  const paintable = { colors, base, attributes };
  paintables.set(parts[0].mesh, paintable);
  return paintable;
}

/** Report whether the membership fits the loaded geometry, so the viewer can ask for a reprocess. */
function useMembershipFit(
  mode: ViewMode,
  membership: Membership | null,
  usable: Membership | null,
) {
  useEffect(() => {
    const mismatch = Boolean(membership && !usable);
    if (mismatch)
      console.warn(
        `Object membership does not match the ${mode} geometry; reprocess the Scene.`,
      );
    useViewer.getState().setMembershipMismatch(mode, mismatch);
    return () => useViewer.getState().setMembershipMismatch(mode, false);
  }, [mode, membership, usable]);
}

/** Highlighted and selected Objects in green with the rest dimmed, and a tint on the hovered one. */
function usePainting(
  paintable: Paintable | null,
  membership: Membership | null,
  members: Members | null,
) {
  const highlighted = useViewer((s) => s.highlightedIds),
    selected = useViewer((s) => s.selectedId),
    hovered = useViewer((s) => s.hovered?.id ?? null);
  const painter = useMemo(
    () =>
      paintable && membership && members
        ? new Painter(
            paintable.colors,
            paintable.base,
            members,
            membership.ids.length,
          )
        : null,
    [paintable, membership, members],
  );
  const upload = () =>
    paintable?.attributes.forEach((attribute) => {
      attribute.needsUpdate = true;
    });
  useEffect(() => {
    if (!painter || !membership) return;
    painter.highlight(
      objectIndices(
        membership,
        selected ? [...highlighted, selected] : highlighted,
      ),
    );
    upload();
  }, [painter, membership, highlighted, selected]);
  useEffect(() => {
    if (!painter || !membership) return;
    const [index] = hovered ? objectIndices(membership, [hovered]) : [];
    painter.hover(index ?? null);
    upload();
  }, [painter, membership, hovered]);
  // Leaving the layer shows real colours again on the cached geometry.
  useEffect(
    () => () => {
      if (!paintable) return;
      paintable.colors.set(paintable.base);
      upload();
    },
    [paintable],
  );
}

function PointCloudAsset({
  url,
  membership,
}: {
  url: string;
  membership: Membership | null;
}) {
  const geometry = useLoader(PLYLoader, url),
    measuring = useViewer((s) => s.measuring),
    pointSize = useViewer((s) => s.pointSize),
    setLoadedBounds = useViewer((s) => s.setLoadedBounds);
  const display = useRef<Points>(null),
    twin = useRef<Points | null>(null);
  useEffect(() => {
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    if (box)
      setLoadedBounds("points", {
        min: box.min.toArray(),
        max: box.max.toArray(),
      });
  }, [geometry, setLoadedBounds]);
  const count = geometry.getAttribute("position").count;
  // Point index = position in points.ply file order, which PLYLoader keeps.
  const usable = membership?.pointCount === count ? membership : null;
  useMembershipFit("points", membership, usable);
  const paintable = useMemo(
    () => (usable ? paintablePoints(geometry) : null),
    [geometry, usable],
  );
  usePainting(paintable, usable, usable ? usable.points : null);
  const pick = useMemo(
    () =>
      usable
        ? pickColors(owners(count, usable.ids.length, usable.points))
        : null,
    [usable, count],
  );
  useEffect(() => {
    if (!pick || !display.current) return;
    const points = pointsTwin(geometry, pick);
    (points.material as PointsMaterial).size = useViewer.getState().pointSize;
    twin.current = points;
    const remove = addPickTwin(points, display.current);
    return () => {
      twin.current = null;
      remove();
    };
  }, [geometry, pick]);
  useEffect(() => {
    if (twin.current)
      (twin.current.material as PointsMaterial).size = pointSize;
  }, [pointSize]);
  const colored = geometry.hasAttribute("color");
  return (
    // Only listen while measuring: raycasting millions of points on every click is expensive.
    <points
      ref={display}
      geometry={geometry}
      onClick={measuring ? measurePick : undefined}
    >
      <pointsMaterial
        key={String(colored)}
        size={pointSize}
        sizeAttenuation
        vertexColors={colored}
        color={colored ? "#ffffff" : POINT_COLOR}
      />
    </points>
  );
}
export function PointCloudLayer({ assets, membership }: SceneLayerProps) {
  const visible = useViewer((s) => s.layers.points);
  return visible && assets.points_url ? (
    <PointCloudAsset url={assets.points_url} membership={membership} />
  ) : null;
}
function MeshAsset({
  url,
  membership,
}: {
  url: string;
  membership: Membership | null;
}) {
  const gltf = useGLTF(url) as unknown as GLTF,
    { scene } = gltf,
    measuring = useViewer((s) => s.measuring);
  useEffect(() => {
    const box = new Box3().setFromObject(scene);
    if (!box.isEmpty())
      useViewer.getState().setLoadedBounds("mesh", {
        min: box.min.toArray(),
        max: box.max.toArray(),
      });
  }, [scene]);
  const parts = useMemo(() => meshParts(gltf), [gltf]);
  const total = parts.reduce((sum, part) => sum + part.count, 0);
  // Vertex index = position in the glTF POSITION accessors; GLTFLoader neither merges nor reorders.
  const usable =
    parts.length && membership?.vertexCount === total ? membership : null;
  useMembershipFit("mesh", membership, usable);
  const paintable = useMemo(
    () => (usable ? paintableMesh(parts, total) : null),
    [parts, total, usable],
  );
  usePainting(paintable, usable, usable ? usable.vertices : null);
  const pick = useMemo(
    () =>
      usable
        ? pickColors(owners(total, usable.ids.length, usable.vertices))
        : null,
    [usable, total],
  );
  useEffect(() => {
    if (!pick) return;
    const removals = parts.map(({ mesh, offset, count }) =>
      addPickTwin(
        meshTwin(
          mesh.geometry,
          pick.subarray(offset * 3, (offset + count) * 3),
          ([mesh.material].flat()[0] as Material).side,
        ),
        mesh,
      ),
    );
    return () => removals.forEach((remove) => remove());
  }, [parts, pick]);
  return (
    <primitive object={scene} onClick={measuring ? measurePick : undefined} />
  );
}
export function MeshLayer({ assets, membership }: SceneLayerProps) {
  const visible = useViewer((s) => s.layers.mesh);
  if (assets.mesh_url)
    return visible ? (
      <MeshAsset url={assets.mesh_url} membership={membership} />
    ) : null;
  return null;
}
export const sceneLayers: Record<
  string,
  React.ComponentType<SceneLayerProps>
> = { points: PointCloudLayer, mesh: MeshLayer };
