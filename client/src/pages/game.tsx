import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { GameSimulation } from "@/components/GameSimulation";
import type { Team, Match } from "@db/schema";
import { useToast } from "@/hooks/use-toast";

export default function GamePage() {
  const [homeTeamId, setHomeTeamId] = useState<string>();
  const [awayTeamId, setAwayTeamId] = useState<string>();
  const [currentMatch, setCurrentMatch] = useState<Match>();
  const { toast } = useToast();

  const { data: teams } = useQuery<Team[]>({
    queryKey: ["/api/teams"],
  });

  const createMatchMutation = useMutation({
    mutationFn: async (newMatch: Partial<Match>) => {
      const res = await fetch("/api/matches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newMatch),
      });
      if (!res.ok) {
        throw new Error("Failed to create match");
      }
      return res.json();
    },
    onSuccess: (match) => {
      setCurrentMatch(match);
      toast({
        title: "Teams Selected",
        description: "Now set up your lineup for each position",
      });
    },
  });

  const updateMatchMutation = useMutation({
    mutationFn: async (match: Match) => {
      const res = await fetch(`/api/matches/${match.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(match),
      });
      if (!res.ok) {
        throw new Error("Failed to update match");
      }
      return res.json();
    },
    onSuccess: (match) => {
      setCurrentMatch(match);
      toast({
        title: "Match Complete",
        description: `Final Score: ${match.homeScore.sets}-${match.awayScore.sets}`,
      });
    },
  });

  const startMatch = () => {
    if (homeTeamId && awayTeamId) {
      createMatchMutation.mutate({
        homeTeamId: parseInt(homeTeamId),
        awayTeamId: parseInt(awayTeamId),
        matchType: "singles", // We'll handle doubles positions separately
        position: 1,
        date: new Date(),
      });
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Match Simulation</h1>

      {!currentMatch ? (
        <Card>
          <CardContent className="py-6">
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <label className="block mb-2">Home Team</label>
                <Select onValueChange={setHomeTeamId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select home team" />
                  </SelectTrigger>
                  <SelectContent>
                    {teams?.map((team) => (
                      <SelectItem key={team.id} value={team.id.toString()}>
                        {team.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block mb-2">Away Team</label>
                <Select onValueChange={setAwayTeamId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select away team" />
                  </SelectTrigger>
                  <SelectContent>
                    {teams?.map((team) => (
                      <SelectItem key={team.id} value={team.id.toString()}>
                        {team.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button
              className="mt-6"
              onClick={startMatch}
              disabled={!homeTeamId || !awayTeamId}
            >
              Continue to Lineup Selection
            </Button>
          </CardContent>
        </Card>
      ) : (
        <GameSimulation
          match={currentMatch}
          onComplete={(match) => updateMatchMutation.mutate(match)}
        />
      )}
    </div>
  );
}