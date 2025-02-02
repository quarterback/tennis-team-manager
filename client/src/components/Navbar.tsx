import { Link } from "wouter";
import { Button } from "@/components/ui/button";

export function Navbar() {
  return (
    <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <div className="mr-4 hidden md:flex">
          <Link href="/" className="mr-6 flex items-center space-x-2">
            <span className="hidden font-bold sm:inline-block">
              Tennis Manager
            </span>
          </Link>
          <nav className="flex items-center space-x-6 text-sm font-medium">
            <Link href="/teams">
              <Button variant="ghost">Teams</Button>
            </Link>
            <Link href="/conferences">
              <Button variant="ghost">Conferences</Button>
            </Link>
            <Link href="/players">
              <Button variant="ghost">Players</Button>
            </Link>
            <Link href="/lineup">
              <Button variant="ghost">Lineup</Button>
            </Link>
            <Link href="/seasons">
              <Button variant="ghost">Seasons</Button>
            </Link>
            <Link href="/matches">
              <Button variant="ghost">Matches</Button>
            </Link>
          </nav>
        </div>
      </div>
    </nav>
  );
}