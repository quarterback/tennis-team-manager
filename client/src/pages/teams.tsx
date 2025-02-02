import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { TeamCard } from "@/components/TeamCard";
import type { Team, Conference } from "@db/schema";
import { generateTeamRoster } from "@/lib/playerGenerator";
import { useToast } from "@/hooks/use-toast";

const teamSchema = z.object({
  name: z.string().min(1, "Name is required"),
  mascot: z.string().min(1, "Mascot is required"),
  location: z.string().min(1, "Location is required"),
  conference: z.string().min(1, "Conference is required"),
  schoolLevel: z.enum(["high_school", "college"], {
    required_error: "School level is required",
  }),
  gender: z.enum(["male", "female"], {
    required_error: "Team gender is required",
  }),
  prestige: z.number().min(1).max(100),
});

type TeamFormData = z.infer<typeof teamSchema>;

export default function TeamsPage() {
  const [isOpen, setIsOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: teams } = useQuery<Team[]>({
    queryKey: ["/api/teams"],
  });

  const { data: conferences } = useQuery<Conference[]>({
    queryKey: ["/api/conferences"],
  });

  const form = useForm<TeamFormData>({
    resolver: zodResolver(teamSchema),
    defaultValues: {
      name: "",
      mascot: "",
      location: "",
      conference: "",
      schoolLevel: "high_school",
      gender: "male",
      prestige: 50,
    },
  });

  const createTeamMutation = useMutation({
    mutationFn: async (newTeam: TeamFormData) => {
      const teamRes = await fetch("/api/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newTeam),
      });

      if (!teamRes.ok) {
        throw new Error("Failed to create team");
      }

      const team = await teamRes.json();

      const roster = generateTeamRoster({
        teamId: team.id,
        prestige: newTeam.prestige,
        gender: newTeam.gender,
      });

      const playerRes = await fetch("/api/players/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(roster),
      });

      if (!playerRes.ok) {
        throw new Error("Failed to create roster");
      }

      return team;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/teams"] });
      queryClient.invalidateQueries({ queryKey: ["/api/players"] });
      form.reset();
      setIsOpen(false);
      toast({
        title: "Team Created",
        description: "Team and roster have been generated successfully.",
      });
    },
  });

  const updateTeamMutation = useMutation({
    mutationFn: async (team: Team) => {
      const res = await fetch(`/api/teams/${team.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(team),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/teams"] });
      form.reset();
      setIsOpen(false);
      setEditingTeam(null);
    },
  });

  const onSubmit = (data: TeamFormData) => {
    if (editingTeam) {
      updateTeamMutation.mutate({ ...editingTeam, ...data });
    } else {
      createTeamMutation.mutate(data);
    }
  };

  const handleEdit = (team: Team) => {
    setEditingTeam(team);
    form.reset({
      name: team.name,
      mascot: team.mascot,
      location: team.location,
      conference: team.conference,
      schoolLevel: team.schoolLevel as "high_school" | "college",
      gender: team.gender as "male" | "female",
      prestige: team.prestige,
    });
    setIsOpen(true);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Teams</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>Create Team</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingTeam ? 'Edit' : 'Create New'} Team</DialogTitle>
              <DialogDescription>
                Add a new team or modify an existing one.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <Label htmlFor="name">Team Name</Label>
                <Input id="name" {...form.register("name")} />
                {form.formState.errors.name && (
                  <p className="text-sm text-red-500">{form.formState.errors.name.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="mascot">Mascot</Label>
                <Input id="mascot" {...form.register("mascot")} />
                {form.formState.errors.mascot && (
                  <p className="text-sm text-red-500">{form.formState.errors.mascot.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="location">Location</Label>
                <Input id="location" {...form.register("location")} />
                {form.formState.errors.location && (
                  <p className="text-sm text-red-500">{form.formState.errors.location.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="schoolLevel">School Level</Label>
                <Select 
                  onValueChange={(value) => form.setValue("schoolLevel", value as "high_school" | "college")}
                  value={form.watch("schoolLevel")}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select school level" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high_school">High School</SelectItem>
                    <SelectItem value="college">College</SelectItem>
                  </SelectContent>
                </Select>
                {form.formState.errors.schoolLevel && (
                  <p className="text-sm text-red-500">{form.formState.errors.schoolLevel.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="gender">Team Gender</Label>
                <Select 
                  onValueChange={(value) => form.setValue("gender", value as "male" | "female")}
                  value={form.watch("gender")}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select team gender" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="male">Men's Team</SelectItem>
                    <SelectItem value="female">Women's Team</SelectItem>
                  </SelectContent>
                </Select>
                {form.formState.errors.gender && (
                  <p className="text-sm text-red-500">{form.formState.errors.gender.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="conference">Conference</Label>
                <Select 
                  onValueChange={(value) => form.setValue("conference", value)}
                  value={form.watch("conference")}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a conference" />
                  </SelectTrigger>
                  <SelectContent>
                    {conferences?.map((conference) => (
                      <SelectItem key={conference.id} value={conference.name}>
                        {conference.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {form.formState.errors.conference && (
                  <p className="text-sm text-red-500">{form.formState.errors.conference.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="prestige">Prestige (1-100)</Label>
                <Input 
                  id="prestige" 
                  type="number" 
                  {...form.register("prestige", { valueAsNumber: true })} 
                  min="1" 
                  max="100" 
                />
                {form.formState.errors.prestige && (
                  <p className="text-sm text-red-500">{form.formState.errors.prestige.message}</p>
                )}
              </div>
              <Button type="submit" className="w-full">
                {editingTeam ? 'Update' : 'Create'} Team
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {teams?.map((team) => (
          <TeamCard 
            key={team.id} 
            team={team} 
            onClick={() => handleEdit(team)}
          />
        ))}
      </div>
    </div>
  );
}