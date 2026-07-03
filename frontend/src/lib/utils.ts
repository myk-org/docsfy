import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Encode branch name for use in URL path segments (slashes → ~2F). */
export function encodeBranch(branch: string): string {
  return branch.replace(/~/g, '~7E').replace(/\//g, '~2F')
}
