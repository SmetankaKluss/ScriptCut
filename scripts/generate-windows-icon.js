#!/usr/bin/env node

/**
 * Build a Windows ICO from the 256px PNG already embedded in icon.icns.
 *
 * Keeping this dependency-free makes Windows release builds reproducible
 * without ImageMagick.
 */

const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const source = path.join(root, 'build', 'icon.icns');
const destination = path.join(root, 'build', 'icon.ico');

function findPng(icns) {
  if (icns.subarray(0, 4).toString('ascii') !== 'icns') {
    throw new Error('build/icon.icns is not a valid ICNS container');
  }
  let offset = 8;
  const preferred = new Map();
  while (offset + 8 <= icns.length) {
    const type = icns.subarray(offset, offset + 4).toString('ascii');
    const length = icns.readUInt32BE(offset + 4);
    if (length < 8 || offset + length > icns.length) break;
    if (['ic08', 'ic09', 'ic10'].includes(type)) {
      preferred.set(type, icns.subarray(offset + 8, offset + length));
    }
    offset += length;
  }
  return preferred.get('ic08') || preferred.get('ic09') || preferred.get('ic10') || null;
}

function main() {
  const png = findPng(fs.readFileSync(source));
  if (!png || png.subarray(1, 4).toString('ascii') !== 'PNG') {
    throw new Error('build/icon.icns does not contain a usable PNG icon');
  }

  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(1, 4);

  const entry = Buffer.alloc(16);
  entry.writeUInt8(0, 0); // 0 represents 256px in ICO.
  entry.writeUInt8(0, 1);
  entry.writeUInt8(0, 2);
  entry.writeUInt8(0, 3);
  entry.writeUInt16LE(1, 4);
  entry.writeUInt16LE(32, 6);
  entry.writeUInt32LE(png.length, 8);
  entry.writeUInt32LE(header.length + entry.length, 12);

  fs.writeFileSync(destination, Buffer.concat([header, entry, png]));
  console.log(`Generated ${path.relative(root, destination)}`);
}

main();
