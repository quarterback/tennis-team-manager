import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Match } from "@db/schema";

export default function MatchDetailPage({ params }: { params: { id: string } }) {
  const [_, setLocation] = useLocation();

  const { data: match } = useQuery<Match>({
    queryKey: [`/api/matches/${params.id}`],
  });

  if (!match) {
    return <div>Loading...</div>;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Match Details</h1>
        <Button variant="outline" onClick={() => setLocation('/matches')}>
          Back to Matches
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Match Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div className="text-xl font-semibold">
                {match.homeTeamId}
              </div>
              <div className="text-2xl font-bold">vs</div>
              <div className="text-xl font-semibold">
                {match.awayTeamId}
              </div>
            </div>
            
            {match.completed && (
              <div className="mt-4">
                <h3 className="font-semibold mb-2">Final Score</h3>
                <div className="flex justify-between items-center">
                  <div>
                    <p>Home: {match.homeScore.sets} sets</p>
                    <div className="text-sm text-muted-foreground">
                      Aces: {match.homeScore.stats.aces}<br />
                      Winners: {match.homeScore.stats.winners}<br />
                      Errors: {match.homeScore.stats.unforcedErrors}
                    </div>
                  </div>
                  <div>
                    <p>Away: {match.awayScore.sets} sets</p>
                    <div className="text-sm text-muted-foreground">
                      Aces: {match.awayScore.stats.aces}<br />
                      Winners: {match.awayScore.stats.winners}<br />
                      Errors: {match.awayScore.stats.unforcedErrors}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
