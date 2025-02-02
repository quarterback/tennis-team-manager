import type { Player } from "@db/schema";

// Types for match statistics
interface MatchStats {
  aces: number;
  doubleFaults: number;
  firstServeIn: number;
  firstServeAttempts: number;
  secondServeIn: number;
  secondServeAttempts: number;
  winners: number;
  unforcedErrors: number;
  breakPointsWon: number;
  breakPointOpportunities: number;
  fatigueIncrease: number;
}

interface PlayerMatchStats {
  player: Player;
  stats: MatchStats;
}

interface MatchScore {
  sets: number[];
  currentGame: number[];
  currentPoint: string;
}

// Match simulation configuration
const POINTS = ['0', '15', '30', '40', 'Ad'];
const TIEBREAK_POINTS = 7;
const SETS_TO_WIN = 2;

class MatchEngine {
  protected servingPlayer: Player;
  protected receivingPlayer: Player;
  protected score: MatchScore;
  protected stats: Map<number, MatchStats>;
  protected isTiebreak: boolean = false;
  protected tiebreakPoints: [number, number] = [0, 0];
  protected tiebreakServer: Player;
  protected initialServer: Player;

  constructor(server: Player, receiver: Player) {
    this.servingPlayer = server;
    this.receivingPlayer = receiver;
    this.initialServer = server;
    this.tiebreakServer = server;
    this.score = {
      sets: [0, 0],
      currentGame: [0, 0],
      currentPoint: '0',
    };
    this.stats = new Map([
      [server.id, this.initializeStats()],
      [receiver.id, this.initializeStats()],
    ]);
  }

  protected initializeStats(): MatchStats {
    return {
      aces: 0,
      doubleFaults: 0,
      firstServeIn: 0,
      firstServeAttempts: 0,
      secondServeIn: 0,
      secondServeAttempts: 0,
      winners: 0,
      unforcedErrors: 0,
      breakPointsWon: 0,
      breakPointOpportunities: 0,
      fatigueIncrease: 0,
    };
  }

  protected calculateFatigueIncrease(player: Player, rallyLength: number): number {
    // Base fatigue increase from rally length and intensity
    let fatigueIncrease = rallyLength * 0.2;

    // Reduce fatigue based on player's fitness attributes
    const fitnessLevel = (player.stamina + player.agility) / 200;
    fatigueIncrease *= Math.max(0.3, 1 - fitnessLevel); // Better fitness reduces fatigue gain

    // Current fatigue affects recovery
    const currentFatiguePenalty = player.fatigue / 100;
    fatigueIncrease *= (1 + currentFatiguePenalty * 0.5);

    return Math.min(5, fatigueIncrease); // Cap at 5 points per rally
  }

  protected calculatePerformanceImpact(player: Player): number {
    // Performance decreases with fatigue, but high mental toughness helps maintain performance
    const baseFatiguePenalty = (player.fatigue / 100) * 0.3; // Up to 30% decrease
    const mentalToughnessBonus = (player.mentalToughness / 100) * 0.1; // Up to 10% compensation
    return Math.max(0.6, 1 - baseFatiguePenalty + mentalToughnessBonus);
  }

  protected calculateServeSuccess(player: Player, isSecondServe: boolean = false): boolean {
    const baseProb = isSecondServe ? 0.85 : 0.6;
    const serveSkill = player.serve / 100;
    const randomFactor = Math.random() * 0.2 - 0.1;
    const performanceFactor = this.calculatePerformanceImpact(player);

    return Math.random() < (baseProb * serveSkill * performanceFactor + randomFactor);
  }

  protected calculateReturnSuccess(returner: Player, server: Player, isSecondServe: boolean = false): boolean {
    const baseProb = isSecondServe ? 0.7 : 0.5;
    const returnSkill = returner.return / 100;
    const serveSkill = server.serve / 100;
    const randomFactor = Math.random() * 0.2 - 0.1;
    const performanceFactor = this.calculatePerformanceImpact(returner);

    return Math.random() < (baseProb * returnSkill * (1 - serveSkill * 0.5) * performanceFactor + randomFactor);
  }

  protected calculateRallyShot(player: Player, opponent: Player): boolean {
    const skills = [
      player.forehand / 100,
      player.backhand / 100,
      player.consistency / 100,
      player.mentalToughness / 100
    ];
    const avgSkill = skills.reduce((a, b) => a + b) / skills.length;
    const performanceFactor = this.calculatePerformanceImpact(player);
    const randomFactor = Math.random() * 0.3 - 0.15; // More variance in rallies

    return Math.random() < (avgSkill * performanceFactor + randomFactor);
  }

  protected updateStats(playerId: number, stat: keyof MatchStats) {
    const playerStats = this.stats.get(playerId);
    if (playerStats) {
      playerStats[stat]++;
      this.stats.set(playerId, playerStats);
    }
  }

  protected switchServer() {
    [this.servingPlayer, this.receivingPlayer] = [this.receivingPlayer, this.servingPlayer];
  }

  public simulatePoint(): { winner: Player; stats: Map<number, MatchStats> } {
    // Simulate first serve
    const firstServeIn = this.calculateServeSuccess(this.servingPlayer);
    this.updateStats(this.servingPlayer.id, 'firstServeAttempts');

    if (firstServeIn) {
      this.updateStats(this.servingPlayer.id, 'firstServeIn');

      // Check if it's an ace
      const isAce = Math.random() < (this.servingPlayer.serve / 200); // Max 50% chance for highest serve
      if (isAce) {
        this.updateStats(this.servingPlayer.id, 'aces');
        return { winner: this.servingPlayer, stats: this.stats };
      }

      // Return of serve
      if (!this.calculateReturnSuccess(this.receivingPlayer, this.servingPlayer)) {
        return { winner: this.servingPlayer, stats: this.stats };
      }
    } else {
      // Second serve
      this.updateStats(this.servingPlayer.id, 'secondServeAttempts');
      const secondServeIn = this.calculateServeSuccess(this.servingPlayer, true);

      if (!secondServeIn) {
        this.updateStats(this.servingPlayer.id, 'doubleFaults');
        return { winner: this.receivingPlayer, stats: this.stats };
      }

      this.updateStats(this.servingPlayer.id, 'secondServeIn');

      // Return of second serve
      if (!this.calculateReturnSuccess(this.receivingPlayer, this.servingPlayer, true)) {
        return { winner: this.servingPlayer, stats: this.stats };
      }
    }

    // Simulate rally
    let rallyLength = 0;
    let lastHitter = this.receivingPlayer;
    let nextHitter = this.servingPlayer;

    while (true) {
      rallyLength++;

      // Update fatigue
      const fatigueIncrease = this.calculateFatigueIncrease(nextHitter, rallyLength);
      const stats = this.stats.get(nextHitter.id);
      if (stats) {
        stats.fatigueIncrease += fatigueIncrease;
        this.stats.set(nextHitter.id, stats);
      }

      if (!this.calculateRallyShot(nextHitter, lastHitter)) {
        // Shot missed/error
        this.updateStats(nextHitter.id, 'unforcedErrors');
        return { winner: lastHitter, stats: this.stats };
      }

      // Winner probability increases with rally length
      const winnerProb = Math.min(0.15 + (rallyLength * 0.01), 0.3);
      if (Math.random() < winnerProb) {
        this.updateStats(nextHitter.id, 'winners');
        return { winner: nextHitter, stats: this.stats };
      }

      [lastHitter, nextHitter] = [nextHitter, lastHitter];
    }
  }

  public simulateGame(): { winner: Player; stats: Map<number, MatchStats> } {
    while (true) {
      const point = this.simulatePoint();
      const isServerPoint = point.winner.id === this.servingPlayer.id;

      // Update score
      if (this.isTiebreak) {
        this.tiebreakPoints[isServerPoint ? 0 : 1]++;

        // Check for tiebreak win
        if (this.tiebreakPoints[0] >= TIEBREAK_POINTS &&
            this.tiebreakPoints[0] >= this.tiebreakPoints[1] + 2) {
          return { winner: this.servingPlayer, stats: this.stats };
        }
        if (this.tiebreakPoints[1] >= TIEBREAK_POINTS &&
            this.tiebreakPoints[1] >= this.tiebreakPoints[0] + 2) {
          return { winner: this.receivingPlayer, stats: this.stats };
        }

        // Switch server every two points (except first point)
        if ((this.tiebreakPoints[0] + this.tiebreakPoints[1]) % 2 === 1) {
          this.switchServer();
        }
      } else {
        // Regular game scoring
        const currentPoints = isServerPoint ?
          this.score.currentGame[0] : this.score.currentGame[1];

        if (currentPoints === 3) { // 40
          if (this.score.currentGame[isServerPoint ? 1 : 0] < 3) {
            return { winner: point.winner, stats: this.stats };
          }
        } else if (currentPoints === 4) { // Ad
          return { winner: point.winner, stats: this.stats };
        }

        this.score.currentGame[isServerPoint ? 0 : 1]++;
      }
    }
  }

  public simulateSet(): { winner: Player; stats: Map<number, MatchStats> } {
    let serverGames = 0;
    let receiverGames = 0;

    while (true) {
      const game = this.simulateGame();
      if (game.winner.id === this.servingPlayer.id) {
        serverGames++;
      } else {
        receiverGames++;
      }

      // Check for set win
      if (serverGames >= 6 && serverGames >= receiverGames + 2) {
        return { winner: this.servingPlayer, stats: this.stats };
      }
      if (receiverGames >= 6 && receiverGames >= serverGames + 2) {
        return { winner: this.receivingPlayer, stats: this.stats };
      }

      // Check for tiebreak
      if (serverGames === 6 && receiverGames === 6) {
        this.isTiebreak = true;
        const tiebreak = this.simulateGame();
        this.isTiebreak = false;
        return tiebreak;
      }

      this.switchServer();
    }
  }

  public simulateMatch(): {
    winner: Player;
    score: number[][];
    stats: Map<number, MatchStats>;
  } {
    const score: number[][] = [];
    let serverSets = 0;
    let receiverSets = 0;

    while (true) {
      const set = this.simulateSet();
      if (set.winner.id === this.initialServer.id) {
        serverSets++;
      } else {
        receiverSets++;
      }

      // Switch initial server for next set
      [this.servingPlayer, this.receivingPlayer] = [this.receivingPlayer, this.servingPlayer];
      this.initialServer = this.servingPlayer;

      if (serverSets === SETS_TO_WIN) {
        return {
          winner: this.initialServer,
          score,
          stats: this.stats
        };
      }
      if (receiverSets === SETS_TO_WIN) {
        return {
          winner: this.receivingPlayer,
          score,
          stats: this.stats
        };
      }
    }
  }
}

export class DoublesMatchEngine extends MatchEngine {
  private servingTeam: [Player, Player];
  private receivingTeam: [Player, Player];
  private currentServer: number = 0;

  constructor(
    servingTeam: [Player, Player],
    receivingTeam: [Player, Player]
  ) {
    super(servingTeam[0], receivingTeam[0]);
    this.servingTeam = servingTeam;
    this.receivingTeam = receivingTeam;
  }

  protected override calculateRallyShot(player: Player, opponent: Player): boolean {
    const netGame = player.volley / 100;
    const teamwork = Math.min(player.mentalToughness, player.consistency) / 100;

    const skills = [
      player.forehand / 100,
      player.backhand / 100,
      netGame,
      teamwork
    ];

    const avgSkill = skills.reduce((a, b) => a + b) / skills.length;
    const performanceFactor = this.calculatePerformanceImpact(player);
    const randomFactor = Math.random() * 0.3 - 0.15;

    return Math.random() < (avgSkill * performanceFactor + randomFactor);
  }

  protected override switchServer() {
    this.currentServer = (this.currentServer + 1) % 2;
    if (this.currentServer === 0) {
      [this.servingTeam, this.receivingTeam] = [this.receivingTeam, this.servingTeam];
    }

    this.servingPlayer = this.servingTeam[this.currentServer];
    this.receivingPlayer = this.receivingTeam[this.currentServer];
  }
}

export { MatchEngine };