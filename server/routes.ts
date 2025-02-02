import type { Express } from "express";
import { createServer, type Server } from "http";
import { db } from "@db";
import { teams, players, matches, conferences, seasons, seasonSchedule, seasonStandings } from "@db/schema";
import { eq, and, sql } from "drizzle-orm";
import { ratingHistory } from "@db/schema"; // Assuming ratingHistory schema exists


export function registerRoutes(app: Express): Server {
  const httpServer = createServer(app);

  // Teams
  app.get("/api/teams", async (_req, res) => {
    const allTeams = await db.select().from(teams);
    res.json(allTeams);
  });

  app.post("/api/teams", async (req, res) => {
    const teamData = {
      ...req.body,
      createdAt: new Date(),
    };
    const team = await db.insert(teams).values(teamData).returning();
    res.json(team[0]);
  });

  // Players
  app.get("/api/players", async (req, res) => {
    const teamId = req.query.teamId;
    const query = db.select().from(players);

    const allPlayers = teamId
      ? await query.where(eq(players.teamId, Number(teamId)))
      : await query;

    res.json(allPlayers);
  });

  app.post("/api/players", async (req, res) => {
    const playerData = {
      ...req.body,
      createdAt: new Date(),
    };
    const player = await db.insert(players).values(playerData).returning();
    res.json(player[0]);
  });

  // New bulk players endpoint
  app.post("/api/players/bulk", async (req, res) => {
    const playerDataArray = req.body.map((player: any) => ({
      ...player,
      createdAt: new Date(),
    }));
    const createdPlayers = await db.insert(players).values(playerDataArray).returning();
    res.json(createdPlayers);
  });

  app.put("/api/players/:id", async (req, res) => {
    const { id } = req.params;
    const { createdAt, ...updateData } = req.body;
    const player = await db
      .update(players)
      .set(updateData)
      .where(eq(players.id, Number(id)))
      .returning();
    res.json(player[0]);
  });

  // Matches
  app.get("/api/matches", async (_req, res) => {
    const allMatches = await db.select().from(matches);
    res.json(allMatches);
  });

  app.post("/api/matches", async (req, res) => {
    const matchData = {
      ...req.body,
      date: new Date(),
      // Initialize scores to prevent null constraint violation
      homeScore: {
        sets: 0,
        stats: {
          aces: 0,
          doubleFaults: 0,
          firstServeIn: 0,
          firstServeAttempts: 0,
          secondServeIn: 0,
          secondServeAttempts: 0,
          winners: 0,
          unforcedErrors: 0,
          breakPointsWon: 0,
          breakPointOpportunities: 0
        }
      },
      awayScore: {
        sets: 0,
        stats: {
          aces: 0,
          doubleFaults: 0,
          firstServeIn: 0,
          firstServeAttempts: 0,
          secondServeIn: 0,
          secondServeAttempts: 0,
          winners: 0,
          unforcedErrors: 0,
          breakPointsWon: 0,
          breakPointOpportunities: 0
        }
      },
      completed: false,
      isTournament: false
    };
    const match = await db.insert(matches).values(matchData).returning();
    res.json(match[0]);
  });

  app.put("/api/matches/:id", async (req, res) => {
    const { id } = req.params;
    const { date, ...updateData } = req.body;
    const match = await db
      .update(matches)
      .set(updateData)
      .where(eq(matches.id, Number(id)))
      .returning();
    res.json(match[0]);
  });

  // Conferences
  app.get("/api/conferences", async (_req, res) => {
    const allConferences = await db.select().from(conferences);
    res.json(allConferences);
  });

  app.post("/api/conferences", async (req, res) => {
    const conferenceData = {
      ...req.body,
      createdAt: new Date(),
    };
    const conference = await db.insert(conferences).values(conferenceData).returning();
    res.json(conference[0]);
  });

  app.put("/api/conferences/:id", async (req, res) => {
    const { id } = req.params;
    const { createdAt, ...updateData } = req.body;
    const conference = await db
      .update(conferences)
      .set(updateData)
      .where(eq(conferences.id, Number(id)))
      .returning();
    res.json(conference[0]);
  });

  // Seasons
  app.get("/api/seasons", async (_req, res) => {
    const allSeasons = await db.select().from(seasons);
    res.json(allSeasons);
  });
  
    app.get("/api/seasons/:id", async (req, res) => {
    const { id } = req.params;
    try {
      const season = await db
        .select()
        .from(seasons)
        .where(eq(seasons.id, Number(id)))
        .limit(1);

      if (!season.length) {
        return res.status(404).json({ error: "Season not found" });
      }

      res.json(season[0]);
    } catch (error) {
      console.error('Error fetching season:', error);
      res.status(500).json({ error: 'Failed to fetch season' });
    }
  });

  app.post("/api/seasons", async (req, res) => {
    const seasonData = {
      ...req.body,
      startDate: new Date(req.body.startDate),
      endDate: new Date(req.body.endDate),
    };
    const season = await db.insert(seasons).values(seasonData).returning();
    res.json(season[0]);
  });
  
  // Update the DELETE endpoint for seasons to remove schedule validation
  app.delete("/api/seasons/:id", async (req, res) => {
    const { id } = req.params;
    try {
      // Delete related schedule entries first
      await db
        .delete(seasonSchedule)
        .where(eq(seasonSchedule.seasonId, Number(id)));

      // Delete related standings
      await db
        .delete(seasonStandings)
        .where(eq(seasonStandings.seasonId, Number(id)));

      // Delete the season
      const deletedSeason = await db
        .delete(seasons)
        .where(eq(seasons.id, Number(id)))
        .returning();

      res.json(deletedSeason[0]);
    } catch (error) {
      console.error('Error deleting season:', error);
      res.status(500).json({ error: 'Failed to delete season' });
    }
  });

  // New route for updating player ratings
  app.post("/api/players/ratings", async (req, res) => {
    const { ratingChanges, matchId, matchType, score } = req.body;
    const updatedPlayers = [];

    try {
      for (const change of ratingChanges) {
        // Update winner
        const winner = await db.update(players)
          .set({
            singlesRating: change.winnerNewRating,
            matchesPlayed: sql`${players.matchesPlayed} + 1`,
            ratingVolatility: sql`CASE 
              WHEN matches_played < 10 THEN 0.80
              WHEN matches_played < 20 THEN 0.65
              WHEN matches_played < 30 THEN 0.50
              ELSE 0.40
            END`
          })
          .where(eq(players.id, change.winnerId))
          .returning();

        // Update loser
        const loser = await db.update(players)
          .set({
            singlesRating: change.loserNewRating,
            matchesPlayed: sql`${players.matchesPlayed} + 1`,
            ratingVolatility: sql`CASE 
              WHEN matches_played < 10 THEN 0.80
              WHEN matches_played < 20 THEN 0.65
              WHEN matches_played < 30 THEN 0.50
              ELSE 0.40
            END`
          })
          .where(eq(players.id, change.loserId))
          .returning();

        updatedPlayers.push(...winner, ...loser);

        // Record rating history for winner
        await db.insert(ratingHistory).values({
          playerId: change.winnerId,
          matchId,
          date: new Date(),
          previousRating: change.winnerOldRating,
          newRating: change.winnerNewRating,
          ratingType: matchType === 'doubles' ? 'doubles' : 'singles',
          matchType: req.body.matchType || 'regular_season',
          opponentId: change.loserId,
          opponentRating: change.loserOldRating,
          result: 'win',
          scoreDetail: score
        });

        // Record rating history for loser
        await db.insert(ratingHistory).values({
          playerId: change.loserId,
          matchId,
          date: new Date(),
          previousRating: change.loserOldRating,
          newRating: change.loserNewRating,
          ratingType: matchType === 'doubles' ? 'doubles' : 'singles',
          matchType: req.body.matchType || 'regular_season',
          opponentId: change.winnerId,
          opponentRating: change.winnerOldRating,
          result: 'loss',
          scoreDetail: score
        });
      }

      res.json(updatedPlayers);
    } catch (error) {
      console.error('Error updating player ratings:', error);
      res.status(500).json({ error: 'Failed to update player ratings' });
    }
  });

  // Updated route for player fatigue and injuries
  app.post("/api/players/fatigue", async (req, res) => {
    const { players } = req.body;
    const updatedPlayers = [];

    try {
      for (const player of players) {
        const updated = await db
          .update(players)
          .set({
            fatigue: player.fatigue,
            // Natural recovery: players recover some fatigue over time
            form: sql`CASE 
              WHEN form > 90 THEN form
              WHEN fatigue > 80 THEN form - 5
              WHEN fatigue > 60 THEN form - 2
              ELSE form + 1
            END`,
            // If injured, adjust eligibility
            eligibleSingles: player.isInjured ? false : true,
            eligibleDoubles: player.isInjured ? false : true
          })
          .where(eq(players.id, player.id))
          .returning();

        updatedPlayers.push(...updated);
      }

      res.json(updatedPlayers);
    } catch (error) {
      console.error('Error updating player fatigue:', error);
      res.status(500).json({ error: 'Failed to update player fatigue' });
    }
  });

  // Enhanced endpoint for natural fatigue recovery (called periodically)
  app.post("/api/players/recover", async (_req, res) => {
    try {
      const recoveredPlayers = await db
        .update(players)
        .set({
          // Higher stamina leads to better recovery
          fatigue: sql`GREATEST(0, fatigue - LEAST(20, stamina / 5))`,
          // Form improves during recovery
          form: sql`CASE 
            WHEN form < 90 THEN form + 5
            ELSE form
          END`,
          // Auto-heal injuries based on time (can be adjusted)
          eligibleSingles: true,
          eligibleDoubles: true
        })
        .where(sql`fatigue > 0`)
        .returning();

      res.json(recoveredPlayers);
    } catch (error) {
      console.error('Error recovering player fatigue:', error);
      res.status(500).json({ error: 'Failed to recover player fatigue' });
    }
  });

  // Add DELETE endpoint for players
  app.delete("/api/players/:id", async (req, res) => {
    const { id } = req.params;
    try {
      // Check if player has any active matches
      const activeMatches = await db
        .select()
        .from(matches)
        .where(
          sql`(home_player_one_id = ${id} OR 
              home_player_two_id = ${id} OR 
              away_player_one_id = ${id} OR 
              away_player_two_id = ${id}) AND 
              completed = false`
        );

      if (activeMatches.length > 0) {
        return res.status(400).json({ error: "Cannot delete player with active matches" });
      }

      const deletedPlayer = await db
        .delete(players)
        .where(eq(players.id, Number(id)))
        .returning();

      res.json(deletedPlayer[0]);
    } catch (error) {
      console.error('Error deleting player:', error);
      res.status(500).json({ error: 'Failed to delete player' });
    }
  });

  // Add DELETE endpoint for teams
  app.delete("/api/teams/:id", async (req, res) => {
    const { id } = req.params;
    try {
      // Check if team has any active matches
      const activeMatches = await db
        .select()
        .from(matches)
        .where(
          sql`(home_team_id = ${id} OR away_team_id = ${id}) AND completed = false`
        );

      if (activeMatches.length > 0) {
        return res.status(400).json({ error: "Cannot delete team with active matches" });
      }

      // Delete all players associated with the team first
      await db
        .delete(players)
        .where(eq(players.teamId, Number(id)));

      // Then delete the team
      const deletedTeam = await db
        .delete(teams)
        .where(eq(teams.id, Number(id)))
        .returning();

      res.json(deletedTeam[0]);
    } catch (error) {
      console.error('Error deleting team:', error);
      res.status(500).json({ error: 'Failed to delete team' });
    }
  });

  // Generate season schedule
  app.post("/api/seasons/:id/schedule", async (req, res) => {
    const { id } = req.params;
    try {
      const season = await db
        .select()
        .from(seasons)
        .where(eq(seasons.id, Number(id)))
        .limit(1);

      if (!season.length) {
        return res.status(404).json({ error: "Season not found" });
      }

      // Get teams in the same conference/division
      const conferenceTeams = await db
        .select()
        .from(teams)
        .where(
          and(
            eq(teams.schoolLevel, season[0].schoolLevel),
            sql`teams.created_at <= ${season[0].startDate}`
          )
        );

      if (conferenceTeams.length < 2) {
        return res.status(400).json({ error: "Not enough teams to generate schedule" });
      }

      // Simple round-robin schedule generation
      const matches = [];
      const weeks = 12; // Standard season length
      let weekNumber = 1;

      for (let i = 0; i < conferenceTeams.length; i++) {
        for (let j = i + 1; j < conferenceTeams.length; j++) {
          // Create home and away matches
          matches.push({
            seasonId: Number(id),
            homeTeamId: conferenceTeams[i].id,
            awayTeamId: conferenceTeams[j].id,
            matchDate: new Date(season[0].startDate),
            weekNumber,
            isConferenceGame: conferenceTeams[i].conference === conferenceTeams[j].conference,
          });

          weekNumber = (weekNumber % weeks) + 1;

          // Return match (swap home/away)
          matches.push({
            seasonId: Number(id),
            homeTeamId: conferenceTeams[j].id,
            awayTeamId: conferenceTeams[i].id,
            matchDate: new Date(season[0].startDate),
            weekNumber,
            isConferenceGame: conferenceTeams[i].conference === conferenceTeams[j].conference,
          });

          weekNumber = (weekNumber % weeks) + 1;
        }
      }

      // Create schedule entries
      const schedule = await db
        .insert(seasonSchedule)
        .values(matches)
        .returning();

      // Initialize standings for all teams
      const standings = conferenceTeams.map(team => ({
        seasonId: Number(id),
        teamId: team.id,
        avgTeamRating: team.teamRating,
      }));

      await db.insert(seasonStandings).values(standings);

      res.json(schedule);
    } catch (error) {
      console.error('Error generating season schedule:', error);
      res.status(500).json({ error: 'Failed to generate season schedule' });
    }
  });

  // Get season schedule
  app.get("/api/seasons/:id/schedule", async (req, res) => {
    const { id } = req.params;
    try {
      const schedule = await db
        .select()
        .from(seasonSchedule)
        .where(eq(seasonSchedule.seasonId, Number(id)))
        .orderBy(seasonSchedule.weekNumber);

      res.json(schedule);
    } catch (error) {
      console.error('Error fetching season schedule:', error);
      res.status(500).json({ error: 'Failed to fetch season schedule' });
    }
  });

  // Get season standings
  app.get("/api/seasons/:id/standings", async (req, res) => {
    const { id } = req.params;
    try {
      const standings = await db
        .select()
        .from(seasonStandings)
        .where(eq(seasonStandings.seasonId, Number(id)))
        .orderBy(sql`conference_wins desc, conference_losses asc, total_wins desc`);

      res.json(standings);
    } catch (error) {
      console.error('Error fetching season standings:', error);
      res.status(500).json({ error: 'Failed to fetch season standings' });
    }
  });

  // Update season standings after a match
  app.post("/api/seasons/:id/standings/update", async (req, res) => {
    const { id } = req.params;
    const { matchId } = req.body;

    try {
      const match = await db
        .select()
        .from(matches)
        .where(eq(matches.id, matchId))
        .limit(1);

      if (!match.length || !match[0].completed) {
        return res.status(400).json({ error: "Invalid or incomplete match" });
      }

      const homeWin = match[0].homeScore.sets > match[0].awayScore.sets;
      const awayWin = !homeWin;

      // Update home team standings
      await db
        .update(seasonStandings)
        .set({
          totalWins: sql`total_wins + ${homeWin ? 1 : 0}`,
          totalLosses: sql`total_losses + ${awayWin ? 1 : 0}`,
          matchesPlayed: sql`matches_played + 1`,
          lastUpdated: new Date(),
        })
        .where(
          and(
            eq(seasonStandings.seasonId, Number(id)),
            eq(seasonStandings.teamId, match[0].homeTeamId)
          )
        );

      // Update away team standings
      await db
        .update(seasonStandings)
        .set({
          totalWins: sql`total_wins + ${awayWin ? 1 : 0}`,
          totalLosses: sql`total_losses + ${homeWin ? 1 : 0}`,
          matchesPlayed: sql`matches_played + 1`,
          lastUpdated: new Date(),
        })
        .where(
          and(
            eq(seasonStandings.seasonId, Number(id)),
            eq(seasonStandings.teamId, match[0].awayTeamId)
          )
        );

      res.json({ success: true });
    } catch (error) {
      console.error('Error updating standings:', error);
      res.status(500).json({ error: 'Failed to update standings' });
    }
  });

  // Add route for season matches
  app.get("/api/matches/:id", async (req, res) => {
    const { id } = req.params;
    try {
      const match = await db
        .select()
        .from(matches)
        .where(eq(matches.id, Number(id)))
        .limit(1);

      if (!match.length) {
        return res.status(404).json({ error: "Match not found" });
      }

      res.json(match[0]);
    } catch (error) {
      console.error('Error fetching match:', error);
      res.status(500).json({ error: 'Failed to fetch match' });
    }
  });

  return httpServer;
}