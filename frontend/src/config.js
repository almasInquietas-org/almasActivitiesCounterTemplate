// Dashboard BFF route served by Vercel Serverless Functions (/api/dashboard) and Vite dev middleware.
// Upstream Lambda URL & credentials remain server-side in API_URL / API_KEY / API_SIGNING_SECRET.
export const DASHBOARD_API_PATH = '/api/dashboard';

// Sport type display config
export const SPORT_CONFIG = {
  Run:        { icon: '🏃', label: 'Carrera' },
  Ride:       { icon: '🚴', label: 'Ciclismo' },
  Swim:       { icon: '🏊', label: 'Natación' },
  Hike:       { icon: '🥾', label: 'Senderismo' },
  Walk:       { icon: '🚶', label: 'Caminata' },
  Workout:    { icon: '💪', label: 'Entreno' },
  Yoga:       { icon: '🧘', label: 'Yoga' },
  VirtualRun: { icon: '🖥️', label: 'Virtual' },
  default:    { icon: '⚡', label: 'Actividad' },
};

export function getSportConfig(sportType) {
  if (!sportType) return SPORT_CONFIG.default;

  // 1. Try exact match first
  if (SPORT_CONFIG[sportType]) {
    return SPORT_CONFIG[sportType];
  }

  // 2. Try case-insensitive substring match
  // Sort keys by length descending to match longer/more specific keys first (e.g. 'VirtualRun' before 'Run')
  const sportTypeLower = sportType.toLowerCase();
  const keys = Object.keys(SPORT_CONFIG).filter(k => k !== 'default');
  const sortedKeys = [...keys].sort((a, b) => b.length - a.length);

  for (const key of sortedKeys) {
    if (sportTypeLower.includes(key.toLowerCase())) {
      return SPORT_CONFIG[key];
    }
  }

  return SPORT_CONFIG.default;
}

