import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Pencil, Trash2, UserPlus } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/hooks/use-toast";
import type { Team } from "@db/schema";

interface TeamCardProps {
  team: Team;
  onClick?: () => void;
}

export function TeamCard({ team, onClick }: TeamCardProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteTeam = useMutation({
    mutationFn: async () => {
      const response = await fetch(`/api/teams/${team.id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to delete team');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/teams"] });
      toast({
        title: "Team Deleted",
        description: `${team.name} has been deleted successfully.`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const autoPopulateRoster = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/players/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(generateRandomPlayers(12, team.id)), // Generate 12 players
      });
      if (!response.ok) throw new Error('Failed to create players');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/players"] });
      toast({
        title: "Roster Created",
        description: `Players have been added to ${team.name}.`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Helper function to generate random players
  const generateRandomPlayers = (count: number, teamId: number) => {
    const firstNames = ["John", "Emma", "Michael", "Sophia", "William", "Olivia", "James", "Ava", "Alexander", "Isabella"];
    const lastNames = ["Smith", "Johnson", "Brown", "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Martin"];

    return Array(count).fill(null).map(() => ({
      teamId,
      firstName: firstNames[Math.floor(Math.random() * firstNames.length)],
      lastName: lastNames[Math.floor(Math.random() * lastNames.length)],
      year: team.schoolLevel === 'high_school' ? Math.floor(Math.random() * 4) + 9 : Math.floor(Math.random() * 4) + 1, // 9-12 for HS, 1-4 for college
      eligibleSingles: true,
      eligibleDoubles: true,
      singlesRating: Number((Math.random() * 5 + 5).toFixed(2)), // Rating between 5.00 and 10.00
      doublesRating: Number((Math.random() * 5 + 5).toFixed(2)),
      dominantHand: Math.random() > 0.5 ? 'right' : 'left',
      serve: Math.floor(Math.random() * 40) + 60, // 60-100
      return: Math.floor(Math.random() * 40) + 60,
      forehand: Math.floor(Math.random() * 40) + 60,
      backhand: Math.floor(Math.random() * 40) + 60,
      volley: Math.floor(Math.random() * 40) + 60,
      stamina: Math.floor(Math.random() * 40) + 60,
      agility: Math.floor(Math.random() * 40) + 60,
      mentalToughness: Math.floor(Math.random() * 40) + 60,
      consistency: Math.floor(Math.random() * 40) + 60,
      fatigue: 0,
      form: 80,
      matchesPlayed: 0,
      ratingVolatility: 0.8,
      isInjured: false
    }));
  };

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{team.name}</span>
          <div className="flex gap-2">
            <Badge variant="outline">
              {team.schoolLevel === 'high_school' ? 'High School' : 'College'}
            </Badge>
            <Badge>{team.conference}</Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <p className="text-sm text-muted-foreground">Location</p>
            <p className="font-medium">{team.location}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Mascot</p>
            <p className="font-medium">{team.mascot}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Record</p>
            <p className="font-medium">{team.seasonWins}-{team.seasonLosses}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Gender</p>
            <p className="font-medium">
              {team.gender === 'male' ? "Men's" : "Women's"} Team
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Prestige</p>
            <p className="font-medium">{team.prestige}</p>
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <Button
            variant="outline"
            className="flex-1"
            onClick={onClick}
          >
            <Pencil className="w-4 h-4 mr-2" />
            Edit Team
          </Button>

          <Button
            variant="outline"
            className="flex-1"
            onClick={() => autoPopulateRoster.mutate()}
          >
            <UserPlus className="w-4 h-4 mr-2" />
            Generate Roster
          </Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="icon">
                <Trash2 className="w-4 h-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Team</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete {team.name}? This action will also delete all players associated with this team and cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={() => deleteTeam.mutate()}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  );
}