(() => {
  "use strict";

  const encoder = new TextEncoder();
  const crcTable = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
    crcTable[index] = value >>> 0;
  }

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  function part(size) {
    return { bytes: new Uint8Array(size), view: null, offset: 0 };
  }

  function view(buffer) {
    if (!buffer.view) buffer.view = new DataView(buffer.bytes.buffer);
    return buffer.view;
  }

  function u16(buffer, value) {
    view(buffer).setUint16(buffer.offset, value, true);
    buffer.offset += 2;
  }

  function u32(buffer, value) {
    view(buffer).setUint32(buffer.offset, value >>> 0, true);
    buffer.offset += 4;
  }

  function write(buffer, bytes) {
    buffer.bytes.set(bytes, buffer.offset);
    buffer.offset += bytes.length;
  }

  function join(parts) {
    const size = parts.reduce((total, bytes) => total + bytes.length, 0);
    const result = new Uint8Array(size);
    let offset = 0;
    for (const bytes of parts) {
      result.set(bytes, offset);
      offset += bytes.length;
    }
    return result;
  }

  function archive(files) {
    const entries = Object.entries(files).map(([name, contents]) => ({
      name: encoder.encode(name),
      data: typeof contents === "string" ? encoder.encode(contents) : contents,
    }));
    const localParts = [];
    const centralParts = [];
    let localOffset = 0;
    for (const entry of entries) {
      const crc = crc32(entry.data);
      const local = part(30 + entry.name.length + entry.data.length);
      u32(local, 0x04034b50);
      u16(local, 20);
      u16(local, 0x0800);
      u16(local, 0);
      u16(local, 0);
      u16(local, 0x0021);
      u32(local, crc);
      u32(local, entry.data.length);
      u32(local, entry.data.length);
      u16(local, entry.name.length);
      u16(local, 0);
      write(local, entry.name);
      write(local, entry.data);
      localParts.push(local.bytes);

      const central = part(46 + entry.name.length);
      u32(central, 0x02014b50);
      u16(central, 20);
      u16(central, 20);
      u16(central, 0x0800);
      u16(central, 0);
      u16(central, 0);
      u16(central, 0x0021);
      u32(central, crc);
      u32(central, entry.data.length);
      u32(central, entry.data.length);
      u16(central, entry.name.length);
      u16(central, 0);
      u16(central, 0);
      u16(central, 0);
      u16(central, 0);
      u32(central, 0);
      u32(central, localOffset);
      write(central, entry.name);
      centralParts.push(central.bytes);
      localOffset += local.bytes.length;
    }
    const localBytes = join(localParts);
    const centralBytes = join(centralParts);
    const end = part(22);
    u32(end, 0x06054b50);
    u16(end, 0);
    u16(end, 0);
    u16(end, entries.length);
    u16(end, entries.length);
    u32(end, centralBytes.length);
    u32(end, localBytes.length);
    u16(end, 0);
    return join([localBytes, centralBytes, end.bytes]);
  }

  globalThis.AAUBoundaryZip = Object.freeze({ archive });
})();
