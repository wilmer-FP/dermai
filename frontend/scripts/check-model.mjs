import { readFileSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
const root = new URL('../public/models/dermai/', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('manifest.json', root), 'utf8'));
const model = readFileSync(new URL('model.onnx', root));
if (model.length !== manifest.bytes || createHash('sha256').update(model).digest('hex') !== manifest.sha256) {
  throw new Error('ONNX missing/corrupt or Git LFS pointer: export and validate before building.');
}
for (const name of ['model_meta.json', 'metrics.json', 'model_card.md', 'LICENSE.txt', 'NOTICE.md', 'validation.json']) {
  if (!statSync(new URL(name, root)).size) throw new Error(`Missing model documentation: ${name}`);
}
console.log(`Verified ${manifest.name} v${manifest.version}, ${model.length} bytes, SHA-256 ${manifest.sha256}`);
