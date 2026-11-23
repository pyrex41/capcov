'use strict';

const { createHash } = require('crypto');
const input = require('fs').readFileSync(0, 'utf8');

class Numeric {
  constructor(token) {
    this.token = token;
  }

  render() {
    const t = this.token;
    if (!/[.eE]/.test(t)) return t === '-0' ? '0' : t;

    const n = Number(t);
    if (!Number.isFinite(n)) throw 'manifest';
    if (n === 0) return Object.is(n, -0) ? '-0.0' : '0.0';

    const [mantissa, exponent] = n.toExponential().split('e');
    const power = Number(exponent);
    if (power < -4 || power >= 16) {
      return mantissa + 'e' + (power < 0 ? '-' : '+') +
        String(Math.abs(power)).padStart(2, '0');
    }
    return String(n) + (Number.isInteger(n) ? '.0' : '');
  }
}

function parse(text) {
  const lexer = /"(?:\\[\s\S]|[^"\\])*"|-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?|true|false|null|[\[\]{},:]/g;
  let token;
  function next() {
    token = lexer.exec(text)?.[0];
  }
  function value() {
    const t = token;
    next();
    if (t === '[') {
      const items = [];
      while (token !== ']') {
        items.push(value());
        if (token === ',') next();
      }
      next();
      return items;
    }
    if (t === '{') {
      const obj = Object.create(null);
      while (token !== '}') {
        const key = JSON.parse(token);
        next();
        next();
        obj[key] = value();
        if (token === ',') next();
      }
      next();
      return obj;
    }
    return /^[-0-9]/.test(t) ? new Numeric(t) : JSON.parse(t);
  }
  next();
  return value();
}

function compare(a, b) {
  return Buffer.compare(Buffer.from(a), Buffer.from(b));
}

function canonical(x) {
  if (x instanceof Numeric) return x.render();
  if (x === null || typeof x !== 'object') return JSON.stringify(x);
  if (Array.isArray(x)) return '[' + x.map(canonical).join(',') + ']';
  return '{' + Object.keys(x).sort(compare)
    .map(k => JSON.stringify(k) + ':' + canonical(x[k])).join(',') + '}';
}

function normalize(path) {
  if (!path || path.includes('\0') || path.includes('\\') ||
      /^(?:\/|[A-Za-z]:)/.test(path)) throw 'manifest';
  const parts = path.split('/').filter(p => p && p !== '.');
  if (!parts.length || parts.includes('..')) throw 'manifest';
  return parts.join('/');
}

function run(history) {
  const blobs = new Map();
  const snapshots = new Map();
  const objects = new Map();
  const unreadable = new Set();
  const absent = '0'.repeat(64);

  function put(text) {
    const digest = createHash('sha256').update(text, 'utf8').digest('hex');
    objects.set(digest, text);
    return digest;
  }

  function lookup(name) {
    if (!snapshots.has(name)) throw 'missing';
    const digest = snapshots.get(name);
    if (unreadable.has(digest)) throw 'manifest';
    return digest;
  }

  return history.map(([op, name, data, parent, metadata]) => {
    try {
      if (op === 'blob') {
        const digest = put(data);
        blobs.set(name, digest);
        return { ok: digest };
      }
      if (op === 'read') return { ok: objects.get(lookup(name)) };

      const files = Object.create(null);
      for (const [path, ref] of new Map(data)) {
        const key = normalize(path);
        if (Object.hasOwn(files, key)) throw 'manifest';
        files[key] = blobs.get(ref) ?? absent;
      }
      const paths = Object.keys(files).sort(compare);
      for (let i = 1; i < paths.length; i++) {
        if (paths[i].startsWith(paths[i - 1] + '/')) throw 'manifest';
      }

      const parentDigest = parent === null ? null : lookup(parent);
      for (const digest of Object.values(files)) {
        if (!objects.has(digest)) throw 'missing';
      }
      const digest = put(canonical({
        files,
        metadata: metadata ?? {},
        parent: parentDigest,
        type: 'capcov.snapshot.v1'
      }));

      // Removing leading dot components can expose a drive prefix on reload.
      if (paths.some(p => /^[A-Za-z]:/.test(p))) unreadable.add(digest);
      snapshots.set(name, digest);
      return { ok: digest };
    } catch (error) {
      if (error !== 'manifest' && error !== 'missing') throw error;
      return { error };
    }
  });
}

process.stdout.write(JSON.stringify(parse(input).map(run)) + '\n');
