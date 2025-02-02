import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { Navbar } from "@/components/Navbar";
import Home from "@/pages/home";
import Teams from "@/pages/teams";
import Players from "@/pages/players";
import Matches from "@/pages/game";
import MatchDetail from "@/pages/match-detail";
import NewMatch from "@/pages/new-match";
import Conferences from "@/pages/conferences";
import Lineup from "@/pages/lineup";
import Seasons from "@/pages/seasons";
import SeasonDetail from "@/pages/season-detail";
import NotFound from "@/pages/not-found";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Home} />
      <Route path="/teams" component={Teams} />
      <Route path="/players" component={Players} />
      <Route path="/matches" component={Matches} />
      <Route path="/matches/new" component={NewMatch} />
      <Route path="/matches/:id" component={MatchDetail} />
      <Route path="/conferences" component={Conferences} />
      <Route path="/lineup" component={Lineup} />
      <Route path="/seasons" component={Seasons} />
      <Route path="/seasons/:id" component={SeasonDetail} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-background">
        <Navbar />
        <main>
          <Router />
        </main>
      </div>
      <Toaster />
    </QueryClientProvider>
  );
}

export default App;