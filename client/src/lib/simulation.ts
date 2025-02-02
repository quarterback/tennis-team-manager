interface Play {
  description: string;
  scored: boolean;
  points: number;
  team: "home" | "away";
}

const PLAY_TYPES = [
  { desc: "serves an ace", points: 1, probability: 0.15 },
  { desc: "hits a winner", points: 1, probability: 0.25 },
  { desc: "forces an error", points: 1, probability: 0.30 },
  { desc: "hits the net", points: 0, probability: 0.15 },
  { desc: "hits long", points: 0, probability: 0.15 },
];

export function simulatePlay(): Play {
  const team = Math.random() > 0.5 ? "home" : "away";
  const playType = PLAY_TYPES[Math.floor(Math.random() * PLAY_TYPES.length)];
  const scored = Math.random() < playType.probability;

  return {
    description: `${team === "home" ? "Home" : "Away"} player ${playType.desc}`,
    scored,
    points: scored ? playType.points : 0,
    team,
  };
}

export interface GameScore {
  games: number;
  points: string; // "0", "15", "30", "40", "AD"
}

export interface SetScore {
  games: GameScore[];
  completed: boolean;
  winner?: "home" | "away";
}

export function convertPointsToTennisScore(points: number): string {
  switch (points) {
    case 0: return "0";
    case 1: return "15";
    case 2: return "30";
    case 3: return "40";
    case 4: return "AD";
    default: return "0";
  }
}