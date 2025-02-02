import { useQuery } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { format, parseISO } from "date-fns";
import type { Season, SeasonSchedule, SeasonStandings, Team } from "@db/schema";

export default function SeasonDetailPage({ params }: { params: { id: string } }) {
  const [_, setLocation] = useLocation();

  // Fetch season details
  const { data: season } = useQuery<Season>({
    queryKey: [`/api/seasons/${params.id}`],
  });

  // Fetch schedule
  const { data: schedule } = useQuery<SeasonSchedule[]>({
    queryKey: [`/api/seasons/${params.id}/schedule`],
    enabled: !!params.id,
  });

  // Fetch standings
  const { data: standings } = useQuery<SeasonStandings[]>({
    queryKey: [`/api/seasons/${params.id}/standings`],
    enabled: !!params.id,
  });

  // Fetch teams for names
  const { data: teams } = useQuery<Team[]>({
    queryKey: ["/api/teams"],
  });

  const getTeamName = (teamId: number | null) => {
    if (!teamId) return "Unknown Team";
    const team = teams?.find(t => t.id === teamId);
    return team?.name || "Unknown Team";
  };

  const formatDate = (dateString: string | Date | null) => {
    if (!dateString) return "N/A";
    try {
      const date = typeof dateString === 'string' ? parseISO(dateString) : dateString;
      return format(date, 'MMM d, yyyy');
    } catch (error) {
      return "Invalid Date";
    }
  };

  if (!season || !teams) {
    return <div>Loading...</div>;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">{season.name}</h1>
          <p className="text-muted-foreground">
            {formatDate(season.startDate)} - {formatDate(season.endDate)}
          </p>
        </div>
        <Button variant="outline" onClick={() => setLocation('/seasons')}>
          Back to Seasons
        </Button>
      </div>

      <Tabs defaultValue="schedule" className="space-y-4">
        <TabsList>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="standings">Standings</TabsTrigger>
        </TabsList>

        <TabsContent value="schedule">
          <div className="grid gap-4">
            {schedule && schedule.length > 0 ? (
              Array.from({ length: 12 }, (_, week) => week + 1).map(weekNumber => {
                const weekMatches = schedule.filter(match => match.weekNumber === weekNumber);
                if (weekMatches.length === 0) return null;

                return (
                  <Card key={weekNumber}>
                    <CardHeader>
                      <CardTitle>Week {weekNumber}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        {weekMatches.map(match => (
                          <div 
                            key={match.id} 
                            className="flex justify-between items-center p-4 border rounded-lg"
                          >
                            <div className="flex-1 text-right">
                              {getTeamName(match.homeTeamId)}
                            </div>
                            <div className="mx-4 font-bold">vs</div>
                            <div className="flex-1 text-left">
                              {getTeamName(match.awayTeamId)}
                            </div>
                            {match.isCompleted ? (
                              <Button 
                                variant="outline" 
                                className="ml-4"
                                onClick={() => setLocation(`/matches/${match.matchId}`)}
                              >
                                View Result
                              </Button>
                            ) : (
                              <Button 
                                className="ml-4"
                                onClick={() => setLocation(`/matches/new?homeTeamId=${match.homeTeamId}&awayTeamId=${match.awayTeamId}&seasonId=${season.id}&scheduleId=${match.id}`)}
                              >
                                Play Match
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            ) : (
              <Card>
                <CardContent className="py-8 text-center">
                  <p className="text-muted-foreground">No schedule available for this season.</p>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        <TabsContent value="standings">
          <Card>
            <CardHeader>
              <CardTitle>Season Standings</CardTitle>
            </CardHeader>
            <CardContent>
              {standings && standings.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2">Team</th>
                        <th className="text-center py-2">Conference</th>
                        <th className="text-center py-2">W</th>
                        <th className="text-center py-2">L</th>
                        <th className="text-center py-2">PCT</th>
                        <th className="text-center py-2">Rating</th>
                      </tr>
                    </thead>
                    <tbody>
                      {standings.map(standing => {
                        const team = teams.find(t => t.id === standing.teamId);
                        const totalWins = standing.totalWins || 0;
                        const totalLosses = standing.totalLosses || 0;
                        const winPct = totalWins / (totalWins + totalLosses) || 0;

                        return (
                          <tr key={standing.id} className="border-b">
                            <td className="py-2">{team?.name}</td>
                            <td className="text-center py-2">{team?.conference}</td>
                            <td className="text-center py-2">{totalWins}</td>
                            <td className="text-center py-2">{totalLosses}</td>
                            <td className="text-center py-2">
                              {winPct.toFixed(3)}
                            </td>
                            <td className="text-center py-2">
                              {Number(standing.avgTeamRating || 0).toFixed(2)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-8 text-center">
                  <p className="text-muted-foreground">No standings available for this season.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}