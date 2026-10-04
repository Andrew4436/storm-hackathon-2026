import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/** The folder Git Bash (or MSYS2) maps to "/": C:/Program Files/Git, or C:/msys64. Empty outside it. */
function msysRoots() {
  const shell = (process.env.SHELL || '').replace(/\\/g, '/') // C:/Program Files/Git/bin/bash.exe
  const exe = (process.env.EXEPATH || '').replace(/\\/g, '/') // C:/Program Files/Git/bin
  return [shell.match(/^(.*?)(\/usr)?\/bin\/[^/]+$/i)?.[1], exe.match(/^(.*?)(\/usr)?\/bin\/?$/i)?.[1]].filter(Boolean)
}

/**
 * The path the site is served from, with one leading and one trailing slash: '/' locally,
 * '/storm-hackathon-2026/' on GitHub Pages (VITE_BASE=/storm-hackathon-2026/ npm run build).
 * Git Bash on Windows rewrites a leading-slash value passed to a Windows program into a path under its install
 * folder ("C:/Program Files/Git/storm-hackathon-2026/"), so that prefix is taken off again here.
 */
function basePath(raw = '') {
  let p = raw.trim().replace(/\\/g, '/')
  if (p === '.' || p === './') return './'
  if (/^[A-Za-z]:\//.test(p)) {
    const root = msysRoots().find((r) => p.toLowerCase().startsWith(`${r.toLowerCase()}/`))
    if (!root) {
      throw new Error(
        `VITE_BASE is a Windows path (${raw}). In Git Bash use: MSYS_NO_PATHCONV=1 VITE_BASE=/storm-hackathon-2026/ npm run build`,
      )
    }
    p = p.slice(root.length)
  }
  const trimmed = p.replace(/^\/+|\/+$/g, '')
  return trimmed ? `/${trimmed}/` : '/'
}

// https://vite.dev/config/
export default defineConfig({
  base: basePath(process.env.VITE_BASE),
  plugins: [react()],
})
