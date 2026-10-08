import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";

const contractPath = new URL("../../backend/openapi.json", import.meta.url);
const sourcePath = new URL("../../backend/src/s3d_app/api.py", import.meta.url);
const outputPath = new URL("../src/generated/api.ts", import.meta.url);
const contract = (await readFile(contractPath, "utf8")).replaceAll("\r\n", "\n");
const source = (await readFile(sourcePath, "utf8")).replaceAll("\r\n", "\n");
const digest = text => createHash("sha256").update(text).digest("hex");
const header = `// OpenAPI: ${digest(contract)}\n// API source: ${digest(source)}\n`;
if (process.argv[2] === "generate") {
  await writeFile(outputPath, header + astToString(await openapiTS(JSON.parse(contract))));
} else {
  const generated = (await readFile(outputPath, "utf8")).replaceAll("\r\n", "\n");
  if (!generated.startsWith(header)) {
    throw new Error("API types are stale. Export backend/openapi.json, then run npm run types:api.");
  }
}
