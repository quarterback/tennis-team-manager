import type { Player, Match, RatingHistory } from "@db/schema";

const PRI_K_FACTOR = 32; // Base factor for rating changes
const TOURNAMENT_MULTIPLIER = 1.5; // Increased rating impact for tournament matches
const MIN_RATING = 1.00;
const MAX_RATING = 16.50;
const TEAM_PRESTIGE_WEIGHT = 0.2; // Weight for team prestige impact

interface RatingChange {
  winnerId: number;
  winnerOldRating: number;
  winnerNewRating: number;
  loserId: number;
  loserOldRating: number;
  loserNewRating: number;
  ratingChange: number;
}

export function calculateExpectedScore(playerRating: number, opponentRating: number, teamPrestigeDiff: number): number {
  // Modified Elo formula that includes team prestige difference
  const prestige_factor = teamPrestigeDiff * TEAM_PRESTIGE_WEIGHT;
  const adjusted_rating_diff = (opponentRating - playerRating) + prestige_factor;
  return 1 / (1 + Math.pow(10, adjusted_rating_diff / 4));
}

export function calculateSetDominance(score: [number, number][]): number {
  // Calculate how dominant the victory was based on set scores
  let dominanceScore = 0;

  score.forEach(([winnerGames, loserGames]) => {
    const gameDiff = winnerGames - loserGames;
    if (gameDiff >= 4) dominanceScore += 1; // Very dominant set
    else if (gameDiff >= 2) dominanceScore += 0.7; // Clear win
    else dominanceScore += 0.4; // Close set
  });

  return dominanceScore / score.length;
}

export function calculatePerformanceRating(
  player: Player,
  opponent: Player,
  score: [number, number][],
  matchType: 'regular_season' | 'tournament' = 'regular_season'
): number {
  // Base rating from match result
  const basePerformance = player.singlesRating;

  // Adjust for opponent strength
  const opponentFactor = opponent.singlesRating / 8; // Normalized to 0-2 range

  // Adjust for dominance
  const dominance = calculateSetDominance(score);

  // Team prestige impact
  const prestigeImpact = (player.teamId && opponent.teamId) ? 
    (opponent.teamId - player.teamId) * TEAM_PRESTIGE_WEIGHT : 0;

  // Tournament bonus
  const tournamentBonus = matchType === 'tournament' ? TOURNAMENT_MULTIPLIER : 1;

  return (
    basePerformance * 0.7 + // Base rating weight
    opponentFactor * 0.15 + // Opponent strength weight
    dominance * 0.1 + // Match dominance weight
    prestigeImpact * 0.05 // Team prestige weight
  ) * tournamentBonus;
}

export function calculateRatingChange(
  winner: Player,
  loser: Player,
  score: [number, number][],
  matchType: 'regular_season' | 'tournament' = 'regular_season'
): RatingChange {
  const winnerRating = Number(winner.singlesRating);
  const loserRating = Number(loser.singlesRating);

  // Calculate team prestige difference
  const teamPrestigeDiff = winner.teamId && loser.teamId ? 
    (winner.teamId - loser.teamId) : 0;

  const expectedWinnerScore = calculateExpectedScore(winnerRating, loserRating, teamPrestigeDiff);
  const actualScore = 1; // Winner always gets 1, loser 0

  // Calculate performance ratings
  const winnerPerformance = calculatePerformanceRating(winner, loser, score, matchType);
  const loserPerformance = calculatePerformanceRating(loser, winner, score, matchType);

  // Calculate base rating change
  let ratingChange = PRI_K_FACTOR * (actualScore - expectedWinnerScore);

  // Adjust for match importance
  if (matchType === 'tournament') {
    ratingChange *= TOURNAMENT_MULTIPLIER;
  }

  // Adjust for score dominance
  const dominanceFactor = calculateSetDominance(score);
  ratingChange *= dominanceFactor;

  // Adjust for performance difference
  const performanceDiff = Math.abs(winnerPerformance - loserPerformance);
  ratingChange *= (1 + performanceDiff * 0.1);

  // Apply confidence and volatility adjustments
  ratingChange *= Number(winner.ratingVolatility);

  // Calculate new ratings
  const winnerNewRating = Math.min(MAX_RATING, Math.max(MIN_RATING, winnerRating + ratingChange));
  const loserNewRating = Math.min(MAX_RATING, Math.max(MIN_RATING, loserRating - ratingChange));

  return {
    winnerId: winner.id,
    winnerOldRating: winnerRating,
    winnerNewRating,
    loserId: loser.id,
    loserOldRating: loserRating,
    loserNewRating,
    ratingChange
  };
}

export function calculateDoublesRatingChange(
  winnerTeam: [Player, Player],
  loserTeam: [Player, Player],
  score: [number, number][],
  matchType: 'regular_season' | 'tournament' = 'regular_season'
): [RatingChange, RatingChange] {
  // Calculate average team ratings
  const winnerTeamRating = (Number(winnerTeam[0].doublesRating) + Number(winnerTeam[1].doublesRating)) / 2;
  const loserTeamRating = (Number(loserTeam[0].doublesRating) + Number(loserTeam[1].doublesRating)) / 2;

  const expectedWinnerScore = calculateExpectedScore(winnerTeamRating, loserTeamRating, 0);
  const actualScore = 1;

  let baseRatingChange = PRI_K_FACTOR * (actualScore - expectedWinnerScore);

  if (matchType === 'tournament') {
    baseRatingChange *= TOURNAMENT_MULTIPLIER;
  }

  const dominanceFactor = calculateSetDominance(score);
  baseRatingChange *= dominanceFactor;

  // Calculate individual rating changes
  const winner1Change = baseRatingChange * Number(winnerTeam[0].ratingVolatility);
  const winner2Change = baseRatingChange * Number(winnerTeam[1].ratingVolatility);
  const loser1Change = baseRatingChange * Number(loserTeam[0].ratingVolatility);
  const loser2Change = baseRatingChange * Number(loserTeam[1].ratingVolatility);

  const winner1Rating = Number(winnerTeam[0].doublesRating);
  const winner2Rating = Number(winnerTeam[1].doublesRating);
  const loser1Rating = Number(loserTeam[0].doublesRating);
  const loser2Rating = Number(loserTeam[1].doublesRating);

  return [
    {
      winnerId: winnerTeam[0].id,
      winnerOldRating: winner1Rating,
      winnerNewRating: Math.min(MAX_RATING, Math.max(MIN_RATING, winner1Rating + winner1Change)),
      loserId: loserTeam[0].id,
      loserOldRating: loser1Rating,
      loserNewRating: Math.min(MAX_RATING, Math.max(MIN_RATING, loser1Rating - loser1Change)),
      ratingChange: winner1Change
    },
    {
      winnerId: winnerTeam[1].id,
      winnerOldRating: winner2Rating,
      winnerNewRating: Math.min(MAX_RATING, Math.max(MIN_RATING, winner2Rating + winner2Change)),
      loserId: loserTeam[1].id,
      loserOldRating: loser2Rating,
      loserNewRating: Math.min(MAX_RATING, Math.max(MIN_RATING, loser2Rating - loser2Change)),
      ratingChange: winner2Change
    }
  ];
}

export function updatePlayerRatings(match: Match, players: Player[]): RatingChange[] {
  const ratingChanges: RatingChange[] = [];
  const matchType = match.isTournament ? 'tournament' : 'regular_season';

  if (match.matchType === 'singles') {
    const homePlayer = players.find(p => p.id === match.homePlayerOneId);
    const awayPlayer = players.find(p => p.id === match.awayPlayerOneId);

    if (!homePlayer || !awayPlayer) return [];

    const homeScore = match.homeScore as { sets: number };
    const awayScore = match.awayScore as { sets: number };
    const homeWon = homeScore.sets > awayScore.sets;
    const winner = homeWon ? homePlayer : awayPlayer;
    const loser = homeWon ? awayPlayer : homePlayer;

    const score = match.homeScore as { [key: string]: { home: number, away: number } };
    const setScores = Object.entries(score)
      .filter(([key]) => key.startsWith('set'))
      .map(([_, setScore]) => [setScore.home, setScore.away] as [number, number]);

    ratingChanges.push(calculateRatingChange(winner, loser, setScores, matchType));
  } else {
    // Doubles match
    const homePlayerOne = players.find(p => p.id === match.homePlayerOneId);
    const homePlayerTwo = players.find(p => p.id === match.homePlayerTwoId);
    const awayPlayerOne = players.find(p => p.id === match.awayPlayerOneId);
    const awayPlayerTwo = players.find(p => p.id === match.awayPlayerTwoId);

    if (!homePlayerOne || !homePlayerTwo || !awayPlayerOne || !awayPlayerTwo) return [];

    const homeScore = match.homeScore as { sets: number };
    const awayScore = match.awayScore as { sets: number };
    const homeWon = homeScore.sets > awayScore.sets;
    const winnerTeam = homeWon ? [homePlayerOne, homePlayerTwo] as [Player, Player] : [awayPlayerOne, awayPlayerTwo] as [Player, Player];
    const loserTeam = homeWon ? [awayPlayerOne, awayPlayerTwo] as [Player, Player] : [homePlayerOne, homePlayerTwo] as [Player, Player];

    const score = match.homeScore as { [key: string]: { home: number, away: number } };
    const setScores = Object.entries(score)
      .filter(([key]) => key.startsWith('set'))
      .map(([_, setScore]) => [setScore.home, setScore.away] as [number, number]);

    ratingChanges.push(...calculateDoublesRatingChange(winnerTeam, loserTeam, setScores, matchType));
  }

  return ratingChanges;
}