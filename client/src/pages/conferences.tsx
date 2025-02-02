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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import type { Conference } from "@db/schema";

const conferenceSchema = z.object({
  name: z.string().min(1, "Name is required"),
  schoolLevel: z.enum(["high_school", "college"], {
    required_error: "School level is required",
  }),
  region: z.string().min(1, "Region is required"),
  prestige: z.number().min(1).max(100),
});

type ConferenceFormData = z.infer<typeof conferenceSchema>;

export default function ConferencesPage() {
  const [isOpen, setIsOpen] = useState(false);
  const [editingConference, setEditingConference] = useState<Conference | null>(null);
  const queryClient = useQueryClient();

  const { data: conferences } = useQuery<Conference[]>({
    queryKey: ["/api/conferences"],
  });

  const form = useForm<ConferenceFormData>({
    resolver: zodResolver(conferenceSchema),
    defaultValues: {
      name: "",
      schoolLevel: "high_school",
      region: "",
      prestige: 50,
    },
  });

  const createConferenceMutation = useMutation({
    mutationFn: async (newConference: ConferenceFormData) => {
      const res = await fetch("/api/conferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newConference),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/conferences"] });
      form.reset();
      setIsOpen(false);
    },
  });

  const updateConferenceMutation = useMutation({
    mutationFn: async (conference: Conference) => {
      const res = await fetch(`/api/conferences/${conference.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(conference),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/conferences"] });
      form.reset();
      setIsOpen(false);
      setEditingConference(null);
    },
  });

  const onSubmit = (data: ConferenceFormData) => {
    if (editingConference) {
      updateConferenceMutation.mutate({ ...editingConference, ...data });
    } else {
      createConferenceMutation.mutate(data);
    }
  };

  const handleEdit = (conference: Conference) => {
    setEditingConference(conference);
    form.reset({
      name: conference.name,
      schoolLevel: conference.schoolLevel as "high_school" | "college",
      region: conference.region,
      prestige: conference.prestige,
    });
    setIsOpen(true);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Conferences</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>Create Conference</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{editingConference ? 'Edit' : 'Create New'} Conference</DialogTitle>
              <DialogDescription>
                Add a new conference or modify an existing one.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <Label htmlFor="name">Conference Name</Label>
                <Input id="name" {...form.register("name")} />
                {form.formState.errors.name && (
                  <p className="text-sm text-red-500">{form.formState.errors.name.message}</p>
                )}
              </div>
              <div>
                <Label htmlFor="schoolLevel">School Level</Label>
                <Select
                  value={form.getValues("schoolLevel")}
                  onValueChange={(value) => form.setValue("schoolLevel", value as "high_school" | "college")}
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
                <Label htmlFor="region">Region</Label>
                <Input id="region" {...form.register("region")} />
                {form.formState.errors.region && (
                  <p className="text-sm text-red-500">{form.formState.errors.region.message}</p>
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
                {editingConference ? 'Update' : 'Create'} Conference
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {conferences?.map((conference) => (
          <Card key={conference.id} className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                <span>{conference.name}</span>
                <span className="text-sm font-normal px-2 py-1 rounded-full bg-primary/10">
                  {conference.schoolLevel === 'high_school' ? 'High School' : 'College'}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div>
                  <p className="text-sm text-muted-foreground">Region</p>
                  <p className="font-medium">{conference.region}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Prestige</p>
                  <p className="font-medium">{conference.prestige}</p>
                </div>
                <Button 
                  variant="outline" 
                  className="w-full mt-4"
                  onClick={() => handleEdit(conference)}
                >
                  Edit Conference
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}