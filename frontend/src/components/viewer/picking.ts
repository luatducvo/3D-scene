/**
 * GPU picking. A room layer that has Object membership adds a pick twin of its geometry: the same
 * position (and index) buffers, coloured by owning Object (`owners`, `pickColors` in highlight.ts).
 * `pickAt` draws the twins into a single scissored pixel under the cursor and reads it back, so a
 * pick fills and reads one pixel and never walks the points on the CPU.
 */
import {
  BufferAttribute,
  BufferGeometry,
  Color,
  Mesh,
  MeshBasicMaterial,
  NoBlending,
  Points,
  PointsMaterial,
  Scene,
  Vector2,
  WebGLRenderTarget,
  type Camera,
  type Material,
  type Object3D,
  type Side,
  type WebGLRenderer,
} from "three";
import { pickedObject } from "./highlight";

const pickScene = new Scene();
// Twins copy their display object's world matrix before each pick; nothing recomputes it.
pickScene.matrixAutoUpdate = false;
pickScene.matrixWorldAutoUpdate = false;

function twinGeometry(source: BufferGeometry, colors: Uint8Array) {
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", source.getAttribute("position"));
  if (source.index) geometry.setIndex(source.index);
  geometry.setAttribute("color", new BufferAttribute(colors, 3, true));
  return geometry;
}

/** A pick twin of a point cloud; its size follows the display material's. */
export function pointsTwin(source: BufferGeometry, colors: Uint8Array) {
  return new Points(
    twinGeometry(source, colors),
    new PointsMaterial({
      sizeAttenuation: true,
      vertexColors: true,
      toneMapped: false,
      blending: NoBlending,
    }),
  );
}

/** A pick twin of one mesh, culling the same faces as the display material. */
export function meshTwin(
  source: BufferGeometry,
  colors: Uint8Array,
  side: Side,
) {
  return new Mesh(
    twinGeometry(source, colors),
    new MeshBasicMaterial({
      vertexColors: true,
      side,
      toneMapped: false,
      blending: NoBlending,
    }),
  );
}

/** Make `twin` pickable in place of `display` until the returned function removes it. */
export function addPickTwin(twin: Points | Mesh, display: Object3D) {
  twin.matrixAutoUpdate = false;
  twin.matrixWorldAutoUpdate = false;
  // A pick draws one pixel; culling would only cost a bounding-sphere pass over every point.
  twin.frustumCulled = false;
  twin.userData.display = display;
  pickScene.add(twin);
  return () => {
    pickScene.remove(twin);
    // The display geometry owns the shared buffers; free only the twin's own colours.
    twin.geometry.deleteAttribute("position");
    twin.geometry.setIndex(null);
    twin.geometry.dispose();
    (twin.material as Material).dispose();
  };
}

const targets = new WeakMap<WebGLRenderer, WebGLRenderTarget>();
const pixel = new Uint8Array(4),
  bufferSize = new Vector2(),
  clearColor = new Color();

/**
 * The index (in membership order) of the Object drawn at canvas pixel (x, y) in CSS pixels, or
 * null. The target matches the drawing buffer, so points keep their on-screen size and are not
 * clipped by a narrowed view, but the scissor limits drawing to the one pixel read back.
 */
export function pickAt(
  gl: WebGLRenderer,
  camera: Camera,
  x: number,
  y: number,
): number | null {
  if (!pickScene.children.length) return null;
  gl.getDrawingBufferSize(bufferSize);
  let target = targets.get(gl);
  if (!target) {
    target = new WebGLRenderTarget(bufferSize.x, bufferSize.y);
    targets.set(gl, target);
  } else if (target.width !== bufferSize.x || target.height !== bufferSize.y)
    target.setSize(bufferSize.x, bufferSize.y);
  const ratio = gl.getPixelRatio();
  const px = Math.min(bufferSize.x - 1, Math.max(0, Math.floor(x * ratio)));
  const py = Math.min(
    bufferSize.y - 1,
    Math.max(0, bufferSize.y - 1 - Math.floor(y * ratio)),
  );
  target.scissor.set(px, py, 1, 1);
  target.scissorTest = true;
  for (const twin of pickScene.children) {
    const display = twin.userData.display as Object3D;
    twin.matrix.copy(display.matrixWorld);
    twin.matrixWorld.copy(display.matrixWorld);
  }
  const previous = gl.getRenderTarget(),
    previousAlpha = gl.getClearAlpha();
  gl.getClearColor(clearColor);
  gl.setRenderTarget(target);
  gl.setClearColor(0x000000, 0);
  gl.clear();
  gl.render(pickScene, camera);
  gl.readRenderTargetPixels(target, px, py, 1, 1, pixel);
  gl.setRenderTarget(previous);
  gl.setClearColor(clearColor, previousAlpha);
  return pickedObject(pixel[0], pixel[1], pixel[2]);
}
