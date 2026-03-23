---
name: brainstorm
description: Brainstorm research ideas, questions, and hypotheses.
always: false
---

# Research Brainstorming

## When to Use
When the user wants to explore research ideas, generate questions, or think through a problem.

## How to Brainstorm

### Step 1: Understand the Starting Point
- What topic/domain is the user interested in?
- What is their background and constraints (compute, time, skills)?

### Step 2: Expand the Topic
Use paper_search to find recent trends, then generate:
- **Subtopics**: Break the main topic into 5-10 subtopics
- **Research Questions (RQs)**: Generate 5-10 specific, answerable questions
- **Hypotheses**: For each RQ, suggest a testable hypothesis
- **Cross-domain Connections**: Link to other fields that might provide insights

### Step 3: Evaluate & Rank
For each idea, assess:
- **Novelty** (1-5): Has this been done? Check with paper_search.
- **Feasibility** (1-5): Can this be done with available resources?
- **Impact** (1-5): Would this matter to the field/community?

### Step 4: Present
Format as a mind-map style document:
```
Topic: [Main Topic]
├── Subtopic A
│   ├── RQ1: [question]?
│   │   └── Hypothesis: [if X then Y]
│   └── RQ2: [question]?
├── Subtopic B
│   ├── RQ3: [question]?
│   └── Connection: [related field/method]
└── ...
```

### Step 5: Save
- Save brainstorm to `brainstorm_{topic}_{date}.md`
- Update MEMORY.md with the top ideas
