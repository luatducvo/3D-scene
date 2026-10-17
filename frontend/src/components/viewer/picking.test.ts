import { expect, test } from "vitest";
import {
  BufferAttribute,
  BufferGeometry,
  DoubleSide,
  GLSL3,
  ShaderMaterial,
} from "three";
import { meshTwin, PICK_ATTRIBUTE } from "./picking";

test("a mesh pick twin passes ids as flat varyings, so a triangle never blends its vertices' ids", () => {
  const source = new BufferGeometry();
  source.setAttribute("position", new BufferAttribute(new Float32Array(9), 3));
  source.setIndex([0, 1, 2]);
  // Three vertices owned by three different Objects.
  const ids = new Uint8Array([0, 0, 1, 0, 0, 2, 0, 0, 3]);
  const twin = meshTwin(source, ids, DoubleSide);
  const material = twin.material as ShaderMaterial;
  expect(material).toBeInstanceOf(ShaderMaterial);
  expect(material.glslVersion).toBe(GLSL3);
  expect(material.vertexShader).toMatch(/flat out vec3 vPickColor;/);
  expect(material.fragmentShader).toMatch(/flat in vec3 vPickColor;/);
  expect(material.vertexShader).toContain(`in vec3 ${PICK_ATTRIBUTE};`);
  expect(material.side).toBe(DoubleSide);
  const attribute = twin.geometry.getAttribute(
    PICK_ATTRIBUTE,
  ) as BufferAttribute;
  expect(attribute.array).toBe(ids);
  expect(attribute.normalized).toBe(true);
  // The twin shares the display's buffers instead of copying them.
  expect(twin.geometry.getAttribute("position")).toBe(
    source.getAttribute("position"),
  );
  expect(twin.geometry.index).toBe(source.index);
});
