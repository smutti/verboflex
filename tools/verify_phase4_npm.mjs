#!/usr/bin/env node
// Installed package identities and exact SPDX license expressions must be approved.
import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";

const allowed = new Set([
  "0BSD",
  "Apache-2.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "BlueOak-1.0.0",
  "CC-BY-4.0",
  "CC0-1.0",
  "ISC",
  "MIT",
  "MIT-0",
  "MPL-2.0",
  "Python-2.0",
]);

export function validateIdentity(relative, installed, locked) {
  assert(locked, "unlocked installed package");
  assert.equal(
    installed.version,
    locked.version,
    "installed version differs from lock",
  );
  const expected = locked.name ?? relative.split("node_modules/").at(-1);
  assert.equal(installed.name, expected, "installed name differs from lock");
  assert(allowed.has(installed.license), "unknown or disallowed license");
  if (locked.license)
    assert.equal(
      installed.license,
      locked.license,
      "license differs from lock",
    );
}

function main() {
  if (process.argv.includes("--self-test")) {
    const valid = { name: "safe", version: "1.0.0", license: "MIT" };
    validateIdentity("node_modules/safe", valid, valid);
    for (const changed of [
      { ...valid, version: "2" },
      { ...valid, name: "other" },
      { ...valid, license: "UNKNOWN" },
    ]) {
      assert.throws(() =>
        validateIdentity("node_modules/safe", changed, valid),
      );
    }
    assert.throws(() => validateIdentity("node_modules/safe", valid, null));
    console.log(JSON.stringify({ negative_controls: 4, status: "passed" }));
    return;
  }
  const root = path.resolve(import.meta.dirname, "../frontend");
  const lock = JSON.parse(
    fs.readFileSync(path.join(root, "package-lock.json")),
  );
  const direct = JSON.parse(fs.readFileSync(path.join(root, "package.json")));
  assert.equal(direct.dependencies["@tanstack/react-virtual"], "3.14.10");
  const seen = new Set();
  function visit(relative) {
    const directory = path.join(root, relative);
    if (!fs.existsSync(directory)) return;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const item = path.join(relative, entry.name);
      if (entry.name.startsWith("@")) {
        visit(item);
        continue;
      }
      const metadata = path.join(root, item, "package.json");
      assert(fs.existsSync(metadata), "installed package missing metadata");
      assert(!entry.isSymbolicLink(), "unexpected installed symlink");
      validateIdentity(
        item,
        JSON.parse(fs.readFileSync(metadata)),
        lock.packages[item],
      );
      seen.add(item);
      visit(path.join(item, "node_modules"));
    }
  }
  visit("node_modules");
  for (const [relative, metadata] of Object.entries(lock.packages)) {
    if (
      !relative ||
      metadata.optional ||
      (metadata.os && !metadata.os.includes(process.platform)) ||
      (metadata.cpu && !metadata.cpu.includes(process.arch))
    )
      continue;
    assert(seen.has(relative), "required locked package missing");
  }
  assert(seen.size > 0, "empty package inventory");
  assert.equal(
    JSON.parse(
      fs.readFileSync(
        path.join(root, "node_modules/@tanstack/react-virtual/package.json"),
      ),
    ).version,
    "3.14.10",
  );
  console.log(
    JSON.stringify({
      status: "passed",
      installed_lock_identities: seen.size,
      license_policy: [...allowed].sort(),
      virtualizer: "3.14.10",
    }),
  );
}

try {
  main();
} catch {
  console.error(
    JSON.stringify({
      status: "failed",
      reason: "installed identity or approved license mismatch",
    }),
  );
  process.exitCode = 1;
}
