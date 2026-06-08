export const VALID_PROVIDERS = ['claude', 'gemini', 'cursor'] as const

export const VALID_REPO_TYPES = ['app', 'tests', 'library', 'framework'] as const

export const DOCSFY_DOCS_URL = 'https://myk-org.github.io/docsfy/'
export const DOCSFY_REPO_URL = 'https://github.com/myk-org/docsfy'

export const TOAST_DEFAULT_MS = 4000
export const TOAST_ERROR_MS = 6000
export const REDIRECT_DELAY_MS = 2000
export const CARD_REMOVE_MS = 300
export const ALERT_DISMISS_MS = 8000
export const COPY_FEEDBACK_MS = 2000
export const WS_HEARTBEAT_INTERVAL_MS = 30000
export const WS_RECONNECT_MAX_DELAY_MS = 30000
export const WS_POLLING_FALLBACK_MS = 10000
export const RELOAD_DELAY_MS = 1000

export const SK_REPO = 'docsfy-repo'
export const SK_BRANCH = 'docsfy-branch'
export const SK_FORCE = 'docsfy-force'
export const SK_REPO_TYPE = 'docsfy-repo-type'

export const TREE_EXPANDED_KEY = 'docsfy-tree-expanded'
export const SELECTED_VIEW_KEY = 'docsfy-selected-view'
export const SIDEBAR_COLLAPSED_KEY = 'docsfy-sidebar-collapsed'

export const SIDEBAR_WIDTH_KEY = 'docsfy-sidebar-width'
export const SIDEBAR_MIN_WIDTH = 180
export const SIDEBAR_MAX_WIDTH = 500
export const SIDEBAR_DEFAULT_WIDTH = 256

export const GENERATION_STAGES = [
  'cloning',
  'analyzing',
  'planning',
  'incremental_planning',
  'generating_pages',
  'validating',
  'completeness_check',
  'cross_linking',
  'rendering',
] as const

/** Shared badge style class strings for signal colors — single source of truth */
export const BADGE_STYLES = {
  green: 'bg-signal-green/10 text-signal-green border-signal-green/20',
  blue: 'bg-signal-blue/10 text-signal-blue border-signal-blue/20',
  red: 'bg-signal-red/10 text-signal-red border-signal-red/20',
  orange: 'bg-signal-orange/10 text-signal-orange border-signal-orange/20',
  purple: 'bg-signal-purple/10 text-signal-purple border-signal-purple/20',
  muted: 'bg-surface-elevated text-text-tertiary border-border-default',
} as const
