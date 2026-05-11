/**
 * Vercel build script — inject environment variables into static index.html
 * Replaces __VIFAKE_API_URL__ and __VIFAKE_AUTH_TOKEN__ placeholders at build time.
 * Runs via: node build.js  (Vercel auto-detects Node from package.json)
 * Vercel has Node.js available even for static sites.
 */
const fs   = require('fs');
const path = require('path');

const API_URL    = process.env.VIFAKE_API_URL    || 'https://vifake-analytics-api.onrender.com' || 'http://localhost:8000';
const AUTH_TOKEN = process.env.VIFAKE_AUTH_TOKEN || 'demo-token-123';

const src  = path.join(__dirname, 'index.html');
const dist = path.join(__dirname, 'dist', 'index.html');

fs.mkdirSync(path.dirname(dist), { recursive: true });

let html = fs.readFileSync(src, 'utf8');
html = html
  .replace(/__VIFAKE_API_URL__/g,    API_URL)
  .replace(/__VIFAKE_AUTH_TOKEN__/g, AUTH_TOKEN);

fs.writeFileSync(dist, html, 'utf8');
console.log(`✅ Built with API_URL=${API_URL}`);
