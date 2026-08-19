const fs = require("fs");
const path = require("path");
const http = require("http");

const DEFAULT_ROOT = path.resolve(__dirname, "..");
const rootDir = path.resolve(process.env.E2E_WEB_ROOT || DEFAULT_ROOT);
const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:43173";
const parsed = new URL(baseURL);
const host = parsed.hostname || "127.0.0.1";
const port = Number(parsed.port || (parsed.protocol === "https:" ? 443 : 80));

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".webp": "image/webp"
};

function safeResolve(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const normalized = decoded === "/" ? "/index.html" : decoded;
  const fullPath = path.resolve(rootDir, `.${normalized}`);
  if (!fullPath.startsWith(rootDir)) {
    return null;
  }
  return fullPath;
}

const server = http.createServer((req, res) => {
  const targetPath = safeResolve(req.url || "/");
  if (!targetPath) {
    res.statusCode = 403;
    res.end("Forbidden");
    return;
  }

  fs.stat(targetPath, (statErr, stats) => {
    if (statErr || !stats.isFile()) {
      res.statusCode = 404;
      res.end("Not Found");
      return;
    }

    const ext = path.extname(targetPath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";
    res.setHeader("Content-Type", contentType);
    fs.createReadStream(targetPath).pipe(res);
  });
});

server.listen(port, host, () => {
  process.stdout.write(`[e2e-static-server] Serving ${rootDir} at ${host}:${port}\n`);
});
