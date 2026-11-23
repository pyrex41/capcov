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
    const e = Number(exponent);
    if (e < -4 || e >= 16) {
      return mantissa + 'e' + (e < 0 ? '-' : '+') +
        String(Math.abs(e)).padStart(2, '0');
    }
    return String(n) + (Number.isInteger(n) ? '.0' : '');
  }
}

function parse(text) {
  const lexer = /"(?:\\[\s\S]|[^"\\])*"|-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?|true|false|null|[\[\]{},:]/g;
  let token;
  function next() { token = lexer.exec(text)?.[0]; }
  function value() {
    const t = token;
    next();
    if (t === '[') {
      const a = [];
      while (token !== ']') {
        a.push(value());
        if (token === ',') next();
      }
      next();
      return a;
    }
    if (t === '{') {
      const o = Object.create(null);
      while (token !== '}') {
        const k = JSON.parse(token);
        next();
        next();
        o[k] = value();
        if (token === ',') next();
      }
      next();
      return o;
    }
    return /^[-0-9]/.test(t) ? new Numeric(t) : JSON.parse(t);
  }
  next();
  return value();
}

function compare(a, b) {
  let i = 0;
  while (i < a.length && i < b.length) {
    const x = a.codePointAt(i), y = b.codePointAt(i);
    if (x !== y) return x - y;
    i += x > 0xffff ? 2 : 1;
  }
  return a.length - b.length;
}

function canonical(x) {
  if (x instanceof Numeric) return x.render();
  if (x === null || typeof x !== 'object') return JSON.stringify(x);
  if (Array.isArray(x)) return '[' + x.map(canonical).join(',') + ']';
  return '{' + Object.keys(x).sort(compare)
    .map(k => JSON.stringify(k) + ':' + canonical(x[k])).join(',') + '}';
}

function normalize(p) {
  if (!p || p.includes('\0') || p.includes('\\') || /^(?:\/|[A-Za-z]:)/.test(p))
    throw 'manifest';
  const parts = p.split('/').filter(s => s && s !== '.');
  if (!parts.length || parts.includes('..')) throw 'manifest';
  return parts.join('/');
}

function run(history) {
  const blobs = new Map(), names = new Map(), objects = new Map();
  const invalid = new Set();
  const absent = '0'.repeat(64);

  function put(text) {
    const digest = createHash('sha256').update(text, 'utf8').digest('hex');
    objects.set(digest, text);
    return digest;
  }

  function lookup(name) {
    if (!names.has(name)) throw 'missing';
    const digest = names.get(name);
    if (invalid.has(digest)) throw 'manifest';
    return digest;
  }

  return history.map(([op, name, data, parent, meta]) => {
    try {
      if (op === 'blob') {
        const digest = put(data);
        blobs.set(name, digest);
        return { ok: digest };
      }
      if (op === 'read') return { ok: objects.get(lookup(name)) };

      const files = Object.create(null);
      for (const [rawPath, b] of new Map(data)) {
        const p = normalize(rawPath);
        if (Object.hasOwn(files, p)) throw 'manifest';
        files[p] = blobs.get(b) ?? absent;
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
        files, metadata: meta ?? {}, parent: parentDigest, type: 'capcov.snapshot.v1'
      }));
      // Removing leading dot segments can expose a drive prefix on reload.
      if (paths.some(p => /^[A-Za-z]:/.test(p))) invalid.add(digest);
      names.set(name, digest);
      return { ok: digest };
    } catch (error) {
      if (error !== 'missing' && error !== 'manifest') throw error;
      return { error };
    }
  });
}

process.stdout.write(JSON.stringify(parse(input).map(run)) + '\n');
