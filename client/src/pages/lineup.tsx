import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";
import { Player } from "@db/schema";

type LineupMode = "singles" | "doubles";

export default function LineupPage() {
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [mode, setMode] = useState<LineupMode>("singles");
  const queryClient = useQueryClient();

  const { data: players } = useQuery<Player[]>({
    queryKey: ["/api/players", selectedTeamId],
    enabled: !!selectedTeamId,
  });

  const { data: teams } = useQuery({
    queryKey: ["/api/teams"],
  });

  const updatePlayerRankMutation = useMutation({
    mutationFn: async ({ playerId, singlesRank, doublesRank }: { playerId: number; singlesRank?: number; doublesRank?: number }) => {
      const res = await fetch(`/api/players/${playerId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ singlesRank, doublesRank }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/players", selectedTeamId] });
    },
  });

  const onDragEnd = (result: any) => {
    if (!result.destination || !players) return;

    const sourceIdx = result.source.index;
    const destIdx = result.destination.index;
    const player = players[sourceIdx];

    // Update player rankings
    if (mode === "singles") {
      updatePlayerRankMutation.mutate({
        playerId: player.id,
        singlesRank: destIdx + 1,
      });
    } else {
      updatePlayerRankMutation.mutate({
        playerId: player.id,
        doublesRank: destIdx + 1,
      });
    }
  };

  const getPlayerStats = (player: Player) => {
    const stats = [];
    if (mode === "singles") {
      stats.push(`Serve: ${player.serve}`);
      stats.push(`Forehand: ${player.forehand}`);
      stats.push(`Backhand: ${player.backhand}`);
    } else {
      stats.push(`Volley: ${player.volley}`);
      stats.push(`Return: ${player.return}`);
    }
    stats.push(`Form: ${player.form}%`);
    stats.push(`Fatigue: ${player.fatigue}%`);
    return stats;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Lineup Management</h1>
        <div className="flex gap-4">
          <select
            className="p-2 border rounded"
            value={selectedTeamId || ""}
            onChange={(e) => setSelectedTeamId(Number(e.target.value))}
          >
            <option value="">Select Team</option>
            {teams?.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button
              variant={mode === "singles" ? "default" : "outline"}
              onClick={() => setMode("singles")}
            >
              Singles
            </Button>
            <Button
              variant={mode === "doubles" ? "default" : "outline"}
              onClick={() => setMode("doubles")}
            >
              Doubles
            </Button>
          </div>
        </div>
      </div>

      {selectedTeamId ? (
        <DragDropContext onDragEnd={onDragEnd}>
          <Droppable droppableId="lineup">
            {(provided) => (
              <div
                {...provided.droppableProps}
                ref={provided.innerRef}
                className="space-y-4"
              >
                {players
                  ?.sort((a, b) => 
                    mode === "singles" 
                      ? (a.singlesRank || 999) - (b.singlesRank || 999)
                      : (a.doublesRank || 999) - (b.doublesRank || 999)
                  )
                  .map((player, index) => (
                    <Draggable
                      key={player.id}
                      draggableId={String(player.id)}
                      index={index}
                    >
                      {(provided) => (
                        <Card
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          {...provided.dragHandleProps}
                          className="hover:shadow-md transition-shadow"
                        >
                          <CardHeader>
                            <CardTitle className="flex justify-between">
                              <span>
                                {index + 1}. {player.firstName} {player.lastName}
                              </span>
                              <span className="text-sm text-muted-foreground">
                                {player.year}
                              </span>
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                              {getPlayerStats(player).map((stat, i) => (
                                <div key={i} className="text-sm">
                                  {stat}
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </Draggable>
                  ))}
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Select a team to manage lineup
          </CardContent>
        </Card>
      )}
    </div>
  );
}
