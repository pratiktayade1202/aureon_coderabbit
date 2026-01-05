#!/usr/bin/env node

/**
 * Aureon Tree Viewer with timestamps
 *
 * Prints a clean tree like:
 *
 * ├── App.jsx (2025-12-07 04:57)
 * └── components
 *     └── Sidebar.jsx (2025-12-06 22:19)
 *
 * Ignored: node_modules, venv, __pycache__, dist, build, .git
 */

import fs from "fs";
import path from "path";

const IGNORE = ["node_modules", "venv", "__pycache__", ".git", "dist", "build"];

// Format YYYY-MM-DD HH:MM
function formatTime(ts) {
  const d = new Date(ts);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

function shouldIgnore(name) {
  return IGNORE.some((i) => name.includes(i));
}

function walk(dir, prefix = "") {
  const entries = fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((e) => !shouldIgnore(e.name))
    .sort((a, b) => a.name.localeCompare(b.name));

  entries.forEach((entry, idx) => {
    const isLast = idx === entries.length - 1;
    const connector = isLast ? "└──" : "├──";
    const fullPath = path.join(dir, entry.name);

    try {
      const stats = fs.statSync(fullPath);
      const modified = formatTime(stats.mtimeMs);

      if (entry.isDirectory()) {
        console.log(`${prefix}${connector} ${entry.name}/`);
        walk(fullPath, prefix + (isLast ? "    " : "│   "));
      } else {
        console.log(`${prefix}${connector} ${entry.name} (${modified})`);
      }
    } catch (err) {
      console.error(`Error reading ${fullPath}`, err);
    }
  });
}

console.log(".");
walk(path.resolve(process.argv[2] || "."));
