import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Link } from "wouter";

export default function Home() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-4">High School Tennis Management</h1>
        <p className="text-lg text-muted-foreground">
          Manage your tennis program. Create matches. Track player development.
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Quick Match</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4">Set up and simulate a tennis match.</p>
            <Link href="/matches">
              <Button>Play Match</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Season Mode</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4">Start a new season as head coach.</p>
            <Link href="/season">
              <Button>Start Season</Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tournament</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4">Create and manage tennis tournaments.</p>
            <Link href="/tournament">
              <Button>Create Tournament</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}