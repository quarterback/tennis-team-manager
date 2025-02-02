import type { Player } from "@db/schema";

// Constants for roster generation
const ROSTER_SIZE = 12;
const YEAR_DISTRIBUTION = {
  Freshman: 0.3,
  Sophomore: 0.3,
  Junior: 0.2,
  Senior: 0.2,
};

const FIRST_NAMES = [
  "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
  "Thomas", "Charles", "Emma", "Olivia", "Ava", "Isabella", "Sophia", "Mia",
  "Charlotte", "Amelia", "Harper", "Evelyn"
];

const LAST_NAMES = [
  "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
  "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
  "Martin", "Lee", "Thompson", "White", "Harris"
];

interface GeneratorConfig {
  teamId: number;
  prestige: number;
  gender: 'male' | 'female';
}

function getRandomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

function generateAttribute(baseValue: number, variance: number): number {
  const min = Math.max(40, baseValue - variance);
  const max = Math.min(99, baseValue + variance);
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function generateYear(): string {
  const random = Math.random();
  let cumulative = 0;
  
  for (const [year, probability] of Object.entries(YEAR_DISTRIBUTION)) {
    cumulative += probability;
    if (random <= cumulative) {
      return year;
    }
  }
  
  return "Freshman"; // fallback
}

function generateHeight(): number {
  // Generate height between 5'6" (66 inches) and 6'6" (78 inches)
  const minHeight = 66;
  const maxHeight = 78;
  return Math.floor(Math.random() * (maxHeight - minHeight + 1)) + minHeight;
}

export function generatePlayer(config: GeneratorConfig): Omit<Player, "id"> {
  const { teamId, prestige, gender } = config;
  
  // Base attribute level based on team prestige (40-99 scale)
  const baseAttribute = Math.floor((prestige / 100) * 30) + 55; // 55-85 range
  const variance = 10; // +/- variance for attributes

  // Technical skills slightly higher based on prestige
  const technicalBase = Math.min(99, baseAttribute + 5);
  
  return {
    teamId,
    firstName: getRandomElement(FIRST_NAMES),
    lastName: getRandomElement(LAST_NAMES),
    gender,
    height: generateHeight(),
    handedness: Math.random() > 0.85 ? "left" : "right",
    year: generateYear(),
    eligibleSingles: true,
    eligibleDoubles: true,
    playerRating: (baseAttribute / 20) + 4, // Convert to UTR scale (roughly)
    singlesRank: null,
    doublesRank: null,
    
    // Technical skills
    serve: generateAttribute(technicalBase, variance),
    forehand: generateAttribute(technicalBase, variance),
    backhand: generateAttribute(technicalBase, variance),
    volley: generateAttribute(technicalBase, variance),
    return: generateAttribute(technicalBase, variance),
    
    // Physical attributes
    speed: generateAttribute(baseAttribute, variance),
    agility: generateAttribute(baseAttribute, variance),
    stamina: generateAttribute(baseAttribute, variance),
    
    // Mental attributes
    mentalToughness: generateAttribute(baseAttribute, variance),
    consistency: generateAttribute(baseAttribute, variance),
    
    // Other attributes
    potential: generateAttribute(baseAttribute + 10, variance), // Higher potential
    fatigue: 0,
    form: 75,
    createdAt: new Date(),
  };
}

export function generateTeamRoster(config: GeneratorConfig): Omit<Player, "id">[] {
  const roster: Omit<Player, "id">[] = [];
  
  for (let i = 0; i < ROSTER_SIZE; i++) {
    roster.push(generatePlayer(config));
  }
  
  return roster;
}
