# Clarification about the homework

During the course, you will build one project: your own AI system working with real, “messy” data. You choose its topic now—for example, an assistant for contracts, invoices or CVs.

The four homework cases are stages of this project: first, the system learns to extract data from documents; then it searches them and answers questions with sources; next, as an agent, it carries out tasks itself; and finally, it works as a complete service with an API, security and monitoring.

The completed system after case 4 is your final course project, which you will present at Demo Day. This way, you follow a process similar to real work, build on the same project throughout the course, and finish with a working product for your portfolio rather than a collection of unrelated homework assignments.

If you would like more practice, or you have a work-related task you need to complete, go ahead and do it. Share the problems and details you encounter in the chat, and we will work through them!

Here is a table of industries you can tailor your course project to, so that you can look for specific data and solve a specific problem.

| Industry | Documents | Project idea |
| --- | --- | --- |
| Legal | Contracts, court decisions, laws | A contract assistant: risky clauses, deadlines, answers with references to clauses. |
| Finance and accounting | Invoices, acceptance certificates, bank statements | Automatic invoice processing and reconciliation with orders. |
| HR and recruitment | CVs, job advertisements, interview feedback | Matching candidates to a vacancy and producing a shortlist with explanations. |
| Support / customer service | Tickets, emails, knowledge base | Classifying requests, finding a solution and drafting a reply. |
| E-commerce and retail | Catalogues, supplier price lists, reviews | Standardising price lists, comparing prices and analysing complaints. |
| Logistics | Consignment notes, customs declarations, CMR documents | Extracting data from consignment notes and checking document completeness. |
| Healthcare | Discharge summaries, treatment protocols, medicine instructions | An assistant for clinical protocols, using de-identified data only. |
| Construction | Cost estimates, specifications, material certificates | Checking estimates, searching standards and processing certificates. |
| Manufacturing | Raw-material certificates, process sheets, instructions | Extracting parameters from certificates and checking compliance. |
| Real estate | Listings, rental agreements, technical property documents | Finding properties that match a request and analysing rental terms. |
| Insurance | Policies, claims, inspection reports | Processing insurance claims and checking coverage against the policy. |
| Public sector and procurement | Tender documentation (Prozorro), regulations | Analysing tenders, finding relevant procurement opportunities and checking requirements. |
| Education | Curricula, textbooks, student work | An assistant for learning materials and checking work against rubrics. |
| IT / software development | Technical documentation, changelogs, Jira tickets | A bot for internal documentation and bug analysis. |

## Use this prompt

I am taking an AI Engineering course. Help me come up with my course project.

About me: [You can provide some context about yourself here.]

Data I have: [For example: de-identified documents from work / I have no data and need public sources.]

The project is one AI system that I will build throughout the course in four stages:

1. The system extracts structured data from raw documents (PDFs, scans) and compares two models: a paid model and a local model.
2. I add document search and answers with references to the source (RAG), plus quality tests.
3. I add an agent that independently carries out multi-step tasks using tools.
4. I turn it into a service: API, security, monitoring and cost calculation.

Suggest three project ideas suited to me. For each one, describe:

- The problem it solves and for whom.
- What data to use and where to find it (at least 50–100 documents).
- What the system will do at each of the four stages—one sentence per stage.

The project must be realistic for one person working for two months at 3–4 hours per week.

Describe the main stages, where to start, and how to create my own repository step by step. Explain why each step is needed.

---

# Homework Assignment 1

## Block 1 case — “Structured Extraction Service”

Build a service that extracts structured data from raw texts according to a schema, compares a provider-hosted model with a local model, and justifies the choice for production. Estimated completion time: **9 hours**. **30 points**. Deadline: **27 October at 23:59**.

## Scenario and data

You are an AI engineer who needs to convert “messy” texts into valid JSON according to a schema and demonstrate, using numbers, which model and prompt should go into production. This is the first part of your ongoing course project: later, these data and model integrations will form the foundation for RAG and an agent.

**Text sources:** data from your course project—customer emails, tickets, job advertisements, product descriptions or technical reports—without personal data.

**Minimum size:** 30 texts, including 10 labelled manually. These 10 texts are your **golden set**, which you will use to measure quality. The texts must be genuinely “messy”: different lengths, typing errors, missing fields and mixed languages.

## Steps

The case is divided into four steps, each based on a specific class. Submit steps 1–2 as a checkpoint by **24 October** in the course chat **#ai-engineering-2-flood**. The checkpoint is ungraded; feedback will be provided at the Q&A on **26 October**.

### 1. Schema and baseline prompt

Approximately 2 hours; lesson 3.

- Define a schema using Pydantic or JSON Schema: at least six fields, including at least one enum and one nested object or list.
- Write a baseline prompt and connect a provider-hosted model through an API with structured output.
- Add retry handling and a timeout; process all the texts and save the results.

### 2. Second model and measurements

Approximately 2 hours; lessons 2–3.

- Connect a local model (Ollama or another open-source option) through a shared interface with the first model.
- Move sampling parameters (`temperature`, `top_p`) into configuration and compare at least two configurations.
- Measure the following for each model: accuracy by field on the golden set, percentage of valid responses, latency p50/p95, and cost per 1,000 documents.

### 3. Prompt versioning and validation

Approximately 3 hours; lesson 4.

- Store prompts in separate files with a version and a changelog. At least two versions are required, with an explanation of what changed and why.
- Validate every response against the schema. If it is invalid, make one repair attempt; if it is still invalid, mark it as `failed`.
- For each result, log the model, prompt version and sampling parameters.

### 4. Comparison report

Approximately 2 hours; after the Q&A on 26 October.

- A table of **model × prompt version × sampling configuration**, including all the metrics from step 2.
- Analysis of 3–5 typical errors: what was returned instead of what was expected, and why.
- The final production choice in one paragraph, plus the conditions under which you would change that decision.

**For experienced students—stretch tasks, with no additional points:** a third model (a low-cost provider-hosted model), automated regression runs of prompts on the golden set, and response caching.

## Requirements, submission and deadlines

Submit one link to a GitHub repository that the instructor or mentor can run with one command.

### Technical requirements

- Python 3.11 or later; any provider (OpenAI, Anthropic, Gemini, etc.) plus a local model.
- Keep keys in `.env`; only `.env.example` goes into the repository.
- Run with one command: `make run` or `python main.py`.
- Getting started should require only free allowances or up to US$5 in API spending; the local model must run on an ordinary laptop.

### What the repository must contain

- Service code and the schema.
- A `prompts/` folder containing versions and a changelog.
- `data/` containing the texts and the golden set.
- `results/` containing model outputs.
- `REPORT.md` containing the comparison report.
- `README.md` explaining how to run the project and what needs to be installed.

### Deadlines

| Milestone | Date | Expected progress |
| --- | --- | --- |
| Start | 12 October | Lesson 1: choose the course project. |
| Checkpoint | 24 October | Steps 1–2 in the repository; ungraded. |
| Q&A | 26 October | Feedback on checkpoints and review of common mistakes. |
| Deadline | 27 October, 23:59 | Complete submission: steps 1–4. |
| Grading | By 3 November | Rubric-based assessment, with a comment for every point deducted. |

**What is NOT required:** a UI, deployment, fine-tuning, a large dataset or perfect accuracy. The assessment focuses on the engineering approach and honest measurements.

**Stuck?** Ask questions in the course chat **#ai-engineering-2-questions**, using the tag **#кейс1**. If you cannot meet the deadline, use the course freeze option.

## Assessment criteria — 30 points

Steps 2 and 3—measurements and versioning—carry the most points. The instructor or mentor will provide a comment for every point deducted.

| Criterion | Points |
| --- | ---: |
| **Step 1. Schema and baseline** | **6** |
| Schema meets the requirements: at least six fields, an enum and a nested structure. | 2 |
| Structured output, retry handling and timeout. | 2 |
| All texts processed and results saved. | 2 |
| **Step 2. Second model and measurements** | **8** |
| Local model connected through a shared interface. | 3 |
| Sampling parameters in configuration; at least two configurations compared. | 2 |
| Correct measurements of accuracy, validity, latency and cost. | 3 |
| **Step 3. Versioning and validation** | **8** |
| At least two prompt versions with a changelog and explanations of the changes. | 3 |
| Schema validation and handling of invalid responses. | 3 |
| Logging of the model, prompt version and parameters. | 2 |
| **Step 4. Comparison report** | **6** |
| Comparison table containing all metrics. | 2 |
| Analysis of 3–5 errors. | 2 |
| A justified final choice. | 2 |
| **Repository quality: README, one-command execution, no keys in the code.** | **2** |
| **Total** | **30** |
