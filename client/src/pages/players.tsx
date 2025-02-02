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
import type { Player, Team } from "@db/schema";
import { useToast } from "@/hooks/use-toast";
import { Pencil } from "lucide-react";

const playerSchema = z.object({
  firstName: z.string().min(1, "First name is required"),
  lastName: z.string().min(1, "Last name is required"),
  year: z.string().min(1, "Year is required"),
  gender: z.enum(["male", "female"], {
    required_error: "Gender is required",
  }),
  height: z.number().min(60).max(84).describe("Height in inches (5'-7')"),
  handedness: z.enum(["left", "right"], {
    required_error: "Handedness is required",
  }),
  teamId: z.number().optional(),
  // Technical skills
  serve: z.number().min(40).max(99),
  forehand: z.number().min(40).max(99),
  backhand: z.number().min(40).max(99),
  volley: z.number().min(40).max(99),
  return: z.number().min(40).max(99),
  // Physical attributes
  speed: z.number().min(40).max(99),
  agility: z.number().min(40).max(99),
  stamina: z.number().min(40).max(99),
  // Mental attributes
  mentalToughness: z.number().min(40).max(99),
  consistency: z.number().min(40).max(99),
  // Other attributes
  potential: z.number().min(40).max(99),
});

type PlayerFormData = z.infer<typeof playerSchema>;

const YEARS = ["Freshman", "Sophomore", "Junior", "Senior"];

export default function PlayersPage() {
  const [isOpen, setIsOpen] = useState(false);
  const [editingPlayer, setEditingPlayer] = useState<Player | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: players } = useQuery<Player[]>({
    queryKey: ["/api/players"],
  });

  const { data: teams } = useQuery<Team[]>({
    queryKey: ["/api/teams"],
  });

  const form = useForm<PlayerFormData>({
    resolver: zodResolver(playerSchema),
    defaultValues: {
      firstName: "",
      lastName: "",
      year: "",
      gender: "male",
      height: 72,
      handedness: "right",
      serve: 70,
      forehand: 70,
      backhand: 70,
      volley: 70,
      return: 70,
      speed: 70,
      agility: 70,
      stamina: 70,
      mentalToughness: 70,
      consistency: 70,
      potential: 70,
    },
  });

  const createPlayerMutation = useMutation({
    mutationFn: async (newPlayer: PlayerFormData) => {
      const res = await fetch("/api/players", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newPlayer),
      });
      if (!res.ok) {
        throw new Error("Failed to create player");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/players"] });
      form.reset();
      setIsOpen(false);
      toast({
        title: "Success",
        description: "Player created successfully",
      });
    },
  });

  const updatePlayerMutation = useMutation({
    mutationFn: async (player: Player) => {
      const res = await fetch(`/api/players/${player.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(player),
      });
      if (!res.ok) {
        throw new Error("Failed to update player");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/players"] });
      form.reset();
      setIsOpen(false);
      setEditingPlayer(null);
      toast({
        title: "Success",
        description: "Player updated successfully",
      });
    },
  });

  const onSubmit = (data: PlayerFormData) => {
    if (data.teamId) {
      data.teamId = Number(data.teamId);
    }
    if (editingPlayer) {
      updatePlayerMutation.mutate({ ...editingPlayer, ...data });
    } else {
      createPlayerMutation.mutate(data);
    }
  };

  const handleEdit = (player: Player) => {
    setEditingPlayer(player);
    form.reset({
      firstName: player.firstName,
      lastName: player.lastName,
      year: player.year,
      gender: player.gender,
      height: player.height,
      handedness: player.handedness,
      teamId: player.teamId,
      serve: player.serve,
      forehand: player.forehand,
      backhand: player.backhand,
      volley: player.volley,
      return: player.return,
      speed: player.speed,
      agility: player.agility,
      stamina: player.stamina,
      mentalToughness: player.mentalToughness,
      consistency: player.consistency,
      potential: player.potential,
    });
    setIsOpen(true);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Players</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>Create Player</Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>{editingPlayer ? 'Edit' : 'Create New'} Player</DialogTitle>
              <DialogDescription>
                {editingPlayer ? 'Modify player attributes.' : 'Create a new tennis player with detailed attributes.'}
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="firstName">First Name</Label>
                  <Input id="firstName" {...form.register("firstName")} />
                  {form.formState.errors.firstName && (
                    <p className="text-sm text-red-500">{form.formState.errors.firstName.message}</p>
                  )}
                </div>
                <div>
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input id="lastName" {...form.register("lastName")} />
                  {form.formState.errors.lastName && (
                    <p className="text-sm text-red-500">{form.formState.errors.lastName.message}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label htmlFor="gender">Gender</Label>
                  <Select onValueChange={(value) => form.setValue("gender", value as "male" | "female")}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select gender" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">Male</SelectItem>
                      <SelectItem value="female">Female</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="height">Height (inches)</Label>
                  <Input
                    id="height"
                    type="number"
                    {...form.register("height", { valueAsNumber: true })}
                    min="60"
                    max="84"
                  />
                  <span className="text-xs text-muted-foreground">
                    {Math.floor(form.watch("height") / 12)}'{form.watch("height") % 12}"
                  </span>
                </div>
                <div>
                  <Label htmlFor="handedness">Handedness</Label>
                  <Select onValueChange={(value) => form.setValue("handedness", value as "left" | "right")}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select hand" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="right">Right-handed</SelectItem>
                      <SelectItem value="left">Left-handed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="year">Year</Label>
                  <Select onValueChange={(value) => form.setValue("year", value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select year" />
                    </SelectTrigger>
                    <SelectContent>
                      {YEARS.map((year) => (
                        <SelectItem key={year} value={year}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="team">Team (Optional)</Label>
                  <Select onValueChange={(value) => form.setValue("teamId", Number(value))}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select team" />
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

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="serve">Serve (40-99)</Label>
                  <Input
                    id="serve"
                    type="number"
                    {...form.register("serve", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
                <div>
                  <Label htmlFor="return">Return (40-99)</Label>
                  <Input
                    id="return"
                    type="number"
                    {...form.register("return", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="forehand">Forehand (40-99)</Label>
                  <Input
                    id="forehand"
                    type="number"
                    {...form.register("forehand", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
                <div>
                  <Label htmlFor="backhand">Backhand (40-99)</Label>
                  <Input
                    id="backhand"
                    type="number"
                    {...form.register("backhand", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="volley">Volley (40-99)</Label>
                  <Input
                    id="volley"
                    type="number"
                    {...form.register("volley", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
                <div>
                  <Label htmlFor="speed">Speed (40-99)</Label>
                  <Input
                    id="speed"
                    type="number"
                    {...form.register("speed", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="agility">Agility (40-99)</Label>
                  <Input
                    id="agility"
                    type="number"
                    {...form.register("agility", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
                <div>
                  <Label htmlFor="stamina">Stamina (40-99)</Label>
                  <Input
                    id="stamina"
                    type="number"
                    {...form.register("stamina", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="mentalToughness">Mental Toughness (40-99)</Label>
                  <Input
                    id="mentalToughness"
                    type="number"
                    {...form.register("mentalToughness", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
                <div>
                  <Label htmlFor="consistency">Consistency (40-99)</Label>
                  <Input
                    id="consistency"
                    type="number"
                    {...form.register("consistency", { valueAsNumber: true })}
                    min="40"
                    max="99"
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="potential">Potential (40-99)</Label>
                <Input
                  id="potential"
                  type="number"
                  {...form.register("potential", { valueAsNumber: true })}
                  min="40"
                  max="99"
                />
              </div>

              <Button type="submit" className="w-full" onClick={form.handleSubmit(onSubmit)}>
                {editingPlayer ? 'Update' : 'Create'} Player
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {players?.map((player) => (
          <Card key={player.id} className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-2"
              onClick={() => handleEdit(player)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <CardHeader>
              <CardTitle>
                {player.firstName} {player.lastName}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-sm text-muted-foreground">Year</p>
                  <p className="font-medium">{player.year}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Gender</p>
                  <p className="font-medium capitalize">{player.gender}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Height</p>
                  <p className="font-medium">
                    {Math.floor(player.height / 12)}'{player.height % 12}"
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Handedness</p>
                  <p className="font-medium capitalize">{player.handedness}-handed</p>
                </div>
              </div>
              <div className="mt-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm">Serve</span>
                  <span className="font-medium">{player.serve}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Return</span>
                  <span className="font-medium">{player.return}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Forehand</span>
                  <span className="font-medium">{player.forehand}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Backhand</span>
                  <span className="font-medium">{player.backhand}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Volley</span>
                  <span className="font-medium">{player.volley}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Speed</span>
                  <span className="font-medium">{player.speed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Agility</span>
                  <span className="font-medium">{player.agility}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Stamina</span>
                  <span className="font-medium">{player.stamina}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Mental Toughness</span>
                  <span className="font-medium">{player.mentalToughness}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Consistency</span>
                  <span className="font-medium">{player.consistency}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Potential</span>
                  <span className="font-medium">{player.potential}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}