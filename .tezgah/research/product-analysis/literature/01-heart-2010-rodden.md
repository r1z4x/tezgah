# HEART: user-centred product metrics

- **Source:** Kerry Rodden, Hilary Hutchinson, Xin Fu, "Measuring the User Experience
  on a Large Scale: User-Centered Metrics for Web Applications", CHI 2010.
- **Read:** the author's version PDF,
  `https://research.google.com/pubs/archive/36299.pdf` (fetched 2026-09-19,
  converted to text). Bibliographic record corroborated by the ACM listing
  `https://dl.acm.org/doi/abs/10.1145/1753326.1753687`. Two independent sources agree
  on title, authors, venue and year.

## What the source says (verbatim where quoted)

- Google's older large-scale defaults are **PULSE**: "Page views, Uptime, Latency,
  Seven-day active users ... and Earnings". The paper's criticism: these are "either
  very low-level or indirect metrics of user experience, making them problematic when
  used to evaluate the impact of user interface changes", with "ambiguous
  interpretation - for example, a rise in page views for a particular feature may
  occur because the feature is genuinely popular, or because a confusing interface
  leads users to get lost in it".
- **HEART** is the replacement: "**H**appiness, **E**ngagement, **A**doption,
  **R**etention, and **T**ask success". Happiness is attitudinal (survey); Engagement,
  Adoption and Retention are behavioural and only possible at scale; Task Success
  covers "efficiency (e.g. time to complete a task), effectiveness (e.g. percent of
  tasks completed), and error rate".
- The framework "is not always appropriate to employ metrics from every category, but
  referring to the framework helps to make an explicit decision about including or
  excluding a particular category" - i.e. the categories force an explicit
  in/out decision rather than an inherited dashboard.
- **The process is Goals -> Signals -> Metrics.** "articulating the *goals* of a
  product or feature, then identifying *signals* that indicate success, and finally
  building specific *metrics* to track on a dashboard."
  - Goals: "Different team members may disagree about what the project goals are."
  - Signals: "Choose signals that are sensitive and specific to the goal - they should
    move only when the user experience is better or worse, not for other, unrelated
    reasons." Also: "Sometimes failure is easier to identify than success (e.g
    abandonment of a task, 'undo' events, frustration)."
  - Metrics: "Raw counts will go up as your user base grows, and need to be
    normalized; ratios, percentages, or averages per user are often more useful."
- Stated limits: metrics "are primarily useful for evaluation of launched products,
  and are not a substitute for early or formative user research". The paper applied
  the framework "to more than 20 different products and projects" inside Google and
  claims generalisation to other organisations as a confidence judgement, not a
  measured result.

## What this settles for the structure

1. A metric with no goal above it is not a metric: the analysis must state
   Goal -> Signal -> Metric in that order, and a metric that cannot be traced to a
   named goal is dropped.
2. Counts are refused; ratios, percentages or per-user averages are required
   (verbatim rule above).
3. A dashboard is an explicit include/exclude decision per HEART category, not a
   default set of panels.
4. The framework is one half only: it measures a launched product's UX. It does not
   cover feasibility, cost, or what the code actually does - the second axis this
   research needs.

## What this source does NOT support

- It does not prescribe feature prioritisation, discovery interviewing, or code
  quality. Anything claimed about those from this source would be an overreach.
- It is a 2010 web-application paper. It is silent on mobile, on agent-built
  software, and on AI-assisted development.
