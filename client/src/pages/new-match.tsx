import { useLocation, useSearch } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import type { Team } from "@db/schema";

export default function NewMatchPage() {
  const [_, setLocation] = useLocation();
  const search = useSearch();
  const searchParams = new URLSearchParams(search);
  const { toast } = useToast();

  const homeTeamId = Number(searchParams.get('homeTeamId'));
  const awayTeamId = Number(searchParams.get('awayTeamId'));
  const seasonId = Number(searchParams.get('seasonId'));
  const scheduleId = Number(searchParams.get('scheduleId'));

  const { data: teams } = useQuery<Team[]>({
    queryKey: ["/api/teams"],
  });

  const createMatchMutation = useMutation({
    mutationFn: async (matchData: any) => {
      const res = await fetch("/api/matches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(matchData),
      });
      if (!res.ok) throw new Error("Failed to create match");
      return res.json();
    },
    onSuccess: (match) => {
      toast({
        title: "Match Created",
        description: "Ready to start the game!",
      });
      setLocation(`/matches/${match.id}`);
    },
  });

  const startMatch = () => {
    createMatchMutation.mutate({
      homeTeamId,
      awayTeamId,
      seasonId,
      scheduleId,
    });
  };

  const getTeamName = (teamId: number) => {
    return teams?.find(t => t.id === teamId)?.name || 'Unknown Team';
  };

  if (!teams) {
    return <div>Loading...</div>;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">New Match</h1>
        <Button variant="outline" onClick={() => window.history.back()}>
          Back
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Match Setup</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div className="text-xl font-semibold">{getTeamName(homeTeamId)}</div>
              <div className="text-2xl font-bold">vs</div>
              <div className="text-xl font-semibold">{getTeamName(awayTeamId)}</div>
            </div>
            
            <Button 
              className="w-full" 
              onClick={startMatch}
              disabled={createMatchMutation.isPending}
            >
              {createMatchMutation.isPending ? "Creating..." : "Start Match"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
