import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Match, Player, Team } from "@db/schema";
import { updatePlayerRatings } from "@/lib/ratingCalculator";
import { AlertCircle, Battery, BatteryCharging } from "lucide-react";

interface Position {
  name: string;
  type: 'singles' | 'doubles';
  homePlayerId?: number | null;
  awayPlayerId?: number | null;
  homePlayerOneId?: number | null;
  homePlayerTwoId?: number | null;
  awayPlayerOneId?: number | null;
  awayPlayerTwoId?: number | null;
  score?: [number, number][];
  injury?: boolean;
  fatigueIncrease?: number;
}

interface MatchScore {
  sets: number;
  stats: {
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
  };
}

interface GameSimulationProps {
  match: Match;
  onComplete: (match: Match) => void;
}

const calculatePostMatchInjuryChance = (player: Player, fatigueIncrease: number): boolean => {
  // Base injury chance is very low (0.5%)
  const baseChance = 0.005;

  // Increase chance based on:
  // 1. Current fatigue level
  const fatigueModifier = (player.fatigue / 100) * 0.01;

  // 2. Low stamina/agility increases injury chance
  const fitnessModifier = (200 - player.stamina - player.agility) / 2000;

  // 3. Match intensity (fatigue increase)
  const intensityModifier = (fatigueIncrease / 100) * 0.01;

  // Calculate final chance (max 5%)
  const injuryChance = Math.min(0.05, baseChance + fatigueModifier + fitnessModifier + intensityModifier);

  return Math.random() < injuryChance;
};

export function GameSimulation({ match, onComplete }: GameSimulationProps) {
  const [isSimulating, setIsSimulating] = useState(false);
  const [positions, setPositions] = useState<Position[]>([
    { name: "#1 Singles", type: 'singles' },
    { name: "#2 Singles", type: 'singles' },
    { name: "#3 Singles", type: 'singles' },
    { name: "#4 Singles", type: 'singles' },
    { name: "#5 Singles", type: 'singles' },
    { name: "#6 Singles", type: 'singles' },
    { name: "#1 Doubles", type: 'doubles' },
    { name: "#2 Doubles", type: 'doubles' },
    { name: "#3 Doubles", type: 'doubles' },
  ]);

  // Fetch players for both teams
  const { data: players } = useQuery<Player[]>({
    queryKey: ["/api/players"],
  });

  const homePlayers = players?.filter(p => p.teamId === match.homeTeamId) || [];
  const awayPlayers = players?.filter(p => p.teamId === match.awayTeamId) || [];

  const getPlayerName = (playerId?: number) => {
    if (!playerId) return "Select Player";
    const player = players?.find(p => p.id === playerId);
    return player ? `${player.firstName} ${player.lastName} (PRI: ${player.singlesRating})` : "Select Player";
  };

  const getFatigueColor = (fatigue: number) => {
    if (fatigue < 30) return 'text-green-500';
    if (fatigue < 60) return 'text-yellow-500';
    if (fatigue < 80) return 'text-orange-500';
    return 'text-red-500';
  };

  const renderFatigueIndicator = (player: Player) => (
    <div className={`flex items-center gap-1 ${getFatigueColor(player.fatigue)}`}>
      <Battery className="w-4 h-4" />
      <span className="text-sm">{100 - player.fatigue}%</span>
    </div>
  );


  const autoFillLineup = () => {
    if (!players) return;

    // Sort players by rating
    const sortedHomePlayers = [...homePlayers].sort((a, b) =>
      Number(b.singlesRating) - Number(a.singlesRating)
    );
    const sortedAwayPlayers = [...awayPlayers].sort((a, b) =>
      Number(b.singlesRating) - Number(a.singlesRating)
    );

    // Create new positions array with auto-filled players
    const newPositions = positions.map((pos, index) => {
      if (pos.type === 'singles') {
        // Fill singles positions in order of rating
        if (index < sortedHomePlayers.length && index < sortedAwayPlayers.length) {
          return {
            ...pos,
            homePlayerId: sortedHomePlayers[index].id,
            awayPlayerId: sortedAwayPlayers[index].id,
          };
        }
      } else {
        // For doubles, take next available players after singles
        const homeStartIdx = 6; // After singles players
        const doublesIndex = index - 6; // Adjust index for doubles pairs
        const homeIdx1 = homeStartIdx + (doublesIndex * 2);
        const homeIdx2 = homeStartIdx + (doublesIndex * 2) + 1;
        const awayIdx1 = homeStartIdx + (doublesIndex * 2);
        const awayIdx2 = homeStartIdx + (doublesIndex * 2) + 1;

        if (homeIdx2 < sortedHomePlayers.length && awayIdx2 < sortedAwayPlayers.length) {
          return {
            ...pos,
            homePlayerOneId: sortedHomePlayers[homeIdx1].id,
            homePlayerTwoId: sortedHomePlayers[homeIdx2].id,
            awayPlayerOneId: sortedAwayPlayers[awayIdx1].id,
            awayPlayerTwoId: sortedAwayPlayers[awayIdx2].id,
          };
        }
      }
      return pos;
    });

    setPositions(newPositions);
  };

  const updateSinglesPosition = (index: number, team: 'home' | 'away', playerId: number) => {
    const newPositions = [...positions];
    const position = newPositions[index] as Position;
    if (team === 'home') {
      position.homePlayerId = playerId;
    } else {
      position.awayPlayerId = playerId;
    }
    setPositions(newPositions);
  };

  const updateDoublesPosition = (
    index: number,
    team: 'home' | 'away',
    playerNum: 1 | 2,
    playerId: number
  ) => {
    const newPositions = [...positions];
    const position = newPositions[index] as Position;
    if (team === 'home') {
      if (playerNum === 1) {
        position.homePlayerOneId = playerId;
      } else {
        position.homePlayerTwoId = playerId;
      }
    } else {
      if (playerNum === 1) {
        position.awayPlayerOneId = playerId;
      } else {
        position.awayPlayerTwoId = playerId;
      }
    }
    setPositions(newPositions);
  };

  const canStartMatch = () => {
    return positions.every(pos => {
      if (pos.type === 'singles') {
        return pos.homePlayerId && pos.awayPlayerId;
      } else {
        return pos.homePlayerOneId && pos.homePlayerTwoId &&
               pos.awayPlayerOneId && pos.awayPlayerTwoId;
      }
    });
  };

  const generateTennisScore = (): [number, number][] => {
    const sets: [number, number][] = [];
    const numSets = Math.random() > 0.7 ? 3 : 2; // 30% chance of 3 sets

    for (let i = 0; i < numSets; i++) {
      let homeGames = 6;
      let awayGames = Math.floor(Math.random() * 5); // 0-4 games
      // Sometimes make it 7-5 or 7-6
      if (Math.random() > 0.7) {
        homeGames = 7;
        awayGames = 5 + Math.floor(Math.random() * 2); // 5 or 6
      }
      // Sometimes let away team win
      if (Math.random() > 0.5) {
        [homeGames, awayGames] = [awayGames, homeGames];
      }
      sets.push([homeGames, awayGames]);
    }
    return sets;
  };

  const simulateMatch = async () => {
    setIsSimulating(true);

    try {
      // Simulate scores for each position
      const simulatedPositions = positions.map(pos => {
        const score = generateTennisScore();
        const fatigueIncrease = Math.floor(Math.random() * 20) + 10; // 10-30 fatigue increase
        return {
          ...pos,
          score,
          fatigueIncrease
        };
      });

      setPositions(simulatedPositions);

      // Calculate overall match score
      const homeWins = simulatedPositions.filter(pos => {
        const setsWon = pos.score?.filter(set => set[0] > set[1]).length || 0;
        return setsWon >= 2;
      }).length;

      const awayWins = simulatedPositions.length - homeWins;

      const updatedMatch = {
        ...match,
        homeScore: {
          sets: homeWins,
          stats: {
            aces: 0,
            doubleFaults: 0,
            firstServeIn: 0,
            firstServeAttempts: 0,
            secondServeIn: 0,
            secondServeAttempts: 0,
            winners: 0,
            unforcedErrors: 0,
            breakPointsWon: 0,
            breakPointOpportunities: 0
          }
        } as MatchScore,
        awayScore: {
          sets: awayWins,
          stats: {
            aces: 0,
            doubleFaults: 0,
            firstServeIn: 0,
            firstServeAttempts: 0,
            secondServeIn: 0,
            secondServeAttempts: 0,
            winners: 0,
            unforcedErrors: 0,
            breakPointsWon: 0,
            breakPointOpportunities: 0
          }
        } as MatchScore,
        completed: true
      };

      // Calculate rating changes
      if (players) {
        const ratingChanges = simulatedPositions
          .map((pos) => {
            if (!pos.score) return null;

            if (pos.type === 'singles') {
              if (!pos.homePlayerId || !pos.awayPlayerId) return null;
              const homePlayer = players.find(p => p.id === pos.homePlayerId);
              const awayPlayer = players.find(p => p.id === pos.awayPlayerId);
              if (!homePlayer || !awayPlayer) return null;

              const homeWon = (pos.score.filter(set => set[0] > set[1]).length || 0) >= 2;
              return updatePlayerRatings({
                ...match,
                matchType: 'singles',
                homePlayerOneId: pos.homePlayerId,
                awayPlayerOneId: pos.awayPlayerId,
                homeScore: { sets: homeWon ? 2 : 1 } as MatchScore,
                awayScore: { sets: homeWon ? 1 : 2 } as MatchScore,
              }, [homePlayer, awayPlayer])[0];
            } else {
              if (!pos.homePlayerOneId || !pos.homePlayerTwoId ||
                  !pos.awayPlayerOneId || !pos.awayPlayerTwoId) return null;
              const homePlayerOne = players.find(p => p.id === pos.homePlayerOneId);
              const homePlayerTwo = players.find(p => p.id === pos.homePlayerTwoId);
              const awayPlayerOne = players.find(p => p.id === pos.awayPlayerOneId);
              const awayPlayerTwo = players.find(p => p.id === pos.awayPlayerTwoId);
              if (!homePlayerOne || !homePlayerTwo || !awayPlayerOne || !awayPlayerTwo) return null;

              const homeWon = (pos.score.filter(set => set[0] > set[1]).length || 0) >= 2;
              return updatePlayerRatings({
                ...match,
                matchType: 'doubles',
                homePlayerOneId: pos.homePlayerOneId,
                homePlayerTwoId: pos.homePlayerTwoId,
                awayPlayerOneId: pos.awayPlayerOneId,
                awayPlayerTwoId: pos.awayPlayerTwoId,
                homeScore: { sets: homeWon ? 2 : 1 } as MatchScore,
                awayScore: { sets: homeWon ? 1 : 2 } as MatchScore,
              }, [homePlayerOne, homePlayerTwo, awayPlayerOne, awayPlayerTwo]);
            }
          })
          .flat()
          .filter((change): change is NonNullable<typeof change> => change !== null);

        if (ratingChanges.length > 0) {
          try {
            const response = await fetch('/api/players/ratings', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                ratingChanges,
                matchId: match.id,
                matchType: match.matchType,
                score: {
                  sets: simulatedPositions.map(pos => pos.score || []),
                  stats: updatedMatch.homeScore.stats
                }
              }),
            });

            if (!response.ok) {
              throw new Error('Failed to update player ratings');
            }
          } catch (error) {
            console.error('Error updating player ratings:', error);
            // Continue with match completion even if rating update fails
          }
        }
      }

      // Handle post-match fatigue and rare injuries
      if (players) {
        const updatedPlayers = players.map(player => {
          const playerPositions = simulatedPositions.filter(pos => 
            pos.homePlayerId === player.id || 
            pos.awayPlayerId === player.id ||
            pos.homePlayerOneId === player.id ||
            pos.homePlayerTwoId === player.id ||
            pos.awayPlayerOneId === player.id ||
            pos.awayPlayerTwoId === player.id
          );

          const totalFatigueIncrease = playerPositions.reduce((sum, pos) => 
            sum + (pos.fatigueIncrease || 0), 0);

          // Check for post-match injuries
          const isInjured = calculatePostMatchInjuryChance(player, totalFatigueIncrease);

          return {
            ...player,
            fatigue: Math.min(100, player.fatigue + totalFatigueIncrease),
            isInjured
          };
        });

        // Update players in the database
        try {
          await fetch('/api/players/fatigue', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              players: updatedPlayers.map(p => ({
                id: p.id,
                fatigue: p.fatigue,
                isInjured: p.isInjured
              }))
            }),
          });
        } catch (error) {
          console.error('Error updating player fatigue:', error);
        }
      }

      setIsSimulating(false);
      onComplete(updatedMatch);
    } catch (error) {
      console.error('Error simulating match:', error);
      setIsSimulating(false);
    }
  };

  // Add function to get team names
  const { data: teams } = useQuery<Team[]>({
    queryKey: ["/api/teams"],
  });

  const homeTeam = teams?.find(t => t.id === match.homeTeamId);
  const awayTeam = teams?.find(t => t.id === match.awayTeamId);

  if (!players) {
    return <div>Loading players...</div>;
  }

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle className="text-center">
          <div className="flex justify-between items-center mb-4">
            <div className="text-xl font-bold">{homeTeam?.name || 'Home Team'}</div>
            <div className="text-lg">vs</div>
            <div className="text-xl font-bold">{awayTeam?.name || 'Away Team'}</div>
          </div>
          <div className="flex justify-between items-center">
            <div className="text-lg">Match Lineup</div>
            <div className="flex gap-4">
              {!match.completed && (
                <Button 
                  variant="outline" 
                  onClick={autoFillLineup}
                  disabled={match.completed}
                  className="flex items-center gap-2"
                >
                  <span>Auto Fill by PRI</span>
                </Button>
              )}
              <Badge variant={match.completed ? "secondary" : "default"}>
                {match.completed ? "Completed" : "Select Players"}
              </Badge>
            </div>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-8">
          {positions.map((position, index) => (
            <div key={index} className="border-b pb-6 last:border-b-0">
              <div className="flex justify-between items-center mb-4">
                 <h3 className="font-semibold">{position.name}</h3>
                  {position.injury && (
                    <div className="flex items-center gap-1 text-red-500">
                      <AlertCircle className="w-4 h-4" />
                      <span className="text-sm">Injury</span>
                    </div>
                  )}
              </div>
            

              {position.type === 'singles' ? (
                // Singles match layout
                <div className="grid grid-cols-3 gap-4 items-center">
                  <div className="space-y-2">
                    <Select
                      value={position.homePlayerId?.toString()}
                      onValueChange={(value) => updateSinglesPosition(index, 'home', parseInt(value))}
                      disabled={match.completed}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select home player" />
                      </SelectTrigger>
                      <SelectContent>
                        {homePlayers.map((player) => (
                          <SelectItem
                            key={player.id}
                            value={player.id.toString()}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span>{player.firstName} {player.lastName} (PRI: {player.singlesRating})</span>
                              {renderFatigueIndicator(player)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {position.score ? (
                    <div className="text-center">
                      {position.score.map((set, i) => (
                        <span key={i} className="mx-1">
                          {set[0]}-{set[1]}
                          {i < position.score!.length - 1 ? ", " : ""}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center">vs</div>
                  )}

                  <div>
                    <Select
                      value={position.awayPlayerId?.toString()}
                      onValueChange={(value) => updateSinglesPosition(index, 'away', parseInt(value))}
                      disabled={match.completed}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select away player" />
                      </SelectTrigger>
                      <SelectContent>
                        {awayPlayers.map((player) => (
                          <SelectItem
                            key={player.id}
                            value={player.id.toString()}
                          >
                           <div className="flex items-center justify-between gap-2">
                              <span>{player.firstName} {player.lastName} (PRI: {player.singlesRating})</span>
                              {renderFatigueIndicator(player)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ) : (
                // Doubles match layout with ratings
                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Select
                      value={position.homePlayerOneId?.toString()}
                      onValueChange={(value) => updateDoublesPosition(index, 'home', 1, parseInt(value))}
                      disabled={match.completed}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select home player 1" />
                      </SelectTrigger>
                      <SelectContent>
                        {homePlayers.map((player) => (
                          <SelectItem
                            key={player.id}
                            value={player.id.toString()}
                          >
                             <div className="flex items-center justify-between gap-2">
                                <span>{player.firstName} {player.lastName} (PRI: {player.doublesRating})</span>
                                {renderFatigueIndicator(player)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={position.homePlayerTwoId?.toString()}
                      onValueChange={(value) => updateDoublesPosition(index, 'home', 2, parseInt(value))}
                      disabled={match.completed}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select home player 2" />
                      </SelectTrigger>
                      <SelectContent>
                        {homePlayers.map((player) => (
                          <SelectItem
                            key={player.id}
                            value={player.id.toString()}
                          >
                           <div className="flex items-center justify-between gap-2">
                              <span>{player.firstName} {player.lastName} (PRI: {player.doublesRating})</span>
                               {renderFatigueIndicator(player)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {position.score ? (
                    <div className="text-center self-center">
                      {position.score.map((set, i) => (
                        <span key={i} className="mx-1">
                          {set[0]}-{set[1]}
                          {i < position.score!.length - 1 ? ", " : ""}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center self-center">vs</div>
                  )}

                  <div className="space-y-2">
                    <Select
                      value={position.awayPlayerOneId?.toString()}
                      onValueChange={(value) => updateDoublesPosition(index, 'away', 1, parseInt(value))}
                      disabled={match.completed}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select away player 1" />
                      </SelectTrigger>
                      <SelectContent>
                        {awayPlayers.map((player) => (
                           <SelectItem
                            key={player.id}
                            value={player.id.toString()}
                          >
                             <div className="flex items-center justify-between gap-2">
                                <span>{player.firstName} {player.lastName} (PRI: {player.doublesRating})</span>
                               {renderFatigueIndicator(player)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={position.awayPlayerTwoId?.toString()}
                      onValueChange={(value) => updateDoublesPosition(index, 'away', 2, parseInt(value))}
                      disabled={match.completed}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select away player 2" />
                      </SelectTrigger>
                      <SelectContent>
                        {awayPlayers.map((player) => (
                          <SelectItem
                            key={player.id}
                            value={player.id.toString()}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span>{player.firstName} {player.lastName} (PRI: {player.doublesRating})</span>
                               {renderFatigueIndicator(player)}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-center">
          <Button
            onClick={simulateMatch}
            disabled={isSimulating || match.completed || !canStartMatch()}
            size="lg"
          >
            {isSimulating ? "Simulating..." : match.completed ? "Match Complete" : "Start Match"}
          </Button>
        </div>

        {match.completed && (
          <div className="mt-6 text-center">
            <h3 className="font-semibold text-xl mb-2">Final Score</h3>
            <div className="flex justify-center items-center gap-4">
              <div className={`text-lg ${Number(match.homeScore.sets) > Number(match.awayScore.sets) ? 'font-bold text-green-600' : ''}`}>
                {homeTeam?.name}: {match.homeScore.sets}
              </div>
              <div>-</div>
              <div className={`text-lg ${Number(match.awayScore.sets) > Number(match.homeScore.sets) ? 'font-bold text-green-600' : ''}`}>
                {awayTeam?.name}: {match.awayScore.sets}
              </div>
            </div>
            <div className="mt-2 text-lg font-semibold text-green-600">
              Winner: {Number(match.homeScore.sets) > Number(match.awayScore.sets) ? homeTeam?.name : awayTeam?.name}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}