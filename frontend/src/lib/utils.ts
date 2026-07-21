import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import type { AvailableModels, ComboboxOption } from "@/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Encode branch name for use in URL path segments (slashes → ~2F). */
export function encodeBranch(branch: string): string {
  return branch.replace(/~/g, '~7E').replace(/\//g, '~2F')
}

/** Map discovered models for a provider into Combobox options (with source badge). */
export function modelOptionsForProvider(
  availableModels: AvailableModels,
  provider: string,
): ComboboxOption[] {
  if (!provider) return []
  return (availableModels[provider] ?? []).map((m) => ({
    value: m.id,
    label: m.name || m.id,
    badge: m.source,
  }))
}
