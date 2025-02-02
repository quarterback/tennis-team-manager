import { pgTable, text, serial, integer, timestamp, boolean, jsonb, decimal, real } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { relations } from "drizzle-orm";

// Team table with enhanced rating system
export const teams = pgTable("teams", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  mascot: text("mascot").notNull(),
  location: text("location").notNull(),
  conference: text("conference").notNull(),
  schoolLevel: text("school_level").notNull(), // 'high_school' or 'college'
  gender: text("gender").notNull().default("male"), // 'male' or 'female'
  teamRating: decimal("team_rating", { precision: 4, scale: 2 }).notNull().default("8.00"), // UTR-style rating (1.00-16.50)
  prestige: integer("prestige").notNull().default(50),
  seasonWins: integer("season_wins").notNull().default(0),
  seasonLosses: integer("season_losses").notNull().default(0),
  totalWins: integer("total_wins").notNull().default(0),
  totalLosses: integer("total_losses").notNull().default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

// Enhanced player table with tennis-specific attributes
export const players = pgTable("players", {
  id: serial("id").primaryKey(),
  teamId: integer("team_id").references(() => teams.id),
  firstName: text("first_name").notNull(),
  lastName: text("last_name").notNull(),
  gender: text("gender").notNull(), // 'male' or 'female'
  height: integer("height").notNull(), // Height in inches
  handedness: text("handedness").notNull().default("right"), // 'left' or 'right'
  year: text("year").notNull(), // Freshman, Sophomore, etc.
  eligibleSingles: boolean("eligible_singles").default(true),
  eligibleDoubles: boolean("eligible_doubles").default(true),

  // UTR-style ratings
  singlesRating: decimal("singles_rating", { precision: 4, scale: 2 }).notNull().default("8.00"),
  doublesRating: decimal("doubles_rating", { precision: 4, scale: 2 }).notNull().default("8.00"),
  ratingConfidence: decimal("rating_confidence", { precision: 4, scale: 2 }).notNull().default("1.00"), // 0.00-1.00
  ratingVolatility: decimal("rating_volatility", { precision: 4, scale: 2 }).notNull().default("0.50"), // Higher means more rating movement
  matchesPlayed: integer("matches_played").notNull().default(0),

  // Rankings
  singlesRank: integer("singles_rank"), // Team ranking for singles lineup
  doublesRank: integer("doubles_rank"), // Team ranking for doubles lineup

  // Technical skills (1-100)
  serve: integer("serve").notNull(),
  forehand: integer("forehand").notNull(),
  backhand: integer("backhand").notNull(),
  volley: integer("volley").notNull(),
  return: integer("return").notNull(),

  // Physical attributes (1-100)
  speed: integer("speed").notNull(),
  agility: integer("agility").notNull(),
  stamina: integer("stamina").notNull(),

  // Mental attributes (1-100)
  mentalToughness: integer("mental_toughness").notNull(),
  consistency: integer("consistency").notNull(),

  potential: integer("potential").notNull(),
  fatigue: integer("fatigue").notNull().default(0),
  form: integer("form").notNull().default(75), // Current form (1-100)
  createdAt: timestamp("created_at").defaultNow(),
});

// Rating history to track player development
export const ratingHistory = pgTable("rating_history", {
  id: serial("id").primaryKey(),
  playerId: integer("player_id").references(() => players.id),
  matchId: integer("match_id").references(() => matches.id),
  date: timestamp("date").notNull().defaultNow(),
  previousRating: decimal("previous_rating", { precision: 4, scale: 2 }).notNull(),
  newRating: decimal("new_rating", { precision: 4, scale: 2 }).notNull(),
  ratingType: text("rating_type").notNull(), // 'singles' or 'doubles'
  matchType: text("match_type").notNull(), // 'regular_season', 'tournament', etc.
  opponentId: integer("opponent_id").references(() => players.id),
  opponentRating: decimal("opponent_rating", { precision: 4, scale: 2 }).notNull(),
  result: text("result").notNull(), // 'win' or 'loss'
  scoreDetail: jsonb("score_detail").notNull(), // Store set scores
});

// Match table for both singles and doubles matches
export const matches = pgTable("matches", {
  id: serial("id").primaryKey(),
  homeTeamId: integer("home_team_id").references(() => teams.id),
  awayTeamId: integer("away_team_id").references(() => teams.id),
  matchType: text("match_type").notNull(), // 'singles' or 'doubles'
  position: integer("position").notNull(), // Position in lineup (1-6 singles, 1-3 doubles)
  homePlayerOneId: integer("home_player_one_id").references(() => players.id),
  homePlayerTwoId: integer("home_player_two_id").references(() => players.id),
  awayPlayerOneId: integer("away_player_one_id").references(() => players.id),
  awayPlayerTwoId: integer("away_player_two_id").references(() => players.id),
  homeScore: jsonb("home_score").notNull(),
  awayScore: jsonb("away_score").notNull(),
  matchStats: jsonb("match_stats"),
  completed: boolean("completed").default(false),
  date: timestamp("date").defaultNow(),
  isPostseason: boolean("is_postseason").default(false),
  isTournament: boolean("is_tournament").default(false),
});

// Season/Tournament structure
export const seasons = pgTable("seasons", {
  id: serial("id").primaryKey(),
  year: integer("year").notNull(),
  schoolLevel: text("school_level").notNull(), // 'high_school' or 'college'
  name: text("name").notNull(),
  seasonType: text("season_type").notNull().default('fall'), // 'fall' or 'spring'
  startDate: timestamp("start_date").notNull(),
  endDate: timestamp("end_date").notNull(),
  status: text("status").notNull().default('upcoming'), // 'upcoming', 'in_progress', 'completed'
  type: text("type").notNull(), // 'regular_season', 'conference_tournament', 'state_tournament', 'national_tournament'
});

// Conferences to organize teams
export const conferences = pgTable("conferences", {
  id: serial("id").primaryKey(),
  name: text("name").notNull().unique(),
  schoolLevel: text("school_level").notNull(), // 'high_school' or 'college'
  region: text("region").notNull(),
  prestige: integer("prestige").notNull().default(50),
  createdAt: timestamp("created_at").defaultNow(),
});

// Define relationships
export const teamRelations = relations(teams, ({ many }) => ({
  players: many(players),
  homeMatches: many(matches, { relationName: "homeTeam" }),
  awayMatches: many(matches, { relationName: "awayTeam" }),
}));

export const playerRelations = relations(players, ({ one, many }) => ({
  team: one(teams, {
    fields: [players.teamId],
    references: [teams.id],
  }),
  ratingHistory: many(ratingHistory),
}));

export const matchRelations = relations(matches, ({ one }) => ({
  homeTeam: one(teams, {
    fields: [matches.homeTeamId],
    references: [teams.id],
  }),
  awayTeam: one(teams, {
    fields: [matches.awayTeamId],
    references: [teams.id],
  }),
}));

// Add new tables for season management
export const seasonSchedule = pgTable("season_schedule", {
  id: serial("id").primaryKey(),
  seasonId: integer("season_id").references(() => seasons.id),
  homeTeamId: integer("home_team_id").references(() => teams.id),
  awayTeamId: integer("away_team_id").references(() => teams.id),
  matchDate: timestamp("match_date").notNull(),
  isCompleted: boolean("is_completed").default(false),
  matchId: integer("match_id").references(() => matches.id),
  weekNumber: integer("week_number").notNull(),
  isConferenceGame: boolean("is_conference_game").default(false),
  createdAt: timestamp("created_at").defaultNow(),
});

export const seasonStandings = pgTable("season_standings", {
  id: serial("id").primaryKey(),
  seasonId: integer("season_id").references(() => seasons.id),
  teamId: integer("team_id").references(() => teams.id),
  conferenceWins: integer("conference_wins").default(0),
  conferenceLosses: integer("conference_losses").default(0),
  totalWins: integer("total_wins").default(0),
  totalLosses: integer("total_losses").default(0),
  matchesPlayed: integer("matches_played").default(0),
  avgTeamRating: decimal("avg_team_rating", { precision: 4, scale: 2 }),
  lastUpdated: timestamp("last_updated").defaultNow(),
});

// Add new relations
export const seasonRelations = relations(seasons, ({ many }) => ({
  schedule: many(seasonSchedule),
  standings: many(seasonStandings),
}));

export const seasonScheduleRelations = relations(seasonSchedule, ({ one }) => ({
  season: one(seasons, {
    fields: [seasonSchedule.seasonId],
    references: [seasons.id],
  }),
  homeTeam: one(teams, {
    fields: [seasonSchedule.homeTeamId],
    references: [teams.id],
  }),
  awayTeam: one(teams, {
    fields: [seasonSchedule.awayTeamId],
    references: [teams.id],
  }),
  match: one(matches, {
    fields: [seasonSchedule.matchId],
    references: [matches.id],
  }),
}));

export const seasonStandingsRelations = relations(seasonStandings, ({ one }) => ({
  season: one(seasons, {
    fields: [seasonStandings.seasonId],
    references: [seasons.id],
  }),
  team: one(teams, {
    fields: [seasonStandings.teamId],
    references: [teams.id],
  }),
}));

// Schemas for validation
export const insertTeamSchema = createInsertSchema(teams);
export const selectTeamSchema = createSelectSchema(teams);
export const insertPlayerSchema = createInsertSchema(players);
export const selectPlayerSchema = createSelectSchema(players);
export const insertMatchSchema = createInsertSchema(matches);
export const selectMatchSchema = createSelectSchema(matches);
export const insertRatingHistorySchema = createInsertSchema(ratingHistory);
export const selectRatingHistorySchema = createSelectSchema(ratingHistory);
export const insertConferenceSchema = createInsertSchema(conferences);
export const selectConferenceSchema = createSelectSchema(conferences);
export const insertSeasonSchema = createInsertSchema(seasons);
export const selectSeasonSchema = createSelectSchema(seasons);


// Add new types
export type SeasonSchedule = typeof seasonSchedule.$inferSelect;
export type SeasonStandings = typeof seasonStandings.$inferSelect;

// Add new schemas
export const insertSeasonScheduleSchema = createInsertSchema(seasonSchedule);
export const selectSeasonScheduleSchema = createSelectSchema(seasonSchedule);
export const insertSeasonStandingsSchema = createInsertSchema(seasonStandings);
export const selectSeasonStandingsSchema = createSelectSchema(seasonStandings);

// Types
export type Team = typeof teams.$inferSelect;
export type Player = typeof players.$inferSelect;
export type Match = typeof matches.$inferSelect;
export type RatingHistory = typeof ratingHistory.$inferSelect;
export type Conference = typeof conferences.$inferSelect;
export type Season = typeof seasons.$inferSelect;