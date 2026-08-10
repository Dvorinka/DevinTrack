import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'k'
  return String(n)
}

export function formatMs(ms: number): string {
  if (ms >= 60_000) return (ms / 60_000).toFixed(1) + 'm'
  if (ms >= 1_000) return (ms / 1_000).toFixed(1) + 's'
  return ms + 'ms'
}

export function formatCost(usd: number): string {
  if (usd >= 1) return '$' + usd.toFixed(2)
  if (usd >= 0.01) return '$' + usd.toFixed(3)
  if (usd > 0) return '$' + usd.toFixed(4)
  return '$0'
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

export function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// Reasoning effort color mapping.
// Values: low, medium, high, xhigh, max (case-insensitive).
// dot is explicit (not derived from text) because Tailwind JIT cannot
// see dynamically-generated class names like bg-red-400.
type EffortStyle = { bg: string; text: string; dot: string; label: string }

const effortMap: Record<string, EffortStyle> = {
  low:    { bg: 'bg-emerald-500/15', text: 'text-emerald-400', dot: 'bg-emerald-400', label: 'Low' },
  medium: { bg: 'bg-sky-500/15',     text: 'text-sky-400',     dot: 'bg-sky-400',     label: 'Medium' },
  high:   { bg: 'bg-amber-500/15',   text: 'text-amber-400',   dot: 'bg-amber-400',   label: 'High' },
  xhigh:  { bg: 'bg-orange-500/15',  text: 'text-orange-400',  dot: 'bg-orange-400',  label: 'XHigh' },
  max:    { bg: 'bg-red-500/15',     text: 'text-red-400',     dot: 'bg-red-400',     label: 'Max' },
}

export function effortStyle(effort: string | null | undefined): EffortStyle | null {
  if (!effort) return null
  const key = effort.toLowerCase().trim()
  return effortMap[key] ?? { bg: 'bg-muted', text: 'text-muted-foreground', label: effort }
}

// Model color mapping for consistent session row coloring.
type ModelColor = { dot: string; bg: string; text: string }

const modelColors: Record<string, ModelColor> = {
  'glm-5-2':    { dot: 'bg-sky-400',    bg: 'bg-sky-500/5',    text: 'text-sky-300' },
  'swe-1-7':    { dot: 'bg-violet-400', bg: 'bg-violet-500/5', text: 'text-violet-300' },
  'claude-opus-5':  { dot: 'bg-amber-400',  bg: 'bg-amber-500/5',  text: 'text-amber-300' },
  'claude-sonnet-5': { dot: 'bg-emerald-400', bg: 'bg-emerald-500/5', text: 'text-emerald-300' },
  'claude-5-fable':  { dot: 'bg-pink-400',   bg: 'bg-pink-500/5',   text: 'text-pink-300' },
}

const fallbackColors: ModelColor[] = [
  { dot: 'bg-sky-400',    bg: 'bg-sky-500/5',    text: 'text-sky-300' },
  { dot: 'bg-violet-400', bg: 'bg-violet-500/5', text: 'text-violet-300' },
  { dot: 'bg-amber-400',  bg: 'bg-amber-500/5',  text: 'text-amber-300' },
  { dot: 'bg-emerald-400', bg: 'bg-emerald-500/5', text: 'text-emerald-300' },
  { dot: 'bg-pink-400',   bg: 'bg-pink-500/5',   text: 'text-pink-300' },
  { dot: 'bg-orange-400', bg: 'bg-orange-500/5', text: 'text-orange-300' },
]

export function modelColor(model: string | null | undefined): ModelColor {
  if (!model) return { dot: 'bg-gray-400', bg: '', text: 'text-muted-foreground' }
  // Try exact match.
  if (modelColors[model]) return modelColors[model]
  // Try prefix match (e.g., "claude-opus-5-high" matches "claude-opus-5").
  for (const key of Object.keys(modelColors)) {
    if (model.startsWith(key)) return modelColors[key]
  }
  // Hash-based fallback for unknown models.
  let hash = 0
  for (let i = 0; i < model.length; i++) hash = (hash * 31 + model.charCodeAt(i)) | 0
  return fallbackColors[Math.abs(hash) % fallbackColors.length]
}

// Strip reasoning effort suffix from display name.
// "SWE-1.7 Max" -> "SWE-1.7", "GLM-5.2 High" -> "GLM-5.2".
const EFFORT_WORDS = ['XHigh', 'Medium', 'High', 'Low', 'Max', 'None']

export function baseModelName(displayName: string | null | undefined): string {
  if (!displayName) return '-'
  for (const word of EFFORT_WORDS) {
    if (displayName.endsWith(' ' + word)) {
      return displayName.slice(0, -(word.length + 1))
    }
  }
  return displayName
}
