const OpenAI = require("openai");
const logger = require("../utils/logger");
const config = require("../config/config.json");

class ScoringEngine {
  constructor() {
    this.openai = new OpenAI({
      apiKey: config.openai.apiKey,
    });
    this.weights = config.scoring.weights;
    this.thresholds = config.scoring.thresholds;
  }

  /**
   * Calculate comprehensive PR score
   * @param {Object} prData - Pull request data
   * @returns {Object} Scoring result with breakdown
   */
  async calculateScore(prData) {
    try {
      const { title, description, files, jiraContext } = prData;

      // Calculate individual scores
      const clarityScore = await this.analyzeClarityScore(title, description);
      const contextScore = this.analyzeContextScore(description, files);
      const completenessScore = this.analyzeCompletenessScore(prData);
      const jiraLinkScore = this.analyzeJiraLinkScore(jiraContext);

      // Calculate weighted total score
      const totalScore =
        clarityScore * this.weights.clarity +
        contextScore * this.weights.context +
        completenessScore * this.weights.completeness +
        jiraLinkScore * this.weights.jiraLink;

      const result = {
        totalScore: Math.round(totalScore * 10) / 10,
        breakdown: {
          clarity: clarityScore,
          context: contextScore,
          completeness: completenessScore,
          jiraLink: jiraLinkScore,
        },
        rating: this.getRating(totalScore),
        suggestions: await this.generateSuggestions(prData, {
          clarity: clarityScore,
          context: contextScore,
          completeness: completenessScore,
          jiraLink: jiraLinkScore,
        }),
        timestamp: new Date().toISOString(),
      };

      logger.info("PR score calculated", {
        prId: prData.id,
        score: result.totalScore,
        rating: result.rating,
      });

      return result;
    } catch (error) {
      logger.error("Error calculating PR score", { error: error.message });
      throw new Error("Failed to calculate PR score");
    }
  }

  /**
   * Analyze clarity using AI
   */
  async analyzeClarityScore(title, description) {
    try {
      const prompt = `
        Analyze the clarity of this pull request:
        
        Title: ${title}
        Description: ${description}
        
        Rate the clarity on a scale of 1-10 based on:
        - Clear, descriptive title
        - Well-structured description
        - Proper grammar and spelling
        - Easy to understand intent
        
        Respond with only a number between 1-10.
      `;

      const response = await this.openai.chat.completions.create({
        model: config.openai.model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 10,
        temperature: config.openai.temperature,
      });

      const score = parseFloat(response.choices[0].message.content.trim());
      return isNaN(score) ? 5.0 : Math.max(1, Math.min(10, score));
    } catch (error) {
      logger.warn("AI clarity analysis failed, using fallback", {
        error: error.message,
      });
      return this.fallbackClarityScore(title, description);
    }
  }

  /**
   * Analyze context score based on description and files
   */
  analyzeContextScore(description, files) {
    let score = 5.0; // Base score

    // Check description length and detail
    if (description && description.length > 100) score += 1.5;
    if (description && description.length > 300) score += 1.0;

    // Check for context keywords
    const contextKeywords = [
      "because",
      "fixes",
      "addresses",
      "implements",
      "refactor",
    ];
    const hasContext = contextKeywords.some((keyword) =>
      description?.toLowerCase().includes(keyword)
    );
    if (hasContext) score += 1.5;

    // Check file changes scope
    if (files && files.length > 0) {
      if (files.length <= 5) score += 1.0; // Focused changes
      if (files.length > 10) score -= 1.0; // Too broad
    }

    return Math.max(1, Math.min(10, score));
  }

  /**
   * Analyze completeness score
   */
  analyzeCompletenessScore(prData) {
    let score = 5.0; // Base score

    const { title, description, files, tests } = prData;

    // Check basic completeness
    if (title && title.length > 10) score += 1.0;
    if (description && description.length > 50) score += 1.0;
    if (files && files.length > 0) score += 1.0;

    // Check for tests
    if (tests && tests.length > 0) score += 2.0;

    // Check for documentation updates
    const hasDocUpdates = files?.some(
      (file) =>
        file.filename.toLowerCase().includes("readme") ||
        file.filename.toLowerCase().includes(".md")
    );
    if (hasDocUpdates) score += 1.0;

    return Math.max(1, Math.min(10, score));
  }

  /**
   * Analyze Jira link score
   */
  analyzeJiraLinkScore(jiraContext) {
    if (!jiraContext) return 0;

    let score = 5.0; // Base score for having Jira context

    // Check if ticket is properly linked
    if (jiraContext.ticketId) score += 2.0;
    if (jiraContext.ticketStatus === "In Progress") score += 1.0;
    if (jiraContext.ticketType) score += 1.0;
    if (jiraContext.priority) score += 1.0;

    return Math.max(0, Math.min(10, score));
  }

  /**
   * Generate AI-powered suggestions
   */
  async generateSuggestions(prData, scores) {
    try {
      const lowScoreAreas = Object.entries(scores)
        .filter(([_, score]) => score < 7)
        .map(([area, _]) => area);

      if (lowScoreAreas.length === 0) {
        return ["Great job! This PR meets all quality standards."];
      }

      const prompt = `
        Generate 2-3 specific improvement suggestions for a pull request with low scores in: ${lowScoreAreas.join(
          ", "
        )}.
        
        PR Title: ${prData.title}
        PR Description: ${prData.description}
        
        Focus on actionable improvements. Keep suggestions concise and helpful.
        Return as a JSON array of strings.
      `;

      const response = await this.openai.chat.completions.create({
        model: config.openai.model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 300,
        temperature: 0.7,
      });

      const suggestions = JSON.parse(response.choices[0].message.content);
      return Array.isArray(suggestions)
        ? suggestions
        : this.getFallbackSuggestions(lowScoreAreas);
    } catch (error) {
      logger.warn("AI suggestion generation failed, using fallback", {
        error: error.message,
      });
      return this.getFallbackSuggestions(lowScoreAreas);
    }
  }

  /**
   * Get rating based on score
   */
  getRating(score) {
    if (score >= this.thresholds.excellent) return "excellent";
    if (score >= this.thresholds.good) return "good";
    if (score >= this.thresholds.needsImprovement) return "needs-improvement";
    return "poor";
  }

  /**
   * Fallback clarity scoring without AI
   */
  fallbackClarityScore(title, description) {
    let score = 5.0;

    if (title && title.length > 10 && title.length < 100) score += 2.0;
    if (description && description.length > 50) score += 2.0;
    if (title && /^(feat|fix|docs|style|refactor|test|chore):/i.test(title))
      score += 1.0;

    return Math.max(1, Math.min(10, score));
  }

  /**
   * Fallback suggestions
   */
  getFallbackSuggestions(lowScoreAreas) {
    const suggestions = {
      clarity:
        "Consider adding more descriptive title and detailed description",
      context: "Provide more context about why this change is needed",
      completeness: "Add tests and update documentation if needed",
      jiraLink: "Link this PR to the relevant Jira ticket",
    };

    return lowScoreAreas.map((area) => suggestions[area]).filter(Boolean);
  }
}

module.exports = ScoringEngine;
