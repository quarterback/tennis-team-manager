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
import type { Season } from "@db/schema";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";

const seasonSchema = z.object({
  name: z.string().min(1, "Name is required"),
  year: z.number().min(2024).max(2050),
  schoolLevel: z.enum(["high_school", "college"], {
    required_error: "School level is required",
  }),
  seasonType: z.enum(["fall", "spring"], {
    required_error: "Season type is required",
  }),
  type: z.enum(["regular_season", "conference_tournament", "state_tournament", "national_tournament"], {
    required_error: "Competition type is required",
  })
});

type SeasonFormData = z.infer<typeof seasonSchema>;

const getStatusColor = (status: string) => {
  switch (status) {
    case 'upcoming':
      return 'bg-blue-100 text-blue-800';
    case 'in_progress':
      return 'bg-green-100 text-green-800';
    case 'completed':
      return 'bg-gray-100 text-gray-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

interface CardComponentProps {
  season: Season;
}

const CardComponent: React.FC<CardComponentProps> = ({ season }) => {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [_, setLocation] = useLocation();

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/seasons/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete season");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/seasons"] });
      toast({
        title: "Season Deleted",
        description: "The season has been deleted successfully.",
      });
    },
  });

  return (
    <Card key={season.id} className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <CardTitle className="flex justify-between items-center">
          <span>{season.name}</span>
          <span className={`text-sm px-2 py-1 rounded-full ${getStatusColor(season.status)}`}>
            {season.status.replace('_', ' ')}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div>
            <p className="text-sm text-muted-foreground">Type</p>
            <p className="font-medium capitalize">{season.type.replace('_', ' ')}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">School Level</p>
            <p className="font-medium capitalize">
              {season.schoolLevel === 'high_school' ? 'High School' : 'College'}
            </p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Season</p>
            <p className="font-medium capitalize">
              {season.seasonType} {season.year}
            </p>
          </div>
          <div className="flex gap-2 mt-4">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => {
                if (season.status === 'upcoming') {
                  // Generate schedule for new season
                  fetch(`/api/seasons/${season.id}/schedule`, {
                    method: 'POST',
                  })
                    .then(response => {
                      if (!response.ok) throw new Error('Failed to generate schedule');
                      return response.json();
                    })
                    .then(() => {
                      toast({
                        title: "Schedule Generated",
                        description: "Season schedule has been created successfully.",
                      });
                      setLocation(`/seasons/${season.id}`);
                    })
                    .catch(error => {
                      toast({
                        title: "Error",
                        description: error.message,
                        variant: "destructive",
                      });
                    });
                } else {
                  // View existing season
                  setLocation(`/seasons/${season.id}`);
                }
              }}
            >
              {season.status === 'upcoming' ? 'Generate Schedule' : 'View Season Details'}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm('Are you sure you want to delete this season?')) {
                  deleteMutation.mutate(season.id);
                }
              }}
            >
              Delete
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default function SeasonsPage() {
  const [isOpen, setIsOpen] = useState(false);
  const [_, setLocation] = useLocation();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: seasons } = useQuery<Season[]>({
    queryKey: ["/api/seasons"],
  });

  const form = useForm<SeasonFormData>({
    resolver: zodResolver(seasonSchema),
    defaultValues: {
      name: "",
      year: new Date().getFullYear(),
      schoolLevel: "high_school",
      seasonType: "fall",
      type: "regular_season",
    },
  });

  const createSeasonMutation = useMutation({
    mutationFn: async (newSeason: SeasonFormData) => {
      // Calculate dates based on season type
      let startDate, endDate;
      if (newSeason.seasonType === "fall") {
        startDate = new Date(newSeason.year, 7, 15); // August 15
        endDate = new Date(newSeason.year, 9, 31);   // October 31
      } else {
        startDate = new Date(newSeason.year, 2, 1);  // March 1
        endDate = new Date(newSeason.year, 4, 31);   // May 31
      }

      const seasonData = {
        ...newSeason,
        startDate,
        endDate,
        status: 'upcoming'
      };

      const res = await fetch("/api/seasons", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(seasonData),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/seasons"] });
      form.reset();
      setIsOpen(false);
      toast({
        title: "Season Created",
        description: "New season has been created successfully.",
      });
    },
  });

  const onSubmit = (data: SeasonFormData) => {
    createSeasonMutation.mutate(data);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Seasons</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>Create Season</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Season</DialogTitle>
              <DialogDescription>
                Set up a new season for your tennis program.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <Label htmlFor="name">Season Name</Label>
                <Input id="name" {...form.register("name")} />
                {form.formState.errors.name && (
                  <p className="text-sm text-red-500">{form.formState.errors.name.message}</p>
                )}
              </div>

              <div>
                <Label htmlFor="year">Year</Label>
                <Input
                  id="year"
                  type="number"
                  {...form.register("year", { valueAsNumber: true })}
                  min="2024"
                  max="2050"
                />
                {form.formState.errors.year && (
                  <p className="text-sm text-red-500">{form.formState.errors.year.message}</p>
                )}
              </div>

              <div>
                <Label htmlFor="seasonType">Season</Label>
                <Select
                  onValueChange={(value) => form.setValue("seasonType", value as "fall" | "spring")}
                  value={form.watch("seasonType")}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select season" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fall">Fall (Aug-Oct)</SelectItem>
                    <SelectItem value="spring">Spring (Mar-May)</SelectItem>
                  </SelectContent>
                </Select>
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
              </div>

              <div>
                <Label htmlFor="type">Competition Type</Label>
                <Select
                  onValueChange={(value) => form.setValue("type", value as any)}
                  value={form.watch("type")}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select competition type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="regular_season">Regular Season</SelectItem>
                    <SelectItem value="conference_tournament">Conference Tournament</SelectItem>
                    <SelectItem value="state_tournament">State Tournament</SelectItem>
                    <SelectItem value="national_tournament">National Tournament</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button type="submit" className="w-full">
                Create Season
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {seasons?.map((season) => (
          <CardComponent key={season.id} season={season} />
        ))}
      </div>
    </div>
  );
}